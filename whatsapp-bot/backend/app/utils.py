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
