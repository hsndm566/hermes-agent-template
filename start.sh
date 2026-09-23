#!/bin/bash
set -e

# Mirror dashboard-ref-only's startup: create every directory hermes expects
# and seed a default config.yaml if the volume is empty. Without these,
# `hermes dashboard` endpoints that hit logs/, sessions/, cron/, etc. can fail
# with opaque errors even though no auth is actually involved.
# NOTE (hermes >= v2026.7.1): several dirs were consolidated and are now
# resolved via get_hermes_dir("<new>", "<old>"), which returns the NEW path
# unless the OLD one already has *content*. Seeding an empty legacy stub no
# longer "claims" it — hermes ignores empty stubs and writes to the new path
# (upstream #27602). So we seed the NEW paths: pairing -> platforms/pairing,
# image_cache -> cache/images, audio_cache -> cache/audio. A populated legacy
# dir from a pre-v2026.7.1 deploy still wins on both sides, so no migration is
# needed. server.py:_resolve_pairing_dir() mirrors this same rule for the
# admin panel's Users tab — keep the two in sync on future bumps.
mkdir -p /data/.hermes/cron /data/.hermes/sessions /data/.hermes/logs \
         /data/.hermes/memories /data/.hermes/skills /data/.hermes/platforms/pairing \
         /data/.hermes/hooks /data/.hermes/cache/images /data/.hermes/cache/audio \
         /data/.hermes/workspace /data/.hermes/skins /data/.hermes/plans \
         /data/.hermes/home

# Stamp the install method as "docker" so hermes treats this as an immutable
# container image, not a pip checkout. hermes's detect_install_method() reads
# $HERMES_HOME/.install_method FIRST (before any .git / pip fallback). Without
# this stamp the template falls through to "pip" — because the Dockerfile strips
# /opt/hermes-agent/.git — and the dashboard's "Update Hermes" button then runs
# a real `hermes update` (PyPI pip-upgrade) INSIDE the running container. That
# upgrade is ephemeral (reverts on the next redeploy) and can desync the Python
# package from the image's pre-built web_dist/ui-tui bundles. Stamping "docker"
# makes that button correctly refuse with "pull a fresh image / redeploy", which
# matches the real upgrade path here (bump HERMES_REF in Railway + redeploy).
# Written unconditionally each boot so it stays correct and self-heals.
printf 'docker\n' > /data/.hermes/.install_method

if [ ! -f /data/.hermes/config.yaml ] && [ -f /opt/hermes-agent/cli-config.yaml.example ]; then
  cp /opt/hermes-agent/cli-config.yaml.example /data/.hermes/config.yaml
fi

[ ! -f /data/.hermes/.env ] && touch /data/.hermes/.env

