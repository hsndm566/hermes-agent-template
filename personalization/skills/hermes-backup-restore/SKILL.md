---
name: hermes-backup-restore
description: Use when Hasan asks to back up, export, migrate, recover, or restore this personal Hermes instance.
---
# Hermes Backup & Restore

This Hermes' live brain is under `/data/.hermes` on Railway.

## Default safe backup
Create a timestamped archive under `/data/.hermes/backups/exports/` containing the durable brain but excluding credentials and bulky caches.

Include when present:
- SOUL.md
- memories/
- skills/
- knowledge/
- cron/
- plans/
- workspace/ only when it contains durable user work
- state.db (conversation/session search history)

Exclude by default:
- .env
- auth.json
- API tokens/keys
- lazy-packages/
- cache/
- logs/
- gateway pid/lock/socket files
- temporary files

Write a text manifest beside the archive listing included paths, archive size, creation time, Hermes version, and SHA-256 checksum.

## Restore
1. Never restore directly over a live brain without first making a pre-restore snapshot.
2. Stop or quiesce the writer if possible so state.db is consistent.
3. Inspect the archive contents before extraction.
4. Restore only the requested components.
5. Preserve current .env/auth unless Hasan explicitly asks for credential recovery.
6. Restart/reload Hermes only if required.
7. Verify memory files, skill discovery, session search, Telegram gateway health, and cron jobs after restoration.

## Off-volume copies
A backup stored only under /data protects against accidental edits but not volume deletion. Once Hasan authorizes Google Drive or another remote store for Hermes, copy safe backup archives there as the preferred disaster-recovery layer.

## Never
Do not send .env, auth.json, raw tokens, or provider secrets in Telegram or commit them to a public repository.
