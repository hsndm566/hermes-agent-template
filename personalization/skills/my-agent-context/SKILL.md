---
name: my-agent-context
description: Use when Hasan asks about his portfolio, projects, prior decisions, profile, knowledge, or recent activity and the answer may live in the shared My Agent context store.
---
# Shared My Agent context

Use the existing owner-scoped context bridge for relevant records instead of
guessing or dumping all memory. Query only the terms needed for the request:

```bash
python /app/scripts/my-agent-context.py "<short query>"
```

Treat the returned JSON as source evidence. Cite the matching `source` in the
answer and say when no record was found. For an important owner/project fact
that should be shared across personas, persist it through the bridge:

```bash
python /app/scripts/my-agent-context.py write knowledge <key> "<fact>" <source>
```

Never print or reveal the bridge credential.
