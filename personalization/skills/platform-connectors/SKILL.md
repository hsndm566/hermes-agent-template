# Platform connectors

Use the owner's connected services through the configured MCP servers and
secret-backed APIs. This skill is available only to the authenticated Telegram
owner; never broaden Telegram access and never ask the owner to paste a secret
into chat.

## Connected services

- `github`: GitHub's hosted MCP server, enabled by the free OAuth flag or a
  scoped `MCP_GITHUB_API_KEY` (the Northflank `GITHUB_TOKEN` alias is also
  accepted).
- `supabase`: Supabase's hosted MCP server, scoped to `SUPABASE_PROJECT_REF`,
  using the free OAuth route or a scoped access token.
- `clerk`: Clerk's official documentation and SDK MCP server.
- `gmail`, `google-drive`, `google-calendar`, and `google-contacts`: Google's
  first-party OAuth MCP endpoints. They are configured by the free
  `GOOGLE_WORKSPACE_MCP_ENABLED` flag; authorization is account-scoped.
- `notion`, `cloudflare`, `heroku`, and `vercel`: official OAuth MCP endpoints
  configured by their corresponding free opt-in flags. A configured endpoint
  is not the same as an authorized account; report those states separately.
- `google-workspace`: an optional private MCP URL supplied by
  `GOOGLE_WORKSPACE_MCP_URL`.
- `northflank`, `resend`, `firecrawl`, `playwright`, `n8n`, and `clerk_api`:
  API or owner-supplied MCP inventory. Use a secret-backed client only when
  its corresponding env variable exists; do not invent credentials or send
  secrets to a model.

## Rules

1. Confirm the target service and intended scope before a write or destructive
   operation. Reads and health checks may be performed directly.
2. Keep operations scoped to the owner's configured project/account. For
   Supabase, never remove the project scope from the MCP URL.
3. Do not print, quote, or include environment values in Telegram replies,
   logs, artifacts, prompts, or command output. Report only redacted status.
4. When reporting status, list the redacted configured endpoint names first,
   then identify which services still need OAuth or a scoped token. Do not
   describe an endpoint as authorized merely because it is configured.
5. If a connector is not configured, explain which Northflank variable or
   opt-in flag is missing instead of falling back to another account.
