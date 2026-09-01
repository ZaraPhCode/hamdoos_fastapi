"""One-time data migration: SQL Server (asha-shop .NET production) -> PostgreSQL (asha-shop-fastapi).

Reads tables from the source SQL Server (READ-ONLY — no writes, ever) and
inserts them into the target PostgreSQL database table-by-table, preserving
UUIDs and enum ints.

Source schema + connection come from environment variables (MIG_SRC_*), e.g.
the source DB used by the .NET host ("Hamdoos"). Target is the FastAPI app's
PostgreSQL `ashadb`. All connection settings can be overridden via environment
variables so the script can be pointed at the deployed (VPS) database as well.

Usage:
    python migrate_sqlserver_to_postgres.py --plan              # analyze mapping, no writes
    python migrate_sqlserver_to_postgres.py                     # perform migration
    python migrate_sqlserver_to_postgres.py --set-admin-pass    # re-hash admin password only

Deployment usage on the VPS (after `alembic upgrade head` created the empty schema):

    # set MIG_SRC_* + POSTGRES_*  in /opt/.env (the migrator compose injects it)
    docker compose -f docker-compose.migrate.yml run --rm migrator --plan
    docker compose -f docker-compose.migrate.yml run --rm migrator
    docker compose -f docker-compose.migrate.yml run --rm migrator --set-admin-pass "@Aa123456"

Environment variables:
    Source (SQL Server, REQUIRED): MIG_SRC_DRIVER, MIG_SRC_HOST, MIG_SRC_DATABASE,
                                   MIG_SRC_USER, MIG_SRC_PASSWORD, MIG_SRC_SCHEMA
    Target (PostgreSQL):           MIG_TARGET_HOST, MIG_TARGET_PORT, MIG_TARGET_DBNAME,
                                   MIG_TARGET_USER, MIG_TARGET_PASSWORD
"""

from __future__ import annotations

import argparse
import os
import sys
import uuid
from collections import defaultdict, deque
from datetime import datetime, timezone

import pyodbc
import psycopg2
from psycopg2.extras import execute_values

# ── Connection config (env-overridable; target defaults to the local compose db) ──
# IMPORTANT (read-only): the source SQL Server connection is used for SELECTs
# ONLY — the session is never autocommit and nothing is ever written to it.
# All credentials come from the environment (never hardcoded in this file):
#   MIG_SRC_DRIVER, MIG_SRC_HOST, MIG_SRC_DATABASE, MIG_SRC_USER,
#   MIG_SRC_PASSWORD, MIG_SRC_SCHEMA   (set in /opt/.env on the VPS)
def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def _require_env(key: str, description: str) -> str:
    val = _env(key)
    if not val:
        print(
            f"ERROR: environment variable {key} is required ({description}).\n"
            "  Set MIG_SRC_HOST / MIG_SRC_DATABASE / MIG_SRC_USER /\n"
            "  MIG_SRC_PASSWORD / MIG_SRC_SCHEMA in /opt/.env (see deploy/.env.example).",
            file=sys.stderr,
        )
        sys.exit(1)
    return val


_MIG_DRIVER_DEFAULT = "FreeTDS"  # VPS uses FreeTDS (no Microsoft repo); override to "ODBC Driver 17 for SQL Server" if installed
_MIG_DRIVER = _env("MIG_SRC_DRIVER", _MIG_DRIVER_DEFAULT)
# Read-only: ApplicationIntent=ReadOnly is honored by the MS ODBC driver when
# talking to an Always-On readable replica; FreeTDS ignores it.
SOURCE_DSN = (
    f"DRIVER={_MIG_DRIVER};"
    f"SERVER={_require_env('MIG_SRC_HOST', 'SQL Server host[:port]')};"
    f"DATABASE={_require_env('MIG_SRC_DATABASE', 'source database name')};"
    f"UID={_require_env('MIG_SRC_USER', 'SQL login (read-only preferred)')};"
    f"PWD={_require_env('MIG_SRC_PASSWORD', 'SQL login password')};"
    "Encrypt=no;TrustServerCertificate=yes"
    + (";TDS_Version=7.4" if _MIG_DRIVER == "FreeTDS" else "")
    + (";ApplicationIntent=ReadOnly" if _MIG_DRIVER != "FreeTDS" else "")
)
SOURCE_SCHEMA = _require_env("MIG_SRC_SCHEMA", "source schema name (e.g. dbo)")

