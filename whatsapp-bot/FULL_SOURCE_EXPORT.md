# FULL SOURCE EXPORT — WhatsApp Booking Bot

Repository: hsndm566/hermes-agent-template
Branch: cf-dns-once-20260919
Folder: whatsapp-bot/

This export intentionally excludes live Railway/Supabase secret values. Runtime secrets remain environment-only.

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


# SOURCE EXPORT CHUNK 2/4



---

## whatsapp-bot/backend/app/booking.py

```python
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from uuid import UUID, uuid4
import asyncpg
from .db import get_pool
from .config import settings
from .prayer import blocked_by_prayer

TZ=ZoneInfo(settings.tz)

async def business(bid):
    p=await get_pool(); return await p.fetchrow('SELECT * FROM businesses WHERE "businessId"=$1 AND id=$1', UUID(str(bid)))
async def services(bid):
    p=await get_pool(); return await p.fetch('SELECT * FROM services WHERE "businessId"=$1 ORDER BY name_ar', UUID(str(bid)))
async def staff(bid):
    p=await get_pool(); return await p.fetch('SELECT * FROM staff WHERE "businessId"=$1 AND is_active=true ORDER BY name_ar', UUID(str(bid)))
async def working_hours(bid, ramadan=False):
    p=await get_pool(); return await p.fetch('SELECT * FROM working_hours WHERE "businessId"=$1 AND is_ramadan=$2 ORDER BY day_of_week', UUID(str(bid)), ramadan)
async def settings_map(bid):
    p=await get_pool(); rows=await p.fetch('SELECT key,value FROM settings WHERE "businessId"=$1', UUID(str(bid))); return {r['key']:r['value'] for r in rows}
async def customer(bid, phone):
    p=await get_pool(); return await p.fetchrow('SELECT * FROM customers WHERE "businessId"=$1 AND phone=$2', UUID(str(bid)), phone)
async def upsert_customer(bid, phone, name=None, preferred_language=None):
    p=await get_pool()
    return await p.fetchrow('''INSERT INTO customers(id,"businessId",phone,name,preferred_language)
    VALUES($1,$2,$3,$4,$5)
    ON CONFLICT ("businessId",phone) DO UPDATE SET
      name=COALESCE(EXCLUDED.name,customers.name),
      preferred_language=COALESCE(EXCLUDED.preferred_language,customers.preferred_language)
    RETURNING *''', uuid4(), UUID(str(bid)), phone, name, preferred_language)

async def set_customer_language(bid, phone, preferred_language):
    return await upsert_customer(bid, phone, preferred_language=preferred_language)

async def available_slots(bid, service_id, exclude_appointment=None):
    p=await get_pool(); bid=UUID(str(bid)); sid=UUID(str(service_id)); now=datetime.now(TZ)
    svc=await p.fetchrow('SELECT * FROM services WHERE "businessId"=$1 AND id=$2', bid,sid)
    if not svc: return []
    cfg=await settings_map(bid); biz=await business(bid); people=await staff(bid)
    if not people: return []
    ramadan=cfg.get('ramadan_mode','false').lower()=='true'; prayer=cfg.get('prayer_buffer_enabled','false').lower()=='true'; pb=int(cfg.get('prayer_buffer_min','30')); step=int(cfg.get('slot_interval_min','30'))
    out=[]
    for offset in range(7):
        d=(now+timedelta(days=offset)).date(); dow=(d.weekday()+1)%7
        wh=await p.fetchrow('SELECT * FROM working_hours WHERE "businessId"=$1 AND day_of_week=$2 AND is_ramadan=$3', bid,dow,ramadan)
        if not wh and ramadan:
            wh=await p.fetchrow('SELECT * FROM working_hours WHERE "businessId"=$1 AND day_of_week=$2 AND is_ramadan=false', bid,dow)
        if not wh or wh['is_closed']: continue
        cur=datetime.combine(d, wh['open_time'], TZ); close=datetime.combine(d, wh['close_time'], TZ)
        while cur + timedelta(minutes=svc['duration_min']+svc['buffer_min']) <= close:
            end=cur+timedelta(minutes=svc['duration_min']+svc['buffer_min'])
            if cur > now+timedelta(minutes=10):
                if not prayer or not blocked_by_prayer(cur,end,biz['latitude'],biz['longitude'],pb,ramadan):
                    for person in people:
                        q='''SELECT 1 FROM appointments WHERE "businessId"=$1 AND staff_id=$2 AND status IN ('confirmed','rescheduled') AND start_time < $3 AND end_time > $4'''
                        args=[bid,person['id'],end,cur]
                        if exclude_appointment:
                            q += ' AND id <> $5'; args.append(UUID(str(exclude_appointment)))
                        busy=await p.fetchval(q,*args)
                        if not busy:
                            out.append({'start':cur.isoformat(),'end':end.isoformat(),'staff_id':str(person['id'])}); break
            cur += timedelta(minutes=step)
    return out[:40]

async def create_appointment(bid, phone, service_id, slot):
    p=await get_pool(); bid=UUID(str(bid)); staff_id=UUID(slot['staff_id']); start=datetime.fromisoformat(slot['start']); end=datetime.fromisoformat(slot['end'])
    async with p.acquire() as conn:
        async with conn.transaction():
            await conn.execute('SELECT pg_advisory_xact_lock(hashtext($1))', f'{bid}:{staff_id}')
            busy=await conn.fetchval('''SELECT 1 FROM appointments WHERE "businessId"=$1 AND staff_id=$2 AND status IN ('confirmed','rescheduled') AND start_time < $3 AND end_time > $4''',bid,staff_id,end,start)
            if busy: raise asyncpg.ExclusionViolationError('slot unavailable')
            return await conn.fetchrow('''INSERT INTO appointments(id,"businessId",customer_phone,service_id,staff_id,start_time,end_time,status) VALUES($1,$2,$3,$4,$5,$6,$7,'confirmed') RETURNING *''',uuid4(),bid,phone,UUID(str(service_id)),staff_id,start,end)

async def upcoming(bid, phone):
    p=await get_pool(); return await p.fetchrow('''SELECT a.*,s.name_ar,s.name_en FROM appointments a JOIN services s ON s."businessId"=a."businessId" AND s.id=a.service_id WHERE a."businessId"=$1 AND a.customer_phone=$2 AND a.status IN ('confirmed','rescheduled') AND a.start_time>NOW() ORDER BY a.start_time LIMIT 1''',UUID(str(bid)),phone)
async def cancel(bid, aid):
    p=await get_pool(); return await p.fetchrow("UPDATE appointments SET status='cancelled' WHERE \"businessId\"=$1 AND id=$2 RETURNING *",UUID(str(bid)),UUID(str(aid)))
async def reschedule(bid, aid, slot):
    p=await get_pool(); bid=UUID(str(bid)); aid=UUID(str(aid)); staff_id=UUID(slot['staff_id']); start=datetime.fromisoformat(slot['start']); end=datetime.fromisoformat(slot['end'])
    async with p.acquire() as conn:
        async with conn.transaction():
            await conn.execute('SELECT pg_advisory_xact_lock(hashtext($1))',f'{bid}:{staff_id}')
            busy=await conn.fetchval("SELECT 1 FROM appointments WHERE \"businessId\"=$1 AND staff_id=$2 AND id<>$3 AND status IN ('confirmed','rescheduled') AND start_time<$4 AND end_time>$5",bid,staff_id,aid,end,start)
            if busy: raise asyncpg.ExclusionViolationError('slot unavailable')
            return await conn.fetchrow("UPDATE appointments SET staff_id=$3,start_time=$4,end_time=$5,status='rescheduled' WHERE \"businessId\"=$1 AND id=$2 RETURNING *",bid,aid,staff_id,start,end)

```


---

## whatsapp-bot/backend/app/config.py

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str
    redis_url: str
    evolution_internal_url: str
    evolution_api_key: str
    evolution_webhook_url: str
    whatsapp_webhook_secret: str
    app_public_url: str
    admin_username: str
    admin_password: str
    session_secret: str
    session_max_age_seconds: int = 43200
    tz: str = "Asia/Riyadh"
    enable_test_mode: bool = False
    default_test_phone: str = ""
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()

```


---

## whatsapp-bot/backend/app/db.py

```python
import asyncpg
from .config import settings

pool: asyncpg.Pool | None = None

async def connect_db():
    global pool
    if pool is None:
        pool = await asyncpg.create_pool(settings.database_url, min_size=2, max_size=10, command_timeout=20)
    return pool

async def close_db():
    global pool
    if pool:
        await pool.close()
        pool = None

async def get_pool():
    return await connect_db()

```


---

## whatsapp-bot/backend/app/evolution.py

```python
import httpx
from .config import settings


class EvolutionClient:
    def __init__(self):
        self.base = settings.evolution_internal_url.rstrip('/')
        self.headers = {"apikey": settings.evolution_api_key, "Content-Type": "application/json"}

    async def _request(self, method: str, path: str, *, json=None, timeout=30):
        async with httpx.AsyncClient(timeout=timeout) as c:
            r = await c.request(method, f"{self.base}{path}", headers=self.headers, json=json)
            r.raise_for_status()
            return r.json() if r.content else {}

    async def configure_webhook(self, instance: str):
        # Evolution API v2.3.x requires webhook settings inside a "webhook"
        # object and uses "byEvents" / "base64" field names.
        payload = {
            "webhook": {
                "enabled": True,
                "url": settings.evolution_webhook_url,
                "headers": {"X-Webhook-Secret": settings.whatsapp_webhook_secret},
                "byEvents": False,
                "base64": False,
                "events": ["MESSAGES_UPSERT", "CONNECTION_UPDATE", "QRCODE_UPDATED"],
            }
        }
        return await self._request("POST", f"/webhook/set/{instance}", json=payload)

    async def find_webhook(self, instance: str):
        return await self._request("GET", f"/webhook/find/{instance}", timeout=15)

    async def create_instance(self, instance: str):
        # Evolution v2 uses a dedicated webhook endpoint. Keeping creation
        # independent from webhook configuration avoids legacy-field mismatches.
        payload = {
            "instanceName": instance,
            "qrcode": True,
            "integration": "WHATSAPP-BAILEYS",
            "groupsIgnore": True,
            "alwaysOnline": False,
            "readMessages": False,
            "syncFullHistory": False,
        }
        data = await self._request("POST", "/instance/create", json=payload)
        await self.configure_webhook(instance)
        hook = await self.find_webhook(instance)

        hook_data = hook.get("webhook", hook) if isinstance(hook, dict) else {}
        if isinstance(hook_data, dict):
            nested = hook_data.get("webhook", hook_data)
            if isinstance(nested, dict) and nested.get("enabled") is False:
                raise RuntimeError("Evolution webhook was created but is disabled")
        return data

    async def connect(self, instance: str):
        return await self._request("GET", f"/instance/connect/{instance}")

    async def state(self, instance: str):
        return await self._request("GET", f"/instance/connectionState/{instance}", timeout=15)

    async def delete_instance(self, instance: str):
        return await self._request("DELETE", f"/instance/delete/{instance}", timeout=20)

    async def send_text(self, instance: str, number: str, text: str):
        if instance.startswith("test-biz-"):
            return {"test": True, "text": text}
        return await self._request(
            "POST",
            f"/message/sendText/{instance}",
            json={"number": number, "text": text, "delay": 300, "linkPreview": True},
        )


evolution = EvolutionClient()

```


---

## whatsapp-bot/backend/app/main.py

```python
import hmac
import asyncio
import httpx
import re
from uuid import UUID,uuid4
from decimal import Decimal
from datetime import datetime, time
from fastapi import FastAPI,Request,Response,Depends,HTTPException
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from .config import settings
from .db import connect_db,close_db,get_pool
from .auth import valid_credentials,issue_session,clear_session,require_admin
from .schemas import LoginIn,BusinessIn,ServiceIn,HoursIn,SettingsIn,StaffIn,BusinessProfileIn
from .evolution import evolution
from .booking import business
from .state_machine import handle
from .utils import jid_to_phone, normalize_phone
from .worker import tick as reminder_tick, r as reminder_redis

app=FastAPI(title='Saudi WhatsApp Booking',docs_url=None,redoc_url=None)
r=Redis.from_url(settings.redis_url,decode_responses=True)
reminder_task=None

async def reminder_loop():
    while True:
        try:
            await reminder_tick()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            print('reminder tick failed', type(exc).__name__)
        await asyncio.sleep(60)

@app.on_event('startup')
async def startup():
    global reminder_task
    await connect_db()
    # Redis conversation state is disposable; durable customer preferences live
    # in PostgreSQL. Rebuild the privileged tenant registry on every start.
    p=await get_pool()
    rows=await p.fetch('SELECT "businessId" FROM businesses')
    if rows:
        await r.sadd('platform:business_ids', *[str(x["businessId"]) for x in rows])
    reminder_task=asyncio.create_task(reminder_loop())

@app.on_event('shutdown')
async def shutdown():
    global reminder_task
    if reminder_task:
        reminder_task.cancel()
        try:
            await reminder_task
        except asyncio.CancelledError:
            pass
    await reminder_redis.aclose()
    await close_db()
    await r.aclose()
async def dependency_checks():
    checks={
        'postgres':False,
        'redis':False,
        'evolution':False,
        'evolution_status':None,
        'evolution_error_type':None,
    }
    try:
        p=await get_pool()
        checks['postgres']=(await p.fetchval('SELECT 1'))==1
    except Exception:
        pass
    try:
        checks['redis']=bool(await r.ping())
    except Exception:
        pass
    try:
        async with httpx.AsyncClient(timeout=5, trust_env=False) as client:
            resp=await client.get(
                settings.evolution_internal_url.rstrip('/') + '/instance/fetchInstances',
                headers={'apikey': settings.evolution_api_key},
            )
            checks['evolution_status']=resp.status_code
            checks['evolution']=resp.status_code == 200
    except Exception as exc:
        checks['evolution_error_type']=type(exc).__name__
    return checks

@app.get('/health')
async def health():
    checks=await dependency_checks()
    return {'ok':True,'checks':checks}

@app.get('/ready')
async def ready():
    checks=await dependency_checks()
    ok=bool(checks['postgres'] and checks['redis'] and checks['evolution'])
    return JSONResponse({'ok':ok,'checks':checks},status_code=200 if ok else 503)

@app.post('/api/login')
async def login(body:LoginIn,response:Response,request:Request):
    forwarded=(request.headers.get('x-forwarded-for') or '').split(',')[0].strip()
    client_ip=forwarded or (request.client.host if request.client else 'unknown')
    limit_key=f'login:fail:{client_ip}:{body.username[:64]}'
    failures=int(await r.get(limit_key) or 0)
    if failures >= 5:
        raise HTTPException(429,'Too many login attempts. Try again later.')
    if not valid_credentials(body.username,body.password):
        failures=await r.incr(limit_key)
        if failures==1:
            await r.expire(limit_key,900)
        raise HTTPException(401,'Invalid credentials')
    await r.delete(limit_key)
    issue_session(response)
    return {'ok':True}
@app.post('/api/logout')
async def logout(response:Response,_=Depends(require_admin)): clear_session(response); return {'ok':True}
@app.get('/api/session')
async def session(_=Depends(require_admin)): return {'ok':True,'username':settings.admin_username}

@app.get('/api/client-defaults')
async def client_defaults(_=Depends(require_admin)):
    return {'test_phone': normalize_phone(settings.default_test_phone) if settings.default_test_phone else ''}

async def tenant_or_404(bid:str):
    try: uid=UUID(bid)
    except: raise HTTPException(404,'Business not found')
    row=await business(uid)
    if not row: raise HTTPException(404,'Business not found')
    return row

def qr_value(data):
    q=data.get('qrcode') or data
    return q.get('base64') if isinstance(q,dict) else None

