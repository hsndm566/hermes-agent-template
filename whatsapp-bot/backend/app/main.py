import hmac
import asyncio
import asyncpg
import httpx
import re
import os
from uuid import UUID,uuid4
from decimal import Decimal
from datetime import datetime, time
from fastapi import FastAPI,Request,Response,Depends,HTTPException
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse, FileResponse
from redis.asyncio import Redis
from .config import settings
from .db import connect_db,close_db,get_pool
from .auth import valid_credentials,issue_session,clear_session,require_admin,current_owner,serializer,COOKIE
from .schemas import LoginIn,BusinessIn,ServiceIn,HoursIn,SettingsIn,StaffIn,BusinessProfileIn,AppointmentActionIn
from .evolution import evolution
from .booking import business, cancel as booking_cancel, reschedule as booking_reschedule
from .state_machine import handle
from .utils import jid_to_phone, normalize_phone, inbound_timestamp
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
async def session(_=Depends(require_admin)): return {'ok':True,'username':_}

@app.post('/api/setup')
async def setup_device(request:Request,response:Response):
    # No registration or password: this browser receives a signed private workspace.
    try:
        owner=await require_admin(request)
    except HTTPException:
        owner=str(uuid4())
        token=serializer.dumps({'u':owner})
        response.set_cookie(COOKIE,token,httponly=True,secure=settings.app_public_url.startswith('https://'),samesite='strict',max_age=2592000,path='/')
    return {'ok':True,'username':owner}

@app.get('/api/client-defaults')
async def client_defaults(_=Depends(require_admin)):
    return {'test_phone': ''}

async def tenant_or_404(bid:str):
    try: uid=UUID(bid)
    except: raise HTTPException(404,'Business not found')
    row=await business(uid)
    if not row: raise HTTPException(404,'Business not found')
    owner=current_owner.get()
    if owner != settings.admin_username and row.get('owner_session') != owner:
        raise HTTPException(404,'Business not found')
    return row

def qr_value(data):
    q=data.get('qrcode') or data
    return q.get('base64') if isinstance(q,dict) else None

@app.post('/api/businesses')
async def add_business(body:BusinessIn,_=Depends(require_admin)):
    owner=current_owner.get()
    if not owner: raise HTTPException(401,'Open your workspace first')
    p=await get_pool()
    if owner != settings.admin_username:
        count=await p.fetchval('SELECT COUNT(*) FROM businesses WHERE owner_session=$1',owner)
        if count: raise HTTPException(409,'This browser already has a WhatsApp workspace')
        throttle=f'new-workspace:{owner}'
        if not await r.set(throttle,'1',nx=True,ex=30): raise HTTPException(429,'Please wait before trying again')
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
            await c.execute('UPDATE businesses SET owner_session=$2 WHERE "businessId"=$1',bid,owner)
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
    p=await get_pool()
    owner=current_owner.get()
    if owner == settings.admin_username:
        rows=await p.fetch('SELECT * FROM businesses ORDER BY created_at DESC')
    else:
        rows=await p.fetch('SELECT * FROM businesses WHERE owner_session=$1 ORDER BY created_at DESC',owner)
    return [{k:(str(v) if isinstance(v,UUID) else v) for k,v in dict(row).items()} for row in rows]

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
        data=await evolution.connect(b['whatsapp_session_id']); return {'qr':qr_value(data)}
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


@app.patch('/api/businesses/{bid}/appointments/{aid}')
async def update_appointment(bid:str,aid:str,body:AppointmentActionIn,_=Depends(require_admin)):
    await tenant_or_404(bid); uid=UUID(bid); p=await get_pool()
    try:
        appt_uid=UUID(aid)
    except Exception:
        raise HTTPException(404,'Appointment not found')
    existing=await p.fetchrow('SELECT * FROM appointments WHERE "businessId"=$1 AND id=$2',uid,appt_uid)
    if not existing:
        raise HTTPException(404,'Appointment not found')

    if body.action=='cancel':
        row=await booking_cancel(uid,appt_uid)
    elif body.action=='reschedule':
        if not body.slot:
            raise HTTPException(400,'slot is required for reschedule')
        try:
            row=await booking_reschedule(uid,appt_uid,body.slot.model_dump())
        except asyncpg.exceptions.ExclusionViolationError:
            raise HTTPException(409,'That slot is no longer available')
    elif body.action=='complete':
        row=await p.fetchrow("UPDATE appointments SET status='completed' WHERE \"businessId\"=$1 AND id=$2 RETURNING *",uid,appt_uid)
        await p.execute('UPDATE customers SET last_visit=$3 WHERE "businessId"=$1 AND phone=$2',uid,existing['customer_phone'],existing['end_time'])
    elif body.action=='no_show':
        row=await p.fetchrow("UPDATE appointments SET status='no_show' WHERE \"businessId\"=$1 AND id=$2 RETURNING *",uid,appt_uid)
        await p.execute('UPDATE customers SET no_show_count=no_show_count+1 WHERE "businessId"=$1 AND phone=$2',uid,existing['customer_phone'])
    else:
        raise HTTPException(400,'Unknown action')

    return {k:(str(v) if isinstance(v,UUID) else v.isoformat() if isinstance(v,datetime) else v) for k,v in dict(row).items()}

