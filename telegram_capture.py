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
TIMEOUT_SECONDS = int(os.getenv("TELEGRAM_CAPTURE_TIMEOUT", "300"))
WARMUP_SECONDS = int(os.getenv("TELEGRAM_CAPTURE_WARMUP", "15"))
PORT = int(os.getenv("PORT", "8080"))
OUT = Path("/data/.hermes/telegram_owner.json")


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            body = b'{"ok":true,"mode":"telegram-owner-capture"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(503)
            self.end_headers()

    def log_message(self, *_args):
        return


def start_health_server():
    server = ThreadingHTTPServer(("0.0.0.0", PORT), HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"[telegram-capture] health server ready on :{PORT}", flush=True)
    return server


def api(method: str, params: dict | None = None):
    if not TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is missing")
    url = f"https://api.telegram.org/bot{TOKEN}/{method}"
    data = None
    if params:
        data = urllib.parse.urlencode(params).encode()
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
        existing = json.loads(OUT.read_text())
    except Exception:
        return None
    if existing.get("user_id"):
        print(
            f"[telegram-capture] existing owner user_id={existing['user_id']} username={existing.get('username','')}",
            flush=True,
        )
        return existing
    return None


def message_from_update(upd: dict):
    # Telegram Business accounts can surface inbound content as business_message.
    for key in ("message", "business_message", "edited_message", "edited_business_message"):
        msg = upd.get(key)
        if isinstance(msg, dict):
            return key, msg
    return "", {}


def capture_owner():
    existing = load_existing_owner()
    if existing:
        return existing

    if not PAIR_CODE:
        print("[telegram-capture] disabled: TELEGRAM_CAPTURE_CODE not set", flush=True)
        return None

    try:
        api("deleteWebhook", {"drop_pending_updates": "false"})
        webhook = api("getWebhookInfo") or {}
        print(
            "[telegram-capture] webhook "
            f"url_set={bool(webhook.get('url'))} pending={webhook.get('pending_update_count', 0)} "
            f"last_error={bool(webhook.get('last_error_message'))}",
            flush=True,
        )
    except Exception as exc:
        print(f"[telegram-capture] webhook diagnostic warning: {type(exc).__name__}: {exc}", flush=True)

    me = api("getMe") or {}
    print(
        f"[telegram-capture] READY bot=@{me.get('username','?')} waiting_for_exact_code={PAIR_CODE}",
        flush=True,
    )

    if WARMUP_SECONDS > 0:
        print(f"[telegram-capture] waiting {WARMUP_SECONDS}s for old pollers to retire", flush=True)
        time.sleep(WARMUP_SECONDS)
    print("[telegram-capture] single-poller capture active", flush=True)

    expected = normalize_text(PAIR_CODE)
    deadline = time.time() + TIMEOUT_SECONDS
    offset = None
    poll_count = 0
    while time.time() < deadline:
        # Do not restrict allowed_updates; this also captures Telegram Business updates.
        params = {"timeout": 15}
        if offset is not None:
            params["offset"] = offset
        try:
            updates = api("getUpdates", params) or []
            poll_count += 1
            if poll_count == 1 or updates:
                print(f"[telegram-capture] poll={poll_count} updates={len(updates)} offset={offset}", flush=True)
        except Exception as exc:
            print(f"[telegram-capture] getUpdates warning: {type(exc).__name__}: {exc}", flush=True)
            time.sleep(2)
            continue

        for upd in updates:
            update_id = upd.get("update_id")
            if isinstance(update_id, int):
                offset = update_id + 1
            kind, msg = message_from_update(upd)
            chat = msg.get("chat") or {}
            sender = msg.get("from") or {}
            text = (msg.get("text") or "").strip()
            print(
                "[telegram-capture] inbound "
                f"update_id={update_id} kind={kind or 'other'} chat_type={chat.get('type','')} "
                f"user_id={sender.get('id','')} username={sender.get('username','')} text_len={len(text)}",
                flush=True,
            )
            normalized = normalize_text(text)
            # Accept exact code, a /start payload carrying the code, or the same code
            # with smart-dash substitutions introduced by copy/paste keyboards.
            is_match = normalized == expected or normalized == f"/START {expected}"
            if chat.get("type") != "private" or not is_match:
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
            return owner

    print("[telegram-capture] TIMEOUT without matching message; starting Hermes without owner capture", flush=True)
    return None


def lock_to_owner(owner):
    if not owner or not owner.get("user_id"):
        return
    user_id = str(owner["user_id"])
    os.environ["TELEGRAM_ALLOWED_USERS"] = user_id
    os.environ["TELEGRAM_ALLOW_ALL_USERS"] = "false"
    os.environ["GATEWAY_ALLOW_ALL_USERS"] = "false"
    os.environ["TELEGRAM_DM_POLICY"] = "allowlist"
    print(f"[telegram-capture] LOCKED owner user_id={user_id} dm_policy=allowlist", flush=True)


if __name__ == "__main__":
    owner = load_existing_owner()
    health_server = None
    if not owner:
        health_server = start_health_server()
    try:
        if not owner:
            owner = capture_owner()
        lock_to_owner(owner)
    except Exception as exc:
        print(f"[telegram-capture] ERROR {type(exc).__name__}: {exc}", flush=True)
    finally:
        if health_server is not None:
            health_server.shutdown()
            health_server.server_close()
    os.execv("/usr/bin/tini", ["/usr/bin/tini", "-g", "--", "/app/start.sh"])