@app.post('/api/businesses')
async def add_business(body:BusinessIn,_=Depends(require_admin)):
    bid=uuid4(); instance=('test-biz-' if body.test_mode else 'biz-')+bid.hex
    lat=Decimal(str(body.latitude)) if body.latitude is not None else None; lng=Decimal(str(body.longitude)) if body.longitude is not None else None
    if body.test_mode:
        if not settings.enable_test_mode: raise HTTPException(403,'Test mode is disabled')
        evo={'qrcode':{'base64':None}}
    else:
        try: evo=await evolution.create_instance(instance)
        except Exception as e: raise HTTPException(502,f'Evolution instance creation failed: {e}')
    p=await get_pool()
    async with p.acquire() as c:
        async with c.transaction():
            await c.execute('''INSERT INTO businesses(id,"businessId",name_ar,name_en,phone,whatsapp_session_id,maps_url,latitude,longitude,vat_number,cr_number) VALUES($1,$1,$2,$3,$4,$5,$6,$7,$8,$9,$10)''',bid,body.name_ar,body.name_en,body.phone,instance,body.maps_url,lat,lng,body.vat_number,body.cr_number)
            await c.execute('INSERT INTO staff(id,"businessId",name_ar,name_en,is_active) VALUES($1,$2,$3,$4,true)',uuid4(),bid,'عام','General')
            for s in body.services:
                await c.execute('INSERT INTO services(id,"businessId",name_ar,name_en,duration_min,price,buffer_min) VALUES($1,$2,$3,$4,$5,$6,$7)',uuid4(),bid,s.name_ar,s.name_en,s.duration_min,Decimal(str(s.price)),s.buffer_min)
            for h in body.hours:
                await c.execute('INSERT INTO working_hours(id,"businessId",day_of_week,open_time,close_time,is_closed,is_ramadan) VALUES($1,$2,$3,$4,$5,$6,$7)',uuid4(),bid,h.day_of_week,time.fromisoformat(h.open_time) if h.open_time else None,time.fromisoformat(h.close_time) if h.close_time else None,h.is_closed,h.is_ramadan)
            defaults={
                'ramadan_mode':'false',
                'prayer_buffer_enabled':'false',
                'prayer_buffer_min':'30',
                'slot_interval_min':'30',
                'cancellation_policy_ar':'يمكنك الإلغاء قبل الموعد.',
                'cancellation_policy_en':'You may cancel before the appointment.',
                'bot_name_ar':(body.bot_name_ar or body.name_ar).strip(),
                'bot_name_en':(body.bot_name_en or body.name_en).strip(),
                'bot_tone':body.bot_tone if body.bot_tone in {'friendly','professional','luxury','concise'} else 'friendly',
                'welcome_ar':(body.welcome_ar or '').strip(),
                'welcome_en':(body.welcome_en or '').strip(),
                'language_prompt_enabled':'true'
            }
            for k,v in defaults.items():
                await c.execute('INSERT INTO settings(id,"businessId",key,value) VALUES($1,$2,$3,$4)',uuid4(),bid,k,v)
    await r.sadd('platform:business_ids',str(bid))
    return {'id':str(bid),'instance':instance,'qr':qr_value(evo)}

@app.get('/api/businesses')
async def list_businesses(_=Depends(require_admin)):
    out=[]
    for raw in sorted(await r.smembers('platform:business_ids')):
        row=await business(raw)
        if row: out.append({k:(str(v) if isinstance(v,UUID) else v) for k,v in dict(row).items()})
    return out

@app.get('/api/businesses/{bid}')
async def get_business(bid:str,_=Depends(require_admin)):
    b=await tenant_or_404(bid); p=await get_pool(); uid=UUID(bid)
    sv=await p.fetch('SELECT * FROM services WHERE "businessId"=$1 ORDER BY name_ar',uid)
    wh=await p.fetch('SELECT * FROM working_hours WHERE "businessId"=$1 ORDER BY is_ramadan,day_of_week',uid)
    st=await p.fetch('SELECT key,value FROM settings WHERE "businessId"=$1',uid)
    people=await p.fetch('SELECT * FROM staff WHERE "businessId"=$1 ORDER BY name_ar',uid)
    def conv(row): return {k:(str(v) if isinstance(v,UUID) else v) for k,v in dict(row).items()}
    return {'business':conv(b),'services':[conv(x) for x in sv],'hours':[conv(x) for x in wh],'staff':[conv(x) for x in people],'settings':{x['key']:x['value'] for x in st}}

@app.get('/api/businesses/{bid}/qr')
async def get_qr(bid:str,_=Depends(require_admin)):
    b=await tenant_or_404(bid)
    if b['whatsapp_session_id'].startswith('test-'): return {'qr':None,'state':'test'}
    try:
        data=await evolution.connect(b['whatsapp_session_id']); return {'qr':qr_value(data),'raw':data}
    except Exception as e: raise HTTPException(502,str(e))

@app.get('/api/businesses/{bid}/connection')
async def connection(bid:str,_=Depends(require_admin)):
    b=await tenant_or_404(bid)
    if b['whatsapp_session_id'].startswith('test-'): return {'instance':{'state':'test'}}
    return await evolution.state(b['whatsapp_session_id'])

@app.put('/api/businesses/{bid}/services')
async def put_services(bid:str,items:list[ServiceIn],_=Depends(require_admin)):
    await tenant_or_404(bid); uid=UUID(bid); p=await get_pool()
    async with p.acquire() as c:
        async with c.transaction():
            keep=[]
            for s in items:
                if s.id:
                    sid=UUID(s.id); keep.append(sid)
                    await c.execute('UPDATE services SET name_ar=$3,name_en=$4,duration_min=$5,price=$6,buffer_min=$7 WHERE "businessId"=$1 AND id=$2',uid,sid,s.name_ar,s.name_en,s.duration_min,Decimal(str(s.price)),s.buffer_min)
                else:
                    sid=uuid4(); keep.append(sid); await c.execute('INSERT INTO services(id,"businessId",name_ar,name_en,duration_min,price,buffer_min) VALUES($1,$2,$3,$4,$5,$6,$7)',sid,uid,s.name_ar,s.name_en,s.duration_min,Decimal(str(s.price)),s.buffer_min)
            if keep:
                await c.execute('DELETE FROM services s WHERE s."businessId"=$1 AND NOT (s.id=ANY($2::uuid[])) AND NOT EXISTS (SELECT 1 FROM appointments a WHERE a."businessId"=$1 AND a.service_id=s.id)',uid,keep)
    return {'ok':True}

@app.put('/api/businesses/{bid}/hours')
async def put_hours(bid:str,items:list[HoursIn],_=Depends(require_admin)):
    await tenant_or_404(bid); uid=UUID(bid); p=await get_pool()
    async with p.acquire() as c:
        async with c.transaction():
            await c.execute('DELETE FROM working_hours WHERE "businessId"=$1',uid)
            for h in items: await c.execute('INSERT INTO working_hours(id,"businessId",day_of_week,open_time,close_time,is_closed,is_ramadan) VALUES($1,$2,$3,$4,$5,$6,$7)',uuid4(),uid,h.day_of_week,time.fromisoformat(h.open_time) if h.open_time else None,time.fromisoformat(h.close_time) if h.close_time else None,h.is_closed,h.is_ramadan)
    return {'ok':True}

@app.put('/api/businesses/{bid}/settings')
async def put_settings(bid:str,body:SettingsIn,_=Depends(require_admin)):
    await tenant_or_404(bid); uid=UUID(bid); p=await get_pool()
    for k,v in body.values.items():
        await p.execute('''INSERT INTO settings(id,"businessId",key,value) VALUES($1,$2,$3,$4) ON CONFLICT ("businessId",key) DO UPDATE SET value=EXCLUDED.value''',uuid4(),uid,k,str(v))
    return {'ok':True}

@app.put('/api/businesses/{bid}/staff')
async def put_staff(bid:str,items:list[StaffIn],_=Depends(require_admin)):
    await tenant_or_404(bid); uid=UUID(bid); p=await get_pool()
    if not items or not any(x.is_active for x in items):
        raise HTTPException(400,'At least one active staff member is required')
    async with p.acquire() as c:
        async with c.transaction():
            keep=[]
            for item in items:
                if item.id:
                    sid=UUID(item.id); keep.append(sid)
                    await c.execute('UPDATE staff SET name_ar=$3,name_en=$4,is_active=$5 WHERE "businessId"=$1 AND id=$2',uid,sid,item.name_ar,item.name_en,item.is_active)
                else:
                    sid=uuid4(); keep.append(sid)
                    await c.execute('INSERT INTO staff(id,"businessId",name_ar,name_en,is_active) VALUES($1,$2,$3,$4,$5)',sid,uid,item.name_ar,item.name_en,item.is_active)
            if keep:
                await c.execute('UPDATE staff SET is_active=false WHERE "businessId"=$1 AND NOT (id=ANY($2::uuid[]))',uid,keep)
    return {'ok':True}

@app.put('/api/businesses/{bid}/profile')
async def put_profile(bid:str,body:BusinessProfileIn,_=Depends(require_admin)):
    await tenant_or_404(bid); uid=UUID(bid); p=await get_pool()
    lat=Decimal(str(body.latitude)) if body.latitude is not None else None
    lng=Decimal(str(body.longitude)) if body.longitude is not None else None
    row=await p.fetchrow('''UPDATE businesses SET name_ar=$2,name_en=$3,phone=$4,maps_url=$5,latitude=$6,longitude=$7,vat_number=$8,cr_number=$9
        WHERE "businessId"=$1 AND id=$1 RETURNING *''',uid,body.name_ar,body.name_en,body.phone,body.maps_url,lat,lng,body.vat_number,body.cr_number)
    return {k:(str(v) if isinstance(v,UUID) else v) for k,v in dict(row).items()}

@app.get('/api/businesses/{bid}/appointments')
async def appointments(bid:str,_=Depends(require_admin)):
    await tenant_or_404(bid); uid=UUID(bid); p=await get_pool()
    rows=await p.fetch('''SELECT a.*,s.name_ar,s.name_en,st.name_ar staff_ar,st.name_en staff_en,c.name customer_name FROM appointments a JOIN services s ON s."businessId"=a."businessId" AND s.id=a.service_id JOIN staff st ON st."businessId"=a."businessId" AND st.id=a.staff_id LEFT JOIN customers c ON c."businessId"=a."businessId" AND c.phone=a.customer_phone WHERE a."businessId"=$1 ORDER BY a.start_time DESC LIMIT 500''',uid)
    return [{k:(str(v) if isinstance(v,UUID) else v.isoformat() if isinstance(v,datetime) else v) for k,v in dict(x).items()} for x in rows]

@app.post('/api/businesses/{bid}/test-message')
async def live_test_message(bid:str,request:Request,_=Depends(require_admin)):
    b=await tenant_or_404(bid)
    if b['whatsapp_session_id'].startswith('test-'):
        raise HTTPException(400,'Connect a real WhatsApp number first')
    body=await request.json()
    phone=normalize_phone(body.get('phone',''))
    lang=(body.get('language') or 'ar').lower()
    if not phone:
        raise HTTPException(400,'A valid test phone is required')
    state=await evolution.state(b['whatsapp_session_id'])
    raw_state=(state.get('instance') or {}).get('state') if isinstance(state,dict) else None
    if raw_state not in {'open','connected'}:
        raise HTTPException(409,'WhatsApp is not connected')
    text=('اختبار الاتصال ✅ أرسل أي رسالة لهذا الرقم الآن لإكمال اختبار الاستقبال.'
          if lang=='ar' else
          'Connection test ✅ Reply with any message now to complete the inbound-message test.')
    started_at=datetime.now().astimezone().isoformat()
    p=await get_pool(); uid=UUID(bid)
    for sk,sv in [('conversation_test_started_at',started_at),('conversation_test_phone',phone)]:
        await p.execute('''INSERT INTO settings(id,"businessId",key,value) VALUES($1,$2,$3,$4)
            ON CONFLICT ("businessId",key) DO UPDATE SET value=EXCLUDED.value''',uuid4(),uid,sk,sv)
    await evolution.send_text(b['whatsapp_session_id'],phone,text)
    return {'ok':True,'phone':phone,'language':lang,'state':raw_state,'started_at':started_at}

@app.get('/api/businesses/{bid}/conversation-test-status')
async def conversation_test_status(bid:str,_=Depends(require_admin)):
    await tenant_or_404(bid); uid=UUID(bid); p=await get_pool()
    keys=['conversation_test_started_at','conversation_test_phone','last_inbound_at','last_inbound_phone','last_inbound_text']
    rows=await p.fetch('SELECT key,value FROM settings WHERE "businessId"=$1 AND key=ANY($2::text[])',uid,keys)
    data={x['key']:x['value'] for x in rows}
    started=data.get('conversation_test_started_at')
    expected=data.get('conversation_test_phone')
    inbound_at=data.get('last_inbound_at')
    inbound_phone=data.get('last_inbound_phone')
    ok=False
    if started and inbound_at and expected and inbound_phone:
        try:
            ok=(normalize_phone(inbound_phone)==normalize_phone(expected)
                and datetime.fromisoformat(inbound_at) >= datetime.fromisoformat(started))
        except Exception:
            ok=False
    return {'ok':ok,'started_at':started,'last_inbound_at':inbound_at,'last_inbound_phone':inbound_phone,'last_inbound_text':data.get('last_inbound_text')}

@app.post('/webhook/whatsapp')
async def whatsapp_webhook(request:Request):
    supplied=request.headers.get('x-webhook-secret','')
    if not supplied or not hmac.compare_digest(supplied,settings.whatsapp_webhook_secret):
        return JSONResponse({'ok':False,'error':'unauthorized webhook'},401)
    payload=await request.json(); event=(payload.get('event') or '').lower().replace('_','.')
    if event not in {'messages.upsert','messages-upsert'}: return {'ok':True}
    data=payload.get('data') or {}; key=data.get('key') or {}
    if key.get('fromMe') or key.get('remoteJid','').endswith('@g.us'): return {'ok':True}
    msg=data.get('message') or {}
    if 'protocolMessage' in msg or msg.get('requestId'): return {'ok':True}
    instance=payload.get('instance') or data.get('instance') or ''
    m=re.search(r'([0-9a-fA-F]{32})$',instance)
    if not m: return JSONResponse({'ok':False,'error':'invalid instance'},400)
    bid=UUID(m.group(1)); b=await business(bid)
    if not b or b['whatsapp_session_id']!=instance: return JSONResponse({'ok':False,'error':'unknown tenant'},404)
    text=msg.get('conversation') or (msg.get('extendedTextMessage') or {}).get('text') or (msg.get('imageMessage') or {}).get('caption') or ''
    if not text: return {'ok':True}
    phone=jid_to_phone(key,data)
    if not phone: return JSONResponse({'ok':False,'error':'unknown sender'},400)
    p=await get_pool()
    now_iso=datetime.now().astimezone().isoformat()
    for sk,sv in [('last_inbound_at',now_iso),('last_inbound_phone',phone),('last_inbound_text',text[:160])]:
        await p.execute('''INSERT INTO settings(id,"businessId",key,value) VALUES($1,$2,$3,$4)
            ON CONFLICT ("businessId",key) DO UPDATE SET value=EXCLUDED.value''',uuid4(),bid,sk,sv)
    mid=key.get('id')
    if mid and not await r.set(f'wa:message:{bid}:{mid}','1',nx=True,ex=86400): return {'ok':True,'duplicate':True}
    lock=r.lock(f'wa:lock:{bid}:{phone}',timeout=15,blocking_timeout=5)
    async with lock:
        reply=await handle(bid,phone,text)
    await evolution.send_text(instance,phone,reply)
    return {'ok':True}

@app.post('/api/test/businesses/{bid}/message')
async def test_message(bid:str,request:Request,_=Depends(require_admin)):
    if not settings.enable_test_mode: raise HTTPException(404)
    b=await tenant_or_404(bid)
    if not b['whatsapp_session_id'].startswith('test-'): raise HTTPException(400,'Not a test business')
    body=await request.json(); phone=body.get('phone','966500000001'); text=body.get('text','')
    return {'reply':await handle(UUID(bid),phone,text)}


# The VPS profile serves static assets through Nginx. The Railway profile copies
# the same dashboard into /app/frontend so the public app can serve it directly.
from pathlib import Path
from fastapi.staticfiles import StaticFiles
if Path('/app/frontend').is_dir():
    app.mount('/', StaticFiles(directory='/app/frontend', html=True), name='frontend')

```


---

## whatsapp-bot/backend/app/migrate.py

```python
import asyncio
from pathlib import Path
import asyncpg
from .config import settings

async def main():
    conn = await asyncpg.connect(settings.database_url)
    try:
        for path in sorted(Path('/app/migrations').glob('*.sql')):
            await conn.execute(path.read_text())
            print(f"applied {path.name}")
    finally:
        await conn.close()

if __name__ == '__main__':
    asyncio.run(main())

```


---

## whatsapp-bot/backend/app/persistence.py

```python
import argparse
import base64
import json
import os
import subprocess
import tempfile
import time
import urllib.request
import urllib.error

SUPABASE_URL = os.getenv("WA_PERSIST_URL", "").rstrip("/")
SUPABASE_KEY = os.getenv("WA_PERSIST_KEY", "")
BACKUP_SECRET = os.getenv("WA_BACKUP_SECRET", "")
INTERVAL = max(15, int(os.getenv("WA_BACKUP_INTERVAL_SECONDS", "30")))

DATABASES = {
    "booking": "booking",
    "evolution": "evolution",
}

def enabled():
    return bool(SUPABASE_URL and SUPABASE_KEY and BACKUP_SECRET)

def rpc(name, payload):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/rpc/{name}",
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as res:
            raw = res.read()
            return json.loads(raw.decode("utf-8")) if raw else None
    except urllib.error.HTTPError as exc:
        body=exc.read().decode("utf-8","replace")[:500]
        print(f"[persistence] rpc {name} HTTP {exc.code}: {body}",flush=True)
        raise

def run(cmd):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

