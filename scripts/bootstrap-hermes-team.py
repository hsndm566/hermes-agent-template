#!/usr/bin/env python3
"""Idempotent Hermes multi-agent team bootstrap for the Railway deployment.

Creates persistent specialist profiles, enables the default gateway multiplexer,
marks the install as Bot-Mode-managed, and optionally wires one Telegram token
per specialist from Railway variables. Secrets are never logged.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path

import yaml

ROOT = Path(os.environ.get("HERMES_HOME", "/data/.hermes"))
PROFILES = ROOT / "profiles"
STATUS_PATH = ROOT / "team" / "status.json"

TEAM = {
    "marketing": {
        "title": "Marketing",
        "description": "Campaigns, content strategy, SEO, social media, positioning, and growth research.",
        "telegram_env": "HERMES_TEAM_MARKETING_TELEGRAM_BOT_TOKEN",
        "toolsets": ["web", "browser", "skills"],
        "soul": """You are the Marketing Agent in a hub-and-spoke team.

Handle campaigns, content strategy, SEO, social media, market research, positioning, and growth experiments. Execute assigned work fully. State assumptions. Return concrete deliverables and concise rationale. When a task originates from the Coordinator or another team Bot, report the result back to that sender. Do not pretend that an action, campaign, publication, or external change happened unless you verified it.
""",
    },
    "auditor": {
        "title": "Auditor",
        "description": "Independent verification, process review, compliance checks, risk identification, and evidence-based QA.",
        "telegram_env": "HERMES_TEAM_AUDITOR_TELEGRAM_BOT_TOKEN",
        "toolsets": ["file", "web", "skills"],
        "soul": """You are the Auditor Agent in a hub-and-spoke team.

Independently verify claims, processes, configurations, evidence, and outputs. Be skeptical. Look for skipped steps, contradictions, hidden failure modes, stale data, and unverified assumptions. Separate observed facts from inference. Report findings with severity levels Critical, High, Medium, Low, and Passed. When a task originates from the Coordinator or another team Bot, report the result back to that sender. Never approve work merely because another agent says it succeeded.
""",
    },
    "cfo": {
        "title": "CFO",
        "description": "Budgeting, forecasting, unit economics, cost analysis, financial models, and commercial tradeoffs.",
        "telegram_env": "HERMES_TEAM_CFO_TELEGRAM_BOT_TOKEN",
        "toolsets": ["file", "web", "skills"],
        "soul": """You are the CFO Agent in a hub-and-spoke team.

Handle budgeting, forecasting, unit economics, pricing, cost analysis, financial models, and commercial tradeoffs. Show numbers, assumptions, formulas, scenarios, and uncertainty. Distinguish measured data from estimates. When a task originates from the Coordinator or another team Bot, report the result back to that sender. Do not fabricate financial data or claim a transaction occurred without evidence.
""",
    },
}

COORDINATOR_BLOCK = """
<!-- HERMES_MULTI_AGENT_COORDINATOR_V1 -->
## Multi-agent Coordinator role

You are the Coordinator for a hub-and-spoke team with persistent specialist profiles named marketing, auditor, and cfo. Receive the human's task, decide whether specialist work is useful, decompose the work, and consolidate the evidence into one answer.