# Target (PostgreSQL): MIG_TARGET_* take precedence, then fall back to the
# .env-driven POSTGRES_* values / DATABASE_URL used by the app itself.
TARGET_DSN = dict(
    host=_env("MIG_TARGET_HOST", _env("POSTGRES_HOST", "localhost")),
    port=int(_env("MIG_TARGET_PORT", _env("POSTGRES_PORT", "5433"))),
    dbname=_env("MIG_TARGET_DBNAME", _env("POSTGRES_DB", "ashadb")),
    user=_env("MIG_TARGET_USER", _env("POSTGRES_USER", "ashauser")),
    password=_env("MIG_TARGET_PASSWORD", _env("POSTGRES_PASSWORD", "ashapass")),
)

# Tables whose target PK (uuid) does not come from source: Id must be generated.
GENERATE_ID = {"RoleClaims", "UserClaims", "UserLogins", "UserTokens"}

# Source-only tables to skip (EF migration history, empty EF join table).
SKIP_SOURCE_TABLES = {"__EFMigrationsHistory", "CategoryTechnicalFeature"}

# datetimeoffset columns: pyodbc cannot read them -> cast to datetime2 in SQL.
DATETIMEOFFSET_COLS = {"LockoutEnd", "Date", "PayDate", "Approval", "PostageDate", "DepositDate"}

BATCH_SIZE = 500


def connect_source():
    conn = pyodbc.connect(SOURCE_DSN)
    conn.autocommit = False
    cur = conn.cursor()
    cur.execute("SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED")
    return conn


def connect_target():
    conn = psycopg2.connect(**TARGET_DSN)
    conn.autocommit = True  # avoid implicit transactions so session params can be set later
    return conn


def load_source_columns(cur):
    """Return {table: {column: data_type}} for the source schema."""
    cur.execute(
        """
        SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = ?
        ORDER BY TABLE_NAME, ORDINAL_POSITION
        """,
        (SOURCE_SCHEMA,),
    )
    cols = defaultdict(dict)
    for table, column, dtype in cur.fetchall():
        cols[table][column] = dtype
    return dict(cols)


def load_target_columns(conn):
    """Return {table: {column: {type, nullable, default}}} from information_schema."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT table_name, column_name, data_type, is_nullable, column_default
        FROM information_schema.columns
        WHERE table_schema = 'public'
        ORDER BY table_name, ordinal_position
        """
    )
    cols = defaultdict(dict)
    for table, column, dtype, nullable, default in cur.fetchall():
        cols[table][column] = {
            "type": dtype,
            "nullable": nullable == "YES",
            "default": default,
        }
    cur.close()
    return dict(cols)


def default_for(meta):
    """Sensible value for a NOT NULL target column missing in source."""
    t = meta["type"]
    if t in ("boolean",):
        return False
    if t in ("integer", "bigint", "smallint"):
        return 0
    if t in ("numeric", "double precision", "real"):
        return 0
    if t in ("uuid",):
        return uuid.uuid4()
    if t.startswith("timestamp"):
        return datetime.now(timezone.utc)
    return ""


def build_table_plan(source_cols, target_cols):
    """For each shared table, compute column mapping + generated/fill columns."""
    plan = {}
    for table, src_meta in source_cols.items():
        if table in SKIP_SOURCE_TABLES:
            continue
        if table not in target_cols:
            print(f"  [skip] {table}: not present in target Postgres")
            continue
        tgt = target_cols[table]
        common = [c for c in src_meta if c in tgt]
        # fill: target NOT NULL columns we cannot source (Id handled separately for GENERATE_ID tables)
        fill = {}
        for col, meta in tgt.items():
            if col in common:
                continue
            if table in GENERATE_ID and col == "Id":
                continue
            if meta["nullable"] or meta["default"]:
                continue
            fill[col] = default_for(meta)
        plan[table] = {
            "common": common,
            "fill": fill,
            "target_nullable": {c: tgt[c]["nullable"] for c in tgt},
        }
    return plan