def backup_one(kind, database):
    fd, path = tempfile.mkstemp(prefix=f"wa-{kind}-", suffix=".dump")
    os.close(fd)
    try:
        run([
            "pg_dump", "-Fc", "-Z", "6",
            "-h", "127.0.0.1", "-p", "5432", "-U", "postgres",
            "-d", database, "-f", path,
        ])
        with open(path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode("ascii")
        rpc("wa_backup_store", {
            "p_secret": BACKUP_SECRET,
            "p_kind": kind,
            "p_payload_b64": encoded,
        })
        print(f"[persistence] backup ok: {kind}", flush=True)
    finally:
        try:
            os.remove(path)
        except FileNotFoundError:
            pass

def backup_all():
    if not enabled():
        print("[persistence] remote persistence is not configured", flush=True)
        return False
    for kind, database in DATABASES.items():
        backup_one(kind, database)
    return True

def load_one(kind):
    data = rpc("wa_backup_load", {
        "p_secret": BACKUP_SECRET,
        "p_kind": kind,
    })
    if not data:
        return None
    if isinstance(data, list):
        if not data:
            return None
        row = data[0]
    else:
        row = data
    return row.get("payload_b64")

def restore_one(kind, database):
    payload = load_one(kind)
    if not payload:
        print(f"[persistence] no remote backup yet: {kind}", flush=True)
        return False
    fd, path = tempfile.mkstemp(prefix=f"wa-restore-{kind}-", suffix=".dump")
    os.close(fd)
    try:
        with open(path, "wb") as f:
            f.write(base64.b64decode(payload))
        run([
            "pg_restore",
            "--clean", "--if-exists", "--no-owner", "--no-privileges",
            "-h", "127.0.0.1", "-p", "5432", "-U", "postgres",
            "-d", database, path,
        ])
        print(f"[persistence] restore ok: {kind}", flush=True)
        return True
    finally:
        try:
            os.remove(path)
        except FileNotFoundError:
            pass

def restore_all():
    if not enabled():
        print("[persistence] remote persistence is not configured", flush=True)
        return False
    restored = False
    for kind, database in DATABASES.items():
        try:
            restored = restore_one(kind, database) or restored
        except Exception as exc:
            print(f"[persistence] restore failed for {kind}: {type(exc).__name__}", flush=True)
            raise
    return restored

def loop():
    # Give migrations / Evolution a few seconds to settle after startup.
    time.sleep(12)
    while True:
        try:
            backup_all()
        except Exception as exc:
            print(f"[persistence] backup cycle failed: {type(exc).__name__}", flush=True)
        time.sleep(INTERVAL)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["backup", "restore", "loop"])
    args = parser.parse_args()
    if args.action == "backup":
        backup_all()
    elif args.action == "restore":
        restore_all()
    else:
        loop()

if __name__ == "__main__":
    main()

```


---

## whatsapp-bot/backend/app/persistence_probe.py

```python
import os
import subprocess
import sys

VALUE=os.getenv("WA_PERSISTENCE_CANARY","wa-persist-canary-v1")

def psql(db, sql):
    r=subprocess.run(
        ["psql","-h","127.0.0.1","-p","5432","-U","postgres","-d",db,"-Atc",sql],
        check=True,capture_output=True,text=True
    )
    return r.stdout.strip()

def write():
    for db in ("booking","evolution"):
        psql(db, """CREATE TABLE IF NOT EXISTS _wa_persistence_probe(
          value text PRIMARY KEY,
          created_at timestamptz NOT NULL DEFAULT now()
        );""")
        safe=VALUE.replace("'","''")
        psql(db, f"INSERT INTO _wa_persistence_probe(value) VALUES('{safe}') ON CONFLICT(value) DO NOTHING;")
    print("PERSISTENCE_PROBE_WRITTEN=booking,evolution",flush=True)

def check():
    safe=VALUE.replace("'","''")
    found=[]
    for db in ("booking","evolution"):
        count=psql(db,f"SELECT count(*) FROM _wa_persistence_probe WHERE value='{safe}';")
        if count!="1":
            raise RuntimeError(f"persistence canary missing in {db}")
        found.append(db)
    print("PERSISTENCE_PROBE_PASS="+",".join(found),flush=True)

def cleanup():
    for db in ("booking","evolution"):
        psql(db,"DROP TABLE IF EXISTS _wa_persistence_probe;")
    print("PERSISTENCE_PROBE_CLEANED=booking,evolution",flush=True)

if __name__=="__main__":
    mode=sys.argv[1] if len(sys.argv)>1 else "check"
    {"write":write,"check":check,"cleanup":cleanup}[mode]()

```


# SOURCE EXPORT CHUNK 3/4



---

## whatsapp-bot/backend/app/prayer.py

```python
from datetime import date, datetime, time, timedelta
from math import sin, cos, tan, asin, acos, atan2, radians, degrees, floor

def _fix(a, b): return a - b * floor(a / b)
def _dsin(x): return sin(radians(x))
def _dcos(x): return cos(radians(x))
def _darcsin(x): return degrees(asin(x))
def _darccos(x): return degrees(acos(x))
def _darctan2(y, x): return degrees(atan2(y, x))

def _julian(d: date):
    y, m = d.year, d.month
    if m <= 2: y -= 1; m += 12
    a = floor(y/100); b = 2-a+floor(a/4)
    return floor(365.25*(y+4716))+floor(30.6001*(m+1))+d.day+b-1524.5

def _sun(jd):
    D = jd - 2451545.0
    g = _fix(357.529 + 0.98560028*D, 360)
    q = _fix(280.459 + 0.98564736*D, 360)
    L = _fix(q + 1.915*_dsin(g) + 0.020*_dsin(2*g), 360)
    e = 23.439 - 0.00000036*D
    ra = _fix(_darctan2(_dcos(e)*_dsin(L), _dcos(L))/15, 24)
    eqt = q/15 - ra
    decl = _darcsin(_dsin(e)*_dsin(L))
    return decl, eqt

def _midday(jd):
    _, eqt = _sun(jd)
    return _fix(12 - eqt, 24)

def _angle_time(jd, angle, lat, before=True):
    decl, _ = _sun(jd)
    noon = _midday(jd)
    x = (-_dsin(angle) - _dsin(decl)*_dsin(lat)) / (_dcos(decl)*_dcos(lat))
    x = max(-1, min(1, x))
    t = _darccos(x)/15
    return noon - t if before else noon + t

def _asr(jd, lat):
    decl, _ = _sun(jd)
    angle = -degrees(atan2(1, 1 + tan(radians(abs(lat-decl)))))
    noon = _midday(jd)
    x = (-_dsin(angle)-_dsin(decl)*_dsin(lat))/(_dcos(decl)*_dcos(lat))
    x = max(-1,min(1,x))
    return noon + _darccos(x)/15

def _to_time(v):
    v = _fix(v + 0.5/60, 24)
    h = int(v); m = int((v-h)*60)
    return time(h, m)

def prayer_times(d: date, lat: float, lon: float, ramadan: bool=False):
    jd = _julian(d) - lon/(15*24)
    tz = 3.0
    fajr = _angle_time(jd, 18.5, lat, True) + tz - lon/15
    sunrise = _angle_time(jd, 0.833, lat, True) + tz - lon/15
    dhuhr = _midday(jd) + tz - lon/15
    asr = _asr(jd, lat) + tz - lon/15
    maghrib = _angle_time(jd, 0.833, lat, False) + tz - lon/15
    isha = maghrib + (2.0 if ramadan else 1.5)
    return {"fajr":_to_time(fajr),"sunrise":_to_time(sunrise),"dhuhr":_to_time(dhuhr),"asr":_to_time(asr),"maghrib":_to_time(maghrib),"isha":_to_time(isha)}

def blocked_by_prayer(start: datetime, end: datetime, lat: float|None, lon: float|None, buffer_min: int, ramadan: bool):
    if lat is None or lon is None: return False
    pts = prayer_times(start.date(), float(lat), float(lon), ramadan)
    for k,v in pts.items():
        if k == 'sunrise': continue
        center = datetime.combine(start.date(), v, tzinfo=start.tzinfo)
        a = center - timedelta(minutes=buffer_min)
        b = center + timedelta(minutes=buffer_min)
        if start < b and end > a: return True
    return False

```


---

## whatsapp-bot/backend/app/schemas.py

```python
from pydantic import BaseModel, Field
from typing import Optional

class LoginIn(BaseModel): username:str; password:str
class ServiceIn(BaseModel):
    id: Optional[str]=None; name_ar:str; name_en:str; duration_min:int=Field(gt=0,le=1440); price:float=Field(ge=0); buffer_min:int=Field(default=0,ge=0,le=240)
class HoursIn(BaseModel):
    day_of_week:int=Field(ge=0,le=6); open_time:Optional[str]=None; close_time:Optional[str]=None; is_closed:bool=False; is_ramadan:bool=False
class BusinessIn(BaseModel):
    name_ar:str
    name_en:str
    phone:str
    maps_url:str
    latitude:Optional[float]=None
    longitude:Optional[float]=None
    vat_number:Optional[str]=None
    cr_number:Optional[str]=None
    bot_name_ar:Optional[str]=None
    bot_name_en:Optional[str]=None
    bot_tone:str='friendly'
    welcome_ar:Optional[str]=None
    welcome_en:Optional[str]=None
    services:list[ServiceIn]
    hours:list[HoursIn]
    test_mode:bool=False
class StaffIn(BaseModel):
    id: Optional[str]=None
    name_ar: str
    name_en: str
    is_active: bool=True

class BusinessProfileIn(BaseModel):
    name_ar: str
    name_en: str
    phone: str
    maps_url: str
    latitude: Optional[float]=None
    longitude: Optional[float]=None
    vat_number: Optional[str]=None
    cr_number: Optional[str]=None

class SettingsIn(BaseModel): values:dict[str,str]

```


---

## whatsapp-bot/backend/app/selftest.py

```python
import asyncio
import json
from datetime import time
from uuid import uuid4

from .db import connect_db, close_db, get_pool
from .state_machine import handle, clear, redis as state_redis
from .evolution import evolution


def has_pairing_payload(value):
    if isinstance(value, dict):
        for k, v in value.items():
            if k in {"base64", "code", "pairingCode"} and isinstance(v, str) and len(v) > 8:
                return True
            if has_pairing_payload(v):
                return True
    elif isinstance(value, list):
        return any(has_pairing_payload(v) for v in value)
    return False


async def create_test_tenant():
    bid = uuid4()
    service_id = uuid4()
    staff_id = uuid4()
    instance = "test-biz-" + bid.hex
    p = await get_pool()
    async with p.acquire() as c:
        async with c.transaction():
            await c.execute(
                '''INSERT INTO businesses(id,"businessId",name_ar,name_en,phone,whatsapp_session_id,maps_url)
                   VALUES($1,$1,$2,$3,$4,$5,$6)''',
                bid, "صالون الاختبار", "Test Salon", "966500000099", instance, "https://maps.google.com"
            )
            await c.execute(
                '''INSERT INTO services(id,"businessId",name_ar,name_en,duration_min,price,buffer_min)
                   VALUES($1,$2,$3,$4,30,75,5)''',
                service_id, bid, "قص شعر", "Haircut"
            )
            await c.execute(
                '''INSERT INTO staff(id,"businessId",name_ar,name_en,is_active)
                   VALUES($1,$2,$3,$4,true)''',
                staff_id, bid, "محمد", "Mohammed"
            )
            for ramadan in (False, True):
                for day in range(7):
                    await c.execute(
                        '''INSERT INTO working_hours(id,"businessId",day_of_week,open_time,close_time,is_closed,is_ramadan)
                           VALUES($1,$2,$3,$4,$5,false,$6)''',
                        uuid4(), bid, day, time(0, 1), time(23, 59), ramadan
                    )
            defaults = {
                "ramadan_mode": "false",
                "prayer_buffer_enabled": "false",
                "prayer_buffer_min": "30",
                "slot_interval_min": "30",
                "cancellation_policy_ar": "يمكنك الإلغاء قبل الموعد.",
                "cancellation_policy_en": "You may cancel before the appointment.",
                "bot_name_ar": "نورا",
                "bot_name_en": "Nora",
                "bot_tone": "friendly",
                "welcome_ar": "",
                "welcome_en": "",
                "language_prompt_enabled": "true",
            }
            for k, v in defaults.items():
                await c.execute(
                    '''INSERT INTO settings(id,"businessId",key,value) VALUES($1,$2,$3,$4)''',
                    uuid4(), bid, k, v
                )
    await state_redis.sadd("platform:business_ids", str(bid))
    return bid


async def run_customer_flow(bid, phone, language):
    first = await handle(bid, phone, "hello" if language == "en" else "السلام عليكم")
    assert "اختر اللغة" in first and "Choose your language" in first

    menu = await handle(bid, phone, "2" if language == "en" else "١")
    if language == "en":
        assert "Nora" in menu and "Choose a service" in menu
    else:
        assert "نورا" in menu and "اختر الخدمة" in menu

    slots = await handle(bid, phone, "1")
    assert ("Available times" in slots) if language == "en" else ("الأوقات المتاحة" in slots)

    ask_name = await handle(bid, phone, "1")
    assert ("What is your name?" in ask_name) if language == "en" else ("ما اسمك؟" in ask_name)

    confirmation = await handle(bid, phone, "John" if language == "en" else "محمد")
    assert ("Booked ✅" in confirmation) if language == "en" else ("تم الحجز ✅" in confirmation)

    location = await handle(bid, phone, "location" if language == "en" else "الموقع")
    assert "maps.google.com" in location

    hours = await handle(bid, phone, "working hours" if language == "en" else "ساعات العمل")
    assert ("Working hours" in hours) if language == "en" else ("ساعات العمل" in hours)

    prices = await handle(bid, phone, "prices" if language == "en" else "الأسعار")
    assert ("Haircut" in prices) if language == "en" else ("قص شعر" in prices)

    upcoming = await handle(bid, phone, "my appointment" if language == "en" else "موعدي")
    assert ("Your next appointment" in upcoming) if language == "en" else ("موعدك القادم" in upcoming)

    return {
        "language_prompt": True,
        "service_menu": True,
        "slot_selection": True,
        "name_capture": True,
        "booking_confirmation": True,
        "location_intent": True,
        "hours_intent": True,
        "prices_intent": True,
        "appointment_lookup": True,
    }


async def test_evolution_qr():
    instance = "selftest-" + uuid4().hex
    created = None
    connected = None
    cleanup = False
    try:
        created = await evolution.create_instance(instance)
        connected = await evolution.connect(instance)
        qr_ok = has_pairing_payload(created) or has_pairing_payload(connected)
        if not qr_ok:
            raise AssertionError("Evolution returned no QR/pairing payload")
        return {"instance_create": True, "qr_or_pairing_code": True}
    finally:
        try:
            await evolution.delete_instance(instance)
            cleanup = True
        except Exception:
            pass
        print("SELFTEST_EVOLUTION_CLEANUP=" + json.dumps({"deleted": cleanup}))


async def main():
    bid = None
    ar_phone = "966500000091"
    en_phone = "966500000092"
    result = {}
    await connect_db()
    try:
        bid = await create_test_tenant()
        result["arabic"] = await run_customer_flow(bid, ar_phone, "ar")
        result["english"] = await run_customer_flow(bid, en_phone, "en")

        p = await get_pool()
        langs = await p.fetch(
            '''SELECT phone,preferred_language FROM customers
               WHERE "businessId"=$1 AND phone=ANY($2::text[]) ORDER BY phone''',
            bid, [ar_phone, en_phone]
        )
        remembered = {row["phone"]: row["preferred_language"] for row in langs}
        assert remembered.get(ar_phone) == "ar"
        assert remembered.get(en_phone) == "en"
        result["language_memory"] = True

        count = await p.fetchval(
            '''SELECT COUNT(*) FROM appointments WHERE "businessId"=$1 AND status='confirmed' ''',
            bid
        )
        assert count == 2
        result["appointments_created"] = 2

        result["evolution"] = await test_evolution_qr()

        print("SELFTEST_PASS=" + json.dumps(result, ensure_ascii=False))
    except Exception as exc:
        print("SELFTEST_FAIL=" + json.dumps({
            "type": type(exc).__name__,
            "message": str(exc)[:300],
            "partial": result,
        }, ensure_ascii=False))
        raise
    finally:
        if bid:
            try:
                p = await get_pool()
                await p.execute('DELETE FROM businesses WHERE "businessId"=$1', bid)
            except Exception:
                pass
            await state_redis.srem("platform:business_ids", str(bid))
            await clear(bid, ar_phone)
            await clear(bid, en_phone)
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())

```


---

## whatsapp-bot/backend/app/state_machine.py

```python
import json,re
from datetime import datetime
from zoneinfo import ZoneInfo
from redis.asyncio import Redis
from .config import settings
from .utils import fmt_money
from . import booking

TZ=ZoneInfo(settings.tz)
redis=Redis.from_url(settings.redis_url, decode_responses=True)

def key(bid,phone): return f'booking:{bid}:{phone}'
async def get_state(bid,phone):
    raw=await redis.get(key(bid,phone)); return json.loads(raw) if raw else {}
