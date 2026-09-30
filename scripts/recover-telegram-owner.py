#!/usr/bin/env python3
"""Recover the single Telegram DM owner before Hermes starts polling.

This is intentionally DM-only. Telegram forum topics require a forum-enabled
supergroup and are not used for personal-bot owner recovery.

Safety:
- never prints or persists TELEGRAM_BOT_TOKEN;
- prefers existing approved owner / allowlist;
- if recovery is needed, reads pending Bot API updates without an offset so
  they are not acknowledged;
- accepts only one unique private, non-bot sender; otherwise refuses to guess;
- persists the owner into Hermes pairing state and TELEGRAM_ALLOWED_USERS.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import yaml

HOME = Path(os.environ.get("HERMES_HOME", "/data/.hermes"))
ENV_FILE = HOME / ".env"
OWNER_FILE = HOME / "telegram_owner.json"
CONFIG_FILE = HOME / "config.yaml"
PAIRING_DIR = HOME / "platforms" / "pairing"
APPROVED_FILE = PAIRING_DIR / "telegram-approved.json"
MARKER = HOME / ".telegram_first_user_lock_done"


def log(message: str) -> None:
    print(f"[telegram-owner] {message}", flush=True)


def read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def atomic_text(path: Path, text: str, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    try:
        os.chmod(tmp, mode)
    except OSError:
        pass
    tmp.replace(path)


def write_env_value(key: str, value: str) -> None:
    try:
        lines = ENV_FILE.read_text(encoding="utf-8").splitlines()
    except OSError:
        lines = []
    lines = [line for line in lines if not line.startswith(f"{key}=")]
    lines.append(f"{key}={value}")
    atomic_text(ENV_FILE, "\n".join(lines) + "\n")


def existing_owner() -> str:
    explicit = os.environ.get("TELEGRAM_OWNER_CHAT_ID", "").strip()
    if explicit.isdigit() and int(explicit) > 0:
        return explicit

    owner = read_json(OWNER_FILE)
    candidate = str(owner.get("chat_id") or owner.get("user_id") or "").strip()
    if candidate.isdigit() and int(candidate) > 0:
        return candidate

    approved = read_json(APPROVED_FILE)
    candidates: set[str] = set()
    for key, value in approved.items():
        uid = str((value or {}).get("user_id") if isinstance(value, dict) else key).strip()
        if not uid:
            uid = str(key).strip()
        if uid.isdigit() and int(uid) > 0:
            candidates.add(uid)
    if len(candidates) == 1:
        return next(iter(candidates))

    allowed_values = [os.environ.get("TELEGRAM_ALLOWED_USERS", "").strip()]
    try:
        for raw in ENV_FILE.read_text(encoding="utf-8").splitlines():
            if raw.startswith("TELEGRAM_ALLOWED_USERS="):
                allowed_values.append(raw.split("=", 1)[1].strip().strip('"').strip("'"))
    except OSError:
        pass
    allowed: set[str] = set()
    for raw in allowed_values:
        for part in re.split(r"[\s,;]+", raw):
            if part.isdigit() and int(part) > 0:
                allowed.add(part)
    if len(allowed) == 1:
        return next(iter(allowed))

    # /sethome persists the owner's private chat in the gateway config.  This
    # is a durable, user-selected identity and is safe to reuse for the
    # private allowlist after a restart.  Restrict this fallback to positive
    # numeric IDs so a group/channel cannot silently become the DM owner.
    try:
        config = yaml.safe_load(CONFIG_FILE.read_text(encoding="utf-8")) or {}
    except Exception:
        config = {}
    for telegram in (
        (config.get("platforms", {}) if isinstance(config, dict) else {}).get("telegram"),
        (config.get("gateway", {}).get("platforms", {}) if isinstance(config, dict) and isinstance(config.get("gateway"), dict) else {}).get("telegram"),
    ):
        home = telegram.get("home_channel") if isinstance(telegram, dict) else None
        chat_id = home.get("chat_id") if isinstance(home, dict) else None
        candidate = str(chat_id or "").strip()
        if candidate.isdigit() and int(candidate) > 0:
            return candidate
    return ""


def telegram_api(token: str, method: str, params: dict) -> object:
    url = f"https://api.telegram.org/bot{token}/{method}"
    req = urllib.request.Request(
        url,
        data=urllib.parse.urlencode(params).encode("utf-8"),
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        try:
            payload = json.loads(exc.read().decode("utf-8", errors="replace"))
            detail = str(payload.get("description") or f"HTTP {exc.code}")
        except Exception:
            detail = f"HTTP {exc.code}"
        raise RuntimeError(detail) from None
    except Exception as exc:
        raise RuntimeError(type(exc).__name__) from None
    if not isinstance(payload, dict) or not payload.get("ok"):
        raise RuntimeError(str(payload.get("description") if isinstance(payload, dict) else "unknown"))
    return payload.get("result")


def pending_private_owner(token: str) -> str:
    updates = telegram_api(
        token,
        "getUpdates",
        {
            "timeout": "0",
            "limit": "100",
            "allowed_updates": json.dumps(
                ["message", "edited_message", "business_message", "edited_business_message"]
            ),
        },
    )
    candidates: set[str] = set()
    for update in updates if isinstance(updates, list) else []:
        if not isinstance(update, dict):
            continue
        msg = next(
            (
                update.get(key)
                for key in ("message", "edited_message", "business_message", "edited_business_message")
                if isinstance(update.get(key), dict)
            ),
            None,
        )
        if not isinstance(msg, dict):
            continue
        chat = msg.get("chat") if isinstance(msg.get("chat"), dict) else {}
        sender = msg.get("from") if isinstance(msg.get("from"), dict) else {}
        if chat.get("type") != "private" or sender.get("is_bot") is True:
            continue
        uid = str(sender.get("id") or chat.get("id") or "").strip()
        if uid.isdigit() and int(uid) > 0:
            candidates.add(uid)

    if len(candidates) == 1:
        return next(iter(candidates))
    if len(candidates) > 1:
        log("multiple private Telegram users are pending; refusing to guess owner")
    return ""


def persist_owner(uid: str, source: str) -> None:
    PAIRING_DIR.mkdir(parents=True, exist_ok=True)
    approved = read_json(APPROVED_FILE)
    approved = {
        uid: {
            "user_id": uid,
            "user_name": "",
            "approved_at": time.time(),
        }
    }
    atomic_text(APPROVED_FILE, json.dumps(approved, indent=2, sort_keys=True) + "\n")
    atomic_text(
        OWNER_FILE,
        json.dumps(
            {
                "user_id": uid,
                "chat_id": uid,
                "captured_at": int(time.time()),
                "source": source,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
    )
    atomic_text(MARKER, "locked\n")
    write_env_value("TELEGRAM_ALLOWED_USERS", uid)

    # Lock the native Telegram adapter to this owner. This is deliberately
    # separate from forum-topic/profile routing.
    try:
        data = yaml.safe_load(CONFIG_FILE.read_text(encoding="utf-8")) or {}
    except Exception:
        data = {}
    if not isinstance(data, dict):
        data = {}
    gateway = data.setdefault("gateway", {})
    if not isinstance(gateway, dict):
        gateway = {}
        data["gateway"] = gateway
    platforms = gateway.setdefault("platforms", {})
    if not isinstance(platforms, dict):
        platforms = {}
        gateway["platforms"] = platforms
    telegram = platforms.setdefault("telegram", {})
    if not isinstance(telegram, dict):
        telegram = {}
        platforms["telegram"] = telegram
    telegram["enabled"] = True
    # Keep the owner's private DM as Hermes' home channel across restarts.
    # `/sethome` writes this gateway setting, but a fresh config bootstrap can
    # recreate the Telegram block before the gateway starts. Reapply it only
    # for the already-persisted single owner; never widen access to other users.
    home = telegram.get("home_channel")
    if not isinstance(home, dict) or str(home.get("chat_id") or "").strip() != uid:
        telegram["home_channel"] = {
            "platform": "telegram",
            "chat_id": uid,
        }
    extra = telegram.setdefault("extra", {})
    if not isinstance(extra, dict):
        extra = {}
        telegram["extra"] = extra
    extra["dm_policy"] = "allowlist"
    atomic_text(CONFIG_FILE, yaml.safe_dump(data, sort_keys=False))


def main() -> int:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        log("bot token missing; recovery skipped")
        return 0

    uid = existing_owner()
    if uid:
        persist_owner(uid, "existing-owner")
        log("single Telegram owner is persisted")
        return 0

    try:
        uid = pending_private_owner(token)
    except RuntimeError as exc:
        log(f"pending-update recovery unavailable: {exc}")
        return 0

    if not uid:
        log("no unique pending private owner found; leaving pairing mode unchanged")
        return 0

    persist_owner(uid, "pending-update-bootstrap")
    log("recovered and persisted one Telegram DM owner")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
