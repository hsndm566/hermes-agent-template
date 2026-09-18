Hermes runs persistently on Railway from hsndm566/hermes-agent-template. Railway project/service: hermes-agent. HERMES_HOME=/data/.hermes on the persistent `hermes-data` volume mounted at /data. Telegram bot is the primary daily interface. Persistent files include SOUL.md, memories/, skills/, state.db, sessions/, config.yaml, cron/, workspace/, plans/, and lazy-packages/.

Hasan's old laptop Hermes was backed up to Google Drive under `hermes agent`, including old USER.md/MEMORY.md, skills, sessions and kanban files. Do not depend on that laptop for continuity. Use the Railway instance as the permanent brain.

Core operating rule: prefer existing open-source solutions, inspect before changing, make the smallest safe fix, verify afterward, and store repeatable procedures as skills. Use session_search before asking Hasan to restate earlier discussions.

AutoApply SA is Hasan's main startup: Saudi-focused job application workflow with human approval before external submission. Live production repos must not be modified casually; new work generally belongs in autoapply-labs and significant production changes should be planned and verified.

Hasan also builds websites for local Saudi businesses, experiments with lead-finding and WhatsApp bots, and uses GitHub/Railway frequently. He wants the agent to remain useful from Telegram without depending on ChatGPT or his laptop.

For large personal/project context, read `/data/.hermes/knowledge/hasan-operating-context.md` through the `hasan-context` skill rather than bloating core memory.