def topo_order(target_conn, tables):
    """Return tables sorted so parents come before children (FK order)."""
    cur = target_conn.cursor()
    cur.execute(
        """
        SELECT tc.table_name, ccu.table_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
             ON tc.constraint_name = kcu.constraint_name
        JOIN information_schema.constraint_column_usage ccu
             ON ccu.constraint_name = tc.constraint_name
        WHERE tc.constraint_type = 'FOREIGN KEY'
          AND tc.table_schema = 'public'
          AND tc.table_name = ANY(%s)
          AND ccu.table_name = ANY(%s)
        """,
        (list(tables), list(tables)),
    )
    edges = [(child, parent) for child, parent in cur.fetchall()]
    cur.close()
    g = defaultdict(list)
    indeg = {t: 0 for t in tables}
    for child, parent in edges:
        if child == parent:
            continue
        g[parent].append(child)
        indeg[child] += 1
    q = deque(sorted(t for t, d in indeg.items() if d == 0))
    order = []
    while q:
        node = q.popleft()
        order.append(node)
        for nxt in sorted(g[node]):
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                q.append(nxt)
    if len(order) != len(tables):
        rest = sorted(t for t in tables if t not in order)
        order.extend(rest)  # cyclic/self FKs -> load after; FK checks disabled anyway
    return order


def normalize_value(value, dtype):
    if value is None:
        return None
    if isinstance(value, bytes):
        try:
            return str(uuid.UUID(bytes_le=value))
        except ValueError:
            return value.hex()
    return value


def migrate_table(src_conn, tgt_conn, table, plan, source_cols):
    common = plan["common"]
    fill = plan["fill"]
    generate_id = table in GENERATE_ID
    select_cols = [c for c in common if not (generate_id and c == "Id")]

    # build SELECT expression: cast datetimeoffset to datetime2
    exprs = []
    for c in select_cols:
        if source_cols[c] == "datetimeoffset" or c in DATETIMEOFFSET_COLS:
            exprs.append(f"CONVERT(datetime2(3), [{c}]) AS [{c}]")
        else:
            exprs.append(f"[{c}]")
    sel = "SELECT " + ", ".join(exprs) + f" FROM [{SOURCE_SCHEMA}].[{table}]"

    target_cols = list(select_cols)
    insert_cols = list(select_cols)
    if generate_id and "Id" in plan["target_nullable"]:
        insert_cols.insert(0, "Id")
        target_cols.insert(0, "Id")
    for col, val in fill.items():
        insert_cols.append(col)
        target_cols.append(col)
    if not insert_cols:
        print(f"  [skip] {table}: no usable columns")
        return 0

    quoted = ", ".join(f'"{c}"' for c in insert_cols)
    placeholders = ", ".join(["%s"] * len(insert_cols))
    insert_sql = f"INSERT INTO \"{table}\" ({quoted}) VALUES %s"

    # index of fill defaults / id gen
    fill_idx = {c: insert_cols.index(c) for c in fill}
    id_idx = insert_cols.index("Id") if "Id" in insert_cols else None
    col_idx = {c: target_cols.index(c) for c in target_cols}

    tgt_cur = tgt_conn.cursor()
    src_cur = src_conn.cursor()
    src_cur.execute(sel)
    total = 0
    while True:
        rows = src_cur.fetchmany(BATCH_SIZE)
        if not rows:
            break
        batch = []
        for row in rows:
            rec = {}
            for i, c in enumerate(select_cols):
                rec[c] = normalize_value(row[i], source_cols.get(c, ""))
            rec2 = [None] * len(insert_cols)
            for c in select_cols:
                rec2[insert_cols.index(c)] = rec[c]
            if id_idx is not None and "Id" not in select_cols:
                rec2[id_idx] = str(uuid.uuid4())
            for c, idx in fill_idx.items():
                rec2[idx] = fill[c]
            batch.append(tuple(rec2))
        execute_values(tgt_cur, insert_sql, batch, page_size=BATCH_SIZE, template=f"({placeholders})")
        total += len(batch)
    src_cur.close()
    tgt_cur.close()
    return total


