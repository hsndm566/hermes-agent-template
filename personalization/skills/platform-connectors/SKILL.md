# Platform connectors

Use the owner's connected services through the configured MCP servers and
secret-backed APIs. This skill is available only to the authenticated Telegram
owner; never broaden Telegram access and never ask the owner to paste a secret
into chat.

## Connected services

- `github`: GitHub's hosted MCP server, enabled when `MCP_GITHUB_API_KEY` (or
  the Northflank `GITHUB_TOKEN` alias) exists.
- `supabase`: Supabase's hosted MCP server, scoped to `SUPABASE_PROJECT_REF`.
- `clerk`: Clerk's official documentation and SDK MCP server.
- `google-workspace`: an optional private MCP URL supplied by
  `GOOGLE_WORKSPACE_MCP_URL`. The built-in `google-workspace` skill remains
  available for OAuth-backed Drive, Docs, Sheets, Slides, Gmail, Calendar and
  Contacts workflows.
- `northflank`, `heroku`, and `clerk_api`: API connector inventory. Use their
  secret-backed API clients only when the corresponding env variable exists;
  do not invent credentials or send secrets to a model.

## Rules

1. Confirm the target service and intended scope before a write or destructive
   operation. Reads and health checks may be performed directly.
2. Keep operations scoped to the owner's configured project/account. For
   Supabase, never remove the project scope from the MCP URL.
3. Do not print, quote, or include environment values in Telegram replies,
   logs, artifacts, prompts, or command output. Report only redacted status.
4. If a connector is not configured, explain which Northflank variable is
   missing instead of falling back to another account or Railway.
