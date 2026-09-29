import json
import os
import threading
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
PAIR_CODE = os.getenv("TELEGRAM_CAPTURE_CODE", "").strip()
PORT = int(os.getenv("PORT", "8080"))
TIMEOUT_SECONDS = int(os.getenv("TELEGRAM_CAPTURE_TIMEOUT", "600"))
PUBLIC_DOMAIN = os.getenv("RAILWAY_PUBLIC_DOMAIN", "").strip()
WEBHOOK_URL = os.getenv("TELEGRAM_CAPTURE_WEBHOOK_URL", "").strip()
OUT = Path("/data/.hermes/telegram_owner.json")
CAPTURED = threading.Event()
OWNER = None


def api(method: str, params: dict | None = None):
    if not TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is missing")
    url = f"https://api.telegram.org/bot{TOKEN}/{method}"
    data = urllib.parse.urlencode(params or {}).encode()
    req = urllib.request.Request(url, data=data)
    with urllib.request.urlopen(req, timeout=25) as r:
        payload = json.load(r)
    if not payload.get("ok"):
        raise RuntimeError(f"Telegram API {method} failed")
    return payload.get("result")


def normalize_text(value: str) -> str:
    return (
        (value or "")
        .strip()
        .replace("–", "-")
        .replace("—", "-")
        .replace("−", "-")
        .replace("\u00a0", " ")
        .upper()
    )


def load_existing_owner():
    if not OUT.exists():
        return None
    try:
        owner = json.loads(OUT.read_text())
    except Exception:
        return None
    if owner.get("user_id"):
        print(f"[telegram-capture] existing owner user_id={owner['user_id']} username={owner.get('username','')}", flush=True)
        return owner
    return None


def message_from_update(update: dict):
    for key in ("message", "business_message", "edited_message", "edited_business_message"):
        msg = update.get(key)
        if isinstance(msg, dict):
            return key, msg
    return "", {}


class Handler(BaseHTTPRequestHandler):
    def _send(self, status: int, body: bytes):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            self._send(200, b'{"ok":true,"mode":"telegram-webhook-capture"}')
        else:
            self._send(404, b'{"ok":false}')

    def do_POST(self):
        global OWNER
        if self.path != "/telegram-capture":
            self._send(404, b'{"ok":false}')
            return

        secret = self.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if not PAIR_CODE or secret != PAIR_CODE:
            self._send(403, b'{"ok":false}')
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            update = json.loads(self.rfile.read(length) or b"{}")
        except Exception:
            self._send(400, b'{"ok":false}')
            return

        kind, msg = message_from_update(update)
        chat = msg.get("chat") or {}
        sender = msg.get("from") or {}
        text = (msg.get("text") or "").strip()
        print(
            "[telegram-capture] webhook inbound "
            f"update_id={update.get('update_id')} kind={kind or 'other'} chat_type={chat.get('type','')} "
            f"user_id={sender.get('id','')} username={sender.get('username','')} text_len={len(text)}",
            flush=True,
        )

        expected = normalize_text(PAIR_CODE)
        normalized = normalize_text(text)
        is_match = normalized == expected or normalized == f"/START {expected}"
        user_id = sender.get("id")

        if chat.get("type") == "private" and is_match and user_id:
            OWNER = {
                "user_id": str(user_id),
                "chat_id": str(chat.get("id") or user_id),
                "username": sender.get("username") or "",
                "first_name": sender.get("first_name") or "",
                "captured_at": int(time.time()),
            }
            OUT.write_text(json.dumps(OWNER, indent=2) + "\n")
            OUT.chmod(0o600)
            print(
                f"[telegram-capture] CAPTURED user_id={OWNER['user_id']} username={OWNER['username']} chat_id={OWNER['chat_id']}",
                flush=True,
            )
            CAPTURED.set()

        self._send(200, b'{"ok":true}')

    def log_message(self, *_args):
        return


def lock_to_owner(owner):
    if not owner or not owner.get("user_id"):
        return
    user_id = str(owner["user_id"])
    os.environ["TELEGRAM_ALLOWED_USERS"] = user_id
    os.environ["TELEGRAM_ALLOW_ALL_USERS"] = "false"
    os.environ["GATEWAY_ALLOW_ALL_USERS"] = "false"
    os.environ["TELEGRAM_DM_POLICY"] = "allowlist"
    print(f"[telegram-capture] LOCKED owner user_id={user_id} dm_policy=allowlist", flush=True)


def resolve_webhook_url():
    if WEBHOOK_URL:
        return WEBHOOK_URL
    if PUBLIC_DOMAIN:
        return f"https://{PUBLIC_DOMAIN}/telegram-capture"
    raise RuntimeError("No Railway public domain available for Telegram webhook capture")


if __name__ == "__main__":
    owner = load_existing_owner()
    server = None

    if not owner:
        if not PAIR_CODE:
            raise RuntimeError("TELEGRAM_CAPTURE_CODE is missing")
        server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        print(f"[telegram-capture] health/webhook server ready on :{PORT}", flush=True)

        webhook_url = resolve_webhook_url()
        api("setWebhook", {
            "url": webhook_url,
            "secret_token": PAIR_CODE,
            "drop_pending_updates": "false",
            "allowed_updates": json.dumps(["message", "business_message", "edited_message", "edited_business_message"]),
        })
        info = api("getWebhookInfo") or {}
        print(
            f"[telegram-capture] WEBHOOK READY bot=@{(api('getMe') or {}).get('username','?')} "
            f"url_set={bool(info.get('url'))} pending={info.get('pending_update_count', 0)}",
            flush=True,
        )

        CAPTURED.wait(timeout=TIMEOUT_SECONDS)
        owner = OWNER or load_existing_owner()

        try:
            api("deleteWebhook", {"drop_pending_updates": "false"})
            print("[telegram-capture] webhook removed; switching to Hermes polling", flush=True)
        except Exception as exc:
            print(f"[telegram-capture] deleteWebhook warning: {type(exc).__name__}: {exc}", flush=True)

        server.shutdown()
        server.server_close()

    if owner:
        lock_to_owner(owner)
    else:
        print("[telegram-capture] no owner captured; Hermes will start in configured restricted mode", flush=True)

    os.execv("/usr/bin/tini", ["/usr/bin/tini", "-g", "--", "/app/start.sh"])
