# SOURCE EXPORT CHUNK 1/4



---

## whatsapp-bot/DEPLOY_REVISION

```text
source-deploy-1

```


---

## whatsapp-bot/DEPLOY_TRIGGER_ONLY

```text
recipient-only-production-1

```


---

## whatsapp-bot/Dockerfile

```text
FROM evoapicloud/evolution-api:v2.3.7

USER root
WORKDIR /evolution

RUN apk add --no-cache bash curl redis postgresql postgresql-client postgresql-contrib python3 py3-pip py3-virtualenv     && apk add --no-cache --virtual .build-deps build-base python3-dev musl-dev postgresql-dev     && python3 -m venv /venv     && /venv/bin/pip install --no-cache-dir --upgrade pip

COPY backend/requirements.txt /tmp/requirements.txt
RUN /venv/bin/pip install --no-cache-dir -r /tmp/requirements.txt     && apk del .build-deps     && npm install --omit=dev --no-audit --no-fund --save-exact baileys@7.0.0-rc13

COPY backend/app /app/app
COPY frontend /app/frontend
COPY migrations /app/migrations
COPY start-all.sh /app/start-all.sh

RUN chmod +x /app/start-all.sh

EXPOSE 8000
ENTRYPOINT ["/bin/bash", "/app/start-all.sh"]

```


---

## whatsapp-bot/railway.json

```json
{
  "$schema": "https://railway.com/railway.schema.json",
  "build": {
    "builder": "DOCKERFILE",
    "dockerfilePath": "Dockerfile"
  },
  "deploy": {
    "startCommand": "/app/start-all.sh",
    "healthcheckPath": "/health",
    "healthcheckTimeout": 180,
    "sleepApplication": false,
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 5
  }
}

```


---

## whatsapp-bot/start-all.sh

```bash
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

FRESH_PG=0
if [[ ! -s "$PGDATA/PG_VERSION" ]]; then
  FRESH_PG=1
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

if [[ "$FRESH_PG" == "1" && -n "${WA_PERSIST_URL:-}" && -n "${WA_PERSIST_KEY:-}" && -n "${WA_BACKUP_SECRET:-}" ]]; then
  echo "[startup] Restoring persistent PostgreSQL snapshots"
  cd /app
  python -m app.persistence restore || echo "[startup] Persistence restore unavailable; continuing"
fi

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

if [[ "${WA_PERSISTENCE_PROBE_MODE:-}" == "write" ]]; then
  echo "[startup] Writing persistence canary"
  python -m app.persistence_probe write
elif [[ "${WA_PERSISTENCE_PROBE_MODE:-}" == "check" ]]; then
  echo "[startup] Checking persistence canary"
  python -m app.persistence_probe check
elif [[ "${WA_PERSISTENCE_PROBE_MODE:-}" == "cleanup" ]]; then
  echo "[startup] Cleaning persistence canary"
  python -m app.persistence_probe cleanup
fi

if [[ -n "${WA_PERSIST_URL:-}" && -n "${WA_PERSIST_KEY:-}" && -n "${WA_BACKUP_SECRET:-}" ]]; then
  echo "[startup] Creating initial persistent snapshot"
  python -m app.persistence backup || echo "[startup] Initial persistence snapshot unavailable; continuing"
  echo "[startup] Persistence loop starting"
  python -m app.persistence loop >/tmp/persistence.log 2>&1 &
fi

echo "[startup] Reminder scheduler runs inside the API process"
echo "[startup] Dashboard/API starting on port $PORT"
exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT" --workers 1 --loop asyncio --http h11

```


---

## whatsapp-bot/backend/requirements.txt

```text
fastapi==0.115.12
uvicorn[standard]==0.34.2
asyncpg==0.30.0
redis==5.2.1
httpx==0.28.1
pydantic==2.11.4
pydantic-settings==2.9.1
itsdangerous==2.2.0
python-multipart==0.0.20

```


---

## whatsapp-bot/backend/app/__init__.py

```python

```


---

## whatsapp-bot/backend/app/auth.py

```python
import hmac
from fastapi import HTTPException, Request, Response
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from .config import settings

serializer = URLSafeTimedSerializer(settings.session_secret, salt="admin-session")
COOKIE = "booking_admin"

def valid_credentials(username: str, password: str) -> bool:
    return hmac.compare_digest(username, settings.admin_username) and hmac.compare_digest(password, settings.admin_password)

def issue_session(response: Response):
    token = serializer.dumps({"u": settings.admin_username})
    response.set_cookie(COOKIE, token, httponly=True, secure=True, samesite="strict", max_age=settings.session_max_age_seconds, path="/")

def clear_session(response: Response):
    response.delete_cookie(COOKIE, path="/")

def require_admin(request: Request):
    # Dashboard is intentionally open for this private demo deployment.
    # Keep the dependency in place so authentication can be re-enabled later
    # without changing every route.
    return True
```
