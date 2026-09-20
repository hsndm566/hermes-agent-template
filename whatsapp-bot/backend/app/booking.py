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
async def settings_map(bid):
    p=await get_pool(); rows=await p.fetch('SELECT key,value FROM settings WHERE "businessId"=$1', UUID(str(bid))); return {r['key']:r['value'] for r in rows}
async def customer(bid, phone):
    p=await get_pool(); return await p.fetchrow('SELECT * FROM customers WHERE "businessId"=$1 AND phone=$2', UUID(str(bid)), phone)
async def upsert_customer(bid, phone, name=None):
    p=await get_pool(); return await p.fetchrow('''INSERT INTO customers(id,"businessId",phone,name) VALUES($1,$2,$3,$4)
    ON CONFLICT ("businessId",phone) DO UPDATE SET name=COALESCE(EXCLUDED.name,customers.name) RETURNING *''', uuid4(), UUID(str(bid)), phone, name)

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