async def set_state(bid,phone,data): await redis.set(key(bid,phone),json.dumps(data),ex=1800)
async def clear(bid,phone): await redis.delete(key(bid,phone))

def t(lang, ar, en): return ar if lang=='ar' else en

def extract_num(text):
    m=re.search(r'\d+',text or '')
    return int(m.group()) if m else None

def language_prompt():
    return "اختر اللغة / Choose your language:\n1. العربية\n2. English"

def language_choice(text):
    v=(text or '').strip().lower()
    if v in {'1','١','ar','arabic','عربي','العربية','العربي'}: return 'ar'
    if v in {'2','٢','en','english','انجليزي','إنجليزي','الانجليزية','الإنجليزية'}: return 'en'
    return None

async def greeting(bid,lang):
    cfg=await booking.settings_map(bid)
    biz=await booking.business(bid)
    bot_name=(cfg.get('bot_name_ar') if lang=='ar' else cfg.get('bot_name_en')) or (biz['name_ar'] if lang=='ar' else biz['name_en'])
    custom=((cfg.get('welcome_ar') if lang=='ar' else cfg.get('welcome_en')) or '').strip()
    if custom:
        return custom
    tone=cfg.get('bot_tone','friendly')
    phrases={
        'friendly':(
            f"أهلاً! أنا {bot_name}، مساعد الحجز. يسعدني أرتب موعدك.",
            f"Hi! I'm {bot_name}, your booking assistant. I'd be happy to arrange your appointment."
        ),
        'professional':(
            f"مرحباً، معك {bot_name} مساعد الحجز. سأساعدك في اختيار الخدمة والموعد المناسب.",
            f"Hello, this is {bot_name}, your booking assistant. I'll help you choose a service and suitable time."
        ),
        'luxury':(
            f"أهلاً وسهلاً بك. أنا {bot_name}، مساعد الحجز الخاص بك. يسعدني تنسيق موعدك.",
            f"Welcome. I'm {bot_name}, your personal booking assistant. It will be my pleasure to arrange your appointment."
        ),
        'concise':(
            f"مرحباً، أنا {bot_name}. لنحجز موعدك.",
            f"Hi, I'm {bot_name}. Let's book your appointment."
        )
    }
    ar,en=phrases.get(tone,phrases['friendly'])
    return ar if lang=='ar' else en

async def service_menu(bid,lang):
    rows=await booking.services(bid)
    lines=[t(lang,'اختر الخدمة بكتابة الرقم:','Choose a service by number:')]
    for i,s in enumerate(rows,1):
        lines.append(f"{i}. {s['name_ar'] if lang=='ar' else s['name_en']} — {s['duration_min']} {t(lang,'د','min')} — {fmt_money(s['price'])} SAR")
    return '\n'.join(lines), rows

def slots_text(slots,lang):
    ar_days=['الاثنين','الثلاثاء','الأربعاء','الخميس','الجمعة','السبت','الأحد']
    lines=[t(lang,'الأوقات المتاحة خلال 7 أيام:','Available times in the next 7 days:')]
    for i,s in enumerate(slots,1):
        d=datetime.fromisoformat(s['start']).astimezone(TZ)
        label=f"{ar_days[d.weekday()]} {d.strftime('%d/%m - %H:%M')}" if lang=='ar' else d.strftime('%a %d/%m - %H:%M')
        lines.append(f"{i}. {label}")
    lines.append(t(lang,'اكتب رقم الموعد.','Reply with the slot number.'))
    return '\n'.join(lines)

async def hours_text(bid,lang):
    cfg=await booking.settings_map(bid)
    ramadan=cfg.get('ramadan_mode','false')=='true'
    rows=await booking.working_hours(bid,ramadan)
    ar_days=['الأحد','الاثنين','الثلاثاء','الأربعاء','الخميس','الجمعة','السبت']
    en_days=['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday']
    lines=[t(lang,'ساعات العمل:','Working hours:')]
    for row in rows:
        day=(ar_days if lang=='ar' else en_days)[row['day_of_week']]
        if row['is_closed']:
            lines.append(f"{day}: {t(lang,'مغلق','Closed')}")
        else:
            lines.append(f"{day}: {row['open_time'].strftime('%H:%M')}–{row['close_time'].strftime('%H:%M')}")
    return '\n'.join(lines)

async def appointment_text(bid,phone,lang):
    ap=await booking.upcoming(bid,phone)
    if not ap:
        return t(lang,'لا يوجد لديك حجز قادم.','You have no upcoming appointment.')
    d=ap['start_time'].astimezone(TZ)
    return t(lang,f"موعدك القادم يوم {d.strftime('%d/%m')} الساعة {d.strftime('%H:%M')}.",f"Your next appointment is on {d.strftime('%d/%m')} at {d.strftime('%H:%M')}.")

async def begin_booking(bid,phone,lang):
    menu,_=await service_menu(bid,lang)
    await set_state(bid,phone,{'lang':lang,'step':'service'})
    return (await greeting(bid,lang))+'\n\n'+menu

async def handle(bid, phone, text):
    text=(text or '').strip()
    low=text.lower()
    st=await get_state(bid,phone)
    customer=await booking.customer(bid,phone)
    saved_lang=customer['preferred_language'] if customer and customer['preferred_language'] else None

    if low in {'لغة','language','lang','change language','تغيير اللغة'}:
        await set_state(bid,phone,{'step':'language'})
        return language_prompt()

    if st.get('step')=='language':
        lang=language_choice(text)
        if not lang:
            return language_prompt()
        await booking.set_customer_language(bid,phone,lang)
        return await begin_booking(bid,phone,lang)

    lang=st.get('lang') or saved_lang
    if not lang:
        await set_state(bid,phone,{'step':'language'})
        return language_prompt()

    if st and not st.get('lang'):
        st['lang']=lang
        await set_state(bid,phone,st)

    if low in {'الموقع','موقع','وين الموقع','العنوان','location','address','where are you'}:
        biz=await booking.business(bid)
        return t(lang,'هذا موقعنا:','Our location:')+'\n'+biz['maps_url']

    if low in {'الأسعار','الاسعار','الأسعار؟','الخدمات','الخدمات؟','prices','price','services','menu'}:
        menu,_=await service_menu(bid,lang)
        return menu

    if low in {'ساعات العمل','اوقات العمل','أوقات العمل','متى تفتحون','hours','opening hours','working hours'}:
        return await hours_text(bid,lang)

    if low in {'موعدي','حجزي','الحجز','my appointment','my booking','appointment'}:
        return await appointment_text(bid,phone,lang)

    if low in {'مساعدة','help','options','القائمة'}:
        menu,_=await service_menu(bid,lang)
        commands=t(lang,'يمكنك أيضاً كتابة: الموقع، ساعات العمل، موعدي، تغيير، إلغاء، لغة.','You can also type: location, working hours, my appointment, change, cancel, language.')
        return commands+'\n\n'+menu

    if low in {'إلغاء','الغاء','cancel'}:
        ap=await booking.upcoming(bid,phone)
        if not ap: return t(lang,'لا يوجد لديك حجز قادم.','You have no upcoming appointment.')
        cfg=await booking.settings_map(bid)
        policy=cfg.get('cancellation_policy_ar' if lang=='ar' else 'cancellation_policy_en',t(lang,'يمكنك الإلغاء قبل الموعد.','You may cancel before the appointment.'))
        await set_state(bid,phone,{'lang':lang,'step':'cancel_confirm','appointment_id':str(ap['id'])})
        return policy+'\n'+t(lang,'لتأكيد الإلغاء اكتب نعم.','Reply YES to confirm cancellation.')

    if low in {'تغيير','change','reschedule'}:
        ap=await booking.upcoming(bid,phone)
        if not ap: return t(lang,'لا يوجد لديك حجز قادم.','You have no upcoming appointment.')
        slots=await booking.available_slots(bid,ap['service_id'],ap['id'])
        if not slots: return t(lang,'لا توجد مواعيد بديلة متاحة حالياً.','No alternative slots are available right now.')
        await set_state(bid,phone,{'lang':lang,'step':'reschedule_slot','appointment_id':str(ap['id']),'service_id':str(ap['service_id']),'slots':slots})
        return slots_text(slots,lang)

    if st.get('step')=='cancel_confirm':
        if low in {'نعم','yes','y'}:
            await booking.cancel(bid,st['appointment_id'])
            await clear(bid,phone)
            return t(lang,'تم إلغاء الحجز.','Your appointment has been cancelled.')
        await clear(bid,phone)
        return t(lang,'لم يتم إلغاء الحجز.','The appointment was not cancelled.')

    if st.get('step')=='reschedule_slot':
        n=extract_num(text); slots=st['slots']
        if not n or n<1 or n>len(slots): return t(lang,'اختر رقم صحيح من القائمة.','Choose a valid slot number.')
        try:
            ap=await booking.reschedule(bid,st['appointment_id'],slots[n-1])
        except Exception:
            return t(lang,'هذا الموعد لم يعد متاحاً. اختر وقتاً آخر.','That slot is no longer available. Choose another time.')
        await clear(bid,phone)
        d=ap['start_time'].astimezone(TZ)
        return t(lang,f"تم تغيير الموعد ✅ يوم {d.strftime('%d/%m')} الساعة {d.strftime('%H:%M')}.",f"Appointment changed ✅ to {d.strftime('%d/%m')} at {d.strftime('%H:%M')}.")

    if not st:
        return await begin_booking(bid,phone,lang)

    if st.get('step')=='service':
        rows=await booking.services(bid)
        n=extract_num(text); chosen=None
        if n and 1<=n<=len(rows):
            chosen=rows[n-1]
        else:
            q=low
            for s in rows:
                if q and (q in s['name_ar'].lower() or q in s['name_en'].lower() or s['name_ar'].lower() in q or s['name_en'].lower() in q):
                    chosen=s; break
        if not chosen:
            menu,_=await service_menu(bid,lang)
            return t(lang,'لم أفهم اختيارك.\n','I could not match that service.\n')+menu
        slots=await booking.available_slots(bid,chosen['id'])
        if not slots: return t(lang,'لا توجد مواعيد متاحة خلال 7 أيام.','No slots are available in the next 7 days.')
        await set_state(bid,phone,{'lang':lang,'step':'slot','service_id':str(chosen['id']),'service_ar':chosen['name_ar'],'service_en':chosen['name_en'],'slots':slots})
        return slots_text(slots,lang)

    if st.get('step')=='slot':
        n=extract_num(text); slots=st['slots']
        if not n or n<1 or n>len(slots): return t(lang,'اختر رقم صحيح من القائمة.','Choose a valid slot number.')
        c=await booking.customer(bid,phone)
        nextst={**st,'slot':slots[n-1]}
        if not c or not c['name']:
            nextst['step']='name'
            await set_state(bid,phone,nextst)
            return t(lang,'ما اسمك؟','What is your name?')
        return await finalize(bid,phone,nextst,c['name'])

    if st.get('step')=='name':
        name=text[:100]
        if len(name)<2: return t(lang,'اكتب الاسم من فضلك.','Please enter your name.')
        await booking.upsert_customer(bid,phone,name,lang)
        return await finalize(bid,phone,st,name)

    await clear(bid,phone)
    return await begin_booking(bid,phone,lang)

async def finalize(bid,phone,st,name):
    lang=st['lang']
    try:
        ap=await booking.create_appointment(bid,phone,st['service_id'],st['slot'])
    except Exception:
        slots=await booking.available_slots(bid,st['service_id'])
        st['slots']=slots; st['step']='slot'
        await set_state(bid,phone,st)
        return t(lang,'هذا الموعد تم حجزه للتو. اختر وقتاً آخر.\n','That slot was just booked. Choose another time.\n')+slots_text(slots,lang)
    await booking.upsert_customer(bid,phone,name,lang)
    biz=await booking.business(bid)
    await clear(bid,phone)
    d=ap['start_time'].astimezone(TZ)
    svc=st['service_ar'] if lang=='ar' else st['service_en']
    msg=t(lang,f"تم الحجز ✅ {svc} يوم {d.strftime('%d/%m')} الساعة {d.strftime('%H:%M')}. نتشرف بزيارتك.",f"Booked ✅ {svc} on {d.strftime('%d/%m')} at {d.strftime('%H:%M')}. We look forward to seeing you.")
    return msg+'\n'+biz['maps_url']

```


---

## whatsapp-bot/backend/app/utils.py

```python
import re
from datetime import datetime
from zoneinfo import ZoneInfo
from .config import settings

TZ = ZoneInfo(settings.tz)
ARABIC_RE = re.compile(r"[\u0600-\u06FF]")

def detect_lang(text: str) -> str:
    return "ar" if ARABIC_RE.search(text or "") else "en"

def normalize_phone(value: str) -> str:
    digits = re.sub(r"\D", "", value or "")
    if digits.startswith("00"):
        digits = digits[2:]
    if digits.startswith("05") and len(digits) == 10:
        digits = "966" + digits[1:]
    elif digits.startswith("5") and len(digits) == 9:
        digits = "966" + digits
    return digits

def jid_to_phone(key: dict, data: dict) -> str:
    candidates = [key.get("remoteJidAlt"), data.get("senderPn"), data.get("remoteJidAlt"), key.get("remoteJid")]
    for c in candidates:
        if not c:
            continue
        if "@s.whatsapp.net" in c or "@c.us" in c or "@lid" not in c:
            return normalize_phone(c.split("@")[0])
    return normalize_phone((key.get("remoteJid") or "").split("@")[0])

def local_dt(dt: datetime) -> datetime:
    return dt.astimezone(TZ)

def fmt_money(value) -> str:
    return f"{float(value):.2f}".rstrip("0").rstrip(".")

```


---

## whatsapp-bot/backend/app/worker.py

```python
import asyncio
from datetime import datetime,timedelta
from uuid import UUID
from zoneinfo import ZoneInfo
from redis.asyncio import Redis
from .config import settings
from .db import connect_db,get_pool
from .evolution import evolution
from .booking import business

TZ=ZoneInfo(settings.tz)
r=Redis.from_url(settings.redis_url,decode_responses=True)

def text_for(lang,ar,en):
    return ar if lang=='ar' else en

async def tick():
    p=await get_pool()
    now=datetime.now(TZ)
    for raw in await r.smembers('platform:business_ids'):
        bid=UUID(raw)
        biz=await business(bid)
        if not biz:
            continue
        rows=await p.fetch('''
            SELECT a.*,s.name_ar,s.name_en,c.preferred_language
            FROM appointments a
            JOIN services s ON s."businessId"=a."businessId" AND s.id=a.service_id
            LEFT JOIN customers c ON c."businessId"=a."businessId" AND c.phone=a.customer_phone
            WHERE a."businessId"=$1
              AND a.status IN ('confirmed','rescheduled')
              AND (
                a.start_time BETWEEN $2 AND $3
                OR a.end_time BETWEEN $4 AND $5
              )
        ''',bid,now-timedelta(minutes=5),now+timedelta(hours=25),now-timedelta(hours=2),now)
        for a in rows:
            lang=a['preferred_language'] or 'ar'
            start=a['start_time'].astimezone(TZ)
            end=a['end_time'].astimezone(TZ)
            delta=start-now
            after_end=now-end
            msg=None
            col=None
            if timedelta(hours=23,minutes=30)<=delta<=timedelta(hours=24,minutes=30) and not a['reminder_24_sent']:
                msg=text_for(
                    lang,
                    f"تذكير: لديك موعد {a['name_ar']} غداً الساعة {start.strftime('%H:%M')}.",
                    f"Reminder: your {a['name_en']} appointment is tomorrow at {start.strftime('%H:%M')}."
                )
                col='reminder_24_sent'
            elif timedelta(hours=1,minutes=30)<=delta<=timedelta(hours=2,minutes=30) and not a['reminder_2_sent']:
                msg=text_for(
                    lang,
                    f"تذكير أخير: موعد {a['name_ar']} بعد حوالي ساعتين.",
                    f"Final reminder: your {a['name_en']} appointment is in about 2 hours."
                )
                col='reminder_2_sent'
            elif timedelta(minutes=30)<=after_end<=timedelta(hours=1,minutes=30) and not a['followup_sent']:
                msg=text_for(
                    lang,
                    "كيف كانت تجربتك؟ يسعدنا سماع رأيك.",
                    "How was your experience? We would love your feedback."
                )
                col='followup_sent'
            if msg:
                try:
                    await evolution.send_text(biz['whatsapp_session_id'],a['customer_phone'],msg)
                    if col=='followup_sent':
                        await p.execute("UPDATE appointments SET followup_sent=true,status='completed' WHERE \"businessId\"=$1 AND id=$2",bid,a['id'])
                        await p.execute('UPDATE customers SET last_visit=$3 WHERE "businessId"=$1 AND phone=$2',bid,a['customer_phone'],a['end_time'])
                    else:
                        await p.execute(f'UPDATE appointments SET {col}=true WHERE "businessId"=$1 AND id=$2',bid,a['id'])
                except Exception as e:
                    print('worker send failed',bid,a['id'],type(e).__name__)

