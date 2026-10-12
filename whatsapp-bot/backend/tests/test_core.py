from datetime import datetime, timedelta, timezone
from uuid import uuid4
from unittest.mock import AsyncMock
import pytest
import fakeredis.aioredis
from httpx import AsyncClient, ASGITransport
from app import main, booking, worker, state_machine as sm
from app.evolution import EvolutionClient
from app.schemas import SettingsIn
from app.utils import jid_to_phone, inbound_timestamp

@pytest.mark.parametrize('key,expected',[
    ({'remoteJid':'123456789012345@lid'},''),
    ({'remoteJid':'123456789012345@lid','remoteJidAlt':'966500000001@s.whatsapp.net'},'966500000001'),
    ({'remoteJid':'966500000001:7@s.whatsapp.net'},'966500000001'),
    ({'remoteJid':'status@broadcast'},''),
    ({'remoteJid':'123456789@g.us'},''),
])
def test_sender_resolution(key,expected): assert jid_to_phone(key,{})==expected

@pytest.mark.parametrize('value',[None,{},'bad',-3,10**100])
def test_untrusted_timestamps(value): assert inbound_timestamp({'messageTimestamp':value}) is None

def test_seconds_and_milliseconds():
    now=int(datetime.now(timezone.utc).timestamp())
    assert inbound_timestamp({'messageTimestamp':now})==inbound_timestamp({'messageTimestamp':now*1000})

@pytest.mark.parametrize('key',['last_inbound_at','conversation_test_sent_at','conversation_test_started_at'])
def test_test_results_cannot_be_forged(key):
    with pytest.raises(ValueError): SettingsIn(values={key:'2030-01-01'})

@pytest.mark.asyncio
async def test_reminders_use_durable_registry(monkeypatch):
    bid=uuid4();p=AsyncMock();p.fetch.side_effect=[[{'businessId':bid}],[]]
    monkeypatch.setattr(worker,'get_pool',AsyncMock(return_value=p))
    monkeypatch.setattr(worker,'business',AsyncMock(return_value={'whatsapp_session_id':'biz-'+bid.hex}))
    # If Redis is touched this test fails; reminders must survive an empty cache.
    redis=AsyncMock();redis.smembers.side_effect=AssertionError('Redis registry used')
    monkeypatch.setattr(worker,'r',redis)
    await worker.tick()
    assert p.fetch.await_count==2
    redis.smembers.assert_not_awaited()

@pytest.mark.asyncio
async def test_failed_webhook_setup_cleans_created_instance(monkeypatch):
    client=EvolutionClient()
    monkeypatch.setattr(client,'_request',AsyncMock(return_value={'instance':{}}))
    monkeypatch.setattr(client,'configure_webhook',AsyncMock(side_effect=RuntimeError('provider unavailable')))
    delete=AsyncMock();monkeypatch.setattr(client,'delete_instance',delete)
    with pytest.raises(RuntimeError):await client.create_instance('new-business')
    delete.assert_awaited_once_with('new-business')

@pytest.mark.asyncio
@pytest.mark.parametrize('sent,age,expected',[(True,10,True),(False,10,False),(True,-10,False)])
async def test_readiness_requires_successful_send_and_fresh_reply(monkeypatch,sent,age,expected):
    started=datetime.now(timezone.utc)
    values={'conversation_test_started_at':started.isoformat(),'conversation_test_sent_at':started.isoformat() if sent else '',
    'conversation_test_phone':'966500000001','last_inbound_phone':'966500000001','last_inbound_at':(started+timedelta(seconds=age)).isoformat()}
    p=AsyncMock();p.fetch.return_value=[{'key':k,'value':v} for k,v in values.items()]
    monkeypatch.setattr(main,'get_pool',AsyncMock(return_value=p));monkeypatch.setattr(main,'tenant_or_404',AsyncMock())
    result=await main.conversation_test_status(str(uuid4()))
    assert result['ok'] is expected

class Lock:
    async def __aenter__(self):return self
    async def __aexit__(self,*args):pass

