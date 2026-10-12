import re
from datetime import datetime, timezone
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
    for candidate in candidates:
        if not isinstance(candidate, str):
            continue
        local, _, domain = candidate.partition('@')
        if domain not in {'', 's.whatsapp.net', 'c.us'}:
            continue  # LIDs, groups and broadcast addresses are not phone numbers.
        phone = normalize_phone(local.split(':')[0])
        if re.fullmatch(r'[1-9][0-9]{7,14}', phone):
            return phone
    return ''

def inbound_timestamp(data: dict) -> datetime | None:
    value = data.get('messageTimestamp')
    if isinstance(value, dict):
        value = value.get('low')
    try:
        stamp = float(value)
        if stamp > 100_000_000_000:
            stamp /= 1000
        result = datetime.fromtimestamp(stamp, timezone.utc)
        if stamp <= 0 or stamp > datetime.now(timezone.utc).timestamp() + 60:
            return None
        return result
    except (ValueError, TypeError, OverflowError, OSError):
        return None

def local_dt(dt: datetime) -> datetime:
    return dt.astimezone(TZ)

def fmt_money(value) -> str:
    return f"{float(value):.2f}".rstrip("0").rstrip(".")
