import json
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
PAIR_CODE = os.getenv("TELEGRAM_CAPTURE_CODE", "").strip()
TIMEOUT_SECONDS = int(os.getenv("TELEGRAM_CAPTURE_TIMEOUT", "180"))
OUT = Path("/data/.hermes/telegram_owner.json")


def api(method: str, params: dict | None = None):
    if not TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is missing")
    url = f"https://api.telegram.org/bot{TOKEN}/{method}"
    data = None
    if params:
        data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(url, data=data)
    with urllib.request.urlopen(req, timeout=20) as r:
        payload = json.load(r)
    if not payload.get("ok"):
        raise RuntimeError(f"Telegram API {method} failed")
    return payload.get("result")


def main():
    if not PAIR_CODE:
        print("[telegram-capture] disabled: TELEGRAM_CAPTURE_CODE not set", flush=True)
        return 0

    if OUT.exists():
        try:
            existing = json.loads(OUT.read_text())
            if existing.get("user_id"):
                print(
                    f"[telegram-capture] existing owner user_id={existing['user_id']} username={existing.get('username','')}",
                    flush=True,
                )
                return 0
        except Exception:
            pass

    # Ensure polling is allowed. Keep pending updates; we only consume them after inspecting them.
    try:
        api("deleteWebhook", {"drop_pending_updates": "false"})
    except Exception as exc:
        print(f"[telegram-capture] deleteWebhook warning: {type(exc).__name__}", flush=True)

    me = api("getMe") or {}
    print(
        f"[telegram-capture] READY bot=@{me.get('username','?')} waiting_for_exact_code={PAIR_CODE}",
        flush=True,
    )

    deadline = time.time() + TIMEOUT_SECONDS
    offset = None
    while time.time() < deadline:
        params = {"timeout": 15, "allowed_updates": json.dumps(["message"])}
        if offset is not None:
            params["offset"] = offset
        try:
            updates = api("getUpdates", params) or []
        except Exception as exc:
            print(f"[telegram-capture] getUpdates warning: {type(exc).__name__}", flush=True)
            time.sleep(2)
            continue

        for upd in updates:
            update_id = upd.get("update_id")
            if isinstance(update_id, int):
                offset = update_id + 1
            msg = upd.get("message") or {}
            chat = msg.get("chat") or {}
            sender = msg.get("from") or {}
            text = (msg.get("text") or "").strip()
            if chat.get("type") != "private" or text != PAIR_CODE:
                continue
            user_id = sender.get("id")
            if not user_id:
                continue
            owner = {
                "user_id": str(user_id),
                "chat_id": str(chat.get("id") or user_id),
                "username": sender.get("username") or "",
                "first_name": sender.get("first_name") or "",
                "captured_at": int(time.time()),
            }
            OUT.write_text(json.dumps(owner, indent=2) + "\n")
            OUT.chmod(0o600)
            print(
                f"[telegram-capture] CAPTURED user_id={owner['user_id']} username={owner['username']} chat_id={owner['chat_id']}",
                flush=True,
            )
            return 0

    print("[telegram-capture] TIMEOUT without matching message; starting Hermes without owner capture", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[telegram-capture] ERROR {type(exc).__name__}: {exc}", flush=True)
        raise SystemExit(0)
