---
name: github-failure-doctor
description: Use when Hasan says a GitHub Action, CI run, deployment check, build, test, or workflow failed and wants it diagnosed or fixed.
---
# GitHub Failure Doctor

1. Identify the exact repo, branch/commit, failed workflow and failed job.
2. Read annotations and logs. Find the first actionable failure, not the last cascade error.
3. Reproduce or validate the failure when possible.
4. Make the smallest safe change that addresses the root cause.
5. Avoid unrelated refactors.
6. Rerun or verify the relevant workflow/check.
7. Do not report success until the required checks are actually green.
8. Summarize: root cause, files changed, verification, anything still blocked.

For production repos, preserve existing behavior and use a branch/PR unless Hasan explicitly directs otherwise.