async def main():
    await connect_db()
    while True:
        try:
            await tick()
        except Exception as e:
            print('worker tick failed',type(e).__name__)
        await asyncio.sleep(60)

if __name__=='__main__':
    asyncio.run(main())

```


---

## whatsapp-bot/frontend/index.html

```html
<!doctype html>
<html lang="ar" dir="rtl">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
  <meta name="theme-color" content="#111827">
  <title>موعدي | WhatsApp Booking</title>
  <link rel="stylesheet" href="/styles.css">
</head>
<body>
  <div id="toast" class="toast hidden" role="status"></div>
  <header class="topbar">
    <div class="brand">
      <div class="brandMark">م</div>
      <div><h1>موعدي</h1><p data-i18n="brandSub">حجوزات واتساب للمنشآت</p></div>
    </div>
    <div class="topActions">
      <button id="langToggle" class="iconBtn" aria-label="Language">EN</button>
      <button id="logout" class="ghost hidden" data-i18n="logout">تسجيل الخروج</button>
    </div>
  </header>

  <main class="shell">
    <section id="loginCard" class="authCard">
      <div class="authIcon">م</div>
      <h2 data-i18n="welcome">أهلاً بك</h2>
      <p class="muted" data-i18n="loginHelp">ادخل لوحة التحكم لإدارة الحجوزات وربط واتساب.</p>
      <label><span data-i18n="username">اسم المستخدم</span><input id="user" autocomplete="username" placeholder="admin"></label>
      <label><span data-i18n="password">كلمة المرور</span><input id="pass" type="password" autocomplete="current-password" placeholder="••••••••"></label>
      <button id="login" class="primary" data-i18n="login">دخول</button>
      <p id="loginMsg" class="errorText"></p>
    </section>

    <div id="app" class="hidden">
      <section class="workspaceBar">
        <div>
          <span class="eyebrow" data-i18n="currentBusiness">المنشأة الحالية</span>
          <select id="businessSelect" aria-label="Business"></select>
        </div>
        <button id="openAddBusiness" class="primary compact" data-i18n="addBusiness">+ إضافة منشأة</button>
      </section>

      <nav class="tabs" aria-label="Navigation">
        <button data-tab="overview" class="active" data-i18n="overview">الرئيسية</button>
        <button data-tab="bookings" data-i18n="bookings">الحجوزات</button>
        <button data-tab="services" data-i18n="services">الخدمات</button>
        <button data-tab="staff" data-i18n="staffTab">الموظفون</button>
        <button data-tab="hours" data-i18n="hours">ساعات العمل</button>
        <button data-tab="settings" data-i18n="settings">الإعدادات</button>
      </nav>

      <section id="overview" class="panel active">
        <div id="emptyState" class="emptyState hidden">
          <div class="emptyIcon">1</div>
          <h2 data-i18n="firstBusiness">أضف أول منشأة</h2>
          <p data-i18n="firstBusinessHelp">أدخل اسم المنشأة وخدمة واحدة على الأقل. بعدها سيظهر QR لربط واتساب.</p>
          <button class="primary" id="emptyAddBusiness" data-i18n="startSetup">ابدأ الإعداد</button>
        </div>

        <div id="overviewContent" class="hidden">
          <div class="heroCard">
            <div>
              <span class="eyebrow" data-i18n="status">الحالة</span>
              <h2 id="heroBusinessName">—</h2>
              <p id="heroSub" class="muted">—</p>
            </div>
            <div id="waBadge" class="statusBadge waiting"><span></span><b data-i18n="checking">جاري التحقق</b></div>
          </div>

          <div class="statsGrid">
            <article class="statCard"><span data-i18n="todayBookings">حجوزات اليوم</span><strong id="todayCount">0</strong></article>
            <article class="statCard"><span data-i18n="upcomingBookings">الحجوزات القادمة</span><strong id="upcomingCount">0</strong></article>
            <article class="statCard"><span data-i18n="servicesCount">الخدمات</span><strong id="servicesCount">0</strong></article>
          </div>

          <div class="contentGrid">
            <article class="card">
              <div class="cardHead"><div><span class="eyebrow" data-i18n="setup">الإعداد</span><h3 data-i18n="goLive">تشغيل المنشأة</h3></div></div>
              <div class="checklist">
                <div class="checkItem done"><span class="check">✓</span><div><b data-i18n="businessAdded">تمت إضافة المنشأة</b><small data-i18n="businessAddedHelp">الاسم والخدمات الأساسية محفوظة.</small></div></div>
                <div id="waChecklist" class="checkItem"><span class="check">2</span><div><b data-i18n="connectWhatsapp">اربط واتساب</b><small data-i18n="connectWhatsappHelp">امسح رمز QR من الأجهزة المرتبطة في واتساب.</small></div></div>
                <div id="testChecklist" class="checkItem"><span class="check">3</span><div><b>اختبار حقيقي / Live test</b><small>أرسل رسالة اختبار واستقبل رداً من نفس الرقم بعد بدء الاختبار.</small></div></div>
                <div id="readyChecklist" class="checkItem"><span class="check">4</span><div><b data-i18n="readyForCustomers">ابدأ استقبال العملاء</b><small data-i18n="readyHelp">بعد نجاح الاختبار الحقيقي يصبح العميل جاهزاً.</small></div></div>
              </div>
              <div id="qrWrap" class="qrBox hidden">
                <img id="qr" alt="WhatsApp QR">
                <div>
                  <h4 data-i18n="scanQr">امسح QR من واتساب</h4>
                  <p class="muted" data-i18n="scanHelp">واتساب ← الإعدادات ← الأجهزة المرتبطة ← ربط جهاز</p>
                  <button id="refreshQr" class="secondary compact" data-i18n="newQr">تحديث QR</button>
                </div>
              </div>
              <div id="liveTestBox" class="liveTestBox hidden">
                <div>
                  <span class="eyebrow">3</span>
                  <h4 id="liveTestTitle">اختبار واتساب الحقيقي</h4>
                  <p id="liveTestHelp" class="muted">أرسل رسالة اختبار إلى رقم آخر، ثم رد من واتساب للتحقق من وصول الرسالة للويب هوك.</p>
                </div>
                <div class="liveTestControls">
                  <input id="liveTestPhone" inputmode="tel" placeholder="9665XXXXXXXX" dir="ltr">
                  <select id="liveTestLang"><option value="ar">العربية</option><option value="en">English</option></select>
                  <button id="sendLiveTest" class="secondary compact" type="button">إرسال اختبار</button>
                  <button id="checkLiveTest" class="secondary compact" type="button">تحقق من الرد</button>
                </div>
                <p id="liveTestResult" class="muted"></p>
              </div>
            </article>

            <article class="card">
              <div class="cardHead"><div><span class="eyebrow" data-i18n="next">التالي</span><h3 data-i18n="nextBookings">أقرب الحجوزات</h3></div><button id="refreshOverview" class="textBtn" data-i18n="refresh">تحديث</button></div>
              <div id="nextAppointments" class="appointmentList"></div>
            </article>
          </div>
        </div>
      </section>

      <section id="bookings" class="panel">
        <div class="card">
          <div class="cardHead"><div><span class="eyebrow" data-i18n="manage">إدارة</span><h2 data-i18n="bookings">الحجوزات</h2></div><button id="loadBookings" class="secondary compact" data-i18n="refresh">تحديث</button></div>
          <div class="tableWrap"><table><thead><tr><th data-i18n="customer">العميل</th><th data-i18n="phone">الهاتف</th><th data-i18n="service">الخدمة</th><th data-i18n="staff">الموظف</th><th data-i18n="time">الوقت</th><th data-i18n="bookingStatus">الحالة</th></tr></thead><tbody id="bookingRows"></tbody></table></div>
        </div>
      </section>

      <section id="services" class="panel">
        <div class="card">
          <div class="cardHead"><div><span class="eyebrow" data-i18n="catalog">القائمة</span><h2 data-i18n="services">الخدمات</h2></div><button id="addService" class="secondary compact" data-i18n="addService">+ خدمة</button></div>
          <p class="muted" data-i18n="serviceHelp">حدد الاسم والمدة والسعر. وقت التجهيز يمنع حجز موعد آخر مباشرة بعد الخدمة.</p>
          <div id="serviceEditor"></div>
          <button id="saveServices" class="primary saveBtn" data-i18n="saveChanges">حفظ التغييرات</button>
        </div>
      </section>

      <section id="staff" class="panel">
        <div class="card">
          <div class="cardHead"><div><span class="eyebrow" data-i18n="team">الفريق</span><h2 data-i18n="staffTab">الموظفون</h2></div><button id="addStaff" class="secondary compact" data-i18n="addStaff">+ موظف</button></div>
          <p class="muted" data-i18n="staffHelp">أضف الأشخاص الذين يمكن الحجز لديهم. يوزع النظام المواعيد على أول موظف متاح.</p>
          <div id="staffEditor"></div>
          <button id="saveStaff" class="primary saveBtn" data-i18n="saveStaff">حفظ الموظفين</button>
        </div>
      </section>

      <section id="hours" class="panel">
        <div class="card">
          <div class="cardHead"><div><span class="eyebrow" data-i18n="schedule">الجدول</span><h2 data-i18n="hours">ساعات العمل</h2></div></div>
          <div class="subTabs"><button data-hours-mode="normal" class="active" data-i18n="normalHours">الأيام العادية</button><button data-hours-mode="ramadan" data-i18n="ramadanHours">رمضان</button></div>
          <div id="hoursEditor"></div>
          <button id="saveHours" class="primary saveBtn" data-i18n="saveHours">حفظ ساعات العمل</button>
        </div>
      </section>

      <section id="settings" class="panel">
        <article class="card profileCard">
          <span class="eyebrow" data-i18n="businessProfile">بيانات المنشأة</span>
          <h3 data-i18n="businessProfileHelp">البيانات التي تظهر في الحجز والتأكيد</h3>
          <div class="formGrid">
            <label><span data-i18n="businessNameAr">اسم المنشأة بالعربي</span><input id="profileNameAr"></label>
            <label><span data-i18n="businessNameEn">Business name in English</span><input id="profileNameEn" dir="ltr"></label>
            <label><span data-i18n="ownerPhone">رقم واتساب</span><input id="profilePhone" dir="ltr"></label>
            <label><span data-i18n="mapsLink">رابط Google Maps</span><input id="profileMaps" dir="ltr"></label>
            <label><span data-i18n="vat">الرقم الضريبي</span><input id="profileVat"></label>
            <label><span data-i18n="cr">رقم السجل التجاري</span><input id="profileCr"></label>
          </div>
          <button id="saveProfile" class="primary saveBtn" data-i18n="saveProfile">حفظ بيانات المنشأة</button>
        </article>
        <article class="card profileCard">
          <span class="eyebrow" data-i18n="botPersonality">شخصية البوت</span>
          <h3 data-i18n="botPersonalityHelp">خصص الاسم والأسلوب ورسالة الترحيب. العميل يختار العربية أو الإنجليزية في أول رسالة.</h3>
          <div class="formGrid">
            <label><span data-i18n="botNameAr">اسم البوت بالعربي</span><input id="settingsBotNameAr" placeholder="موعدي"></label>
            <label><span data-i18n="botNameEn">Bot name in English</span><input id="settingsBotNameEn" dir="ltr" placeholder="Maw3idi"></label>
            <label><span data-i18n="botTone">الأسلوب</span><select id="settingsBotTone">
              <option value="friendly" data-i18n="toneFriendly">ودود</option>
              <option value="professional" data-i18n="toneProfessional">احترافي</option>
              <option value="luxury" data-i18n="toneLuxury">راقي</option>
              <option value="concise" data-i18n="toneConcise">مختصر</option>
            </select></label>
          </div>
          <div class="formGrid">
            <label><span data-i18n="welcomeAr">رسالة ترحيب عربية اختيارية</span><textarea id="settingsWelcomeAr" rows="3" placeholder="اتركها فارغة لاستخدام الرسالة التلقائية"></textarea></label>
            <label><span data-i18n="welcomeEn">Optional English welcome</span><textarea id="settingsWelcomeEn" rows="3" dir="ltr" placeholder="Leave blank to use the automatic greeting"></textarea></label>
          </div>
        </article>
        <div class="settingsGrid">
          <article class="card"><span class="eyebrow" data-i18n="automation">الأتمتة</span><h3 data-i18n="bookingRules">قواعد الحجز</h3>
            <label class="switchRow"><div><b data-i18n="ramadanMode">تفعيل جدول رمضان</b><small data-i18n="ramadanModeHelp">استخدم ساعات رمضان بدلاً من الجدول العادي.</small></div><input type="checkbox" id="ramadanMode"></label>
            <label class="switchRow"><div><b data-i18n="prayerBlock">حجب وقت الصلاة</b><small data-i18n="prayerBlockHelp">يمنع المواعيد حول أوقات الصلاة.</small></div><input type="checkbox" id="prayerEnabled"></label>
            <label><span data-i18n="prayerBuffer">مدة الحجب حول الصلاة بالدقائق</span><input id="prayerBuffer" type="number" min="0" value="30"></label>
            <label><span data-i18n="slotInterval">الفاصل بين الأوقات المتاحة بالدقائق</span><input id="slotInterval" type="number" min="5" value="30"></label>
          </article>
          <article class="card"><span class="eyebrow" data-i18n="policies">السياسات</span><h3 data-i18n="cancellation">سياسة الإلغاء</h3>
            <label><span>العربية</span><textarea id="cancelAr" rows="4"></textarea></label>
            <label><span>English</span><textarea id="cancelEn" rows="4" dir="ltr"></textarea></label>
          </article>
        </div>
        <button id="saveSettings" class="primary saveBtn" data-i18n="saveSettings">حفظ الإعدادات</button>
      </section>
    </div>
  </main>

  <dialog id="businessDialog">
    <form method="dialog" class="dialogCard" id="businessForm">
      <button class="dialogClose" value="cancel" aria-label="Close">×</button>
      <span class="eyebrow" data-i18n="quickSetup">إعداد سريع</span>
      <h2 data-i18n="addBusinessTitle">أضف منشأة جديدة</h2>
      <p class="muted" data-i18n="addBusinessHelp">نحتاج المعلومات الأساسية فقط. يمكنك تعديل كل شيء لاحقاً.</p>

      <div class="onboardProgress" aria-label="Onboarding progress">
        <span class="active" data-onboard-dot="1">1</span>
        <span data-onboard-dot="2">2</span>
        <span data-onboard-dot="3">3</span>
        <b id="onboardStepLabel">بيانات المنشأة</b>
      </div>

      <section class="onboardStep active" data-onboard-step="1">
        <div class="formGrid">
          <label><span data-i18n="businessNameAr">اسم المنشأة بالعربي</span><input id="nameAr" required placeholder="مثال: صالون الرياض"></label>
          <label><span data-i18n="businessNameEn">Business name in English</span><input id="nameEn" required placeholder="Example: Riyadh Salon" dir="ltr"></label>
          <label><span data-i18n="ownerPhone">رقم واتساب</span><input id="phone" required inputmode="tel" placeholder="9665XXXXXXXX"></label>
          <label><span data-i18n="mapsLink">رابط Google Maps</span><input id="maps" required placeholder="https://maps.google.com/..."></label>
        </div>
        <details><summary data-i18n="invoiceDetails">بيانات المنشأة والفوترة الاختيارية</summary><div class="formGrid"><label><span data-i18n="vat">الرقم الضريبي</span><input id="vat"></label><label><span data-i18n="cr">رقم السجل التجاري</span><input id="cr"></label><input id="lat" type="hidden"><input id="lng" type="hidden"></div></details>
      </section>

      <section class="onboardStep" data-onboard-step="2">
        <span class="eyebrow" data-i18n="botPersonality">شخصية البوت</span>
        <h3 data-i18n="botSetupHelp">اختر كيف يتحدث البوت مع عملاء هذه المنشأة.</h3>
        <div class="formGrid">
          <label><span data-i18n="botNameAr">اسم البوت بالعربي</span><input id="botNameAr" placeholder="موعدي"></label>
          <label><span data-i18n="botNameEn">Bot name in English</span><input id="botNameEn" dir="ltr" placeholder="Maw3idi"></label>
          <label><span data-i18n="botTone">الأسلوب</span><select id="botTone">
            <option value="friendly" data-i18n="toneFriendly">ودود</option>
            <option value="professional" data-i18n="toneProfessional">احترافي</option>
            <option value="luxury" data-i18n="toneLuxury">راقي</option>
            <option value="concise" data-i18n="toneConcise">مختصر</option>
          </select></label>
        </div>
        <div class="formGrid">
          <label><span data-i18n="welcomeAr">رسالة ترحيب عربية اختيارية</span><textarea id="welcomeAr" rows="3"></textarea></label>
          <label><span data-i18n="welcomeEn">Optional English welcome</span><textarea id="welcomeEn" rows="3" dir="ltr"></textarea></label>
        </div>
        <p class="muted" data-i18n="languageChoiceHelp">أول رسالة من أي عميل جديد ستكون: اختر اللغة / Choose your language.</p>
      </section>

      <section class="onboardStep" data-onboard-step="3">
        <div class="cardHead onboardingServicesHead">
          <div><h3 data-i18n="firstServices">الخدمات الأولى</h3><p class="muted" data-i18n="serviceInputHelp">أضف خدمة واحدة على الأقل. يمكنك إضافة المزيد لاحقاً.</p></div>
          <button type="button" id="addOnboardingService" class="secondary compact" data-i18n="addService">+ خدمة</button>
        </div>
        <div id="onboardingServices"></div>
        <p class="muted">ساعات العمل الافتراضية 10:00–22:00 ويمكن تعديلها بعد الإنشاء. / Default hours are 10:00–22:00 and can be edited after setup.</p>
      </section>

      <div class="dialogActions">
        <button type="button" id="onboardBack" class="secondary hidden">السابق / Back</button>
        <button type="button" id="onboardNext" class="primary">التالي / Next</button>
        <button type="button" id="createBusiness" class="primary hidden" data-i18n="createConnect">إنشاء وربط واتساب</button>
        <button value="cancel" class="secondary" data-i18n="cancel">إلغاء</button>
      </div>
      <p id="createMsg"></p>
    </form>
  </dialog>

  <script src="/i18n.js"></script>
  <script src="/app-core.js"></script>
  <script src="/app-admin.js"></script>
  <script src="/app-settings.js"></script>
