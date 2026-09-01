#!/usr/bin/env bash
# Fresh VPS one-off migration: SQL Server (.NET) -> Postgres (FastAPI)
# Run from the repo root on the VPS. The shared image is BUILT here (the VPS
# has Docker Hub + apt + pip access):
#
# Usage:
#   ./deploy/migrate.sh --plan                  # dry-run (no writes)
#   ./deploy/migrate.sh                         # full migration (TRUNCATE + bulk load)
#   ./deploy/migrate.sh --set-admin-pass 'NEW_STRONG_PASS' --admin-user 'admin@yourdomain.com'
#
# Prereqs: Docker + compose plugin, repo cloned.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

COMPOSE_MIG="docker-compose.migrate.yml"
COMPOSE_PROD="deploy/docker-compose.prod.yml"
MIG_IMAGE="asha-shop-app:v1"

# --- 0. .env guard (supports /opt/.env for VPS + .env for local dev) ---
ENV_FILE=""
if [[ -f /opt/.env ]]; then
  ENV_FILE="/opt/.env"
elif [[ -f .env ]]; then
  ENV_FILE=".env"
else
  echo "[migrate] ERROR: no env file (/opt/.env or .env). Create it from deploy/.env.example."
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
  sudo chown "$USER":"$USER" /opt/.env 2>/dev/null || sudo chmod 644 /opt/.env
  echo "[migrate] Fixed permissions: $(ls -l /opt/.env)"
fi

# Detect docker compose command (v2 plugin vs standalone)
if docker compose version >/dev/null 2>&1; then
  DC="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
  DC="docker-compose"
else
  echo "[migrate] ERROR: neither 'docker compose' nor 'docker-compose' found."
  exit 1
fi
echo "[migrate] Using: $DC"

# Default to --plan if no args (safe dry-run)
ARGS=("$@")
if [[ ${#ARGS[@]} -eq 0 ]]; then
  ARGS=(--plan)
  echo "[migrate] No args given — defaulting to --plan (dry-run)."
  echo "[migrate] To actually migrate: ./deploy/migrate.sh run"
  echo ""
fi
# Allow alias `run` -> full migration without args
if [[ "${ARGS[0]:-}" == "run" ]]; then
  ARGS=()
fi

# --- Build / pull the shared image (VPS has Docker Hub + apt + pip) ---
echo "[migrate] Building shared image $MIG_IMAGE (Docker Hub + apt + pip) ..."
$DC -f "$COMPOSE_MIG" build migrator

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

# --- 2. Create empty schema (alembic upgrade head) ---
# Skip if caller only wants --set-admin-pass (schema already exists)
SKIP_ALEMBIC=false
for a in "${ARGS[@]}"; do
  if [[ "$a" == "--set-admin-pass" || "$a" == "--admin-user" || "$a" == "--admin-pass" ]]; then
    SKIP_ALEMBIC=true
  fi
done

if [[ "$SKIP_ALEMBIC" == "false" ]]; then
  echo "[migrate] Running alembic upgrade head (via migrator image) ..."
  $DC -f "$COMPOSE_MIG" run --rm --entrypoint sh migrator -c "alembic upgrade head"
else
  echo "[migrate] Skipping alembic (admin-pass mode) ..."
fi

# --- 3. Run migrator ---
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
else
  echo "[migrate] Next steps (if you just did a full load):"
  echo "  1. Re-hash admin (bcrypt — .NET hash incompatible):"
  echo "     ./deploy/migrate.sh --set-admin-pass 'NEW_STRONG_PASS' --admin-user 'a.dastan@ashabeam.com'"
  echo "  2. Boot prod stack:"
  echo "     $DC -f $COMPOSE_PROD up -d --build"
  echo "  3. Verify:"
  echo "     docker exec asha-db psql -U \$POSTGRES_USER -d \$POSTGRES_DB -c 'select count(*) from \"Users\";'"
fi