@pytest.mark.asyncio
async def test_webhook_retry_does_not_double_process_or_refresh_test(monkeypatch):
    bid=uuid4();instance='biz-'+bid.hex;redis=fakeredis.aioredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(redis,'lock',lambda *a,**k:Lock())
    monkeypatch.setattr(main,'r',redis)
    monkeypatch.setattr(main,'business',AsyncMock(return_value={'whatsapp_session_id':instance}))
    pool=AsyncMock();monkeypatch.setattr(main,'get_pool',AsyncMock(return_value=pool))
    history=AsyncMock();monkeypatch.setattr(main,'record_message',history)
    handle=AsyncMock(return_value='reply');monkeypatch.setattr(main,'handle',handle)
    send=AsyncMock(side_effect=[RuntimeError('temporary provider failure'),{'key':{'id':'outbound'}}]);monkeypatch.setattr(main.evolution,'send_text',send)
    payload={'event':'MESSAGES_UPSERT','instance':instance,'data':{'key':{'id':'msg-1','remoteJid':'966500000001@s.whatsapp.net','fromMe':False},'messageTimestamp':int(datetime.now(timezone.utc).timestamp()),'message':{'conversation':'hello'}}}
    async with AsyncClient(transport=ASGITransport(app=main.app,raise_app_exceptions=False),base_url='https://test.local') as c:
        assert (await c.post('/webhook/whatsapp',headers={'x-webhook-secret':'test-hook'},json=payload)).status_code==500
        updates=pool.execute.await_count
        retry=await c.post('/webhook/whatsapp',headers={'x-webhook-secret':'test-hook'},json=payload)
        assert retry.json()['retried']
        duplicate=await c.post('/webhook/whatsapp',headers={'x-webhook-secret':'test-hook'},json=payload)
        assert duplicate.json()['duplicate']
    handle.assert_awaited_once();assert send.await_count==2
    assert pool.execute.await_count==updates
    await redis.aclose()

@pytest.mark.asyncio
@pytest.mark.parametrize('lang,choice,name',[('ar','١','حسن'),('en','2','Hasan')])
async def test_existing_booking_conversation_flow(monkeypatch,lang,choice,name):
    bid=uuid4();phone='966500000001';sid=uuid4();staff=uuid4();aid=uuid4()
    redis=fakeredis.aioredis.FakeRedis(decode_responses=True);monkeypatch.setattr(sm,'redis',redis)
    customers={};appointment=None
    start=datetime.now(timezone.utc)+timedelta(days=2);slot={'start':start.isoformat(),'end':(start+timedelta(minutes=30)).isoformat(),'staff_id':str(staff)}
    async def customer(*args):return customers.get(phone)
    async def upsert(b,p,n=None,preferred_language=None):
        c=customers.setdefault(p,{'name':None,'preferred_language':None})
        if n:c['name']=n
        if preferred_language:c['preferred_language']=preferred_language
        return c
    async def language(b,p,l):return await upsert(b,p,preferred_language=l)
    async def create(*args):
        nonlocal appointment
        appointment={'id':aid,'service_id':sid,'start_time':start};return appointment
    async def upcoming(*args):return appointment
    async def cancel(*args):
        nonlocal appointment
        appointment=None
    async def reschedule(*args):return appointment
    for key,fn in {'customer':customer,'upsert_customer':upsert,'set_customer_language':language,'create_appointment':create,'upcoming':upcoming,'cancel':cancel,'reschedule':reschedule}.items():monkeypatch.setattr(booking,key,fn)
    monkeypatch.setattr(booking,'settings_map',AsyncMock(return_value={}))
    monkeypatch.setattr(booking,'business',AsyncMock(return_value={'name_ar':'مساعد','name_en':'Assistant','maps_url':'https://maps.example'}))
    monkeypatch.setattr(booking,'services',AsyncMock(return_value=[{'id':sid,'name_ar':'خدمة','name_en':'Service','duration_min':30,'price':0}]))
    monkeypatch.setattr(booking,'available_slots',AsyncMock(return_value=[slot]))
    assert 'Choose your language' in await sm.handle(bid,phone,'hello')
    assert ('اختر الخدمة' if lang=='ar' else 'Choose a service') in await sm.handle(bid,phone,choice)
    assert ('الأوقات المتاحة' if lang=='ar' else 'Available times') in await sm.handle(bid,phone,'1')
    assert ('ما اسمك' if lang=='ar' else 'What is your name') in await sm.handle(bid,phone,'1')
    assert ('تم الحجز' if lang=='ar' else 'Booked') in await sm.handle(bid,phone,name)
    assert customers[phone]['preferred_language']==lang and appointment is not None
    assert ('موعدك القادم' if lang=='ar' else 'Your next appointment') in await sm.handle(bid,phone,'my booking')
    await sm.handle(bid,phone,'change')
    assert ('تم تغيير' if lang=='ar' else 'Appointment changed') in await sm.handle(bid,phone,'1')
    await sm.handle(bid,phone,'cancel')
    assert ('تم إلغاء' if lang=='ar' else 'has been cancelled') in await sm.handle(bid,phone,'yes')
    assert appointment is None
    await redis.aclose()