</body>
</html>

```


---

## whatsapp-bot/frontend/styles.css

```css
:root {
  font-family: Tahoma, Arial, sans-serif;
  color: #111827;
  background: #f5f6f8;
  --ink: #111827;
  --muted: #667085;
  --line: #e5e7eb;
  --paper: #ffffff;
  --green: #15803d;
  --red: #b42318;
}
* { box-sizing: border-box; }
body { margin: 0; min-height: 100vh; background: #f5f6f8; }
button, input, textarea, select { font: inherit; }
button { cursor: pointer; }
.hidden { display: none !important; }
.topbar {
  position: sticky; top: 0; z-index: 20;
  display: flex; justify-content: space-between; align-items: center;
  padding: 14px max(16px, calc((100vw - 1180px) / 2));
  background: rgba(255,255,255,.96); border-bottom: 1px solid var(--line);
}
.brand, .topActions, .workspaceBar, .cardHead, .heroCard, .dialogActions { display: flex; align-items: center; }
.brand { gap: 10px; }
.brandMark, .authIcon {
  display: grid; place-items: center; background: var(--ink); color: white;
  border-radius: 12px; font-weight: 800;
}
.brandMark { width: 40px; height: 40px; }
.authIcon { width: 54px; height: 54px; margin-bottom: 18px; }
.brand h1 { margin: 0; font-size: 18px; }
.brand p { margin: 3px 0 0; color: var(--muted); font-size: 12px; }
.topActions { gap: 8px; }
.shell { max-width: 1180px; margin: 26px auto; padding: 0 16px 56px; }
.authCard, .card, .heroCard, .statCard, .emptyState {
  background: var(--paper); border: 1px solid var(--line); border-radius: 18px;
}
.authCard { max-width: 430px; margin: 8vh auto; padding: 28px; }
.authCard h2 { margin: 0 0 8px; }
.authCard label, .dialogCard label, .card > label { display: block; margin-top: 14px; }
.authCard label span, .dialogCard label span, .card > label span {
  display: block; margin-bottom: 6px; font-size: 13px; font-weight: 700;
}
.workspaceBar { justify-content: space-between; gap: 14px; margin-bottom: 16px; }
.workspaceBar > div { width: min(360px, 65vw); }
.workspaceBar select { background: transparent; border: 0; font-weight: 800; padding: 0; }
.eyebrow { display: block; color: var(--muted); font-size: 11px; font-weight: 800; margin-bottom: 5px; }
.tabs, .subTabs { display: flex; gap: 6px; overflow-x: auto; }
.tabs { padding: 5px; margin-bottom: 18px; background: #eceef1; border-radius: 13px; }
.tabs button, .subTabs button {
  border: 0; background: transparent; color: #475467; padding: 10px 14px; border-radius: 9px; white-space: nowrap;
}
.tabs button.active, .subTabs button.active { background: white; color: var(--ink); font-weight: 800; }
.panel { display: none; }
.panel.active { display: block; }
.heroCard { justify-content: space-between; gap: 12px; padding: 22px; margin-bottom: 14px; }
.heroCard h2 { margin: 3px 0; }
.statsGrid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-bottom: 14px; }
.statCard { padding: 18px; }
.statCard span { color: var(--muted); font-size: 13px; }
.statCard strong { display: block; margin-top: 7px; font-size: 29px; }
.contentGrid, .settingsGrid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.card { padding: 22px; }
.cardHead { justify-content: space-between; gap: 12px; margin-bottom: 14px; }
.card h2, .card h3 { margin: 3px 0 10px; }
.muted { color: var(--muted); line-height: 1.55; }
.primary, .secondary, .ghost, .iconBtn, .textBtn {
  border-radius: 10px; border: 1px solid transparent; padding: 10px 14px;
}
.primary { background: var(--ink); color: white; font-weight: 800; }
.secondary, .ghost, .iconBtn { background: white; color: var(--ink); border-color: #d0d5dd; }
.textBtn { background: transparent; color: #344054; }
.compact, .saveBtn { width: auto; }
.saveBtn { margin-top: 18px; }
.statusBadge { display: flex; align-items: center; gap: 8px; padding: 9px 12px; border-radius: 999px; font-size: 13px; }
.statusBadge span { width: 8px; height: 8px; border-radius: 50%; }
.statusBadge.waiting { background: #fffbeb; color: #b45309; }
.statusBadge.waiting span { background: #f59e0b; }
.statusBadge.connected { background: #ecfdf3; color: var(--green); }
.statusBadge.connected span { background: #16a34a; }
.statusBadge.offline { background: #fef2f2; color: var(--red); }
.statusBadge.offline span { background: #ef4444; }
.checkItem { display: flex; gap: 12px; padding: 12px 0; border-bottom: 1px solid #f0f1f3; }
.check { width: 28px; height: 28px; flex: 0 0 28px; display: grid; place-items: center; border-radius: 50%; background: #f2f4f7; }
.checkItem.done .check { background: #ecfdf3; color: var(--green); }
.checkItem small { display: block; margin-top: 4px; color: var(--muted); }
.qrBox { display: grid; grid-template-columns: 170px 1fr; gap: 18px; align-items: center; margin-top: 16px; padding: 16px; background: #f9fafb; border-radius: 14px; }
.qrBox img { width: 170px; max-width: 100%; padding: 7px; background: white; border-radius: 10px; }
.appointmentList { display: grid; gap: 9px; }
.appointmentItem { display: flex; justify-content: space-between; gap: 12px; padding: 12px; border: 1px solid #eef0f2; border-radius: 12px; }
.appointmentItem small { display: block; margin-top: 4px; color: var(--muted); }
.pill { padding: 6px 9px; background: #f2f4f7; border-radius: 999px; font-size: 11px; }
.emptyList, .emptyState { text-align: center; color: var(--muted); }
.emptyList { padding: 28px; background: #f9fafb; border-radius: 12px; }
.emptyState { padding: 52px 24px; }
input, textarea, select { width: 100%; padding: 11px 12px; border: 1px solid #d0d5dd; border-radius: 10px; background: white; color: var(--ink); }
textarea { resize: vertical; }
.tableWrap { overflow: auto; }
table { width: 100%; min-width: 720px; border-collapse: collapse; }
th, td { padding: 12px 9px; border-bottom: 1px solid #eef0f2; text-align: start; white-space: nowrap; }
th { color: var(--muted); font-size: 12px; }
.serviceRow { display: grid; grid-template-columns: 2fr 2fr .8fr .8fr .8fr auto; gap: 8px; align-items: end; padding: 11px 0; border-bottom: 1px solid #eef0f2; }
.serviceRow label { margin: 0; }
.serviceRow label span { display: block; margin-bottom: 5px; color: var(--muted); font-size: 11px; }
.deleteBtn { width: 40px; height: 42px; border: 1px solid #fecaca; border-radius: 9px; background: white; color: var(--red); }
.hourGroup { display: none; }
.hourGroup.active { display: block; }
.hourRow { display: grid; grid-template-columns: 1.2fr 1fr 1fr 1fr; gap: 10px; align-items: center; padding: 8px 0; border-bottom: 1px solid #f1f2f4; }
.dayName { font-weight: 800; }
.closedLabel, .switchRow { display: flex !important; align-items: center; gap: 8px; }
.closedLabel input, .switchRow > input { width: auto; }
.switchRow { justify-content: space-between; padding: 13px 0; border-bottom: 1px solid #eef0f2; margin: 0 !important; }
.switchRow small { display: block; margin-top: 4px; color: var(--muted); }
.formGrid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
dialog { width: min(720px, 100%); padding: 12px; border: 0; background: transparent; }
dialog::backdrop { background: rgba(17,24,39,.52); }
.dialogCard { position: relative; padding: 26px; border-radius: 20px; background: white; }
.dialogClose { position: absolute; top: 14px; left: 16px; width: 34px; height: 34px; border: 0; border-radius: 50%; background: #f2f4f7; }
.dialogActions { gap: 9px; margin-top: 20px; }
.divider { height: 1px; margin: 20px 0; background: #eef0f2; }
.toast { position: fixed; z-index: 100; left: 22px; bottom: 22px; max-width: calc(100vw - 44px); padding: 12px 16px; border-radius: 12px; background: var(--ink); color: white; }
.toast.error { background: var(--red); }
.errorText, .err { color: var(--red); }
.ok { color: var(--green); }
@media (max-width: 850px) {
  .contentGrid, .settingsGrid { grid-template-columns: 1fr; }
  .serviceRow { grid-template-columns: 1fr 1fr 1fr; }
}
@media (max-width: 640px) {
  .topbar { padding: 12px; }
  .brand p { display: none; }
  .shell { margin-top: 18px; padding: 0 12px 40px; }
  .statsGrid { gap: 7px; }
  .statCard { padding: 13px; }
  .statCard strong { font-size: 23px; }
  .heroCard, .card { padding: 16px; }
  .formGrid, .qrBox { grid-template-columns: 1fr; }
  .qrBox { text-align: center; }
  .qrBox img { width: 190px; margin: auto; }
  .serviceRow, .hourRow { grid-template-columns: 1fr 1fr; }
}
.profileCard { margin-bottom: 14px; }
.staffRow { display:grid; grid-template-columns:2fr 2fr 1fr auto; gap:8px; align-items:end; padding:11px 0; border-bottom:1px solid #eef0f2; }
.staffRow label { margin:0; }
.staffRow label span { display:block; margin-bottom:5px; color:var(--muted); font-size:11px; }
.staffActive { min-height:42px; display:flex !important; align-items:center; gap:8px; }
.staffActive input { width:auto; }
.onboardingServicesHead { margin-top:18px; }
.onboardingServiceRow { display:grid; grid-template-columns:2fr 2fr .8fr .8fr .8fr auto; gap:8px; align-items:end; padding:10px 0; }
.heroActions { display:flex; gap:8px; flex-wrap:wrap; align-items:center; }
@media (max-width:850px) {
  .staffRow, .onboardingServiceRow { grid-template-columns:1fr 1fr 1fr; }
}
@media (max-width:640px) {
  .staffRow, .onboardingServiceRow { grid-template-columns:1fr 1fr; }
}

.onboardProgress{display:flex;align-items:center;gap:8px;margin:18px 0;padding:10px 0;border-bottom:1px solid #eef0f2}
.onboardProgress span{display:grid;place-items:center;width:28px;height:28px;border-radius:50%;background:#eef0f2;color:var(--muted);font-weight:700;font-size:12px}
.onboardProgress span.active{background:var(--ink);color:#fff}
.onboardProgress b{margin-inline-start:6px;font-size:13px}
.onboardStep{display:none;min-height:260px}
.onboardStep.active{display:block}
.liveTestBox{margin-top:14px;padding:14px;border:1px solid #e5e7eb;border-radius:14px;background:#fafafa}
.liveTestControls{display:grid;grid-template-columns:2fr 1fr auto auto;gap:8px;align-items:end;margin-top:10px}
.liveTestControls input,.liveTestControls select{margin:0}
@media(max-width:760px){.liveTestControls{grid-template-columns:1fr 1fr}.onboardStep{min-height:auto}}

```


# SOURCE EXPORT CHUNK 4/4



---

## whatsapp-bot/frontend/i18n.js

```javascript
const $=id=>document.getElementById(id);
let current=null,detail=null,appointmentsCache=[],lang=localStorage.getItem('bookingLang')||'ar',hoursMode='normal';
const i18n={
 ar:{brandSub:'حجوزات واتساب للمنشآت',logout:'تسجيل الخروج',welcome:'أهلاً بك',loginHelp:'ادخل لوحة التحكم لإدارة الحجوزات وربط واتساب.',username:'اسم المستخدم',password:'كلمة المرور',login:'دخول',currentBusiness:'المنشأة الحالية',addBusiness:'+ إضافة منشأة',overview:'الرئيسية',bookings:'الحجوزات',services:'الخدمات',hours:'ساعات العمل',settings:'الإعدادات',firstBusiness:'أضف أول منشأة',firstBusinessHelp:'أدخل اسم المنشأة وخدمة واحدة على الأقل. بعدها سيظهر QR لربط واتساب.',startSetup:'ابدأ الإعداد',status:'الحالة',checking:'جاري التحقق',todayBookings:'حجوزات اليوم',upcomingBookings:'الحجوزات القادمة',servicesCount:'الخدمات',setup:'الإعداد',goLive:'تشغيل المنشأة',businessAdded:'تمت إضافة المنشأة',businessAddedHelp:'الاسم والخدمات الأساسية محفوظة.',connectWhatsapp:'اربط واتساب',connectWhatsappHelp:'امسح رمز QR من الأجهزة المرتبطة في واتساب.',readyForCustomers:'ابدأ استقبال العملاء',readyHelp:'بعد الاتصال يستطيع العملاء مراسلة الرقم مباشرة.',scanQr:'امسح QR من واتساب',scanHelp:'واتساب ← الإعدادات ← الأجهزة المرتبطة ← ربط جهاز',newQr:'تحديث QR',next:'التالي',nextBookings:'أقرب الحجوزات',refresh:'تحديث',manage:'إدارة',customer:'العميل',phone:'الهاتف',service:'الخدمة',staff:'الموظف',time:'الوقت',bookingStatus:'الحالة',catalog:'القائمة',addService:'+ خدمة',serviceHelp:'حدد الاسم والمدة والسعر. وقت التجهيز يمنع حجز موعد آخر مباشرة بعد الخدمة.',saveChanges:'حفظ التغييرات',schedule:'الجدول',normalHours:'الأيام العادية',ramadanHours:'رمضان',saveHours:'حفظ ساعات العمل',automation:'الأتمتة',bookingRules:'قواعد الحجز',ramadanMode:'تفعيل جدول رمضان',ramadanModeHelp:'استخدم ساعات رمضان بدلاً من الجدول العادي.',prayerBlock:'حجب وقت الصلاة',prayerBlockHelp:'يمنع المواعيد حول أوقات الصلاة.',prayerBuffer:'مدة الحجب حول الصلاة بالدقائق',slotInterval:'الفاصل بين الأوقات المتاحة بالدقائق',policies:'السياسات',cancellation:'سياسة الإلغاء',saveSettings:'حفظ الإعدادات',quickSetup:'إعداد سريع',addBusinessTitle:'أضف منشأة جديدة',addBusinessHelp:'نحتاج المعلومات الأساسية فقط. يمكنك تعديل كل شيء لاحقاً.',businessNameAr:'اسم المنشأة بالعربي',businessNameEn:'Business name in English',ownerPhone:'رقم واتساب',mapsLink:'رابط Google Maps',invoiceDetails:'بيانات المنشأة والفوترة الاختيارية',vat:'الرقم الضريبي',cr:'رقم السجل التجاري',firstServices:'الخدمات الأولى',serviceInputHelp:'أضف خدمة واحدة على الأقل. يمكنك إضافة المزيد لاحقاً.',createConnect:'إنشاء وربط واتساب',cancel:'إلغاء',connected:'واتساب متصل',notConnected:'واتساب غير متصل',noBookings:'لا توجد حجوزات قادمة.',saved:'تم الحفظ',created:'تم إنشاء المنشأة. اربط واتساب لإكمال التشغيل.',delete:'حذف',duration:'المدة',price:'السعر',buffer:'تجهيز',closed:'مغلق',sar:'ر.س',minutes:'دقيقة',normal:'عادي',ramadan:'رمضان',staffTab:'الموظفون',team:'الفريق',addStaff:'+ موظف',staffHelp:'أضف الأشخاص الذين يمكن الحجز لديهم. يوزع النظام المواعيد على أول موظف متاح.',saveStaff:'حفظ الموظفين',active:'نشط',businessProfile:'بيانات المنشأة',businessProfileHelp:'البيانات التي تظهر في الحجز والتأكيد',saveProfile:'حفظ بيانات المنشأة',botPersonality:'شخصية البوت',botPersonalityHelp:'خصص الاسم والأسلوب ورسالة الترحيب. العميل يختار العربية أو الإنجليزية في أول رسالة.',botSetupHelp:'اختر كيف يتحدث البوت مع عملاء هذه المنشأة.',botNameAr:'اسم البوت بالعربي',botNameEn:'اسم البوت بالإنجليزية',botTone:'الأسلوب',toneFriendly:'ودود',toneProfessional:'احترافي',toneLuxury:'راقي',toneConcise:'مختصر',welcomeAr:'رسالة ترحيب عربية اختيارية',welcomeEn:'رسالة ترحيب إنجليزية اختيارية',languageChoiceHelp:'أول رسالة من أي عميل جديد ستكون: اختر اللغة / Choose your language.'},
 en:{brandSub:'WhatsApp booking for service businesses',logout:'Log out',welcome:'Welcome',loginHelp:'Sign in to manage bookings and connect WhatsApp.',username:'Username',password:'Password',login:'Sign in',currentBusiness:'Current business',addBusiness:'+ Add business',overview:'Overview',bookings:'Bookings',services:'Services',hours:'Working hours',settings:'Settings',firstBusiness:'Add your first business',firstBusinessHelp:'Enter the business name and at least one service. Then connect WhatsApp with a QR code.',startSetup:'Start setup',status:'Status',checking:'Checking',todayBookings:'Today',upcomingBookings:'Upcoming',servicesCount:'Services',setup:'Setup',goLive:'Go live',businessAdded:'Business added',businessAddedHelp:'Basic business details and services are saved.',connectWhatsapp:'Connect WhatsApp',connectWhatsappHelp:'Scan the QR from WhatsApp Linked Devices.',readyForCustomers:'Start receiving customers',readyHelp:'Once connected, customers can message the number directly.',scanQr:'Scan with WhatsApp',scanHelp:'WhatsApp → Settings → Linked Devices → Link a Device',newQr:'Refresh QR',next:'Next',nextBookings:'Upcoming bookings',refresh:'Refresh',manage:'Manage',customer:'Customer',phone:'Phone',service:'Service',staff:'Staff',time:'Time',bookingStatus:'Status',catalog:'Catalog',addService:'+ Service',serviceHelp:'Set the name, duration and price. Buffer blocks the period immediately after a service.',saveChanges:'Save changes',schedule:'Schedule',normalHours:'Regular days',ramadanHours:'Ramadan',saveHours:'Save working hours',automation:'Automation',bookingRules:'Booking rules',ramadanMode:'Use Ramadan schedule',ramadanModeHelp:'Use Ramadan hours instead of the regular schedule.',prayerBlock:'Block prayer times',prayerBlockHelp:'Prevents appointments around prayer times.',prayerBuffer:'Prayer buffer in minutes',slotInterval:'Available-slot interval in minutes',policies:'Policies',cancellation:'Cancellation policy',saveSettings:'Save settings',quickSetup:'Quick setup',addBusinessTitle:'Add a new business',addBusinessHelp:'Only the basics are required. Everything can be edited later.',businessNameAr:'Arabic business name',businessNameEn:'English business name',ownerPhone:'WhatsApp number',mapsLink:'Google Maps link',invoiceDetails:'Optional business and invoice details',vat:'VAT number',cr:'CR number',firstServices:'First services',serviceInputHelp:'Add at least one service. You can add more later.',createConnect:'Create and connect WhatsApp',cancel:'Cancel',connected:'WhatsApp connected',notConnected:'WhatsApp not connected',noBookings:'No upcoming bookings.',saved:'Saved',created:'Business created. Connect WhatsApp to finish setup.',delete:'Delete',duration:'Duration',price:'Price',buffer:'Buffer',closed:'Closed',sar:'SAR',minutes:'min',normal:'Regular',ramadan:'Ramadan',staffTab:'Staff',team:'Team',addStaff:'+ Staff',staffHelp:'Add people who can receive bookings. The system assigns the first available team member.',saveStaff:'Save staff',active:'Active',businessProfile:'Business profile',businessProfileHelp:'Details used in bookings and confirmations',saveProfile:'Save business profile',botPersonality:'Bot personality',botPersonalityHelp:'Customize the name, tone and greeting. New customers choose Arabic or English on their first message.',botSetupHelp:'Choose how the bot should speak to this business’s customers.',botNameAr:'Arabic bot name',botNameEn:'English bot name',botTone:'Tone',toneFriendly:'Friendly',toneProfessional:'Professional',toneLuxury:'Premium',toneConcise:'Concise',welcomeAr:'Optional Arabic welcome',welcomeEn:'Optional English welcome',languageChoiceHelp:'Every new customer is first asked to choose Arabic or English.'}
};
const t=k=>i18n[lang][k]||k;
function applyLanguage(){document.documentElement.lang=lang;document.documentElement.dir=lang==='ar'?'rtl':'ltr';$('langToggle').textContent=lang==='ar'?'EN':'ع';document.querySelectorAll('[data-i18n]').forEach(el=>el.textContent=t(el.dataset.i18n));if(detail){renderServices();renderStaff();renderHours(detail.hours);renderOverview()} }
$('langToggle').onclick=()=>{lang=lang==='ar'?'en':'ar';localStorage.setItem('bookingLang',lang);applyLanguage()};
function toast(msg,error=false){let el=$('toast');el.textContent=msg;el.className='toast'+(error?' error':'');setTimeout(()=>el.classList.add('hidden'),2800);el.classList.remove('hidden')}

```


---

## whatsapp-bot/frontend/app-core.js

```javascript
async function api(path,opt={}){const r=await fetch(path,{credentials:'same-origin',headers:{'Content-Type':'application/json',...(opt.headers||{})},...opt});if(r.status===401){showLogin();throw Error('unauthorized')}const d=await r.json().catch(()=>({}));if(!r.ok)throw Error(d.detail||d.error||r.statusText);return d}
function showLogin(){$('loginCard').classList.remove('hidden');$('app').classList.add('hidden');$('logout').classList.add('hidden')}
function showApp(){$('loginCard').classList.add('hidden');$('app').classList.remove('hidden');$('logout').classList.add('hidden')}
async function init(){applyLanguage();showApp();await loadBusinesses()}
$('login').onclick=async()=>{try{await api('/api/login',{method:'POST',body:JSON.stringify({username:$('user').value,password:$('pass').value})});$('loginMsg').textContent='';showApp();await loadBusinesses()}catch(e){$('loginMsg').textContent=lang==='ar'?'بيانات الدخول غير صحيحة.':'Incorrect login details.'}}
$('pass').addEventListener('keydown',e=>{if(e.key==='Enter')$('login').click()});
$('logout').onclick=async()=>{await api('/api/logout',{method:'POST'}).catch(()=>{});showLogin()};
document.querySelectorAll('.tabs button').forEach(b=>b.onclick=async()=>{document.querySelectorAll('.tabs button,.panel').forEach(x=>x.classList.remove('active'));b.classList.add('active');$(b.dataset.tab).classList.add('active');if(b.dataset.tab==='bookings')await loadBookings()});
function onboardingServiceRow(s={}){
  let div=document.createElement('div');
  div.className='onboardingServiceRow';
  div.innerHTML=`<label><span>${lang==='ar'?'العربية':'Arabic'}</span><input class="o-ar" value="${escapeAttr(s.name_ar||'')}" placeholder="قص شعر"></label><label><span>English</span><input class="o-en" dir="ltr" value="${escapeAttr(s.name_en||'')}" placeholder="Haircut"></label><label><span>${t('duration')}</span><input class="o-duration" type="number" min="5" value="${s.duration_min||30}"></label><label><span>${t('price')}</span><input class="o-price" type="number" min="0" step="0.01" value="${s.price||0}"></label><label><span>${t('buffer')}</span><input class="o-buffer" type="number" min="0" value="${s.buffer_min||0}"></label><button class="deleteBtn onboardingDelete" type="button" title="${t('delete')}">×</button>`;
  div.querySelector('.onboardingDelete').onclick=()=>{if(document.querySelectorAll('#onboardingServices .onboardingServiceRow').length>1)div.remove()};
  return div;
}
let onboardingStep=1;
function setOnboardStep(step){
  onboardingStep=Math.max(1,Math.min(3,step));
  document.querySelectorAll('[data-onboard-step]').forEach(x=>x.classList.toggle('active',+x.dataset.onboardStep===onboardingStep));
  document.querySelectorAll('[data-onboard-dot]').forEach(x=>x.classList.toggle('active',+x.dataset.onboardDot<=onboardingStep));
  $('onboardBack').classList.toggle('hidden',onboardingStep===1);
  $('onboardNext').classList.toggle('hidden',onboardingStep===3);
  $('createBusiness').classList.toggle('hidden',onboardingStep!==3);
  const labels=lang==='ar'?['بيانات المنشأة','شخصية البوت','الخدمات']:['Business details','Bot personality','Services'];
  $('onboardStepLabel').textContent=labels[onboardingStep-1];
}
function validateOnboardStep(){
  if(onboardingStep===1){
    if(!$('nameAr').value.trim()||!$('nameEn').value.trim()||!normalizePhone($('phone').value)||!$('maps').value.trim())
      throw Error(lang==='ar'?'أكمل بيانات المنشأة المطلوبة.':'Complete the required business details.');
  }
  if(onboardingStep===3){
    let rows=[...document.querySelectorAll('#onboardingServices .onboardingServiceRow')];
    if(!rows.some(r=>r.querySelector('.o-ar').value.trim()&&r.querySelector('.o-en').value.trim()))
      throw Error(lang==='ar'?'أضف خدمة واحدة على الأقل.':'Add at least one service.');
  }
  return true;
}
$('onboardNext').onclick=()=>{try{validateOnboardStep();setOnboardStep(onboardingStep+1)}catch(e){toast(e.message,true)}};
$('onboardBack').onclick=()=>setOnboardStep(onboardingStep-1);

function resetBusinessDialog(){
  $('businessForm').reset();
  $('createMsg').textContent='';
  $('botTone').value='friendly';
  $('onboardingServices').innerHTML='';
  $('onboardingServices').appendChild(onboardingServiceRow({name_ar:'قص شعر',name_en:'Haircut',duration_min:30,price:60,buffer_min:10}));
  setOnboardStep(1);
}
$('openAddBusiness').onclick=$('emptyAddBusiness').onclick=()=>{resetBusinessDialog();$('businessDialog').showModal()};
$('addOnboardingService').onclick=()=>$('onboardingServices').appendChild(onboardingServiceRow());

function defaultHours(){let a=[];for(let ram of [false,true])for(let d=0;d<7;d++)a.push({day_of_week:d,open_time:'10:00',close_time:'22:00',is_closed:d===5,is_ramadan:ram});return a}
$('createBusiness').onclick=async()=>{let btn=$('createBusiness');try{validateOnboardStep();btn.disabled=true;btn.textContent=lang==='ar'?'جاري الإنشاء...':'Creating...';let sv=[...document.querySelectorAll('#onboardingServices .onboardingServiceRow')].map(r=>({name_ar:r.querySelector('.o-ar').value.trim(),name_en:r.querySelector('.o-en').value.trim(),duration_min:+r.querySelector('.o-duration').value,price:+r.querySelector('.o-price').value,buffer_min:+r.querySelector('.o-buffer').value})).filter(x=>x.name_ar&&x.name_en);if(!sv.length||sv.some(x=>!x.duration_min||x.duration_min<5||Number.isNaN(x.price)||x.price<0))throw Error(lang==='ar'?'تحقق من بيانات الخدمات.':'Check the service details.');let body={name_ar:$('nameAr').value.trim(),name_en:$('nameEn').value.trim(),phone:normalizePhone($('phone').value),maps_url:$('maps').value.trim(),latitude:null,longitude:null,vat_number:$('vat').value||null,cr_number:$('cr').value||null,bot_name_ar:$('botNameAr').value.trim()||null,bot_name_en:$('botNameEn').value.trim()||null,bot_tone:$('botTone').value,welcome_ar:$('welcomeAr').value.trim()||null,welcome_en:$('welcomeEn').value.trim()||null,services:sv,hours:defaultHours()};if(!body.name_ar||!body.name_en||!body.phone||!body.maps_url)throw Error(lang==='ar'?'أكمل الحقول المطلوبة.':'Complete all required fields.');let d=await api('/api/businesses',{method:'POST',body:JSON.stringify(body)});$('createMsg').innerHTML='<span class="ok">'+t('created')+'</span>';await loadBusinesses(d.id);if(d.qr)showQr(d.qr);setTimeout(()=>$('businessDialog').close(),600);toast(t('created'))}catch(e){$('createMsg').innerHTML='<span class="err">'+escapeHtml(e.message)+'</span>';toast(e.message,true)}finally{btn.disabled=false;btn.textContent=t('createConnect')}};
function normalizePhone(v){let p=v.replace(/\D/g,'');if(p.startsWith('05'))p='966'+p.slice(1);if(p.startsWith('5')&&p.length===9)p='966'+p;return p}
async function loadBusinesses(select){let rows=await api('/api/businesses');$('businessSelect').innerHTML=rows.map(x=>`<option value="${x.id}">${escapeHtml(lang==='ar'?x.name_ar:x.name_en)}</option>`).join('');if(select)$('businessSelect').value=select;if(rows.length){current=$('businessSelect').value;$('emptyState').classList.add('hidden');$('overviewContent').classList.remove('hidden');await loadDetail()}else{current=null;detail=null;$('emptyState').classList.remove('hidden');$('overviewContent').classList.add('hidden')}}
$('businessSelect').onchange=async()=>{current=$('businessSelect').value;await loadDetail()};
async function loadDetail(){if(!current)return;detail=await api('/api/businesses/'+current);renderServices();renderStaff();renderHours(detail.hours);renderSettings();renderProfile();await Promise.all([loadBookings(false),refreshConnection()]);renderOverview()}

```


---

## whatsapp-bot/frontend/app-admin.js

```javascript
function renderOverview(){if(!detail)return;let b=detail.business;$('heroBusinessName').textContent=lang==='ar'?b.name_ar:b.name_en;$('heroSub').textContent=(b.phone||'')+(b.maps_url?' · '+(lang==='ar'?'الموقع محفوظ':'Map saved'):'');$('servicesCount').textContent=(detail.services||[]).length;let now=new Date(),todayKey=dayKey(now);let active=appointmentsCache.filter(a=>a.status!=='cancelled');$('todayCount').textContent=active.filter(a=>dayKey(new Date(a.start_time))===todayKey).length;$('upcomingCount').textContent=active.filter(a=>new Date(a.start_time)>=now).length;let next=active.filter(a=>new Date(a.start_time)>=now).sort((a,b)=>new Date(a.start_time)-new Date(b.start_time)).slice(0,5);$('nextAppointments').innerHTML=next.length?next.map(a=>`<div class="appointmentItem"><div><strong>${escapeHtml(a.customer_name||a.customer_phone)}</strong><small>${escapeHtml(lang==='ar'?a.name_ar:a.name_en)} · ${formatDate(a.start_time)}</small></div><span class="pill">${escapeHtml(a.status)}</span></div>`).join(''):`<div class="emptyList">${t('noBookings')}</div>`}
async function refreshConnection(){if(!current)return;let badge=$('waBadge');badge.className='statusBadge waiting';badge.querySelector('b').textContent=t('checking');try{let d=await api(`/api/businesses/${current}/connection`);let state=((d.instance||d||{}).state||'').toLowerCase();let connected=['open','connected'].includes(state);let tested=false;if(connected){try{let s=await api(`/api/businesses/${current}/conversation-test-status`);tested=!!s.ok}catch{tested=false}}badge.className='statusBadge '+(connected?'connected':'offline');badge.querySelector('b').textContent=connected?t('connected'):t('notConnected');$('waChecklist').classList.toggle('done',connected);$('testChecklist').classList.toggle('done',tested);$('readyChecklist').classList.toggle('done',tested);$('waChecklist').querySelector('.check').textContent=connected?'✓':'2';$('testChecklist').querySelector('.check').textContent=tested?'✓':'3';$('readyChecklist').querySelector('.check').textContent=tested?'✓':'4';if(connected){$('qrWrap').classList.add('hidden');$('liveTestBox').classList.remove('hidden');await fillDefaultTestPhone()}else{$('liveTestBox').classList.add('hidden');await qr()}}catch{badge.className='statusBadge offline';badge.querySelector('b').textContent=t('notConnected');$('testChecklist').classList.remove('done');$('readyChecklist').classList.remove('done');await qr().catch(()=>{})}}
function showQr(q){if(!q)return;$('qrWrap').classList.remove('hidden');$('qr').src=q.startsWith('data:')?q:'data:image/png;base64,'+q}
async function qr(){if(!current)return;let d=await api(`/api/businesses/${current}/qr`);if(d.qr)showQr(d.qr)}
async function fillDefaultTestPhone(){
  try{
    if($('liveTestPhone').value)return;
    let d=await api('/api/client-defaults');
    if(d.test_phone)$('liveTestPhone').value=d.test_phone;
  }catch{}
}
$('refreshQr').onclick=async()=>{await qr();toast(lang==='ar'?'تم تحديث QR':'QR refreshed')};
$('sendLiveTest').onclick=async()=>{try{
  let phone=normalizePhone($('liveTestPhone').value);
  if(!phone)throw Error(lang==='ar'?'أدخل رقم اختبار صحيح.':'Enter a valid test number.');
  let d=await api(`/api/businesses/${current}/test-message`,{method:'POST',body:JSON.stringify({phone,language:$('liveTestLang').value})});
  $('liveTestResult').textContent=lang==='ar'?'تم الإرسال. رد الآن من واتساب ثم اضغط "تحقق من الرد".':'Sent. Reply from WhatsApp, then press "Check reply".';
  toast(lang==='ar'?'تم إرسال رسالة الاختبار':'Test message sent');
}catch(e){$('liveTestResult').textContent=e.message;toast(e.message,true)}};
$('checkLiveTest').onclick=async()=>{try{
  let d=await api(`/api/businesses/${current}/conversation-test-status`);
  if(d.ok){
    $('liveTestResult').textContent=(lang==='ar'?'تم استلام رد واتساب الحقيقي ✅ ':'Real WhatsApp reply received ✅ ')+(d.last_inbound_phone||'');
    $('testChecklist').classList.add('done');$('testChecklist').querySelector('.check').textContent='✓';$('readyChecklist').classList.add('done');$('readyChecklist').querySelector('.check').textContent='✓';toast(lang==='ar'?'اختبار واتساب مكتمل':'WhatsApp test complete');
  }else{
    $('liveTestResult').textContent=lang==='ar'?'لم يصل رد بعد. أرسل أي رسالة من رقم الاختبار.':'No reply received yet. Send any message from the test number.';
  }
}catch(e){toast(e.message,true)}};

$('refreshOverview').onclick=async()=>{await loadDetail();toast(t('saved'))};
function renderServices(){let box=$('serviceEditor');box.innerHTML='';(detail?.services||[]).forEach(s=>addServiceRow(s))}
function addServiceRow(s={}){let div=document.createElement('div');div.className='serviceRow';div.dataset.id=s.id||'';div.innerHTML=`<label><span>العربية</span><input value="${escapeAttr(s.name_ar||'')}" placeholder="قص شعر"></label><label><span>English</span><input value="${escapeAttr(s.name_en||'')}" placeholder="Haircut" dir="ltr"></label><label><span>${t('duration')} (${t('minutes')})</span><input type="number" min="1" value="${s.duration_min||30}"></label><label><span>${t('price')} (${t('sar')})</span><input type="number" min="0" step="0.01" value="${s.price||0}"></label><label><span>${t('buffer')} (${t('minutes')})</span><input type="number" min="0" value="${s.buffer_min||0}"></label><button class="deleteBtn" type="button" title="${t('delete')}">×</button>`;div.querySelector('.deleteBtn').onclick=()=>div.remove();box.appendChild(div)}
$('addService').onclick=()=>addServiceRow();
$('saveServices').onclick=async()=>{try{let items=[...document.querySelectorAll('.serviceRow')].map(r=>{let i=r.querySelectorAll('input');return{id:r.dataset.id||null,name_ar:i[0].value,name_en:i[1].value,duration_min:+i[2].value,price:+i[3].value,buffer_min:+i[4].value}}).filter(x=>x.name_ar&&x.name_en);if(!items.length)throw Error(lang==='ar'?'أضف خدمة واحدة على الأقل.':'Add at least one service.');await api(`/api/businesses/${current}/services`,{method:'PUT',body:JSON.stringify(items)});await loadDetail();toast(t('saved'))}catch(e){toast(e.message,true)}};
const dayNames={ar:['الأحد','الاثنين','الثلاثاء','الأربعاء','الخميس','الجمعة','السبت'],en:['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday']};
function renderHours(items){let map=new Map((items||[]).map(h=>[`${h.is_ramadan}-${h.day_of_week}`,h]));let box=$('hoursEditor');box.innerHTML='';for(let ram of [false,true]){let group=document.createElement('div');group.className='hourGroup '+((ram&&hoursMode==='ramadan')||(!ram&&hoursMode==='normal')?'active':'');group.dataset.group=ram?'ramadan':'normal';for(let d=0;d<7;d++){let x=map.get(`${ram}-${d}`)||{day_of_week:d,open_time:'10:00',close_time:'22:00',is_closed:false,is_ramadan:ram};let div=document.createElement('div');div.className='hourRow';div.dataset.day=d;div.dataset.ramadan=ram;div.innerHTML=`<span class="dayName">${dayNames[lang][d]}</span><input type="time" value="${(x.open_time||'10:00').slice(0,5)}"><input type="time" value="${(x.close_time||'22:00').slice(0,5)}"><label class="closedLabel"><input type="checkbox" ${x.is_closed?'checked':''}> ${t('closed')}</label>`;group.appendChild(div)}box.appendChild(group)}}
document.querySelectorAll('[data-hours-mode]').forEach(b=>b.onclick=()=>{hoursMode=b.dataset.hoursMode;document.querySelectorAll('[data-hours-mode]').forEach(x=>x.classList.toggle('active',x===b));document.querySelectorAll('.hourGroup').forEach(x=>x.classList.toggle('active',x.dataset.group===hoursMode))});

```


---

## whatsapp-bot/frontend/app-settings.js

```javascript

function renderStaff(){
  let box=$('staffEditor'); if(!box)return; box.innerHTML='';
  (detail?.staff||[]).forEach(s=>addStaffRow(s));
}
function addStaffRow(s={}){
  let div=document.createElement('div'); div.className='staffRow'; div.dataset.id=s.id||'';
  div.innerHTML=`<label><span>${lang==='ar'?'العربية':'Arabic'}</span><input class="st-ar" value="${escapeAttr(s.name_ar||'')}" placeholder="محمد"></label><label><span>English</span><input class="st-en" dir="ltr" value="${escapeAttr(s.name_en||'')}" placeholder="Mohammed"></label><label class="staffActive"><input class="st-active" type="checkbox" ${s.is_active===false?'':'checked'}> ${t('active')}</label><button class="deleteBtn staffDelete" type="button" title="${t('delete')}">×</button>`;
  div.querySelector('.staffDelete').onclick=()=>{div.querySelector('.st-active').checked=false;div.classList.add('hidden')};
  $('staffEditor').appendChild(div);
}
$('addStaff').onclick=()=>addStaffRow();
$('saveStaff').onclick=async()=>{
  try{
    let items=[...document.querySelectorAll('#staffEditor .staffRow')].map(r=>({id:r.dataset.id||null,name_ar:r.querySelector('.st-ar').value.trim(),name_en:r.querySelector('.st-en').value.trim(),is_active:r.querySelector('.st-active').checked})).filter(x=>x.name_ar&&x.name_en);
    if(!items.some(x=>x.is_active))throw Error(lang==='ar'?'يجب أن يكون هناك موظف نشط واحد على الأقل.':'At least one active staff member is required.');
    await api(`/api/businesses/${current}/staff`,{method:'PUT',body:JSON.stringify(items)});await loadDetail();toast(t('saved'));
  }catch(e){toast(e.message,true)}
};

function renderProfile(){
  if(!detail?.business)return; let b=detail.business;
  $('profileNameAr').value=b.name_ar||''; $('profileNameEn').value=b.name_en||''; $('profilePhone').value=b.phone||'';
  $('profileMaps').value=b.maps_url||''; $('profileVat').value=b.vat_number||''; $('profileCr').value=b.cr_number||'';
}
$('saveProfile').onclick=async()=>{
  try{
    let b=detail.business;
    let body={name_ar:$('profileNameAr').value.trim(),name_en:$('profileNameEn').value.trim(),phone:normalizePhone($('profilePhone').value),maps_url:$('profileMaps').value.trim(),latitude:b.latitude,longitude:b.longitude,vat_number:$('profileVat').value.trim()||null,cr_number:$('profileCr').value.trim()||null};
    if(!body.name_ar||!body.name_en||!body.phone||!body.maps_url)throw Error(lang==='ar'?'أكمل الحقول المطلوبة.':'Complete all required fields.');
    await api(`/api/businesses/${current}/profile`,{method:'PUT',body:JSON.stringify(body)});await loadBusinesses(current);toast(t('saved'));
  }catch(e){toast(e.message,true)}
};

$('saveHours').onclick=async()=>{try{let items=[...document.querySelectorAll('.hourRow')].map(r=>{let i=r.querySelectorAll('input');return{day_of_week:+r.dataset.day,open_time:i[0].value,close_time:i[1].value,is_closed:i[2].checked,is_ramadan:r.dataset.ramadan==='true'}});await api(`/api/businesses/${current}/hours`,{method:'PUT',body:JSON.stringify(items)});await loadDetail();toast(t('saved'))}catch(e){toast(e.message,true)}};
function renderSettings(){let s=detail?.settings||{};$('ramadanMode').checked=s.ramadan_mode==='true';$('prayerEnabled').checked=s.prayer_buffer_enabled==='true';$('prayerBuffer').value=s.prayer_buffer_min||30;$('slotInterval').value=s.slot_interval_min||30;$('cancelAr').value=s.cancellation_policy_ar||'';$('cancelEn').value=s.cancellation_policy_en||'';$('settingsBotNameAr').value=s.bot_name_ar||detail?.business?.name_ar||'';$('settingsBotNameEn').value=s.bot_name_en||detail?.business?.name_en||'';$('settingsBotTone').value=s.bot_tone||'friendly';$('settingsWelcomeAr').value=s.welcome_ar||'';$('settingsWelcomeEn').value=s.welcome_en||''}
$('saveSettings').onclick=async()=>{try{let values={ramadan_mode:String($('ramadanMode').checked),prayer_buffer_enabled:String($('prayerEnabled').checked),prayer_buffer_min:$('prayerBuffer').value,slot_interval_min:$('slotInterval').value,cancellation_policy_ar:$('cancelAr').value,cancellation_policy_en:$('cancelEn').value,bot_name_ar:$('settingsBotNameAr').value.trim(),bot_name_en:$('settingsBotNameEn').value.trim(),bot_tone:$('settingsBotTone').value,welcome_ar:$('settingsWelcomeAr').value.trim(),welcome_en:$('settingsWelcomeEn').value.trim(),language_prompt_enabled:'true'};await api(`/api/businesses/${current}/settings`,{method:'PUT',body:JSON.stringify({values})});await loadDetail();toast(t('saved'))}catch(e){toast(e.message,true)}};
$('loadBookings').onclick=()=>loadBookings(true);
async function loadBookings(showToast=false){if(!current)return;appointmentsCache=await api(`/api/businesses/${current}/appointments`);$('bookingRows').innerHTML=appointmentsCache.length?appointmentsCache.map(a=>`<tr><td>${escapeHtml(a.customer_name||'-')}</td><td dir="ltr">${escapeHtml(a.customer_phone)}</td><td>${escapeHtml(lang==='ar'?a.name_ar:a.name_en)}</td><td>${escapeHtml(lang==='ar'?a.staff_ar:a.staff_en)}</td><td>${formatDate(a.start_time)}</td><td><span class="pill">${escapeHtml(a.status)}</span></td></tr>`).join(''):`<tr><td colspan="6"><div class="emptyList">${t('noBookings')}</div></td></tr>`;renderOverview();if(showToast)toast(t('saved'))}
function formatDate(v){try{return new Intl.DateTimeFormat(lang==='ar'?'ar-SA':'en-GB',{weekday:'short',day:'numeric',month:'short',hour:'numeric',minute:'2-digit',timeZone:'Asia/Riyadh'}).format(new Date(v))}catch{return v}}
function dayKey(d){return new Intl.DateTimeFormat('en-CA',{year:'numeric',month:'2-digit',day:'2-digit',timeZone:'Asia/Riyadh'}).format(d)}
function escapeHtml(v=''){return String(v).replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]))}
function escapeAttr(v=''){return escapeHtml(v)}
init();

```


---

## whatsapp-bot/migrations/001_init.sql

```sql
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS btree_gist;

CREATE TABLE IF NOT EXISTS businesses (
    id UUID PRIMARY KEY,
    "businessId" UUID NOT NULL UNIQUE,
    name_ar TEXT NOT NULL,
    name_en TEXT NOT NULL,
    phone TEXT NOT NULL,
    whatsapp_session_id TEXT NOT NULL UNIQUE,
    maps_url TEXT NOT NULL,
    latitude NUMERIC(9,6),
    longitude NUMERIC(9,6),
    vat_number TEXT,
    cr_number TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT businesses_tenant_identity CHECK (id = "businessId")
);

CREATE TABLE IF NOT EXISTS services (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "businessId" UUID NOT NULL REFERENCES businesses("businessId") ON DELETE CASCADE,
    name_ar TEXT NOT NULL,
    name_en TEXT NOT NULL,
    duration_min INTEGER NOT NULL CHECK (duration_min > 0 AND duration_min <= 1440),
    price NUMERIC(10,2) NOT NULL CHECK (price >= 0),
    buffer_min INTEGER NOT NULL DEFAULT 0 CHECK (buffer_min >= 0 AND buffer_min <= 240)
);

CREATE TABLE IF NOT EXISTS working_hours (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "businessId" UUID NOT NULL REFERENCES businesses("businessId") ON DELETE CASCADE,
    day_of_week SMALLINT NOT NULL CHECK (day_of_week BETWEEN 0 AND 6),
    open_time TIME,
    close_time TIME,
    is_closed BOOLEAN NOT NULL DEFAULT FALSE,
    is_ramadan BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT working_hours_times CHECK (
        is_closed OR (open_time IS NOT NULL AND close_time IS NOT NULL AND close_time > open_time)
    ),
    UNIQUE ("businessId", day_of_week, is_ramadan)
);

CREATE TABLE IF NOT EXISTS staff (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "businessId" UUID NOT NULL REFERENCES businesses("businessId") ON DELETE CASCADE,
    name_ar TEXT NOT NULL,
    name_en TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS appointments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "businessId" UUID NOT NULL REFERENCES businesses("businessId") ON DELETE CASCADE,
    customer_phone TEXT NOT NULL,
    service_id UUID NOT NULL REFERENCES services(id),
    staff_id UUID NOT NULL REFERENCES staff(id),
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('confirmed','rescheduled','cancelled','completed','no_show')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reminder_24_sent BOOLEAN NOT NULL DEFAULT FALSE,
    reminder_2_sent BOOLEAN NOT NULL DEFAULT FALSE,
    followup_sent BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT appointment_time_order CHECK (end_time > start_time)
);

CREATE TABLE IF NOT EXISTS customers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "businessId" UUID NOT NULL REFERENCES businesses("businessId") ON DELETE CASCADE,
    phone TEXT NOT NULL,
    name TEXT,
    no_show_count INTEGER NOT NULL DEFAULT 0 CHECK (no_show_count >= 0),
    last_visit TIMESTAMPTZ,
    UNIQUE ("businessId", phone)
);

CREATE TABLE IF NOT EXISTS settings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "businessId" UUID NOT NULL REFERENCES businesses("businessId") ON DELETE CASCADE,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    UNIQUE ("businessId", key)
);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'appointments_no_overlap'
    ) THEN
        ALTER TABLE appointments
        ADD CONSTRAINT appointments_no_overlap
        EXCLUDE USING gist (
            "businessId" WITH =,
            staff_id WITH =,
            tstzrange(start_time, end_time, '[)') WITH &&
        ) WHERE (status IN ('confirmed','rescheduled'));
    END IF;
END $$;

```


---

## whatsapp-bot/migrations/002_indexes.sql

```sql
CREATE INDEX IF NOT EXISTS idx_services_business ON services("businessId");
CREATE INDEX IF NOT EXISTS idx_hours_business_day ON working_hours("businessId", day_of_week, is_ramadan);
CREATE INDEX IF NOT EXISTS idx_staff_business_active ON staff("businessId", is_active);
CREATE INDEX IF NOT EXISTS idx_appointments_business_start ON appointments("businessId", start_time);
CREATE INDEX IF NOT EXISTS idx_appointments_business_phone ON appointments("businessId", customer_phone, start_time);
CREATE INDEX IF NOT EXISTS idx_customers_business_phone ON customers("businessId", phone);
CREATE INDEX IF NOT EXISTS idx_settings_business_key ON settings("businessId", key);

```


---

## whatsapp-bot/migrations/003_customer_language.sql

```sql
ALTER TABLE customers
  ADD COLUMN IF NOT EXISTS preferred_language TEXT;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname='customers_preferred_language_check'
  ) THEN
    ALTER TABLE customers
      ADD CONSTRAINT customers_preferred_language_check
      CHECK (preferred_language IS NULL OR preferred_language IN ('ar','en'));
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_customers_business_language
  ON customers("businessId", preferred_language);

```


