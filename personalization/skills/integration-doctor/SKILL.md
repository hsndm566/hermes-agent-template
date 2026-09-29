---
name: integration-doctor
description: Use when Hasan wants to connect, test, repair, or add an API provider, MCP server, OAuth app, Google service, scraper, or external integration to Hermes.
---
# Integration Doctor

Goal: make integrations actually work, not merely look configured.

## Procedure
1. Inspect current Hermes/Railway state before changing anything.
2. Identify the integration type: API key, OAuth, HTTP MCP, stdio MCP, CLI, webhook, or native Hermes plugin.
3. Verify the provider endpoint or integration status live before claiming it is broken or connected.
4. Distinguish these failure classes:
   - invalid/revoked credential
   - valid credential but no quota/credits
   - provider outage/rate limit
   - network/egress/IP block
   - wrong endpoint/model/provider label
   - missing runtime dependency
   - config saved but gateway not reloaded
5. Prefer Hermes-native setup and current official commands over hand-editing config.
6. Persist secrets only in Railway variables or Hermes' private .env/auth storage. Never print secret values.
7. For OAuth, do every machine-side step first and ask Hasan only for the browser approval/login that truly requires him.
8. After setup, run a real minimal request. A stored key is not proof of a working integration.
9. For messaging/inbound services, verify both directions when relevant.
10. Record durable quirks/workarounds in memory or patch this skill if they recur.

## MCP
Prefer hosted HTTP MCP when available on this Railway/Linux instance. For stdio MCP, verify the required runtime exists inside the container. Use Hermes' current MCP commands and inspect current docs when syntax is uncertain.

## Provider changes
Do not replace the working main model merely because a new provider was added. Add it as an alias/fallback first, test it, then switch only when Hasan asks or the evidence clearly supports the change.

## Verification
Report: what was connected, live test result, where the credential/config lives (without its value), and any remaining user-only action.
