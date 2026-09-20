import asyncio
from datetime import datetime,timedelta
from uuid import UUID
from zoneinfo import ZoneInfo
from redis.asyncio import Redis
from .config import settings
from .db import connect_db,get_pool
from .evolution import evolution
from .booking import business

TZ=ZoneInfo(settings.tz); r=Redis.from_url(settings.redis_url,decode_responses=True)

async def tick():
    p=await get_pool(); now=datetime.now(TZ)
    for raw in await r.smembers('platform:business_ids'):
        bid=UUID(raw); biz=await business(bid)
        if not biz: continue
        rows=await p.fetch('''SELECT a.*,s.name_ar,s.name_en FROM appointments a JOIN services s ON s."businessId"=a."businessId" AND s.id=a.service_id WHERE a."businessId"=$1 AND a.status IN ('confirmed','rescheduled') AND a.start_time BETWEEN $2 AND $3''',bid,now-timedelta(hours=2),now+timedelta(hours=25))
        for a in rows:
            delta=a['start_time'].astimezone(TZ)-now; msg=None; col=None
            if timedelta(hours=23,minutes=30)<=delta<=timedelta(hours=24,minutes=30) and not a['reminder_24_sent']:
                msg=f"تذكير: لديك موعد غداً الساعة {a['start_time'].astimezone(TZ).strftime('%H:%M')}\nReminder: your appointment is tomorrow at {a['start_time'].astimezone(TZ).strftime('%H:%M')}"; col='reminder_24_sent'
            elif timedelta(hours=1,minutes=30)<=delta<=timedelta(hours=2,minutes=30) and not a['reminder_2_sent']:
                msg=f"تذكير أخير: موعدك بعد ساعتين.\nFinal reminder: your appointment is in about 2 hours."; col='reminder_2_sent'
            elif timedelta(hours=-1,minutes=-30)<=delta<=timedelta(minutes=-30) and not a['followup_sent']:
                msg="كيف كانت تجربتك؟ يسعدنا سماع رأيك.\nHow was your experience? We would love your feedback."; col='followup_sent'
            if msg:
                try:
                    await evolution.send_text(biz['whatsapp_session_id'],a['customer_phone'],msg)
                    if col=='followup_sent':
                        await p.execute("UPDATE appointments SET followup_sent=true,status='completed' WHERE \"businessId\"=$1 AND id=$2",bid,a['id'])
                        await p.execute('UPDATE customers SET last_visit=$3 WHERE "businessId"=$1 AND phone=$2',bid,a['customer_phone'],a['start_time'])
                    else:
                        await p.execute(f'UPDATE appointments SET {col}=true WHERE "businessId"=$1 AND id=$2',bid,a['id'])
                except Exception as e: print('worker send failed',bid,a['id'],e)

async def main():
    await connect_db()
    while True:
        try: await tick()
        except Exception as e: print('worker tick failed',e)
        await asyncio.sleep(60)
if __name__=='__main__': asyncio.run(main())
