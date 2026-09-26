FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

# Which hermes-agent revision to install. Accepts any git ref the upstream
# repo publishes — a release tag (recommended for reproducibility) or a
# branch name (`main`) for bleeding edge.
#
# To bump: check https://github.com/NousResearch/hermes-agent/releases for the
# newest tag (format `vYYYY.M.D`, optionally with a `.PATCH` suffix, e.g.
# `v2026.5.29.2`) and update the default below. Use `main` only if you accept
# that every rebuild can pull arbitrary new upstream commits.
ARG HERMES_REF=v2026.9.11

# Persist the build arg into the runtime env so the admin UI can display which
# Hermes release this image actually pins. Reading it (rather than hardcoding a
# version in the template) keeps the badge honest when someone overrides
# HERMES_REF as a Railway service variable to pin an older release — a Railway
# runtime variable simply shadows this ENV, so the UI still shows the truth.
ENV HERMES_REF=${HERMES_REF}

# tini = tiny init that we run as PID 1. Without it, hermes's grandchild
# processes (MCP stdio servers, git, bun, browser daemons spawned by tools)
# reparent to PID 1 when their parents exit and pile up as zombies. After
# weeks of uptime that exhausts the kernel's PID table → "fork: cannot
# allocate memory" and the container dies. tini reaps zombies in the
# background and forwards SIGTERM/SIGINT to our entrypoint so Railway's
# stop signal still triggers our graceful shutdown. Standard container init
# (same as Docker's `--init` flag and Kubernetes' pause container).
#
# Node.js is required only at build time to compile the Hermes React dashboard.
# We strip the source + apt lists afterwards to keep the image lean.
#
# Keep setup_22.x. v2026.8.3's new .npmrc sets engine-strict=true, so hermes'
# `node >=22.22.0` + `npm <11.10.0 || >=11.17.0` is now a hard EBADENGINE build
# failure, not a warning — setup_24.x bundles an npm that satisfies neither.
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl ca-certificates git gh tini build-essential ffmpeg && \
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    rm -rf /var/lib/apt/lists/*

# Install hermes-agent (provides the `hermes` CLI) and pre-build its React
# dashboard so `hermes dashboard` has nothing to build at runtime.
#
# [all] in v2026.6.5 no longer pulls in [dev]; messaging platforms, TTS, and
# other heavy backends are lazy-installed by hermes at first use. We pre-install
# the ones this template actually uses so first-message latency is instant.
# `vision` guards image downscaling (without Pillow an oversized image >5 MB /
# >8000px bakes into immutable history and bricks the session on Anthropic's
# non-retryable 400). The extra itself has been EMPTY since v2026.6.19 — Pillow
# moved into core deps — so it resolves to a no-op; kept for back-compat.
# When bumping HERMES_REF, re-check hermes-agent's pyproject.toml [all] and
# the extras below against the new release's pyproject.toml.
#
# The `-e` is LOAD-BEARING since v2026.8.3: upstream's new setup.py raises on
# bdist_wheel/sdist unless HERMES_NIX_BUILD=1. PEP 660 editable installs route
# through build_editable and are exempt — drop `-e` and the image won't build.
#
# v2026.8.3 also added [tool.uv] to pyproject.toml, which uv reads from this
# cwd (upstream builds from a frozen lock; we re-resolve every time):
# override-dependencies fixes discord.py's vulnerable pynacl pin, and
# exclude-newer="14 days" can fail a build on a fresh dep — override with
# `uv pip install --exclude-newer <date>`.
#
# v2026.8.13 made that escape hatch sharper, and v2026.9.11 moved the floor
# again: nemo-relay is now >=0.8.3,<0.9 (0.8.3 published 2026-09-02), which
# only resolves because upstream lists it in exclude-newer-package. A manual
# `--exclude-newer <date>` re-imposes a GLOBAL cutoff, so any date before
# 2026-09-02 leaves nemo-relay>=0.8.3 unsatisfiable and hard-fails the build.
# Same trap for cryptography==50.0.0 and h2 4.4.1. Re-read this floor on every
# bump — it tracks whatever nemo-relay pin the pinned tag carries.
# Narrow build-time patch for Telegram voice ingress. Keep it before the
# Hermes clone/install layer because that layer applies the patch immediately.
COPY scripts/patch-hermes-telegram-voice.py /tmp/patch-hermes-telegram-voice.py
COPY scripts/patch-hermes-telegram-voice.py /app/scripts/patch-hermes-telegram-voice.py

RUN git clone --depth 1 --branch ${HERMES_REF} https://github.com/NousResearch/hermes-agent.git /opt/hermes-agent && \
    python /tmp/patch-hermes-telegram-voice.py && \
    cd /opt/hermes-agent && \
    uv pip install --system --no-cache -e ".[all,messaging,tts-premium,honcho,bedrock,anthropic,edge-tts,hindsight,vision,voice]" && \
    cd /opt/hermes-agent/web && \
    npm install --silent && \
    npm run build && \
    cd /opt/hermes-agent/ui-tui && \
    npm install --silent --no-fund --no-audit --progress=false && \
    npm run build && \
    rm -rf /opt/hermes-agent/web /opt/hermes-agent/.git /root/.npm

# Why pre-build ui-tui (and why we don't delete it after):
# - The dashboard's embedded Chat tab spawns `node ui-tui/dist/entry.js`
#   on every WebSocket connect to /api/pty.
# - Without HERMES_TUI_DIR, hermes's _make_tui_argv falls through to the
#   npm install + build path (since git-editable installs don't have the
#   bundled tui_dist/ that PyPI wheels include), adding 30-60s to the
#   first chat-open and blocking the asyncio event loop.
# - Pre-building at image time surfaces build failures here rather than
#   at user request time, and makes first-chat-open instant.
# - We keep ui-tui/ entirely (node_modules + dist + src) so HERMES_TUI_DIR
#   can point at it (see below).

# Stamp the CODE-SCOPED install method next to the running package. hermes'
# detect_install_method() reads <install-tree>/.install_method FIRST (priority 1,
# authoritative) — before the home-scoped $HERMES_HOME/.install_method that
# start.sh writes (priority 2, honored only when is_container() is true). The
# install tree for our editable install is /opt/hermes-agent (parent of
# hermes_cli/, i.e. Path(config.py).parent.parent). Baking the stamp here makes
# the dashboard "Update Hermes" button refuse regardless of runtime container
# detection — exactly what upstream's own published image does (it bakes a
# docker stamp into /opt/hermes). Belt-and-suspenders with start.sh's home stamp:
# if a future hermes release changes or drops is_container()'s Railway marker
# (/run/.containerenv), the home stamp would stop being honored but this one
# still refuses. Re-verify the install-tree path if hermes stops installing
# editable from /opt/hermes-agent.
RUN printf 'docker\n' > /opt/hermes-agent/.install_method

# Local open-source speech-to-text for Telegram voice notes.
# Hermes v2026.9.11 uses faster-whisper directly. Bake the multilingual Base
# CTranslate2 model into the immutable image so runtime transcription needs no
# model download, no cloud STT key, and no persistent-volume cache. This also
# avoids carrying a second whisper.cpp engine + two duplicate GGML models.
RUN mkdir -p /opt/faster-whisper-models/base && \
    python -c "from huggingface_hub import snapshot_download; snapshot_download(repo_id='Systran/faster-whisper-base', local_dir='/opt/faster-whisper-models/base')" && \
    rm -rf /opt/faster-whisper-models/base/.cache

# firecrawl-anydoc (the PDF / legacy-Office reader behind read_file) is a CORE
# dependency as of v2026.8.31 — pyproject.toml pins ==0.2.4 and exempts it from
# [tool.uv] exclude-newer, so the main install above already has it.
#
# Do NOT re-pin it in a later layer. We used to (==0.1.6, when it was lazy-only):
# that layer runs AFTER the editable install and uv DOWNGRADES the core version,
# and v2026.8.31 also bumped the lazy self-heal pin (tools/lazy_deps.py
# "tool.doc_extract") to ==0.2.4. _is_satisfied() compares versions, not
# presence, so the first PDF read tries to heal into HERMES_LAZY_INSTALL_TARGET
# with a --constraint file built from every installed dist — which pins
# firecrawl-anydoc==0.1.6 — and uv hard-fails "No solution found". Result:
# EVERY PDF/.docx/.xlsx/.pptx/.odt/.rtf/.epub read fails, on every deploy,
# retried every 300s (ANYDOC_RETRY_SECONDS) and never succeeding.
#
# Same trap for any other package we might pin separately: on a version bump,
# grep the new pyproject's core dependencies for anything this Dockerfile pins.


# Pin the curated third-party skill sources into the image. Runtime skill-hub
# fetches can be slow/flaky on Railway; build-time Git fetches are deterministic.
# Hierarchical-agents main currently omits scripts referenced by its own README.
# Pin the last verified commit containing sync_hermes_profiles.py and
# hierarchy_gateway.py. Install it into a separate venv so its generic top-level
# "core" / "integrations" packages cannot shadow Hermes modules.
ARG HIERARCHICAL_AGENTS_REF=de37f8a46458fc76cc57094cde4f404bd9bda309

RUN set -eux; \
    mkdir -p /opt/vendor/superpowers /opt/vendor/gstack /opt/vendor/planning-with-files /opt/vendor/hermeshub /opt/vendor/hierarchical-agents; \
    git -C /opt/vendor/superpowers init; \
    git -C /opt/vendor/superpowers fetch --depth 1 https://github.com/obra/superpowers.git b36e0829c6d0140e93cfef2ca599b1b07d4a7797; \
    git -C /opt/vendor/superpowers checkout FETCH_HEAD; \
    git -C /opt/vendor/gstack init; \
    git -C /opt/vendor/gstack fetch --depth 1 https://github.com/garrytan/gstack.git a6b3a57512ca6d5c6aa5b68f74f736195021f96e; \
    git -C /opt/vendor/gstack checkout FETCH_HEAD; \
    git -C /opt/vendor/planning-with-files init; \
    git -C /opt/vendor/planning-with-files fetch --depth 1 https://github.com/OthmanAdi/planning-with-files.git 2fbbd77ba9a74cddb9504285935ef9ae0837cdec; \
    git -C /opt/vendor/planning-with-files checkout FETCH_HEAD; \
    git -C /opt/vendor/hermeshub init; \
    git -C /opt/vendor/hermeshub fetch --depth 1 https://github.com/amanning3390/hermeshub.git 7bd1fb508799cc536c767caf99edbc3e3d97ebd3; \
    git -C /opt/vendor/hermeshub checkout FETCH_HEAD; \
    git -C /opt/vendor/hierarchical-agents init; \
    git -C /opt/vendor/hierarchical-agents fetch --depth 1 https://github.com/GieshBuilds/hierarchical-agents.git ${HIERARCHICAL_AGENTS_REF}; \
    git -C /opt/vendor/hierarchical-agents checkout FETCH_HEAD; \
    test -f /opt/vendor/hierarchical-agents/scripts/sync_hermes_profiles.py; \
    test -f /opt/vendor/hierarchical-agents/scripts/hierarchy_gateway.py; \
    # Upstream's pinned commit declares a nonexistent setuptools backend. \
    # Use setuptools' standard PEP 517 backend without changing package code. \
    sed -i 's#setuptools.backends._legacy:_Backend#setuptools.build_meta#' /opt/vendor/hierarchical-agents/pyproject.toml; \
    grep -Fq 'build-backend = "setuptools.build_meta"' /opt/vendor/hierarchical-agents/pyproject.toml; \
    rm -rf /opt/vendor/superpowers/.git /opt/vendor/gstack/.git /opt/vendor/planning-with-files/.git /opt/vendor/hermeshub/.git /opt/vendor/hierarchical-agents/.git

RUN uv venv /opt/hierarchy-venv && \
    uv pip install --python /opt/hierarchy-venv/bin/python --no-cache -e /opt/vendor/hierarchical-agents && \
    /opt/hierarchy-venv/bin/python -m py_compile \
      /opt/vendor/hierarchical-agents/scripts/sync_hermes_profiles.py \
      /opt/vendor/hierarchical-agents/scripts/hierarchy_gateway.py \
      /opt/vendor/hierarchical-agents/tools/hierarchy_tools.py

COPY requirements.txt /app/requirements.txt
RUN uv pip install --system --no-cache -r /app/requirements.txt

RUN mkdir -p /data/.hermes

COPY server.py /app/server.py
COPY templates/ /app/templates/
COPY personalization/ /app/personalization/
COPY start.sh /app/start.sh
COPY telegram_capture.py /app/telegram_capture.py
COPY scripts/hermes-drive-archive.py /app/scripts/hermes-drive-archive.py
COPY scripts/bootstrap-hermes-team.py /app/scripts/bootstrap-hermes-team.py
COPY scripts/configure-telegram-topics.py /app/scripts/configure-telegram-topics.py
RUN chmod +x /app/start.sh /app/scripts/hermes-drive-archive.py /app/scripts/configure-telegram-topics.py && \
    python -m py_compile /app/server.py /app/scripts/hermes-drive-archive.py /app/scripts/bootstrap-hermes-team.py /app/scripts/configure-telegram-topics.py /app/scripts/patch-hermes-telegram-voice.py \
      /app/personalization/scripts/final_certify.py \
      /opt/hermes-agent/plugins/platforms/telegram/adapter.py && \
    bash -n /app/start.sh && \
    grep -Fq '[Telegram] Pre-transcribed user voice' /opt/hermes-agent/plugins/platforms/telegram/adapter.py && \
    grep -Fq 'attempts = 3 if kind == "voice" else 1' /opt/hermes-agent/plugins/platforms/telegram/adapter.py && \
    python -c 'import faster_whisper; from faster_whisper import WhisperModel' && \
    /opt/hierarchy-venv/bin/python -c 'from core.registry.profile_registry import ProfileRegistry; from core.ipc.message_bus import MessageBus' && \
    test -s /opt/faster-whisper-models/base/model.bin && \
    test -s /opt/faster-whisper-models/base/config.json

ENV HOME=/data
ENV HERMES_HOME=/data/.hermes

# Points hermes at our pre-built TUI bundle. hermes's _make_tui_argv checks
# HERMES_TUI_DIR first: if dist/entry.js exists there, it skips the npm
# install/build entirely. This is the official packager path (Nix uses it too)
# and avoids the 30-60s npm bootstrap that git-editable installs would otherwise
# trigger on first /chat connection.
ENV HERMES_TUI_DIR=/opt/hermes-agent/ui-tui

# tini wraps start.sh so it runs as PID 1's child instead of as PID 1 itself.
# `-g` propagates signals to the whole process group so `docker stop` /
# Railway's SIGTERM cleanly terminates the entire tree, not just start.sh.
ENTRYPOINT ["/usr/bin/tini", "-g", "--"]
CMD ["/app/start.sh"]
