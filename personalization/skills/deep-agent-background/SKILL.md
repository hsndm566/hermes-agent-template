---
name: deep-agent-background
description: Run a harmless request through the durable My Agent Deep Agent boundary when the owner asks for background work.
---
# Durable background work

When the owner explicitly asks for a background task, run the existing durable
boundary and return the JSON result, including its `run_id`, status, and model
provider:

```bash
python /app/scripts/deep-agent-run.py "<the owner's exact harmless task>"
```

The command creates and queues a Supabase `agent_control.runs` row, leases it,
uses the configured remote model, records a verified artifact, and archives the
queue message only after completion. Never print credentials or claim completion
if the command reports failure.