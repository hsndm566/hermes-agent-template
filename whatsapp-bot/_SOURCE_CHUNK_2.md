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
