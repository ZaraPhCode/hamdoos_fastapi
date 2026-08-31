#!/usr/bin/env bash
# Fresh VPS one-off migration: SQL Server (.NET) -> Postgres (FastAPI)
# No containers/images built yet. Run from repo root.
#
#   chmod +x deploy/migrate.sh
#   ./deploy/migrate.sh --plan        # dry-run (no writes)
#   ./deploy/migrate.sh               # full migration (TRUNCATE + bulk load)
#   ./deploy/migrate.sh --set-admin-pass 'NEW_STRONG_PASS' --admin-user 'admin@yourdomain.com'
#
# Prereqs: Docker + compose plugin, repo cloned.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

COMPOSE_MIG="docker-compose.migrate.yml"
COMPOSE_PROD="deploy/docker-compose.prod.yml"

# --- 0. .env guard (supports /opt/.env for VPS + .env for local dev) ---
# Primary location on VPS is /opt/.env (outside repo, not in git).
# Fall back to ./ .env for local development.
ENV_FILE=""
if [[ -f /opt/.env ]]; then
  ENV_FILE="/opt/.env"
elif [[ -f .env ]]; then
  ENV_FILE=".env"
else
  if [[ -f deploy/.env.example ]]; then
    echo "[migrate] No env file found (.env or /opt/.env). Creating /opt/.env from deploy/.env.example ..."
    if [[ -w /opt ]] 2>/dev/null; then
      cp deploy/.env.example /opt/.env
    else
      sudo cp deploy/.env.example /opt/.env
      sudo chmod 600 /opt/.env
    fi
  else
    echo "[migrate] ERROR: No env file and no deploy/.env.example"
    exit 1
  fi
  echo "[migrate] EDIT /opt/.env NOW then re-run:"
  echo "  sudo nano /opt/.env  # set POSTGRES_USER/PASSWORD/DB, SECRET_KEY, ZARINPAL_*, EMAIL_*, etc."
  echo "  # For admin identity (applied after migration via --set-admin-pass):"
  echo "  # SEED_ADMIN_USER / SEED_ADMIN_PASSWORD only matter for fresh seed, not for migrated data"
  exit 1
fi
echo "[migrate] Using env file: $ENV_FILE"

if grep -q "CHANGE_ME" "$ENV_FILE" 2>/dev/null; then
  echo "[migrate] WARNING: $ENV_FILE still contains CHANGE_ME — edit before prod."
fi
if grep -q "replace-with-a-strong-secret" "$ENV_FILE" 2>/dev/null; then
  echo "[migrate] WARNING: SECRET_KEY in $ENV_FILE is default dev value — rotate."
fi
if [[ -f /opt/.env && ! -r /opt/.env ]]; then
  echo "[migrate] /opt/.env is not readable by $USER (600 root:root). Fixing..."
  # Make it readable for compose (which runs as $USER). Keep secrets off world-readable if possible.
  sudo chown "$USER":"$USER" /opt/.env 2>/dev/null || sudo chmod 644 /opt/.env
  echo "[migrate] Fixed permissions: $(ls -l /opt/.env)"
fi
# Detect docker compose command (v2 plugin vs standalone)
if docker compose version >/dev/null 2>&1; then
  DC="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
  DC="docker-compose"
else
  echo "[migrate] ERROR: neither 'docker compose' nor 'docker-compose' found. Install docker compose plugin:"
  echo "  sudo apt-get update && sudo apt-get install -y docker-compose-plugin"
  exit 1
fi
echo "[migrate] Using: $DC"

