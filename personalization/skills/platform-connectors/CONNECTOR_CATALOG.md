# Canonical MCP connector catalog

This is the deduplicated priority list for Hermes. A tool appears once under
its canonical service, with product aliases grouped beside it. “Remote MCP”
means Hermes can load an official HTTPS MCP endpoint. “Codex connector” means
the service is connected in this desktop session but its OAuth session is not
automatically portable to Northflank.

## Tier 1 — daily

| Rank | Canonical service | Aliases grouped here | Portability | Hermes state |
| ---: | --- | --- | --- | --- |
| 1 | Gmail / Google Workspace | Gmail, Drive, Docs, Sheets, Calendar, Contacts | Remote MCP + OAuth | Endpoint support added; enable Google OAuth once |
| 2 | GitHub | GitHub Actions, GitHub MCP | Official remote MCP + PAT/OAuth | Secret-backed endpoint added |
| 3 | Notion | Notion MCP | Official remote MCP / connector | Use the existing Notion connector or add a private MCP URL |

## Tier 2 — weekly

| Rank | Canonical service | Aliases grouped here | Portability | Hermes state |
| ---: | --- | --- | --- | --- |
| 4 | Supabase | Supabase MCP, database, Edge Functions | Official remote MCP | Project-scoped endpoint added |
| 5 | Cloudflare | Cloudflare MCP | Remote MCP / connector | Configure separately when the target account is selected |
| 6 | Heroku | Heroku MCP, Heroku API | Official remote MCP + OAuth | Endpoint added; enable OAuth or provide a scoped token |
| 7 | Resend | Email delivery | API/MCP connector | Keep as a separate scoped connector |
| 8 | Vercel | Deployments | API/MCP connector | Keep as a separate scoped connector |
| 9 | OpenRouter | Model routing | API provider | Already represented by Hermes provider settings |

## Tier 3 — monthly

| Rank | Canonical service | Aliases grouped here | Portability | Hermes state |
| ---: | --- | --- | --- | --- |
| 10 | Clerk | Clerk MCP, Clerk API, BetterAuth | Official remote MCP for SDK guidance; API for account data | Public MCP endpoint added; API token is optional |
| 11 | Northflank | Northflank API, deployment control | REST API | Secret-backed inventory added; no fabricated MCP endpoint |
| 12 | Firecrawl | Crawl4AI, Apify, Scrapyfy | MCP/API | Keep one web extraction backend selected at a time |
| 13 | Playwright | Playwright MCP, WhatsApp Web | MCP | Use only for explicit browser tasks |
| 14 | n8n | workflow automation | MCP/API | Add only when a concrete workflow endpoint exists |
| 15 | Telegram | WhatsApp, WhatsApp Business, Evolution API, Chatwoot | Native channel/API | Telegram is Hermes' authenticated owner channel |

## Deferred

Cloudflare, Resend, Vercel, Notion, n8n, and Northflank still need a selected
account plus a scoped credential or OAuth grant before they can be enabled in
the Northflank runtime. The rare/researched list (TinyFish, Exa, Semrush,
video tools, job tools, and duplicate WhatsApp transports) is intentionally
excluded from the runtime catalog until a real workflow needs it.

Never copy Codex's browser OAuth tokens into Telegram, Git, or Northflank
variables. Authenticate remote OAuth MCP servers from Hermes' dashboard, or
store a narrowly scoped token in Northflank secrets.
