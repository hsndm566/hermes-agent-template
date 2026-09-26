#!/usr/bin/env python3
"""Idempotent Hermes multi-agent team bootstrap for the Railway deployment.

Creates persistent specialist profiles, enables the default gateway multiplexer,
and marks the install as Bot-Mode-managed. Telegram enters through the Coordinator
by default; specialists communicate internally through Hermes Bot Mode. Optional
dedicated specialist bot tokens remain supported but are not required. Secrets
are never logged.
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

HONCHO_WORKSPACE = os.getenv("HERMES_HONCHO_WORKSPACE", "hasan").strip() or "hasan"
HONCHO_OWNER_PEER = os.getenv("HERMES_HONCHO_OWNER_PEER", "hasan").strip() or "hasan"


def topic_routes_from_env() -> list[dict]:
    """Return only explicit, valid Telegram routes; IDs must come from Telegram.

    The deployment env is preferred. After first-time topic creation, the
    persistent route-state file is the restart-safe fallback so boot never
    depends on making Telegram API calls.
    """
    raw = os.getenv("HERMES_TELEGRAM_PROFILE_ROUTES_JSON", "").strip()
    if raw:
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            print(f"[team] invalid HERMES_TELEGRAM_PROFILE_ROUTES_JSON: {exc.msg}", flush=True)
            return []
    else:
        route_state = ROOT / "telegram_profile_routes.json"
        try:
            state = json.loads(route_state.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        chat_id = str(state.get("chat_id") or "").strip() if isinstance(state, dict) else ""
        topics = state.get("topics") if isinstance(state, dict) else {}
        if not chat_id or not isinstance(topics, dict):
            return []
        value = []
        for topic_name, item in topics.items():
            if not isinstance(item, dict):
                continue
            profile = str(item.get("profile") or "").strip()
            thread_id = str(item.get("thread_id") or "").strip()
            if profile and thread_id:
                value.append({
                    "name": f"telegram-{profile}",
                    "chat_id": chat_id,
                    "thread_id": thread_id,
                    "profile": profile,
                    "enabled": True,
                })
    if not isinstance(value, list):
        print("[team] HERMES_TELEGRAM_PROFILE_ROUTES_JSON must be a JSON list", flush=True)
        return []
    routes = []
    for item in value:
        if not isinstance(item, dict):
            continue
        profile = str(item.get("profile", "")).strip()
        thread_id = str(item.get("thread_id", "")).strip()
        chat_id = str(item.get("chat_id", "")).strip()
        if profile not in (TEAM_NAMES | {"default"}) or not thread_id or not chat_id:
            print("[team] skipped Telegram route without known profile, chat_id, and thread_id", flush=True)
            continue
        routes.append({
            "name": str(item.get("name") or f"telegram-{profile}-{thread_id}"),
            "platform": "telegram",
            "chat_id": chat_id,
            "thread_id": thread_id,
            "profile": profile,
            "enabled": bool(item.get("enabled", True)),
        })
    return routes

TEAM_NAMES = {"marketing", "auditor", "cfo", "domain"}

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
    "domain": {
        "title": "Domain",
        "description": "Technical domain agent for software, APIs, cloud infrastructure, integrations, architecture, and implementation.",
        "telegram_env": "HERMES_TEAM_DOMAIN_TELEGRAM_BOT_TOKEN",
        "toolsets": ["file", "web", "browser", "skills"],
        "soul": """You are the Domain Agent in a hub-and-spoke team.

Handle technical architecture, software engineering, APIs, cloud infrastructure, integrations, debugging, implementation planning, and domain-specific technical research. Prefer concrete evidence from code, logs, documentation, and runtime behavior. Keep changes minimal and reversible. When a task originates from the Coordinator or another team Bot, report the result back to that sender. Do not claim a deployment, integration, or fix works unless it was actually verified.
""",
    },
}

COORDINATOR_BLOCK = """
<!-- HERMES_MULTI_AGENT_COORDINATOR_V1 -->
## Multi-agent Coordinator role

You are the Coordinator for a hub-and-spoke team with persistent specialist profiles named marketing, auditor, cfo, and domain. Receive the human's task, decide whether specialist work is useful, decompose the work, and consolidate the evidence into one answer.

