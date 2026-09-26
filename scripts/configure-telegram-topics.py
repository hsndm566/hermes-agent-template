#!/usr/bin/env python3
"""Create/persist Hasan's Telegram DM topics and Hermes profile routes.

Idempotent:
- reuses persisted thread IDs from /data/.hermes/telegram_profile_routes.json
  or config.yaml;
- creates only missing topics;
- never prints or persists TELEGRAM_BOT_TOKEN;
- writes HERMES_TELEGRAM_PROFILE_ROUTES_JSON into the persistent Hermes .env.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import yaml

HOME = Path(os.environ.get("HERMES_HOME", "/data/.hermes"))
OWNER_FILE = HOME / "telegram_owner.json"
ROUTES_FILE = HOME / "telegram_profile_routes.json"
STATUS_FILE = HOME / "telegram_topic_setup_status.json"
CONFIG_FILE = HOME / "config.yaml"
ENV_FILE = HOME / ".env"

TOPICS = [
    ("Main", "default"),
    ("Marketing", "marketing"),
    ("Auditor", "auditor"),
    ("CFO", "cfo"),
    ("Domain", "domain"),
]


def log(msg: str) -> None:
    print(f"[telegram-routes] {msg}", file=sys.stderr, flush=True)


def read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def read_yaml(path: Path) -> dict:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
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


def write_yaml(path: Path, value: dict) -> None:
    atomic_text(path, yaml.safe_dump(value, sort_keys=False))

def write_status(state: str, *, chat_id: str = "", topic: str = "", detail: str = "", known: dict[str, str] | None = None) -> None:
    payload = {
        "state": state,
        "chat_id": chat_id,
        "topic": topic,
        "detail": detail[:500],
        "known_topics": dict(known or {}),
    }
    atomic_text(STATUS_FILE, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def persist_partial(chat_id: str, known: dict[str, str]) -> None:
    topic_state: dict[str, dict[str, str]] = {}
    profile_for = dict(TOPICS)
    for name, tid in known.items():
        if name in profile_for and str(tid).isdigit():
            topic_state[name] = {"thread_id": str(tid), "profile": profile_for[name]}
    atomic_text(
        ROUTES_FILE,
        json.dumps({"chat_id": chat_id, "topics": topic_state}, indent=2, sort_keys=True) + "\n",
    )



def write_env_value(path: Path, key: str, value: str) -> None:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        lines = []
    lines = [line for line in lines if not line.startswith(f"{key}=")]
    lines.append(f"{key}={value}")
    atomic_text(path, "\n".join(lines) + "\n")


def resolve_chat_id() -> str:
    explicit = os.getenv("TELEGRAM_OWNER_CHAT_ID", "").strip()
    if explicit.isdigit() and int(explicit) > 0:
        return explicit

    owner = read_json(OWNER_FILE)
    candidate = str(owner.get("chat_id") or owner.get("user_id") or "").strip()
    if candidate.isdigit() and int(candidate) > 0:
        return candidate

    # Reuse Hermes' already-approved Telegram owner before touching Bot API
    # polling. Current Hermes stores approvals under platforms/pairing; older
    # deployments may still use the legacy pairing directory.
    for approved_path in (
        HOME / "platforms" / "pairing" / "telegram-approved.json",
        HOME / "pairing" / "telegram-approved.json",
    ):
        approved = read_json(approved_path)
        candidates: list[str] = []
        for key, value in approved.items():
            if isinstance(value, dict):
                uid = str(value.get("user_id") or key or "").strip()
            else:
                uid = str(key or "").strip()
            if uid.isdigit() and int(uid) > 0:
                candidates.append(uid)
        unique = sorted(set(candidates))
        if len(unique) == 1:
            log(f"resolved owner chat_id from Hermes approved pairing state ({approved_path.parent.name})")
            return unique[0]

    allowed_values = [os.getenv("TELEGRAM_ALLOWED_USERS", "").strip()]
    try:
        for raw in ENV_FILE.read_text(encoding="utf-8").splitlines():
            if raw.startswith("TELEGRAM_ALLOWED_USERS="):
                allowed_values.append(raw.split("=", 1)[1].strip().strip('"').strip("'"))
    except OSError:
        pass
    ids: list[str] = []
    for allowed in allowed_values:
        ids.extend(part for part in re.split(r"[\\s,;]+", allowed) if part)
    ids = [part for part in ids if part.isdigit() and int(part) > 0]
    unique_allowed = sorted(set(ids))
    if len(unique_allowed) == 1:
        log("resolved owner chat_id from TELEGRAM_ALLOWED_USERS")
        return unique_allowed[0]

    # Last local-only fallback: recover a single Telegram DM owner from Hermes'
    # persistent session DB. This reads state only; it does not call Telegram.
    db_path = HOME / "state.db"
    if db_path.exists():
        candidates: set[str] = set()
        try:
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=2)
            try:
                cols = {row[1] for row in conn.execute("PRAGMA table_info(sessions)")}
                wanted = [name for name in ("chat_id", "user_id", "session_key", "source") if name in cols]
                if wanted:
                    rows = conn.execute(f"SELECT {','.join(wanted)} FROM sessions").fetchall()
                    for row in rows:
                        item = dict(zip(wanted, row))
                        source = str(item.get("source") or "")
                        skey = str(item.get("session_key") or "")
                        if source != "telegram" and ":telegram:" not in skey:
                            continue
                        for key in ("chat_id", "user_id"):
                            value = str(item.get(key) or "").strip()
                            if value.isdigit() and int(value) > 0:
                                candidates.add(value)
                        match = re.search(r":telegram:dm:(\\d+)(?::|$)", skey)
                        if match:
                            candidates.add(match.group(1))
            finally:
                conn.close()
        except Exception as exc:
            log(f"state.db owner lookup skipped: {type(exc).__name__}")
        if len(candidates) == 1:
            value = next(iter(candidates))
            log("resolved owner chat_id from Hermes session state")
            return value

    return ""


def telegram_api(token: str, method: str, params: dict) -> object:
    url = f"https://api.telegram.org/bot{token}/{method}"
    body = urllib.parse.urlencode(params).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=25) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        try:
            payload = json.loads(exc.read().decode("utf-8", errors="replace"))
            description = str(payload.get("description") or f"HTTP {exc.code}")
        except Exception:
            description = f"HTTP {exc.code}"
        raise RuntimeError(f"Telegram {method} failed: {description}") from None
    except Exception as exc:
        raise RuntimeError(f"Telegram {method} failed: {type(exc).__name__}") from None

    if not isinstance(payload, dict) or not payload.get("ok"):
        description = str(payload.get("description") if isinstance(payload, dict) else "unknown error")
        raise RuntimeError(f"Telegram {method} failed: {description}")
    return payload.get("result")


def thread_ids_from_config(config: dict, chat_id: str) -> dict[str, str]:
    out: dict[str, str] = {}
    try:
        entries = config.get("platforms", {}).get("telegram", {}).get("extra", {}).get("dm_topics", [])
    except AttributeError:
        return out
    if not isinstance(entries, list):
        return out
    for entry in entries:
        if not isinstance(entry, dict) or str(entry.get("chat_id", "")) != chat_id:
            continue
        for topic in entry.get("topics", []) or []:
            if not isinstance(topic, dict):
                continue
            name = str(topic.get("name") or "").strip()
            tid = str(topic.get("thread_id") or "").strip()
            if name and tid.isdigit():
                out[name] = tid
    return out


def main() -> int:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        write_status("blocked", detail="TELEGRAM_BOT_TOKEN missing")
        log("TELEGRAM_BOT_TOKEN missing; topic setup deferred")
        return 2

    chat_id = resolve_chat_id()
    if not chat_id:
        write_status("blocked", detail="owner chat_id unavailable")
        log("owner chat_id unavailable; topic setup deferred")
        return 3

    config = read_yaml(CONFIG_FILE)
    persisted = read_json(ROUTES_FILE)
    known: dict[str, str] = {}

    persisted_chat = str(persisted.get("chat_id") or "").strip()
    if persisted_chat == chat_id:
        raw_topics = persisted.get("topics", {})
        if isinstance(raw_topics, dict):
            for name, item in raw_topics.items():
                if isinstance(item, dict):
                    tid = str(item.get("thread_id") or "").strip()
                else:
                    tid = str(item or "").strip()
                if tid.isdigit():
                    known[str(name)] = tid

    known.update({k: v for k, v in thread_ids_from_config(config, chat_id).items() if k not in known})

    persist_partial(chat_id, known)
    write_status("running", chat_id=chat_id, detail="starting topic reconciliation", known=known)

    created: list[str] = []
    for topic_name, _profile in TOPICS:
        if topic_name in known:
            continue
        try:
            result = telegram_api(token, "createForumTopic", {"chat_id": chat_id, "name": topic_name})
        except RuntimeError as exc:
            message = str(exc)
            if "TOPIC_NAME_DUPLICATE" in message.upper() or "ALREADY" in message.upper():
                detail = (
                    f"topic '{topic_name}' already exists but its thread_id is not in persistent state; "
                    "Telegram exposes no list-topics API"
                )
                write_status("duplicate_without_id", chat_id=chat_id, topic=topic_name, detail=detail, known=known)
                log(detail)
            else:
                write_status("telegram_error", chat_id=chat_id, topic=topic_name, detail=message, known=known)
                log(message)
            return 4

        if not isinstance(result, dict):
            detail = f"Telegram createForumTopic returned no object for '{topic_name}'"
            write_status("telegram_error", chat_id=chat_id, topic=topic_name, detail=detail, known=known)
            log(detail)
            return 5
        tid = str(result.get("message_thread_id") or "").strip()
        if not tid.isdigit():
            detail = f"Telegram createForumTopic returned no thread id for '{topic_name}'"
            write_status("telegram_error", chat_id=chat_id, topic=topic_name, detail=detail, known=known)
            log(detail)
            return 6
        known[topic_name] = tid
        created.append(topic_name)
        persist_partial(chat_id, known)
        write_status("running", chat_id=chat_id, topic=topic_name, detail="captured real thread_id", known=known)

        try:
            telegram_api(
                token,
                "sendMessage",
                {
                    "chat_id": chat_id,
                    "message_thread_id": tid,
                    "text": f"📌 {topic_name} is connected.",
                },
            )
        except RuntimeError as exc:
            log(f"seed message warning for '{topic_name}': {exc}")

    routes = []
    topic_state: dict[str, dict[str, str]] = {}
    dm_topics = []
    for topic_name, profile in TOPICS:
        tid = known.get(topic_name, "")
        if not tid:
            detail = f"missing thread id after setup: {topic_name}"
            write_status("incomplete", chat_id=chat_id, topic=topic_name, detail=detail, known=known)
            log(detail)
            return 7
        routes.append(
            {
                "name": f"telegram-{profile}",
                "chat_id": chat_id,
                "thread_id": tid,
                "profile": profile,
                "enabled": True,
            }
        )
        topic_state[topic_name] = {"thread_id": tid, "profile": profile}
        dm_topics.append({"name": topic_name, "thread_id": int(tid)})

    state = {"chat_id": chat_id, "topics": topic_state}
    atomic_text(ROUTES_FILE, json.dumps(state, indent=2, sort_keys=True) + "\n")

    platforms = config.setdefault("platforms", {})
    if not isinstance(platforms, dict):
        platforms = {}
        config["platforms"] = platforms
    telegram = platforms.setdefault("telegram", {})
    if not isinstance(telegram, dict):
        telegram = {}
        platforms["telegram"] = telegram
    telegram["enabled"] = True
    extra = telegram.setdefault("extra", {})
    if not isinstance(extra, dict):
        extra = {}
        telegram["extra"] = extra
    extra["dm_topics"] = [{"chat_id": int(chat_id), "topics": dm_topics}]

    gateway = config.setdefault("gateway", {})
    if not isinstance(gateway, dict):
        gateway = {}
        config["gateway"] = gateway
    gateway["multiplex_profiles"] = True
    gateway["profile_routes"] = [
        {
            "name": item["name"],
            "platform": "telegram",
            "chat_id": item["chat_id"],
            "thread_id": item["thread_id"],
            "profile": item["profile"],
            "enabled": True,
        }
        for item in routes
    ]
    write_yaml(CONFIG_FILE, config)

    route_json = json.dumps(routes, separators=(",", ":"), sort_keys=True)
    write_env_value(ENV_FILE, "HERMES_TELEGRAM_PROFILE_ROUTES_JSON", route_json)

    write_status("ready", chat_id=chat_id, detail="all five topics mapped", known=known)
    log(
        "READY "
        + " ".join(f"{name}={known[name]}" for name, _ in TOPICS)
        + (f" created={','.join(created)}" if created else " reused=all")
    )

    print(route_json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
