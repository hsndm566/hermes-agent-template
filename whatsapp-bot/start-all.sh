#!/bin/bash
set -euo pipefail

export PATH="/venv/bin:$PATH"
export TZ="${TZ:-Asia/Riyadh}"
export PORT="${PORT:-8000}"
export DATABASE_URL="${DATABASE_URL:-postgresql://postgres@127.0.0.1:5432/booking}"
export REDIS_URL="${REDIS_URL:-redis://127.0.0.1:6379/0}"
export EVOLUTION_INTERNAL_URL="${EVOLUTION_INTERNAL_URL:-http://127.0.0.1:8080}"
export EVOLUTION_WEBHOOK_URL="${EVOLUTION_WEBHOOK_URL:-http://127.0.0.1:${PORT}/webhook/whatsapp}"
export DATABASE_PROVIDER="${DATABASE_PROVIDER:-postgresql}"
export DATABASE_CONNECTION_URI="${DATABASE_CONNECTION_URI:-postgresql://postgres@127.0.0.1:5432/evolution}"
export CACHE_REDIS_ENABLED="${CACHE_REDIS_ENABLED:-true}"
export CACHE_REDIS_URI="${CACHE_REDIS_URI:-redis://127.0.0.1:6379/1}"
export DATABASE_SAVE_DATA_INSTANCE="${DATABASE_SAVE_DATA_INSTANCE:-true}"
export DATABASE_SAVE_DATA_NEW_MESSAGE="${DATABASE_SAVE_DATA_NEW_MESSAGE:-false}"
export DATABASE_SAVE_MESSAGE_UPDATE="${DATABASE_SAVE_MESSAGE_UPDATE:-false}"
export DATABASE_SAVE_DATA_CONTACTS="${DATABASE_SAVE_DATA_CONTACTS:-false}"
export DATABASE_SAVE_DATA_CHATS="${DATABASE_SAVE_DATA_CHATS:-false}"
export DATABASE_SAVE_DATA_HISTORIC="${DATABASE_SAVE_DATA_HISTORIC:-false}"
export SERVER_PORT="${SERVER_PORT:-8080}"
export SERVER_URL="${SERVER_URL:-http://127.0.0.1:8080}"
export NODE_OPTIONS="${NODE_OPTIONS:---max-old-space-size=192}"

PGDATA=/tmp/pgdata
mkdir -p "$PGDATA" /run/postgresql
chown -R postgres:postgres "$PGDATA" /run/postgresql

if [[ ! -s "$PGDATA/PG_VERSION" ]]; then
  su postgres -c "initdb -D '$PGDATA' --auth-local=trust --auth-host=trust" >/tmp/initdb.log
fi

su postgres -c "postgres -D '$PGDATA' -c listen_addresses=127.0.0.1 -p 5432 -c shared_buffers=16MB -c max_connections=20 -c work_mem=1MB -c maintenance_work_mem=8MB -c effective_cache_size=64MB" >/tmp/postgres.log 2>&1 &
for i in {1..40}; do
  if pg_isready -h 127.0.0.1 -p 5432 >/dev/null 2>&1; then break; fi
  sleep 1
done
pg_isready -h 127.0.0.1 -p 5432 >/dev/null 2>&1 || { cat /tmp/postgres.log; exit 1; }

su postgres -c "psql -tAc \"SELECT 1 FROM pg_database WHERE datname='booking'\"" | grep -q 1 || su postgres -c "createdb booking"
su postgres -c "psql -tAc \"SELECT 1 FROM pg_database WHERE datname='evolution'\"" | grep -q 1 || su postgres -c "createdb evolution"

redis-server --bind 127.0.0.1 --port 6379 --save "" --appendonly no --maxmemory 24mb --maxmemory-policy allkeys-lru --daemonize yes

echo "[startup] PostgreSQL ready"
echo "[startup] Redis starting"
redis-cli ping >/dev/null
echo "[startup] Redis ready"

cd /evolution
echo "[startup] Evolution migrations starting"
if ! ( . ./Docker/scripts/deploy_database.sh ) >/tmp/evolution-migrate.log 2>&1; then
  echo "[startup] Evolution migrations FAILED"
  cat /tmp/evolution-migrate.log
  exit 1
fi
echo "[startup] Evolution migrations complete"

echo "[startup] Evolution API starting"
npm run start:prod >/tmp/evolution.log 2>&1 &
EVOLUTION_PID=$!

for i in {1..90}; do
  if curl -fsS http://127.0.0.1:8080 >/dev/null 2>&1; then
    echo "[startup] Evolution API ready"
    break
  fi
  if ! kill -0 "$EVOLUTION_PID" 2>/dev/null; then
    echo "[startup] Evolution API exited early"
    cat /tmp/evolution.log
    exit 1
  fi
  sleep 1
done
if ! curl -fsS http://127.0.0.1:8080 >/dev/null 2>&1; then
  echo "[startup] Evolution API readiness timeout"
  cat /tmp/evolution.log
  exit 1
fi

cd /app
echo "[startup] Booking migrations starting"
python -m app.migrate
echo "[startup] Booking migrations complete"

if [[ "${RUN_E2E_SELFTEST:-false}" == "true" ]]; then
  echo "[startup] Client-readiness selftest starting"
  python -m app.selftest
  echo "[startup] Client-readiness selftest passed"
fi

echo "[startup] Reminder scheduler runs inside the API process"
echo "[startup] Dashboard/API starting on port $PORT"
exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT" --workers 1 --loop asyncio --http h11
