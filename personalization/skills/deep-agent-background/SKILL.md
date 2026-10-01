---
name: deep-agent-background
description: Run a harmless request through the durable My Agent Deep Agent boundary when the owner asks for background work.
---
# Durable background work

When the owner explicitly asks for a background task, use the **terminal tool**
with `background=true` and detach the worker immediately so the Telegram
coordinator does not hold the model turn open. Run this exact shape (the worker
sends the completion JSON back to the owner chat itself):

```bash
nohup python /app/scripts/deep-agent-run.py --telegram "<the owner's exact harmless task>" >/tmp/deep-agent-run.log 2>&1 &
```

The command creates and queues a Supabase `agent_control.runs` row, leases it,
uses the configured remote model, records a verified artifact, and archives the
queue message only after completion. The worker then sends the JSON result to
the
original Telegram owner chat. Do not substitute `sleep`, do not wait on the
background process, and never claim completion if the worker reports failure.