def set_admin_password(target_dsn, username, password):
    """Re-hash a migrated user's PasswordHash (SQL Server .NET Identity hash) to bcrypt."""
    try:
        import bcrypt
    except ImportError:
        print("  ERROR: `bcrypt` not installed (add to requirements.txt)")
        return False
    conn = psycopg2.connect(**target_dsn)
    cur = conn.cursor()
    pw = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    cur.execute(
        'UPDATE "Users" SET "PasswordHash"=%s, "HasPassword"=true WHERE "UserName"=%s',
        (pw, username),
    )
    print(f"  re-hashed password for {username}: {cur.rowcount} row(s) updated")
    conn.commit()
    cur.close()
    conn.close()
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", action="store_true", help="analyze mapping without writing")
    ap.add_argument("--tables", default="", help="comma-separated table subset")
    ap.add_argument("--no-truncate", action="store_true", help="do not TRUNCATE target tables before load")
    ap.add_argument(
        "--set-admin-pass",
        nargs="?",
        const="@Aa123456",
        default=None,
        help="re-hash the admin user's password to bcrypt (default user = a.dastan@ashabeam.com)",
    )
    ap.add_argument(
        "--admin-user",
        default="a.dastan@ashabeam.com",
        help="user to re-hash with --set-admin-pass",
    )
    ap.add_argument("--admin-pass", default="@Aa123456", help="password value for --set-admin-pass")
    args = ap.parse_args()

    print("Connecting to target PostgreSQL...")
    tgt = connect_target()
    target_cols = load_target_columns(tgt)
    print(f"  target tables: {len(target_cols)}")

    if args.set_admin_pass is not None:
        print("Re-hashing admin password...")
        set_admin_password(TARGET_DSN, args.admin_user, args.set_admin_pass or args.admin_pass)
        tgt.close()
        return

    print("Connecting to source SQL Server (read-only)...")
    src = connect_source()
    cur = src.cursor()
    source_cols = load_source_columns(cur)
    print(f"  source tables: {len(source_cols)}")

    plan = build_table_plan(source_cols, target_cols)
    print(f"  shared tables to migrate: {len(plan)}")

    if args.tables:
        subset = {t.strip() for t in args.tables.split(",")}
        plan = {t: p for t, p in plan.items() if t in subset}
        print(f"  subset tables: {len(plan)}")

    if args.plan:
        for table, p in sorted(plan.items()):
            gen = " (Id generated)" if table in GENERATE_ID else ""
            fill_info = ", ".join(f"{c}={p['fill'][c]!r}" for c in sorted(p["fill"]))
            print(f"  {table}{gen}: {len(p['common'])} cols" + (f" | fill {fill_info}" if fill_info else ""))
        src.close()
        tgt.close()
        return

    order = topo_order(tgt, list(plan.keys()))
    print(f"  insert order (topological): {', '.join(order)}")

    tgt.autocommit = False
    tgt_cur = tgt.cursor()
    tgt_cur.execute("SET TIME ZONE 'UTC'")
    tgt_cur.execute("SET session_replication_role = replica")  # bypass FK checks (bulk load)
    tgt.commit()

    if not args.no_truncate:
        tables_to_truncate = [t for t in order if t != "alembic_version"]
        if tables_to_truncate:
            tgt_cur.execute(
                "TRUNCATE TABLE " + ", ".join(f'"{t}"' for t in tables_to_truncate) + " CASCADE"
            )
            tgt.commit()
            print(f"  TRUNCATED {len(tables_to_truncate)} target tables (CASCADE)")

    try:
        for table in order:
            p = plan[table]
            n = migrate_table(src, tgt, table, p, source_cols[table])
            tgt.commit()
            print(f"  {table}: {n} rows")
    except Exception as e:
        tgt.rollback()
        print(f"  ERROR: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
    finally:
        tgt_cur.execute("SET session_replication_role = origin")
        tgt_cur.close()
        tgt.commit()

    print("Done. Source connection closed.")
    src.close()
    tgt.close()


if __name__ == "__main__":
    main()
