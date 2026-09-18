---
name: hermes-self-admin
description: Use when Hasan asks this Telegram Hermes to inspect, repair, upgrade, configure, extend, or explain its own Railway/Hermes setup.
---
# Hermes Self Admin

This instance runs on Railway with `HERMES_HOME=/data/.hermes` on the persistent `hermes-data` volume.

For self-administration:
1. Inspect current state before changing it.
2. Preserve `/data/.hermes`; it contains identity, memory, skills, sessions and runtime configuration.
3. Treat `hsndm566/hermes-agent-template` as deployment source. Use branches for changes that can break startup.
4. Never expose secret values from Railway variables or `.env`.
5. Validate startup/config syntax before deployment.
6. After deployment, verify health, Telegram gateway startup, provider stack and skill loading in logs.
7. Prefer current Hermes native commands and official docs over old laptop-specific procedures.
8. For a requested new capability, use the `skill-upgrader` skill and native Skills Hub first.
9. Do not overwrite learned memory/skills on redeploy; migrations must be one-time or merge-aware.
