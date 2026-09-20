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

    menu = await handle(bid, phone, "2" if language == "en" else "1")
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

    return {
        "language_prompt": True,
        "service_menu": True,
        "slot_selection": True,
        "name_capture": True,
        "booking_confirmation": True,
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
