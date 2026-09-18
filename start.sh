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
    f"fallbacks={len(fallbacks)}",
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

exec python /app/server.py