# Default to --plan if no args (safe dry-run)
ARGS=("$@")
if [[ ${#ARGS[@]} -eq 0 ]]; then
  ARGS=(--plan)
  echo "[migrate] No args given — defaulting to --plan (dry-run)."
  echo "[migrate] To actually migrate: ./deploy/migrate.sh run   (or: docker compose -f $COMPOSE_MIG run --rm migrator)"
  echo ""
fi
# Allow alias `run` -> full migration without args
if [[ "${ARGS[0]:-}" == "run" ]]; then
  ARGS=()
fi

# --- 1. Boot postgres ---
echo "[migrate] Starting postgres (db) ..."
$DC -f "$COMPOSE_MIG" up -d db

echo "[migrate] Waiting for postgres health ..."
for i in $(seq 1 30); do
  if docker inspect --format='{{.State.Health.Status}}' asha-db 2>/dev/null | grep -q "healthy"; then
    echo "[migrate] postgres is healthy."
    break
  fi
  sleep 2
  if [[ $i -eq 30 ]]; then
    echo "[migrate] ERROR: postgres did not become healthy in 60s"
    $DC -f "$COMPOSE_MIG" logs db | tail -n 80
    exit 1
  fi
done

# --- 2. Build migrator image (contains ODBC driver + pyodbc + alembic) ---
echo "[migrate] Building migrator image (Dockerfile.migrate) — first build ~3-5 min ..."
BUILD_ARGS=()
if [[ -n "${PIP_INDEX:-}" ]]; then
  echo "[migrate] Using PIP_INDEX=$PIP_INDEX for pip install"
  BUILD_ARGS+=(--build-arg "PIP_INDEX=$PIP_INDEX")
fi
# --deps offline => install from ./wheels/ (pre-downloaded; no network at build).
# Needs:  docker compose -f docker-compose.migrate.yml build --build-arg PYTHON_DEPS=offline migrator
if [[ "${ARGS[*]:-}" == *"--deps offline"* ]]; then
  echo "[migrate] Using pre-downloaded wheels (offline install) — expecting ./wheels/"
  BUILD_ARGS+=(--build-arg "PYTHON_DEPS=offline")
  ARGS=("${ARGS[@]/--deps/}"); ARGS=("${ARGS[@]/offline/}")
fi
$DC -f "$COMPOSE_MIG" build --no-cache "${BUILD_ARGS[@]}" migrator

# --- 3. Create empty schema (alembic upgrade head) ---
# Skip if caller only wants --set-admin-pass (schema already exists)
SKIP_ALEMBIC=false
for a in "${ARGS[@]}"; do
  if [[ "$a" == "--set-admin-pass" || "$a" == "--admin-user" || "$a" == "--admin-pass" ]]; then
    SKIP_ALEMBIC=true
  fi
done

if [[ "$SKIP_ALEMBIC" == "false" ]]; then
  echo "[migrate] Running alembic upgrade head (via migrator) ..."
  $DC -f "$COMPOSE_MIG" run --rm migrator sh -c "alembic upgrade head"
else
  echo "[migrate] Skipping alembic (admin-pass mode) ..."
fi

# --- 4. Run migrator ---
echo "[migrate] Running migrator: ${ARGS[*]:-<full load>}"
if [[ ${#ARGS[@]} -eq 0 ]]; then
  $DC -f "$COMPOSE_MIG" run --rm migrator
else
  $DC -f "$COMPOSE_MIG" run --rm migrator "${ARGS[@]}"
fi

echo ""
echo "[migrate] Done."
if [[ " ${ARGS[*]} " == *" --plan "* ]]; then
  echo "[migrate] This was --plan (no writes). To actually migrate:"
  echo "  ./deploy/migrate.sh run"
  echo "  # or: $DC -f $COMPOSE_MIG run --rm migrator"
else
  echo "[migrate] Next steps (if you just did a full load):"
  echo "  1. Re-hash admin (bcrypt — .NET hash incompatible):"
  echo "     ./deploy/migrate.sh --set-admin-pass 'NEW_STRONG_PASS' --admin-user 'a.dastan@ashabeam.com'"
  echo "     # or new email: --admin-user admin@yourdomain.com"
  echo "  2. Boot prod stack:"
  echo "     $DC -f $COMPOSE_PROD up -d --build"
  echo "     $DC -f $COMPOSE_PROD logs -f app"
  echo "  3. Verify:"
  echo "     docker exec asha-db psql -U \$POSTGRES_USER -d \$POSTGRES_DB -c 'select count(*) from \"Users\";'"
  echo "  4. Clean migrator (optional, frees ~600MB):"
  echo "     docker rmi asha-shop-fastapi-migrator"
  echo "     # keep docker-compose.migrate.yml + Dockerfile.migrate for future re-migrations"
fi
