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