@app.get('/api/businesses/{bid}/customers')
async def customers_list(bid:str,_=Depends(require_admin)):
    await tenant_or_404(bid); uid=UUID(bid); p=await get_pool()
    rows=await p.fetch('SELECT * FROM customers WHERE "businessId"=$1 ORDER BY last_visit DESC NULLS LAST, phone',uid)
    return [{k:(str(v) if isinstance(v,UUID) else v.isoformat() if isinstance(v,datetime) else v) for k,v in dict(x).items()} for x in rows]

async def record_message(bid, phone, direction, text, provider_id=None):
    p=await get_pool()
    await p.execute('''INSERT INTO messages(id,"businessId",phone,direction,body,provider_id)
        VALUES($1,$2,$3,$4,$5,$6) ON CONFLICT ("businessId",direction,provider_id) DO NOTHING''',
        uuid4(),UUID(str(bid)),phone,direction,text[:10000],provider_id)

@app.get('/api/businesses/{bid}/conversations')
async def conversations(bid:str,_=Depends(require_admin)):
    await tenant_or_404(bid); p=await get_pool()
    rows=await p.fetch('''SELECT * FROM (
        SELECT DISTINCT ON (phone) phone,body,direction,created_at
        FROM messages WHERE "businessId"=$1 ORDER BY phone,created_at DESC
        ) latest ORDER BY created_at DESC LIMIT 100''',UUID(bid))
    return [dict(row) for row in rows]

@app.get('/api/businesses/{bid}/messages')
async def conversation_messages(bid:str,phone:str,_=Depends(require_admin)):
    await tenant_or_404(bid); p=await get_pool()
    rows=await p.fetch('''SELECT id,phone,direction,body,created_at FROM messages
        WHERE "businessId"=$1 AND phone=$2 ORDER BY created_at DESC LIMIT 200''',UUID(bid),normalize_phone(phone))
    return [dict(row) for row in reversed(rows)]

@app.delete('/api/businesses/{bid}/connection')
async def disconnect(bid:str,_=Depends(require_admin)):
    b=await tenant_or_404(bid)
    if b['whatsapp_session_id'].startswith('test-'):
        raise HTTPException(400,'Test-mode businesses have no real connection to disconnect')
    try:
        await evolution.logout(b['whatsapp_session_id'])
    except Exception as e:
        raise HTTPException(502,str(e))
    return {'ok':True}

@app.post('/api/businesses/{bid}/test-message')
async def live_test_message(bid:str,request:Request,_=Depends(require_admin)):
    b=await tenant_or_404(bid)
    if b['whatsapp_session_id'].startswith('test-'):
        raise HTTPException(400,'Connect a real WhatsApp number first')
    body=await request.json()
    phone=normalize_phone(body.get('phone',''))
    lang=(body.get('language') or 'ar').lower()
    if not re.fullmatch(r'[1-9][0-9]{7,14}',phone):
        raise HTTPException(400,'Enter a valid phone number with country code')
    state=await evolution.state(b['whatsapp_session_id'])
    raw_state=(state.get('instance') or {}).get('state') if isinstance(state,dict) else None
    if raw_state not in {'open','connected'}:
        raise HTTPException(409,'WhatsApp is not connected')
    text=('اختبار الاتصال ✅ أرسل أي رسالة لهذا الرقم الآن لإكمال اختبار الاستقبال.'
          if lang=='ar' else
          'Connection test ✅ Reply with any message now to complete the inbound-message test.')
    started_at=datetime.now().astimezone().isoformat()
    p=await get_pool(); uid=UUID(bid)
    for sk,sv in [('conversation_test_started_at',started_at),('conversation_test_phone',phone),('conversation_test_sent_at','')]:
        await p.execute('''INSERT INTO settings(id,"businessId",key,value) VALUES($1,$2,$3,$4)
            ON CONFLICT ("businessId",key) DO UPDATE SET value=EXCLUDED.value''',uuid4(),uid,sk,sv)
    await evolution.send_text(b['whatsapp_session_id'],phone,text)
    await p.execute('''INSERT INTO settings(id,"businessId",key,value) VALUES($1,$2,'conversation_test_sent_at',$3)
        ON CONFLICT ("businessId",key) DO UPDATE SET value=EXCLUDED.value''',uuid4(),uid,started_at)
    return {'ok':True,'phone':phone,'language':lang,'state':raw_state,'started_at':started_at}

