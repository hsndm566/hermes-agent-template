# Canonical MCP connector catalog

This is the deduplicated priority list for Hermes. A tool appears once under
its canonical service, with product aliases grouped beside it. “Remote MCP”
means Hermes can load an official HTTPS MCP endpoint. “Codex connector” means
the service is connected in this desktop session but its OAuth session is not
automatically portable to Northflank.

## Tier 1 — daily

| Rank | Canonical service | Aliases grouped here | Portability | Hermes state |
| ---: | --- | --- | --- | --- |
| 1 | Gmail / Google Workspace | Gmail, Drive, Docs, Sheets, Calendar, Contacts | Remote MCP + OAuth | Free OAuth endpoint configured; authorize once |
| 2 | GitHub | GitHub Actions, GitHub MCP | Official remote MCP + PAT/OAuth | Free OAuth endpoint configured; PAT is optional |
| 3 | Notion | Notion MCP | Official remote MCP / connector | Free OAuth endpoint configured; authorize once |

## Tier 2 — weekly

| Rank | Canonical service | Aliases grouped here | Portability | Hermes state |
| ---: | --- | --- | --- | --- |
| 4 | Supabase | Supabase MCP, database, Edge Functions | Official remote MCP | Free project-scoped OAuth endpoint configured |
| 5 | Cloudflare | Cloudflare MCP | Remote MCP / connector | Free OAuth endpoint configured; authorize once |
| 6 | Heroku | Heroku MCP, Heroku API | Official remote MCP + OAuth | Free OAuth endpoint configured; token is optional |
| 7 | Resend | Email delivery | API/MCP connector | Add `RESEND_MCP_URL` and a scoped API key |
| 8 | Vercel | Deployments | Official remote MCP + OAuth | Free OAuth endpoint configured; authorize once |
| 9 | OpenRouter | Model routing | API provider | Already represented by Hermes provider settings |

## Tier 3 — monthly

| Rank | Canonical service | Aliases grouped here | Portability | Hermes state |
| ---: | --- | --- | --- | --- |
| 10 | Clerk | Clerk MCP, Clerk API, BetterAuth | Official remote MCP for SDK guidance; API for account data | Public MCP endpoint added; API token is optional |
| 11 | Northflank | Northflank API, deployment control | REST API | Secret-backed inventory added; no fabricated MCP endpoint |
| 12 | Firecrawl | Crawl4AI, Apify, Scrapyfy | MCP/API | Add `FIRECRAWL_MCP_URL`; keep one extraction backend selected |
| 13 | Playwright | Playwright MCP, WhatsApp Web | MCP | Add a private `PLAYWRIGHT_MCP_URL` for browser tasks |
| 14 | n8n | workflow automation | MCP/API | Add the workspace `N8N_MCP_URL` when available |
| 15 | Telegram | WhatsApp, WhatsApp Business, Evolution API, Chatwoot | Native channel/API | Telegram is Hermes' authenticated owner channel |

## Deferred

Resend, n8n, and Northflank still need a selected account plus a scoped
credential or self-hosted/free endpoint before they can be enabled in the
Northflank runtime. The official OAuth endpoints above do not require a paid
plan, but each account still requires one interactive authorization.
The rare/researched list (TinyFish, Exa, Semrush,
video tools, job tools, and duplicate WhatsApp transports) is intentionally
excluded from the runtime catalog until a real workflow needs it.

Never copy Codex's browser OAuth tokens into Telegram, Git, or Northflank
variables. Authenticate remote OAuth MCP servers from Hermes' dashboard, or
store a narrowly scoped token in Northflank secrets.