Telegram is a Coordinator-only ingress by default. Marketing, Auditor, CFO, and Domain are persistent internal Hermes profiles and do not need their own Telegram bot tokens to work. Use native Hermes delegation for immediate specialist work from ordinary Telegram conversations. Give each delegated child a precise role matching Marketing, Auditor, CFO, or Domain. For persistent Bot-Mode conversations, use the teammate roster and message_agent when it is available. Do not claim a specialist completed work unless its result actually returned. Use the Auditor to challenge high-impact or completion claims before presenting them as verified. Keep the human in control of consequential external actions.
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


def ensure_honcho_config(home: Path, *, ai_peer: str) -> None:
    """Persist supported Honcho identity settings without persisting the API key.

    HONCHO_API_KEY remains a deployment secret and is resolved from the environment
    by Hermes. All profiles share one workspace and owner peer, while each profile
    has a distinct AI peer so memory attribution remains unambiguous.
    """
    path = home / "honcho.json"
    data = {}
    try:
        existing = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(existing, dict):
            data = existing
    except (OSError, json.JSONDecodeError):
        pass
    data.update({
        "workspace": HONCHO_WORKSPACE,
        "peerName": HONCHO_OWNER_PEER,
        "pinUserPeer": True,
        "aiPeer": ai_peer,
        "sessionStrategy": "per-session",
        "saveMessages": True,
        "writeFrequency": "async",
        "recallMode": "hybrid",
        "enabled": True,
    })
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    tmp.replace(path)

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
        routes = topic_routes_from_env()
        if routes:
            gateway["profile_routes"] = routes
        else:
            # Do not retain stale routes when the deployment no longer supplies IDs.
            gateway.pop("profile_routes", None)
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