@app.get('/api/businesses/{bid}/conversation-test-status')
async def conversation_test_status(bid:str,_=Depends(require_admin)):
    await tenant_or_404(bid); uid=UUID(bid); p=await get_pool()
    keys=['conversation_test_sent_at','conversation_test_started_at','conversation_test_phone','last_inbound_at','last_inbound_phone','last_inbound_text']
    rows=await p.fetch('SELECT key,value FROM settings WHERE "businessId"=$1 AND key=ANY($2::text[])',uid,keys)
    data={x['key']:x['value'] for x in rows}
    started=data.get('conversation_test_started_at')
    expected=data.get('conversation_test_phone')
    inbound_at=data.get('last_inbound_at')
    inbound_phone=data.get('last_inbound_phone')
    ok=False
    if started and data.get('conversation_test_sent_at') == started and inbound_at and expected and inbound_phone:
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
    if key.get('fromMe') or key.get('remoteJid','').endswith(('@g.us','@broadcast','@newsletter')): return {'ok':True}
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
    if not phone: return {'ok':True,'ignored':'sender phone unavailable'}
    mid=key.get('id')
    done_key=f'wa:message:done:{bid}:{mid}' if mid else None
    reply_key=f'wa:message:reply:{bid}:{mid}' if mid else None

    # A WhatsApp delivery is only "done" after both the booking logic and the
    # outbound reply succeed. Cache the generated reply before sending it so an
    # Evolution retry can resend the same reply without running booking logic
    # twice (important if the send succeeded partially or the HTTP call failed).
    if done_key and await r.get(done_key):
        return {'ok':True,'duplicate':True}

    async def process_message():
        user_lock=r.lock(f'wa:lock:{bid}:{phone}',timeout=45,blocking_timeout=10)
        async with user_lock:
            if done_key and await r.get(done_key):
                return {'ok':True,'duplicate':True}

            cached_reply=await r.get(reply_key) if reply_key else None
            if cached_reply:
                await evolution.send_text(instance,phone,cached_reply)
                await record_message(bid,phone,'outbound',cached_reply,mid)
                pipe=r.pipeline()
                pipe.set(done_key,'1',ex=86400)
                pipe.delete(reply_key)
                await pipe.execute()
                return {'ok':True,'retried':True}

            await record_message(bid,phone,'inbound',text,mid)
            received_at=inbound_timestamp(data)
            if received_at:
                p=await get_pool()
                for sk,sv in [('last_inbound_at',received_at.isoformat()),('last_inbound_phone',phone),('last_inbound_text',text[:160])]:
                    await p.execute('''INSERT INTO settings(id,"businessId",key,value) VALUES($1,$2,$3,$4)
                        ON CONFLICT ("businessId",key) DO UPDATE SET value=EXCLUDED.value''',uuid4(),bid,sk,sv)
            reply=await handle(bid,phone,text)
            if reply_key:
                await r.set(reply_key,reply,ex=86400)

            await evolution.send_text(instance,phone,reply)
            await record_message(bid,phone,'outbound',reply,mid)

            if done_key:
                pipe=r.pipeline()
                pipe.set(done_key,'1',ex=86400)
                pipe.delete(reply_key)
                await pipe.execute()
            return {'ok':True}

    if mid:
        message_lock=r.lock(f'wa:message-lock:{bid}:{mid}',timeout=60,blocking_timeout=10)
        async with message_lock:
            return await process_message()
    return await process_message()

@app.post('/api/test/businesses/{bid}/message')
async def test_message(bid:str,request:Request,_=Depends(require_admin)):
    if not settings.enable_test_mode: raise HTTPException(404)
    b=await tenant_or_404(bid)
    if not b['whatsapp_session_id'].startswith('test-'): raise HTTPException(400,'Not a test business')
    body=await request.json(); phone=body.get('phone','966500000001'); text=body.get('text','')
    return {'reply':await handle(UUID(bid),phone,text)}


@app.get('/connect', include_in_schema=False)
async def connect_whatsapp():
    return RedirectResponse('/#/whatsapp')

from pathlib import Path
from fastapi.staticfiles import StaticFiles
FRONTEND = Path(os.getenv('FRONTEND_DIR', '/app/frontend' if Path('/app/frontend').is_dir() else str(Path(__file__).resolve().parents[2] / 'frontend')))

@app.get('/', include_in_schema=False)
async def product_root():
    index = FRONTEND / 'index.html'
    if not index.is_file():
        raise HTTPException(503, 'Dashboard assets are not built')
    return FileResponse(index, headers={'Cache-Control': 'no-store'})

if FRONTEND.is_dir():
    app.mount('/', StaticFiles(directory=str(FRONTEND), html=True), name='frontend')
