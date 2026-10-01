---
name: deep-agent-background
description: Run a harmless request through the durable My Agent Deep Agent boundary when the owner asks for background work.
---
# Durable background work

When the owner explicitly asks for a background task, use the **terminal tool**
with `background=true` (so the Telegram coordinator does not hold the model
turn open) and run the existing durable boundary. Do not substitute `sleep` or
claim success without the script output:

```bash
python /app/scripts/deep-agent-run.py "<the owner's exact harmless task>"
```

The command creates and queues a Supabase `agent_control.runs` row, leases it,
uses the configured remote model, records a verified artifact, and archives the
queue message only after completion. Report the process completion JSON when
the background watcher returns it. Never print credentials or claim completion
if the command reports failure.
