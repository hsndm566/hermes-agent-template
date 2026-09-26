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
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import yaml

HOME = Path(os.environ.get("HERMES_HOME", "/data/.hermes"))
OWNER_FILE = HOME / "telegram_owner.json"
ROUTES_FILE = HOME / "telegram_profile_routes.json"
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

    allowed = os.getenv("TELEGRAM_ALLOWED_USERS", "").strip()
    ids = [part for part in re.split(r"[\\s,;]+", allowed) if part]
    ids = [part for part in ids if part.isdigit() and int(part) > 0]
    if len(ids) == 1:
        return ids[0]
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
        log("TELEGRAM_BOT_TOKEN missing; topic setup deferred")
        return 2

    chat_id = resolve_chat_id()
    if not chat_id:
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

    created: list[str] = []
    for topic_name, _profile in TOPICS:
        if topic_name in known:
            continue
        try:
            result = telegram_api(token, "createForumTopic", {"chat_id": chat_id, "name": topic_name})
        except RuntimeError as exc:
            message = str(exc)
            if "TOPIC_NAME_DUPLICATE" in message.upper() or "ALREADY" in message.upper():
                log(
                    f"topic '{topic_name}' already exists but Telegram exposes no list-topics API; "
                    "preserve the prior mapping or send a message in that topic so Hermes can map it"
                )
            else:
                log(message)
            return 4

        if not isinstance(result, dict):
            log(f"Telegram createForumTopic returned no object for '{topic_name}'")
            return 5
        tid = str(result.get("message_thread_id") or "").strip()
        if not tid.isdigit():
            log(f"Telegram createForumTopic returned no thread id for '{topic_name}'")
            return 6
        known[topic_name] = tid
        created.append(topic_name)

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
            log(f"missing thread id after setup: {topic_name}")
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

    log(
        "READY "
        + " ".join(f"{name}={known[name]}" for name, _ in TOPICS)
        + (f" created={','.join(created)}" if created else " reused=all")
    )

    print(route_json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
