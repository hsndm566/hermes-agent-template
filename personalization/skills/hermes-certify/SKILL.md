---
name: hermes-certify
description: Use when Hasan asks whether Hermes is healthy, complete, persistent, agentic, or self-learning, or asks for a full system check.
---
# Hermes Certification

The deployment contains a durable certification harness at:
`/app/personalization/scripts/final_certify.py`

The final certification report is stored at:
`/data/.hermes/certification/final.json`

## Normal health check
1. Read the final report first.
2. Run `hermes doctor --live`.
3. Run `hermes skills list` and `hermes skills audit`.
4. Confirm Telegram gateway and the public /health endpoint are healthy.
5. Confirm `/data/.hermes` is still the active HERMES_HOME and the persistence sentinel exists.
6. If a check fails, use `hermes-self-admin` and `integration-doctor` to diagnose the first actionable cause, make the smallest safe repair, and re-run the failed check.

## Self-learning health
Confirm memory and user profile are enabled, background review is enabled, skill writes are enabled, and `/learn`, `/refine`, and skill-management capabilities remain available.

## Recovery
If state is damaged, use `hermes-backup-restore`. Never overwrite live state without a pre-restore snapshot.

Do not claim the system is healthy from configuration alone; verify runtime checks.
