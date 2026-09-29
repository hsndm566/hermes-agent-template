---
name: hermes-self-maintenance
description: Use when Hasan asks this Hermes to fix, upgrade, diagnose, maintain, back up, or improve itself, its Telegram gateway, memory, skills, config, or Railway deployment.
---
# Hermes Self Maintenance

This instance's durable home is `/data/.hermes` on Railway's persistent `hermes-data` volume. Code comes from `hsndm566/hermes-agent-template`; the running Hermes package is image-scoped and immutable.

## Rules
1. Diagnose before changing. Read current config/logs/state and identify the smallest safe fix.
2. Never delete or overwrite durable memory, sessions, skills, auth, cron, or state.db without a timestamped backup.
3. Changes intended to survive container rebuilds belong either in `/data/.hermes` (runtime/user state) or in the GitHub deployment template (bootstrap/code). Do not rely on ephemeral `/tmp`, `/root`, `/app`, or `/opt` runtime edits.
4. Preserve the one-time personalization marker. Do not reset SOUL/USER/MEMORY from template defaults on each deploy.
5. For skill issues, use `hermes skills inspect/list/audit/check/update` before manual surgery.
6. For third-party skills, invoke the skill-upgrader/skillspector workflow.
7. Verify gateway health and Telegram after any restart/redeploy.
8. Never print credentials or token values.

If a deployment-level change requires GitHub/Railway credentials that are not available inside Hermes, state that exact blocker instead of pretending the change was made.
