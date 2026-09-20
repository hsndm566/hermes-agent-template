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
