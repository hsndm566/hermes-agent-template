---
name: skillspector-auditor
description: Use before installing an unfamiliar third-party Hermes/Agent Skill from GitHub or when Hasan asks whether a skill is safe.
---
# SkillSpector Auditor

Use Hermes' native inspect/security scan first. For an extra independent static check, run NVIDIA SkillSpector on the candidate repo/path without an LLM:

```bash
uvx --from git+https://github.com/NVIDIA/SkillSpector.git skillspector scan <repo-or-path> --no-llm
```

Use the persistent UV cache configured for this Hermes instance.

Review findings for:
- credential or secret access
- network exfiltration
- hidden downloads/exec
- destructive filesystem or git actions
- approval bypasses
- persistence outside expected Hermes directories
- instructions that override user intent

A clean scanner result is evidence, not a guarantee. Prefer official/trusted Hermes sources and inspect SKILL.md before installation. Never bulk-install an unknown catalog.