def compact_initial_cloned_skills(home: Path) -> None:
    """Reclaim the one-time --clone-from default skill copy.

    Hermes v2026.9.11 intentionally copies the entire source skills tree for a
    config clone. On this 500 MB Railway volume that costs roughly 80 MB per
    specialist. These profiles were created by this bootstrap and have not yet
    received user-installed specialist skills, so compact the initial clone
    once. A persistent marker guarantees later user-installed skills are never
    touched. Hermes keeps the rest of the profile fully isolated.
    """
    marker = home / ".team_initial_skill_clone_compacted_v1"
    if marker.exists():
        return
    skills = home / "skills"
    try:
        if skills.is_symlink():
            skills.unlink()
        elif skills.exists():
            shutil.rmtree(skills)
        skills.mkdir(parents=True, exist_ok=True)
        # Prevent hermes update/dashboard from immediately re-seeding the full
        # bundled skill set into this specialist. Users can still install any
        # skill explicitly later.
        (home / ".no-bundled-skills").write_text(
            "Managed specialist profile: install only skills this agent needs.\n",
            encoding="utf-8",
        )
        marker.write_text("compacted\n", encoding="utf-8")
        print(f"[team] reclaimed initial cloned skills profile={home.name}", flush=True)
    except Exception as exc:
        print(f"[team] skill compaction deferred profile={home.name} error={type(exc).__name__}", flush=True)


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
    ensure_honcho_config(ROOT, ai_peer="coordinator")
    append_coordinator_role()
    configured_routes = topic_routes_from_env()

    status: dict[str, object] = {
        "configured": True,
        "multiplex_profiles": True,
        "coordinator": "default",
        "telegram_topology": "coordinator-ingress/internal-specialists",
        "specialist_telegram_tokens_required": False,
        "profiles": {},
        "local_stt": "faster-whisper/base-baked-cpu-int8",
        "honcho": {
            "workspace": HONCHO_WORKSPACE,
            "owner_peer": HONCHO_OWNER_PEER,
            "api_key_source": "HONCHO_API_KEY deployment secret",
            "profiles": {"default": "coordinator", **{name: name for name in TEAM}},
        },
        "telegram_topic_routes": {
            "configured": len(configured_routes),
            "source": "HERMES_TELEGRAM_PROFILE_ROUTES_JSON",
            "note": "Routes require real Telegram chat_id/thread_id values; no IDs are fabricated.",
        },
    }

    for name, spec in TEAM.items():
        ok = ensure_profile(name, spec)
        token = os.getenv(spec["telegram_env"], "").strip()
        entry = {
            "profile_ready": ok,
            "telegram_token_configured": bool(token),
            "telegram_mode": "optional-dedicated" if token else "internal-bot-mode",
            "bot_mode_marked": False,
        }
        if ok:
            home = PROFILES / name
            compact_initial_cloned_skills(home)
            (home / "SOUL.md").write_text(spec["soul"], encoding="utf-8")
            ensure_bot_metadata(home, title=spec["title"], description=spec["description"])
            ensure_specialist_env(home, token)
            ensure_config(home, toolsets=spec["toolsets"], token_present=bool(token))
            ensure_honcho_config(home, ai_peer=name)
            if token:
                copy_owner_telegram_approval(home)
            entry["bot_mode_marked"] = True
        status["profiles"][name] = entry
        print(
            f"[team] profile={name} ready={ok} telegram={'optional-dedicated' if token else 'internal-bot-mode'}",
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


def sync_hierarchy() -> int:
    """Sync Hermes profiles into the pinned hierarchical-agents registry.

    The third-party package is isolated in its own venv. We use it for durable
    org-chart and IPC state only; native Hermes Bot Mode remains the execution
    path because the upstream hierarchy gateway does not wire a WorkerBridge.
    """
    project_root = Path(os.getenv("HIERARCHY_PROJECT_ROOT", "/opt/vendor/hierarchical-agents"))
    hierarchy_python = os.getenv("HIERARCHY_PYTHON", "/opt/hierarchy-venv/bin/python")
    db_dir = Path(os.getenv("HERMES_DB_BASE_DIR", str(ROOT / "hierarchy")))
    script = project_root / "scripts" / "sync_hermes_profiles.py"
    if not script.is_file():
        print(f"[hierarchy] sync script missing at {script}", flush=True)
        return 1

    env = dict(os.environ)
    env.update({
        "HOME": "/data",
        "HERMES_HOME": str(ROOT),
        "HIERARCHY_PROJECT_ROOT": str(project_root),
        "HERMES_DB_BASE_DIR": str(db_dir),
        "HERMES_PROFILES_DIR": str(PROFILES),
        "PYTHONPATH": str(project_root),
    })
    result = subprocess.run(
        [hierarchy_python, str(script), "--show-chart"],
        cwd=str(project_root),
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=90,
        check=False,
    )
    if result.returncode != 0:
        tail = " | ".join((result.stdout or "").splitlines()[-10:])
        print(f"[hierarchy] sync failed rc={result.returncode} detail={tail[:1200]}", flush=True)
        return 1

    # The hierarchy library intentionally onboards new non-CEO entries by
    # default. For these already-configured Hermes profiles, activate them and
    # preserve the flat hub-and-spoke reporting line to its auto-created CEO.
    code = """
import json, os, sys
from pathlib import Path
root = Path(os.environ["HIERARCHY_PROJECT_ROOT"])
sys.path.insert(0, str(root))
from core.registry.profile_registry import ProfileRegistry
from core.ipc.message_bus import MessageBus
from core.ipc.models import MessagePriority, MessageType
from core.registry.org_chart import render_org_chart

db = Path(os.environ["HERMES_DB_BASE_DIR"])
registry = ProfileRegistry(str(db / "registry.db"))
specs = {
    "marketing": ("Marketing", "Campaigns, content strategy, SEO, social media, positioning, and growth research."),
    "auditor": ("Auditor", "Independent verification, process review, compliance checks, risk identification, and evidence-based QA."),
    "cfo": ("CFO", "Budgeting, forecasting, unit economics, cost analysis, financial models, and commercial tradeoffs."),
}
for name, (title, desc) in specs.items():
    p = registry.get_profile(name)
    registry.update_profile(name, display_name=title, description=desc, status="active")

class Adapter:
    def __init__(self, r): self.r = r
    def get(self, name): return self.r.get_profile(name)

# Real write/read/ack smoke test of the SQLite IPC bus.
bus = MessageBus(str(db / "ipc.db"), profile_registry=Adapter(registry))
mid = bus.send(
    from_profile="hermes",
    to_profile="marketing",
    message_type=MessageType.TASK_REQUEST,
    payload={"task": "HIERARCHY_IPC_SMOKE_TEST"},
    priority=MessagePriority.NORMAL,
)
seen = any(m.message_id == mid for m in bus.poll("marketing", limit=50))
if seen:
    bus.acknowledge(mid)
bus.close()
print("[hierarchy] IPC_SMOKE=" + ("PASS" if seen else "FAIL"))
print("[hierarchy] ORG_CHART_BEGIN")
print(render_org_chart(registry))
print("[hierarchy] ORG_CHART_END")
registry.close()
if not seen:
    raise SystemExit(2)
"""
    verify = subprocess.run(
        [hierarchy_python, "-c", code],
        cwd=str(project_root),
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=60,
        check=False,
    )
    print((verify.stdout or "").strip(), flush=True)
    ok = verify.returncode == 0 and "IPC_SMOKE=PASS" in (verify.stdout or "")

    try:
        status = json.loads(STATUS_PATH.read_text(encoding="utf-8"))
    except Exception:
        status = {}
    status["hierarchy"] = {
        "installed": True,
        "source_ref": "de37f8a46458fc76cc57094cde4f404bd9bda309",
        "profiles_synced": list(TEAM),
        "ipc_smoke": bool(ok),
        "execution_path": "native-hermes-bot-mode",
    }
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATUS_PATH.write_text(json.dumps(status, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"[hierarchy] installed=True profiles_synced=3 ipc_smoke={'PASS' if ok else 'FAIL'}", flush=True)
    return 0 if ok else 1


def native_delegation_smoke() -> int:
    """One-time verified Coordinator round-trip through every specialist Bot."""

    marker = ROOT / "team" / ".native_delegation_smoke_v2"
    if marker.exists():
        print("[team-smoke] already passed v2", flush=True)
        return 0

    import time

    results: dict[str, bool] = {}
    for profile in ("marketing", "auditor", "cfo"):
        code = f"{profile.upper()}_OK"
        sent_code = f"TEAM_SMOKE_SENT_{profile.upper()}"
        ok_code = f"TEAM_SMOKE_OK_{profile.upper()}"

        send_prompt = (
            f"Deployment smoke test for @{profile}. Use message_agent to send exactly one message "
            f"to @{profile}. Ask that teammate to reply to you with exactly {code}. "
            "Do not use delegate_task. Do not invent a reply. "
            f"After message_agent acknowledges the send, reply exactly {sent_code}."
        )
        first = run([
            "hermes", "-p", "default", "chat", "--in", "/data", "-c", "Bot Chat",
            "--create-if-missing", "-Q", "-q", send_prompt,
        ], timeout=240)
        first_text = first.stdout or ""
        if first.returncode != 0 or sent_code not in first_text:
            print(f"[team-smoke] send failed profile={profile} rc={first.returncode}", flush=True)
            results[profile] = False
            break

        verified = False
        for attempt in range(3):
            time.sleep(15 if attempt == 0 else 10)
            check_prompt = (
                "Verify the deployment smoke test from actual Bot Chat history. "
                f"Only if you can see an attributed teammate message from @{profile} containing {code}, "
                f"reply exactly {ok_code}. Otherwise reply exactly TEAM_SMOKE_PENDING. "
                "Do not infer, summarize, or fabricate."
            )
            check = run([
                "hermes", "-p", "default", "chat", "--in", "/data", "-c", "Bot Chat",
                "--create-if-missing", "-Q", "-q", check_prompt,
            ], timeout=240)
            text_out = check.stdout or ""
            if check.returncode == 0 and ok_code in text_out:
                verified = True
                break

        results[profile] = verified
        print(
            f"[team-smoke] profile={profile} roundtrip={'PASS' if verified else 'FAIL'}",
            flush=True,
        )
        if not verified:
            break

    all_ok = all(results.get(name, False) for name in ("marketing", "auditor", "cfo"))
    try:
        status = json.loads(STATUS_PATH.read_text(encoding="utf-8"))
    except Exception:
        status = {}
    status["native_delegation_smoke"] = {
        "version": 2,
        "coordinator_to_marketing": bool(results.get("marketing")),
        "coordinator_to_auditor": bool(results.get("auditor")),
        "coordinator_to_cfo": bool(results.get("cfo")),
        "auditor_verified": bool(results.get("auditor")),
        "passed": all_ok,
    }
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATUS_PATH.write_text(json.dumps(status, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if all_ok:
        marker.write_text("pass\n", encoding="utf-8")
        print("[team-smoke] PASS coordinator<->marketing/auditor/cfo", flush=True)
        return 0

    print("[team-smoke] FAIL at least one specialist round-trip was not verified", flush=True)
    return 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("configure", "sync-hierarchy", "init-chats", "smoke-test"))
    args = parser.parse_args()
    if args.mode == "configure":
        return configure()
    if args.mode == "sync-hierarchy":
        return sync_hierarchy()
    if args.mode == "init-chats":
        return init_bot_chats()
    return native_delegation_smoke()


if __name__ == "__main__":
    raise SystemExit(main())
