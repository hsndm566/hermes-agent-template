---
name: skillspector
description: Use before trusting or installing an unfamiliar third-party agent skill, GitHub skill pack, or SKILL.md source.
---
# SkillSpector

Use Hermes' native skill inspection/security scan first. For additional static review of unfamiliar community repositories, run NVIDIA SkillSpector on demand without permanently installing it into system Python:

```bash
uvx --from git+https://github.com/NVIDIA/SkillSpector.git skillspector scan <repo-or-path> --no-llm
```

Review findings before installation. Do not override a dangerous verdict merely because Hasan wants the capability. Prefer official/trusted sources when equivalent functionality exists. Record the source and installed version/provenance so future updates are auditable.