Use native Hermes delegation for immediate parallel specialist work from ordinary Telegram conversations. Give each delegated child a precise role matching Marketing, Auditor, or CFO. For persistent Bot-Mode conversations, use the teammate roster and message_agent when it is available. Do not claim a specialist completed work unless its result actually returned. Use the Auditor to challenge high-impact or completion claims before presenting them as verified. Keep the human in control of consequential external actions.
<!-- /HERMES_MULTI_AGENT_COORDINATOR_V1 -->
""".lstrip()


def load_yaml(path: Path) -> dict:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    tmp.replace(path)


def read_env(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return out
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        out[key.strip()] = value.strip().strip('"').strip("'")
    return out


def write_env(path: Path, values: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"{k}={v}" for k, v in sorted(values.items()) if v]
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    tmp.replace(path)


def profile_exists(name: str) -> bool:
    p = PROFILES / name
    return p.is_dir() and any((p / marker).exists() for marker in (
        "config.yaml", ".env", "SOUL.md", "profile.yaml", "auth.json", "state.db"
    ))


def run(cmd: list[str], timeout: int = 90) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["HOME"] = "/data"
    env["HERMES_HOME"] = str(ROOT)
    return subprocess.run(
        cmd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
        timeout=timeout,
        check=False,
    )


def ensure_profile(name: str, spec: dict) -> bool:
    if profile_exists(name):
        return True
    result = run([
        "hermes", "profile", "create", name,
        "--clone-from", "default",
    ])
    if result.returncode != 0 or not profile_exists(name):
        tail = " | ".join((result.stdout or "").splitlines()[-4:])
        print(f"[team] profile create failed name={name} rc={result.returncode} detail={tail[:600]}", flush=True)
        return False
    print(f"[team] created persistent profile={name}", flush=True)
    return True


def ensure_bot_metadata(home: Path, *, title: str, description: str) -> None:
    path = home / "profile.yaml"
    data = load_yaml(path)
    data["display_name"] = title
    data["description"] = description
    ui_meta = data.get("ui_meta")
    if not isinstance(ui_meta, dict):
        ui_meta = {}
    bot_meta = ui_meta.get("hermes-bots")
    if not isinstance(bot_meta, dict):
        bot_meta = {}
    bot_meta.setdefault("title", title)
    bot_meta.setdefault("description", description)
    ui_meta["hermes-bots"] = bot_meta
    data["ui_meta"] = ui_meta
    write_yaml(path, data)


def ensure_config(home: Path, *, toolsets: list[str] | None = None, token_present: bool = False) -> None:
    path = home / "config.yaml"
    data = load_yaml(path)

    agent = data.get("agent")
    if not isinstance(agent, dict):
        agent = {}
    agent["bot_mode_protocol"] = True
    data["agent"] = agent

    if home == ROOT:
        gateway = data.get("gateway")
        if not isinstance(gateway, dict):
            gateway = {}
        gateway["multiplex_profiles"] = True
        data["gateway"] = gateway
    else:
        gateway = data.get("gateway")
        if isinstance(gateway, dict):
            gateway.pop("multiplex_profiles", None)
            gateway.pop("standalone", None)
            gateway.pop("profile_routes", None)
            if gateway:
                data["gateway"] = gateway
            else:
                data.pop("gateway", None)

    if toolsets:
        pts = data.get("platform_toolsets")
        if not isinstance(pts, dict):
            pts = {}
        pts["cli"] = list(toolsets)
        pts["telegram"] = list(toolsets)
        data["platform_toolsets"] = pts

    platforms = data.get("platforms")
    if not isinstance(platforms, dict):
        platforms = {}
    if token_present:
        tg = platforms.get("telegram")
        if not isinstance(tg, dict):
            tg = {}
        tg["enabled"] = True
        platforms["telegram"] = tg
    else:
        platforms.pop("telegram", None)
    if platforms:
        data["platforms"] = platforms
    else:
        data.pop("platforms", None)

    write_yaml(path, data)


def ensure_specialist_env(home: Path, token: str) -> None:
    env_path = home / ".env"
    data = read_env(env_path)
    for key in (
        "TELEGRAM_BOT_TOKEN", "TELEGRAM_ALLOWED_USERS", "TELEGRAM_ALLOW_ALL_USERS",
        "TELEGRAM_AUTO_APPROVE_FIRST", "TELEGRAM_CAPTURE_CODE", "TELEGRAM_CAPTURE_WEBHOOK_URL",
    ):
        data.pop(key, None)

    if token:
        data["TELEGRAM_BOT_TOKEN"] = token
        root_env = read_env(ROOT / ".env")
        for key in ("TELEGRAM_ALLOWED_USERS", "TELEGRAM_ALLOW_ALL_USERS"):
            if root_env.get(key):
                data[key] = root_env[key]
    write_env(env_path, data)


def copy_owner_telegram_approval(home: Path) -> None:
    candidates = [
        ROOT / "platforms" / "pairing" / "telegram-approved.json",
        ROOT / "pairing" / "telegram-approved.json",
    ]
    source = next((p for p in candidates if p.is_file() and p.stat().st_size > 2), None)
    if source is None:
        return
    dest_dir = home / "platforms" / "pairing"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / "telegram-approved.json"
    if not dest.exists() or dest.stat().st_size <= 2:
        shutil.copy2(source, dest)
        try:
            os.chmod(dest, 0o600)
        except OSError:
            pass
        print(f"[team] copied existing owner Telegram approval into profile={home.name}", flush=True)


def append_coordinator_role() -> None:
    path = ROOT / "SOUL.md"
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    if "HERMES_MULTI_AGENT_COORDINATOR_V1" not in existing:
        sep = "" if not existing else ("\n" if existing.endswith("\n") else "\n\n")
        path.write_text(existing + sep + COORDINATOR_BLOCK, encoding="utf-8")
        print("[team] coordinator role appended to default SOUL.md", flush=True)


def configure() -> int:
    PROFILES.mkdir(parents=True, exist_ok=True)
    (ROOT / "team").mkdir(parents=True, exist_ok=True)

    ensure_bot_metadata(ROOT, title="Coordinator", description="Receives human tasks, delegates specialist work, verifies completion, and consolidates results.")
    ensure_config(ROOT)
    append_coordinator_role()

    status: dict[str, object] = {
        "configured": True,
        "multiplex_profiles": True,
        "coordinator": "default",
        "profiles": {},
        "local_stt": "whisper.cpp",
    }

    for name, spec in TEAM.items():
        ok = ensure_profile(name, spec)
        token = os.getenv(spec["telegram_env"], "").strip()
        entry = {
            "profile_ready": ok,
            "telegram_token_configured": bool(token),
            "bot_mode_marked": False,
        }
        if ok:
            home = PROFILES / name
            (home / "SOUL.md").write_text(spec["soul"], encoding="utf-8")
            ensure_bot_metadata(home, title=spec["title"], description=spec["description"])
            ensure_specialist_env(home, token)
            ensure_config(home, toolsets=spec["toolsets"], token_present=bool(token))
            if token:
                copy_owner_telegram_approval(home)
            entry["bot_mode_marked"] = True
        status["profiles"][name] = entry
        print(
            f"[team] profile={name} ready={ok} telegram={'configured' if token else 'awaiting-token'}",
            flush=True,
        )

    STATUS_PATH.write_text(json.dumps(status, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("[team] native Hermes multiplexer enabled; specialist profiles configured", flush=True)
    return 0 if all(v["profile_ready"] for v in status["profiles"].values()) else 1


def init_bot_chats() -> int:
    names = ["default", *TEAM.keys()]
    failures: list[str] = []
    for name in names:
        home = ROOT if name == "default" else PROFILES / name
        marker = home / ".team_bot_chat_initialized"
        if marker.exists():
            continue
        prompt = (
            "Initialize this profile's canonical Bot Chat for the multi-agent team. "
            "Do not perform external actions. Reply with exactly READY."
        )
        result = run([
            "hermes", "-p", name, "chat", "--in", "/data", "-c", "Bot Chat",
            "--create-if-missing", "-Q", "-q", prompt,
        ], timeout=180)
        if result.returncode == 0:
            marker.write_text("ready\n", encoding="utf-8")
            print(f"[team] canonical Bot Chat initialized profile={name}", flush=True)
        else:
            failures.append(name)
            tail = " | ".join((result.stdout or "").splitlines()[-4:])
            print(f"[team] Bot Chat init deferred profile={name} rc={result.returncode} detail={tail[:600]}", flush=True)

    try:
        status = json.loads(STATUS_PATH.read_text(encoding="utf-8"))
    except Exception:
        status = {}
    status["bot_chats_initialized"] = {name: (ROOT if name == "default" else PROFILES / name).joinpath(".team_bot_chat_initialized").exists() for name in names}
    status["bot_chat_failures"] = failures
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATUS_PATH.write_text(json.dumps(status, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if not failures else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("configure", "init-chats"))
    args = parser.parse_args()
    if args.mode == "configure":
        return configure()
    return init_bot_chats()


if __name__ == "__main__":
    raise SystemExit(main())
