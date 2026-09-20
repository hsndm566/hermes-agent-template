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
    if v in {'1','ar','arabic','عربي','العربية','العربي'}: return 'ar'
    if v in {'2','en','english','انجليزي','إنجليزي','الانجليزية','الإنجليزية'}: return 'en'
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
    lines=[t(lang,'الأوقات المتاحة خلال 7 أيام:','Available times in the next 7 days:')]
    for i,s in enumerate(slots,1):
        d=datetime.fromisoformat(s['start']).astimezone(TZ)
        lines.append(f"{i}. {d.strftime('%a %d/%m - %H:%M')}")
    lines.append(t(lang,'اكتب رقم الموعد.','Reply with the slot number.'))
    return '\n'.join(lines)

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