# Railway volume guard. This deployment has a 500 MB persistent volume, and
# Hermes can become partially functional when it is full (SQLite/log writes fail
# while network requests still succeed). Keep durable user state, credentials,
# sessions, skills and config; prune only disposable caches and rotated logs.
echo "[storage-guard] usage before cleanup:" >&2
du -sm /data/.hermes/* /data/.hermes/.[!.]* 2>/dev/null | sort -nr | head -30 >&2 || true

rm -rf /data/.hermes/cache/terminal/* \
       /data/.hermes/cache/audio/* \
       /data/.hermes/cache/images/* \
       /data/.hermes/cache/uv/* 2>/dev/null || true

# Old lazy-installed Python packages are reproducible and are the largest
# disposable class on a small persistent volume. Runtime packages now live in
# /tmp below, so remove the old persistent copy.
rm -rf /data/.hermes/lazy-packages 2>/dev/null || true

# Remove rotated log generations. Keep the live files, but cap each at 2 MiB so
# diagnostics survive without consuming the volume.
find /data/.hermes/logs -maxdepth 1 -type f \
  \( -name '*.log.[0-9]*' -o -name '*.log.*.gz' \) -delete 2>/dev/null || true
for f in /data/.hermes/logs/*.log; do
  [ -f "$f" ] || continue
  size="$(wc -c < "$f" 2>/dev/null || echo 0)"
  if [ "$size" -gt 2097152 ]; then
    tail -c 2097152 "$f" > "$f.trim" 2>/dev/null && mv "$f.trim" "$f" || rm -f "$f.trim"
  fi
done

echo "[storage-guard] cleanup complete; filesystem:" >&2
df -h /data >&2 || true

# One-time migration helper for a Railway variable that was accidentally created
# as "TELEGRAM BOT TOKEN" (with spaces). POSIX process environments can contain
# such a key even though normal shell variable syntax cannot reference it.
# If present, promote its value internally to the canonical TELEGRAM_BOT_TOKEN.
# The secret never gets printed.
legacy_telegram_token="$(printenv 'TELEGRAM BOT TOKEN' 2>/dev/null || true)"
if [ -n "$legacy_telegram_token" ]; then
  export TELEGRAM_BOT_TOKEN="$legacy_telegram_token"
  echo "[telegram-token-migrate] promoted legacy spaced variable to TELEGRAM_BOT_TOKEN" >&2
fi
unset legacy_telegram_token

# Railway injects service variables into the process environment, while the admin
# dashboard persists Hermes runtime settings in /data/.hermes/.env. Keep the
# Telegram authorization controls synchronized into the persistent runtime file
# so gateway policy survives restarts and redeploys.
sync_runtime_env_var() {
  local key="$1"
  local value="${!key:-}"
  [ -z "$value" ] && return 0

  local tmp
  tmp="$(mktemp)"
  grep -v "^${key}=" /data/.hermes/.env > "$tmp" || true
  printf '%s=%s\n' "$key" "$value" >> "$tmp"
  mv "$tmp" /data/.hermes/.env
}

sync_runtime_env_var LLM_MODEL
sync_runtime_env_var GROQ_API_KEY
sync_runtime_env_var OPENROUTER_API_KEY
sync_runtime_env_var DEEPSEEK_API_KEY
sync_runtime_env_var OLLAMA_API_KEY
sync_runtime_env_var TELEGRAM_BOT_TOKEN
sync_runtime_env_var TELEGRAM_ALLOW_ALL_USERS
sync_runtime_env_var TELEGRAM_ALLOWED_USERS
sync_runtime_env_var GATEWAY_ALLOW_ALL_USERS

# Multi-provider model stack.
# Priority: Ollama Cloud Gemma 4 main -> Groq GPT-OSS 120B -> DeepSeek V4 Pro
# -> OpenRouter Auto. Each provider is only enabled when its own credential is
# present. Model aliases let Telegram switch providers instantly with /model.
python - <<'PY' || true
import os
from pathlib import Path
import yaml

home = Path("/data/.hermes")
env_path = home / ".env"
cfg_path = home / "config.yaml"

def read_env(path):
    out = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return out
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out

def write_env_value(path, key, value):
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        lines = []
    lines = [line for line in lines if not line.startswith(f"{key}=")]
    lines.append(f"{key}={value}")
    tmp = path.with_suffix(".tmp")
    tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    tmp.replace(path)

env = read_env(env_path)
for key in ("OLLAMA_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY", "DEEPSEEK_API_KEY"):
    val = os.getenv(key, "").strip()
    if val:
        env[key] = val

ollama_ready = bool(env.get("OLLAMA_API_KEY"))
groq_ready = bool(env.get("GROQ_API_KEY"))
openrouter_ready = bool(env.get("OPENROUTER_API_KEY"))
deepseek_ready = bool(env.get("DEEPSEEK_API_KEY"))

try:
    data = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
except Exception:
    data = {}
if not isinstance(data, dict):
    data = {}

# Groq is OpenAI-compatible and Hermes supports named custom providers.
providers = data.get("providers")
if not isinstance(providers, dict):
    providers = {}
providers["groq"] = {
    "api": "https://api.groq.com/openai/v1",
    "key_env": "GROQ_API_KEY",
    "discover_models": True,
    "models": ["openai/gpt-oss-120b", "openai/gpt-oss-20b"],
}
data["providers"] = providers

aliases = data.get("model_aliases")
if not isinstance(aliases, dict):
    aliases = {}
if ollama_ready:
    aliases["gemma"] = {"provider": "ollama-cloud", "model": "gemma4:31b-cloud"}
if groq_ready:
    aliases["groq"] = {"provider": "custom:groq", "model": "openai/gpt-oss-120b"}
    aliases["fast"] = {"provider": "custom:groq", "model": "openai/gpt-oss-20b"}
if deepseek_ready:
    aliases["deep"] = {"provider": "deepseek", "model": "deepseek-v4-pro"}
if openrouter_ready:
    aliases["router"] = {"provider": "openrouter", "model": "openrouter/auto"}
data["model_aliases"] = aliases

fallbacks = []
if groq_ready:
    fallbacks.append({"provider": "custom:groq", "model": "openai/gpt-oss-120b"})
if deepseek_ready:
    fallbacks.append({"provider": "deepseek", "model": "deepseek-v4-pro"})
if openrouter_ready:
    fallbacks.append({"provider": "openrouter", "model": "openrouter/auto"})
data["fallback_providers"] = fallbacks

# Media pipeline:
# - Gemma 4 Cloud handles image analysis for every chat model, so switching to
#   text-only Groq/DeepSeek does not break Telegram photo understanding.
# - Telegram voice notes use a fully local/open-source whisper.cpp command
#   provider. No Groq/OpenAI speech API key is required.
if ollama_ready:
    auxiliary = data.get("auxiliary")
    if not isinstance(auxiliary, dict):
        auxiliary = {}
    vision = auxiliary.get("vision")
    if not isinstance(vision, dict):
        vision = {}
    vision["provider"] = "ollama-cloud"
    vision["model"] = "gemma4:31b-cloud"
    auxiliary["vision"] = vision
    data["auxiliary"] = auxiliary

stt = data.get("stt")
if not isinstance(stt, dict):
    stt = {}
stt["enabled"] = True
stt["echo_transcripts"] = True
stt["provider"] = "whispercpp"
# The wrapper forces Whisper language auto-detection so Arabic, English, and
# mixed voice notes do not depend on a cloud language hint.
stt["language"] = ""
stt_providers = stt.get("providers")
if not isinstance(stt_providers, dict):
    stt_providers = {}
stt_providers["whispercpp"] = {
    "type": "command",
    "command": "/usr/local/bin/hermes-whisper-stt {input_path} {output_path}",
    "format": "txt",
    "timeout": 300,
}
stt["providers"] = stt_providers
data["stt"] = stt

model = data.get("model")
if not isinstance(model, dict):
    model = {}

# Ollama Cloud Gemma 4 is the requested main model whenever its key exists.
# Otherwise preserve the current working provider instead of breaking startup.
if ollama_ready:
    model["provider"] = "ollama-cloud"
    model["default"] = "gemma4:31b-cloud"
    for stale in ("base_url", "api_key", "api", "api_mode"):
        model.pop(stale, None)
    data["model"] = model
    write_env_value(env_path, "LLM_MODEL", "gemma4:31b-cloud")
elif groq_ready:
    model["provider"] = "custom:groq"
    model["default"] = "openai/gpt-oss-120b"
    for stale in ("base_url", "api_key", "api", "api_mode"):
        model.pop(stale, None)
    data["model"] = model
    write_env_value(env_path, "LLM_MODEL", "openai/gpt-oss-120b")

cfg_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

configured = []
for name, ready in (
    ("ollama-cloud", ollama_ready),
    ("groq", groq_ready),
    ("deepseek", deepseek_ready),
    ("openrouter", openrouter_ready),
):
    if ready:
        configured.append(name)

if ollama_ready:
    main = "ollama-cloud/gemma4:31b-cloud"
elif groq_ready:
    main = "groq/openai/gpt-oss-120b"
else:
    main = "existing"

print(
    f"[provider-stack] configured={','.join(configured) or 'none'} "
    f"main={main} aliases={','.join(sorted(aliases)) or 'none'} "
    f"fallbacks={len(fallbacks)} "
    f"vision={'gemma4:31b-cloud' if ollama_ready else 'default'} "
    f"stt=local/whisper.cpp-small-q5_1",
    flush=True,
)
PY

# Hermes has a second access-control layer on the platform adapter itself.
# For Telegram DMs, an allow-all env flag alone is not sufficient when the
# adapter's dm_policy remains pairing/allowlist. Make that policy explicitly
# controllable from Railway so bootstrap can temporarily use "open" and then
# switch back to "allowlist" once the owner's numeric Telegram ID is known.
python - <<'PY' || true
import os
from pathlib import Path

policy = os.getenv("TELEGRAM_DM_POLICY", "").strip().lower()
if policy:
    if policy not in {"open", "allowlist", "disabled", "pairing"}:
        print(f"[telegram-policy] ignoring invalid TELEGRAM_DM_POLICY={policy!r}", flush=True)
    else:
        try:
            import yaml
            path = Path("/data/.hermes/config.yaml")
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
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
            extra = telegram.setdefault("extra", {})
            if not isinstance(extra, dict):
                extra = {}
                telegram["extra"] = extra
            extra["dm_policy"] = policy
            path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
            print(f"[telegram-policy] dm_policy={policy}", flush=True)
        except Exception as exc:
            print(f"[telegram-policy] failed: {type(exc).__name__}", flush=True)
PY

# One-time private Telegram bootstrap for a brand-new bot.
# When enabled, clear stale Telegram pairing state inherited from the previous
# bot, then approve only the first *fresh* Telegram pairing request and persist
# that approval on the Railway volume. A marker prevents this from ever running
# again after a user has been locked in.
if [ "${TELEGRAM_AUTO_APPROVE_FIRST:-false}" = "true" ] && [ ! -f /data/.hermes/.telegram_first_user_lock_done ]; then
  python - <<'PY' &
import json
import os
import time
from pathlib import Path

home = Path("/data/.hermes")
marker = home / ".telegram_first_user_lock_done"

def active_pairing_dir():
    legacy = home / "pairing"
    try:
        if legacy.is_dir() and any(legacy.iterdir()):
            return legacy
    except OSError:
        return legacy
    return home / "platforms" / "pairing"

d = active_pairing_dir()
d.mkdir(parents=True, exist_ok=True)

# New bot, clean Telegram pairing slate only. Other platforms are untouched.
for name in ("telegram-pending.json", "telegram-approved.json"):
    p = d / name
    try:
        p.write_text("{}\n", encoding="utf-8")
        os.chmod(p, 0o600)
    except OSError:
        pass

print("[telegram-auto-pair] armed for first fresh Telegram user", flush=True)

pending_path = d / "telegram-pending.json"
approved_path = d / "telegram-approved.json"
deadline = time.time() + 900

while time.time() < deadline:
    try:
        pending = json.loads(pending_path.read_text(encoding="utf-8")) if pending_path.exists() else {}
    except Exception:
        pending = {}

    if pending:
        # Approve the oldest fresh request only.
        entry_id, entry = min(
            pending.items(),
            key=lambda kv: (kv[1] or {}).get("created_at", time.time())
            if isinstance(kv[1], dict) else time.time(),
        )
        if isinstance(entry, dict):
            user_id = str(entry.get("user_id") or "").strip()
            if user_id:
                pending.pop(entry_id, None)
                try:
                    approved = json.loads(approved_path.read_text(encoding="utf-8")) if approved_path.exists() else {}
                except Exception:
                    approved = {}
                approved[user_id] = {
                    "user_name": entry.get("user_name", ""),
                    "approved_at": time.time(),
                }
                pending_path.write_text(json.dumps(pending, indent=2) + "\n", encoding="utf-8")
                approved_path.write_text(json.dumps(approved, indent=2) + "\n", encoding="utf-8")
                os.chmod(pending_path, 0o600)
                os.chmod(approved_path, 0o600)
                marker.write_text("locked\n", encoding="utf-8")
                os.chmod(marker, 0o600)
                print("[telegram-auto-pair] first fresh Telegram user approved and locked", flush=True)
                break
    time.sleep(1)
else:
    print("[telegram-auto-pair] no fresh pairing request received before timeout", flush=True)
PY
fi

# Safe Telegram diagnostic: verify which bot the configured token belongs to
# without logging or persisting the token itself.
python - <<'PY' || true
import json, os, urllib.request

token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
if token:
    try:
        with urllib.request.urlopen(
            f"https://api.telegram.org/bot{token}/getMe", timeout=8
        ) as response:
            payload = json.load(response)
        result = payload.get("result") or {}
        username = result.get("username")
        bot_id = result.get("id")
        if payload.get("ok") and username:
            print(f"[telegram-diagnostic] token identity=@{username} bot_id={bot_id}", flush=True)
        else:
            print("[telegram-diagnostic] getMe returned no valid bot identity", flush=True)
    except Exception as exc:
        print(f"[telegram-diagnostic] getMe failed: {type(exc).__name__}", flush=True)
else:
    print("[telegram-diagnostic] TELEGRAM_BOT_TOKEN is missing", flush=True)
PY

# Bootstrap OAuth tokens from env var (e.g. xAI Grok SuperGrok).
# Set HERMES_AUTH_JSON_BOOTSTRAP to the contents of a locally-generated
# ~/.hermes/auth.json. Written only once — subsequent token refreshes update
# the file in place on the persistent volume.
if [ ! -f /data/.hermes/auth.json ] && [ -n "${HERMES_AUTH_JSON_BOOTSTRAP}" ]; then
  printf '%s' "${HERMES_AUTH_JSON_BOOTSTRAP}" > /data/.hermes/auth.json
  chmod 600 /data/.hermes/auth.json
fi

# Clear stale gateway runtime files left over from the previous container.
# hermes writes these on start but does not remove them on SIGTERM, and /data
# is a persistent volume, so they survive into the next boot:
#   gateway.pid   -> "PID file race lost to another gateway instance"
#   gateway.lock  -> since v2026.8.27 get_running_pid() also consults the lock,
#                    and the new cross-profile gate makes `--replace` REFUSE a
#                    pid it cannot prove owns this HERMES_HOME (gateway/run.py
#                    "Refusing --replace"), which no retry can clear
#   gateway.sock  -> a stale control socket blocks the fresh bind
# No hermes process can be running here (we are pre-exec in a fresh
# container), so removing all three unconditionally is safe.
rm -f /data/.hermes/gateway.pid /data/.hermes/gateway.lock /data/.hermes/gateway.sock


# Durable lazy-install target for opt-in backends (supermemory, mem0, firecrawl, etc.).
# The template installs hermes into system Python (`uv pip install --system`) with no
# venv, so `uv pip install` at runtime fails with "No virtual environment found." Set
# HERMES_LAZY_INSTALL_TARGET to redirect runtime package installs into a writable dir
# on the persistent volume — same mechanism the official Docker image bakes in. This
# must be exported so the gateway process inherits it; hermes_bootstrap.py activates it
# at startup. Without it, any lazy dep (including opt-in providers like supermemory)
# fails on every fresh container deploy.
mkdir -p /data/.hermes/lazy-packages
export HERMES_LAZY_INSTALL_TARGET=/data/.hermes/lazy-packages

# HERMES_DASHBOARD_PUBLIC_URL is deliberately NOT exported here. server.py owns
# it: build_hermes_env() sets it only alongside the basic-auth credentials that
# satisfy hermes' auth gate. Declaring the URL without them makes the dashboard
# SystemExit at startup (v2026.8.27's should_require_dashboard_auth), and since
# Dashboard has no respawn supervisor every proxied page 503s until redeploy
# while /setup and /health stay green. Setting it here would skip that pairing.

# ---- HASAN PERSONAL HERMES BOOTSTRAP v2 ----
# One-time personalization migration. Back up any existing identity/memory first,
# then seed Hasan's curated baseline. The marker prevents future redeploys from
# overwriting whatever Hermes learns or Hasan edits afterward.
PERSONAL_MARKER="/data/.hermes/.hasan_personalization_v2"
if [ ! -f "$PERSONAL_MARKER" ]; then
  stamp="$(date -u +%Y%m%dT%H%M%SZ)"
  backup="/data/.hermes/backups/personalization-$stamp"
  mkdir -p "$backup" /data/.hermes/memories /data/.hermes/knowledge /data/.hermes/skills

  [ -f /data/.hermes/SOUL.md ] && cp /data/.hermes/SOUL.md "$backup/SOUL.md" || true
  [ -f /data/.hermes/memories/USER.md ] && cp /data/.hermes/memories/USER.md "$backup/USER.md" || true
  [ -f /data/.hermes/memories/MEMORY.md ] && cp /data/.hermes/memories/MEMORY.md "$backup/MEMORY.md" || true

  # Personal identity/context comes from private Railway variables. This keeps
  # personal data out of the public deployment-template repository.
  if [ -n "${HERMES_PERSONAL_SOUL:-}" ]; then
    printf '%s\n' "$HERMES_PERSONAL_SOUL" > /data/.hermes/SOUL.md
  elif [ -f /app/personalization/SOUL.md ]; then
    cp /app/personalization/SOUL.md /data/.hermes/SOUL.md
  fi
  if [ -n "${HERMES_PERSONAL_USER:-}" ]; then
    printf '%s\n' "$HERMES_PERSONAL_USER" > /data/.hermes/memories/USER.md
  elif [ -f /app/personalization/USER.md ]; then
    cp /app/personalization/USER.md /data/.hermes/memories/USER.md
  fi
  if [ -n "${HERMES_PERSONAL_MEMORY:-}" ]; then
    printf '%s\n' "$HERMES_PERSONAL_MEMORY" > /data/.hermes/memories/MEMORY.md
  elif [ -f /app/personalization/MEMORY.md ]; then
    cp /app/personalization/MEMORY.md /data/.hermes/memories/MEMORY.md
  fi
  if [ -n "${HERMES_PERSONAL_KNOWLEDGE:-}" ]; then
    printf '%s\n' "$HERMES_PERSONAL_KNOWLEDGE" > /data/.hermes/knowledge/hasan-operating-context.md
  elif [ -f /app/personalization/knowledge/hasan-operating-context.md ]; then
    cp /app/personalization/knowledge/hasan-operating-context.md /data/.hermes/knowledge/hasan-operating-context.md
  fi
  cp -a /app/personalization/skills/. /data/.hermes/skills/

  python - <<'PY' || true
from pathlib import Path
import yaml
p = Path("/data/.hermes/config.yaml")
try:
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
except Exception:
    data = {}
if not isinstance(data, dict):
    data = {}
memory = data.setdefault("memory", {})
if not isinstance(memory, dict):
    memory = {}
    data["memory"] = memory
memory["memory_enabled"] = True
memory["user_profile_enabled"] = True
memory["write_approval"] = False
memory["nudge_interval"] = 10

skills_cfg = data.setdefault("skills", {})
if not isinstance(skills_cfg, dict):
    skills_cfg = {}
    data["skills"] = skills_cfg
skills_cfg["write_approval"] = False
skills_cfg["creation_nudge_interval"] = 12

auxiliary = data.setdefault("auxiliary", {})
if not isinstance(auxiliary, dict):
    auxiliary = {}
    data["auxiliary"] = auxiliary
background_review = auxiliary.setdefault("background_review", {})
if not isinstance(background_review, dict):
    background_review = {}
    auxiliary["background_review"] = background_review
background_review["enabled"] = True

display = data.setdefault("display", {})
if not isinstance(display, dict):
    display = {}
    data["display"] = display
display["memory_notifications"] = "on"
p.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
PY

  touch "$PERSONAL_MARKER"
  echo "[personalization] Hasan personal Hermes v2 seeded; previous identity/memory backed up to $backup"
fi

# Enforce self-learning settings on every boot without touching personal memory.
# This is intentionally outside the one-time personalization migration.
python - <<'PY' || true
from pathlib import Path
import yaml

p = Path("/data/.hermes/config.yaml")
try:
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
except Exception:
    data = {}
if not isinstance(data, dict):
    data = {}

memory = data.setdefault("memory", {})
if not isinstance(memory, dict):
    memory = {}
    data["memory"] = memory
memory["memory_enabled"] = True
memory["user_profile_enabled"] = True
memory["write_approval"] = False
memory["nudge_interval"] = 10

skills_cfg = data.setdefault("skills", {})
if not isinstance(skills_cfg, dict):
    skills_cfg = {}
    data["skills"] = skills_cfg
skills_cfg["write_approval"] = False
skills_cfg["creation_nudge_interval"] = 12

auxiliary = data.setdefault("auxiliary", {})
if not isinstance(auxiliary, dict):
    auxiliary = {}
    data["auxiliary"] = auxiliary
background_review = auxiliary.setdefault("background_review", {})
if not isinstance(background_review, dict):
    background_review = {}
    auxiliary["background_review"] = background_review
background_review["enabled"] = True

display = data.setdefault("display", {})
if not isinstance(display, dict):
    display = {}
    data["display"] = display
display["memory_notifications"] = "on"

p.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
print("[self-learning] memory=on skills=on background_review=on", flush=True)
PY

# Configure GitHub's official remote MCP server. The bearer value itself stays
# in Railway as MCP_GITHUB_API_KEY; config.yaml stores only an environment
# reference, so Hermes can use authenticated GitHub tools without exposing the
# raw credential to Telegram or terminal commands.
python - <<'PY' || true
from pathlib import Path
import yaml

p = Path("/data/.hermes/config.yaml")
try:
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
except Exception:
    data = {}
if not isinstance(data, dict):
    data = {}

servers = data.setdefault("mcp_servers", {})
if not isinstance(servers, dict):
    servers = {}
    data["mcp_servers"] = servers

existing = servers.get("github")
if not isinstance(existing, dict):
    existing = {}
servers["github"] = {
    **existing,
    "url": "https://api.githubcopilot.com/mcp/",
    "headers": {
        **(existing.get("headers") if isinstance(existing.get("headers"), dict) else {}),
        "Authorization": "Bearer ${MCP_GITHUB_API_KEY}",
    },
    "enabled": True,
}

p.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
print("[github-mcp] configured official remote GitHub MCP server", flush=True)
PY

# Keep reproducible vendor/official skills OUT of the tiny persistent volume.
# These sources already exist in the immutable image; symlinks make them available
# to Hermes without duplicating whole repositories under /data. User-created
# skills with other names remain untouched.
link_image_skill() {
  local name="$1"
  local src="$2"
  [ -d "$src" ] || return 0
  if [ -L "/data/.hermes/skills/$name" ]; then
    ln -sfn "$src" "/data/.hermes/skills/$name"
    return 0
  fi
  if [ -e "/data/.hermes/skills/$name" ]; then
    rm -rf "/data/.hermes/skills/$name"
  fi
  ln -s "$src" "/data/.hermes/skills/$name"
}

link_image_skill planning-with-files /opt/vendor/planning-with-files/.hermes/skills/planning-with-files
link_image_skill using-superpowers /opt/vendor/superpowers/skills/using-superpowers
link_image_skill systematic-debugging /opt/vendor/superpowers/skills/systematic-debugging
link_image_skill test-driven-development /opt/vendor/superpowers/skills/test-driven-development
link_image_skill writing-plans /opt/vendor/superpowers/skills/writing-plans
link_image_skill executing-plans /opt/vendor/superpowers/skills/executing-plans
link_image_skill verification-before-completion /opt/vendor/superpowers/skills/verification-before-completion
link_image_skill gstack /opt/vendor/gstack
link_image_skill plan-ceo-review /opt/vendor/gstack/plan-ceo-review
link_image_skill plan-eng-review /opt/vendor/gstack/plan-eng-review
link_image_skill design-review /opt/vendor/gstack/design-review
link_image_skill review /opt/vendor/gstack/review
link_image_skill qa /opt/vendor/gstack/qa
link_image_skill investigate /opt/vendor/gstack/investigate
link_image_skill ship /opt/vendor/gstack/ship
link_image_skill google-workspace /opt/hermes-agent/skills/productivity/google-workspace
link_image_skill github /opt/hermes-agent/skills/software-development/github
link_image_skill qmd /opt/hermes-agent/optional-skills/research/qmd
link_image_skill scrapling /opt/hermes-agent/optional-skills/research/scrapling
link_image_skill publish-site /opt/hermes-agent/optional-skills/web-development/publish-site
echo "[storage-guard] vendor skills linked from immutable image" >&2
df -h /data >&2 || true

# Make newly bundled custom skills available on later upgrades too, while
# preserving any existing/learned version on the persistent volume.
for src in /app/personalization/skills/*; do
  [ -d "$src" ] || continue
  name="$(basename "$src")"
  if [ ! -e "/data/.hermes/skills/$name" ]; then
    cp -a "$src" "/data/.hermes/skills/$name"
    echo "[personalization] seeded missing bundled custom skill: $name"
  fi
done


# Seed pinned third-party skills from the immutable image. Copy only when
# missing so Hermes can edit/learn from its persistent copy without deploys
# resetting it.
seed_vendor_skill() {
  local name="$1"
  local src="$2"
  if [ ! -e "/data/.hermes/skills/$name" ] && [ -d "$src" ]; then
    ln -s "$src" "/data/.hermes/skills/$name"
    echo "[skills] linked pinned skill: $name"
  fi
}

seed_vendor_skill planning-with-files /opt/vendor/planning-with-files/.hermes/skills/planning-with-files
seed_vendor_skill using-superpowers /opt/vendor/superpowers/skills/using-superpowers
seed_vendor_skill systematic-debugging /opt/vendor/superpowers/skills/systematic-debugging
seed_vendor_skill test-driven-development /opt/vendor/superpowers/skills/test-driven-development
seed_vendor_skill writing-plans /opt/vendor/superpowers/skills/writing-plans
seed_vendor_skill executing-plans /opt/vendor/superpowers/skills/executing-plans
seed_vendor_skill verification-before-completion /opt/vendor/superpowers/skills/verification-before-completion

# gstack root skill plus the modes most useful for Hasan's founder/build flow.
seed_vendor_skill gstack /opt/vendor/gstack
seed_vendor_skill plan-ceo-review /opt/vendor/gstack/plan-ceo-review
seed_vendor_skill plan-eng-review /opt/vendor/gstack/plan-eng-review
seed_vendor_skill design-review /opt/vendor/gstack/design-review
seed_vendor_skill review /opt/vendor/gstack/review
seed_vendor_skill qa /opt/vendor/gstack/qa
seed_vendor_skill investigate /opt/vendor/gstack/investigate
seed_vendor_skill ship /opt/vendor/gstack/ship

# Prefer the official Google Workspace skill bundled with the pinned Hermes release.
# Replace the legacy trimmed persistent copy once if it lacks the official OAuth setup script.
if [ ! -f /data/.hermes/skills/google-workspace/scripts/setup.py ] && [ -d /opt/hermes-agent/skills/productivity/google-workspace ]; then
  rm -rf /data/.hermes/skills/google-workspace
  ln -s /opt/hermes-agent/skills/productivity/google-workspace /data/.hermes/skills/google-workspace
  echo "[skills] linked google-workspace to official bundled skill"
fi
seed_vendor_skill google-workspace /opt/hermes-agent/skills/productivity/google-workspace

# Persist the official GitHub skill as well. GitHub auth itself is stored separately.
seed_vendor_skill github /opt/hermes-agent/skills/software-development/github

mkdir -p /data/.hermes/wiki /data/.hermes/cache/uv
export WIKI_PATH=/data/.hermes/wiki
export PWF_PLAN_ROOT=/data/.hermes/plans
export UV_CACHE_DIR=/data/.hermes/cache/uv
sync_runtime_env_var WIKI_PATH
sync_runtime_env_var PWF_PLAN_ROOT

# Curated skill pack. These installs are idempotent: existing skills are kept,
# so later edits/learning on the persistent volume are not overwritten.
install_skill_if_missing() {
  local skill_name="$1"
  local identifier="$2"
  if [ -d "/data/.hermes/skills/$skill_name" ]; then
    return 0
  fi
  echo "[skills] installing $skill_name from $identifier"
  timeout 45s hermes skills install "$identifier" --yes >/tmp/hermes-skill-install.log 2>&1 || {
    echo "[skills] install failed for $skill_name (will retry on next deploy)"
    tail -20 /tmp/hermes-skill-install.log || true
    return 0
  }
}

# Install third-party/optional skills in the background so a slow registry
# can never hold the Telegram gateway's health check hostage.
(
# Official / bundled knowledge and web capabilities.
install_skill_if_missing qmd official/research/qmd
install_skill_if_missing scrapling official/research/scrapling
install_skill_if_missing publish-site official/web-development/publish-site

# Long-task planning.
install_skill_if_missing planning-with-files OthmanAdi/planning-with-files/.hermes/skills/planning-with-files

if [ ! -f /data/.hermes/.planning_with_files_plugin_v1 ]; then
  echo "[plugins] installing native planning-with-files plugin"
  if timeout 60s hermes plugins install /opt/vendor/planning-with-files/.hermes/plugins/planning-with-files --enable >/tmp/hermes-pwf-plugin.log 2>&1; then
    touch /data/.hermes/.planning_with_files_plugin_v1
    echo "[plugins] planning-with-files enabled"
  else
    echo "[plugins] planning-with-files plugin install failed (skill still available; retry next deploy)"
    tail -20 /tmp/hermes-pwf-plugin.log || true
  fi
fi

# Superpowers: install the router plus the most useful engineering procedures.
install_skill_if_missing using-superpowers obra/superpowers/skills/using-superpowers
install_skill_if_missing systematic-debugging obra/superpowers/skills/systematic-debugging
install_skill_if_missing test-driven-development obra/superpowers/skills/test-driven-development
install_skill_if_missing writing-plans obra/superpowers/skills/writing-plans
install_skill_if_missing executing-plans obra/superpowers/skills/executing-plans
install_skill_if_missing verification-before-completion obra/superpowers/skills/verification-before-completion

# gstack: broad founder/product/engineering operating modes.
install_skill_if_missing gstack garrytan/gstack
install_skill_if_missing plan-ceo-review garrytan/gstack/plan-ceo-review
install_skill_if_missing plan-eng-review garrytan/gstack/plan-eng-review
install_skill_if_missing design-review garrytan/gstack/design-review
install_skill_if_missing review garrytan/gstack/review
install_skill_if_missing qa garrytan/gstack/qa
install_skill_if_missing investigate garrytan/gstack/investigate
install_skill_if_missing ship garrytan/gstack/ship

# Google Workspace community skill. It is usable once Google OAuth credentials
# are configured for this Railway Hermes instance.
install_skill_if_missing google-workspace amanning3390/hermeshub/skills/google-workspace

# llm-wiki ships bundled with Hermes already. WIKI_PATH above puts its durable
# knowledge base on the Railway volume.

# Run the native Hermes skill audit after installs. SkillSpector is available
# on demand through the local skill-upgrader via uvx for extra third-party scans.
timeout 45s hermes skills audit >/tmp/hermes-skills-audit.log 2>&1 || true
echo "[skills] curated pack ready"
) &
# Non-secret GitHub boot diagnostic. Railway keeps the token in service variables;
# this only confirms the credential resolves and can read the Hermes repository.
if command -v gh >/dev/null 2>&1 && [ -n "${GITHUB_TOKEN:-}" ]; then
  if GH_TOKEN="$GITHUB_TOKEN" gh api user --jq '.login' >/tmp/hermes-github-login 2>/dev/null; then
    GH_LOGIN="$(cat /tmp/hermes-github-login 2>/dev/null || true)"
    if GH_TOKEN="$GITHUB_TOKEN" gh repo view hsndm566/hermes-agent-template --json nameWithOwner --jq '.nameWithOwner' >/tmp/hermes-github-repo 2>/dev/null; then
      GH_REPO="$(cat /tmp/hermes-github-repo 2>/dev/null || true)"
      echo "[github] AUTH_OK login=${GH_LOGIN:-unknown} repo=${GH_REPO:-unknown}"
    else
      echo "[github] AUTH_PARTIAL login=${GH_LOGIN:-unknown} repo_read=failed"
    fi
  else
    echo "[github] AUTH_FAILED"
  fi
else
  echo "[github] AUTH_MISSING"
fi

echo "[skills] background installer started"

# External storage worker: keep Railway as fast live state, use Google Drive for
# durable snapshots/log archives. The worker is a no-op until Hermes' own Google
# OAuth token exists. Archives are built under /tmp, never on the persistent disk.
(
  sleep 20
  while true; do
    python /app/scripts/hermes-drive-archive.py || true
    sleep 21600
  done
) &
echo "[drive-archive] worker started (6h cadence)"
# ---- END HASAN PERSONAL HERMES BOOTSTRAP v2 ----


# Final certification / ongoing lightweight boot verification.
# Runs in the background so health checks and Telegram startup are never blocked.
# First boot performs full agent + learning + backup + Telegram tests.
# Second boot proves the /data sentinel survived a real redeploy.
# Later boots perform only the cheap static integrity check.
(
  sleep 8
  set +e
  mkdir -p /data/.hermes/logs
  python /app/personalization/scripts/final_certify.py 2>&1 | tee -a /data/.hermes/logs/final-certification.log
  cert_rc=${PIPESTATUS[0]}
  echo "[certification] runner exited rc=${cert_rc}"
  exit 0
) &

exec python /app/server.py
