---
name: skill-upgrader
description: Use when Hasan asks Hermes to add, install, learn, copy, improve, replace, or discover a skill, plugin, workflow, agent capability, or GitHub skill.
---
# Skill Upgrader

Goal: let this Hermes improve itself safely without needing another assistant.

Workflow:
1. Search native Hermes sources first: `hermes skills search <query>`.
2. Inspect candidates before installation: `hermes skills inspect <identifier>`.
3. Prefer official/trusted sources, then established community sources.
4. For third-party GitHub skills, use Hermes' built-in security scan. When useful, run NVIDIA SkillSpector static analysis with:
   `uvx --from git+https://github.com/NVIDIA/SkillSpector.git skillspector scan <repo-or-path> --no-llm`
5. Do not bulk-install giant catalogs. Install the smallest useful skill or suite.
6. Install with `hermes skills install <identifier> --yes`.
7. Verify it appears in `hermes skills list` and note that a new session may be required.
8. If an installed skill has a better upstream version, use `hermes skills check` then `hermes skills update`.
9. If the source is not already a Hermes skill (docs, repo, workflow, file, conversation, or URL), use Hermes `/learn <source>` to turn it into a reusable skill, then inspect the generated result.
10. After a successful complex workflow, use `/refine` or the built-in background review so durable lessons can become memory/skill updates.
11. If the workflow is unique to Hasan and repeated, create or patch a local skill instead of forcing a generic one.
12. Keep provenance clear: know whether a skill is bundled, official, hub-installed, GitHub-sourced, or locally learned.

Never expose secrets or weaken approval/security settings merely to make an install pass.
