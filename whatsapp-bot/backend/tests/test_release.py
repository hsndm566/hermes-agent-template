import os
from pathlib import Path
from uuid import uuid4
from unittest.mock import AsyncMock
import pytest
from fastapi import HTTPException, Response
from starlette.requests import Request
from httpx import AsyncClient, ASGITransport

for key,value in {
'DATABASE_URL':'postgresql://localhost/booking','REDIS_URL':'redis://localhost:6379',
'EVOLUTION_INTERNAL_URL':'http://localhost:8080','EVOLUTION_API_KEY':'test',
'EVOLUTION_WEBHOOK_URL':'http://localhost/webhook/whatsapp','WHATSAPP_WEBHOOK_SECRET':'test-hook',
'APP_PUBLIC_URL':'https://test.local','ADMIN_USERNAME':'owner','ADMIN_PASSWORD':'test-password',
'SESSION_SECRET':'testing-only-secret-not-for-production',
}.items(): os.environ[key]=value
from app import auth, main
from app.schemas import HoursIn, SettingsIn, BusinessIn

def request(token=None):
    headers=[] if token is None else [(b'cookie',f'{auth.COOKIE}={token}'.encode())]
    return Request({'type':'http','headers':headers})

@pytest.mark.parametrize('token',[None,'forged',auth.serializer.dumps({'u':'other'})])
@pytest.mark.asyncio
async def test_reject_invalid_session(token):
    with pytest.raises(HTTPException) as exc: await auth.require_admin(request(token))
    assert exc.value.status_code == 401

@pytest.mark.asyncio
async def test_expired_session(monkeypatch):
    token=auth.serializer.dumps({'u':'owner'})
    monkeypatch.setattr(auth.settings,'session_max_age_seconds',-1)
    with pytest.raises(HTTPException): await auth.require_admin(request(token))

@pytest.mark.asyncio
async def test_session_and_cookie():
    assert await auth.require_admin(request(auth.serializer.dumps({'u':'owner'})))=='owner'
    response=Response();auth.issue_session(response)
    cookie=response.headers['set-cookie']
    assert 'Secure' in cookie and 'HttpOnly' in cookie and 'SameSite=strict' in cookie
    assert auth.valid_credentials('owner','test-password')
    assert not auth.valid_credentials('owner','wrong')

@pytest.mark.parametrize('values',[{'slot_interval_min':'0'},{'slot_interval_min':'-1'},{'slot_interval_min':'bad'},{'prayer_buffer_min':'200'}])
def test_bad_settings(values):
    with pytest.raises(ValueError):SettingsIn(values=values)

@pytest.mark.parametrize('start,end',[('20:00','09:00'),('09:00','09:00'),('bad','17:00'),(None,None)])
def test_bad_hours(start,end):
    with pytest.raises(ValueError):HoursIn(day_of_week=0,open_time=start,close_time=end)

def test_closed_hours_and_valid_settings():
    assert HoursIn(day_of_week=0,is_closed=True,open_time='').open_time is None
    assert SettingsIn(values={'slot_interval_min':'30'}).values['slot_interval_min']=='30'

@pytest.mark.asyncio
async def test_public_routes_and_protected_api():
    async with AsyncClient(transport=ASGITransport(app=main.app),base_url='https://test.local') as c:
        for url in ['/api/session','/api/businesses','/api/client-defaults','/api/businesses/invalid/conversations']:
            assert (await c.get(url)).status_code==401
        root=await c.get('/')
        assert root.status_code==200 and 'id="root"' in root.text
        assert 'assets/index-' in root.text
        assert (await c.get('/connect')).headers['location']=='/#/whatsapp'
        assert (await c.get('/pair/obsolete')).status_code==404
        assert (await c.post('/webhook/whatsapp',json={})).status_code==401

@pytest.mark.asyncio
async def test_database_is_tenant_registry(monkeypatch):
    p=AsyncMock();p.fetch.return_value=[]
    monkeypatch.setattr(main,'get_pool',AsyncMock(return_value=p))
    assert await main.list_businesses() == []
    assert 'FROM businesses' in p.fetch.call_args.args[0]

@pytest.mark.asyncio
async def test_messages_scoped_to_selected_business(monkeypatch):
    bid=str(uuid4()); p=AsyncMock();p.fetch.return_value=[]
    monkeypatch.setattr(main,'tenant_or_404',AsyncMock(return_value={}))
    monkeypatch.setattr(main,'get_pool',AsyncMock(return_value=p))
    await main.conversation_messages(bid,'+966500000001')
    query,tenant,phone=p.fetch.call_args.args
    assert '"businessId"=$1 AND phone=$2' in query
    assert str(tenant)==bid and phone=='966500000001'
    await main.conversations(bid)
    assert '"businessId"=$1' in p.fetch.call_args.args[0]

@pytest.mark.asyncio
async def test_history_dedupe(monkeypatch):
    p=AsyncMock();monkeypatch.setattr(main,'get_pool',AsyncMock(return_value=p))
    await main.record_message(uuid4(),'966500000001','inbound','hello','message-id')
    assert 'ON CONFLICT ("businessId",direction,provider_id) DO NOTHING' in p.execute.call_args.args[0]

@pytest.mark.asyncio
async def test_no_signup_setup_cookie_and_workspace_isolation(monkeypatch):
    bid=str(uuid4()); owner=str(uuid4())
    monkeypatch.setattr(main,'business',AsyncMock(return_value={'id':bid,'owner_session':owner}))
    async with AsyncClient(transport=ASGITransport(app=main.app),base_url='https://test.local') as c:
        response=await c.post('/api/setup')
        assert response.status_code==200
        assert 'HttpOnly' in response.headers['set-cookie']
        session=await c.get('/api/session')
        assert session.status_code==200
        assert session.json()['username']==response.json()['username']
        assert (await c.get(f'/api/businesses/{bid}')).status_code==404
        again=await c.post('/api/setup')
        assert again.json()['username']==response.json()['username']
