# Maw3idi — Phase Build Plan

## Goal
A sellable in-person demo: a store owner can add their business, connect WhatsApp by QR, send/receive a real test, and let a customer book in Arabic or English.

## Phase 0 — Proven transport/runtime — COMPLETE
- Evolution API 2.3.7 / Baileys
- FastAPI
- PostgreSQL
- Redis
- durable booking + Evolution database snapshots to Supabase
- automatic restore after a fresh Railway deployment
- health/readiness endpoints
- reminder scheduler
- signed Evolution webhook
- duplicate-message protection

## Phase 1 — Premium operator dashboard — COMPLETE
- React + TypeScript + Vite + Tailwind
- Arabic-first RTL + English LTR
- premium application shell
- 10 dashboard areas
- six-step onboarding
- bot personality preview
- services + hours configuration
- full-width QR connection step
- 3-second connection polling
- QR refresh
- real send/reply test
- mobile-responsive navigation

## Phase 2 — Real backend administration — COMPLETE
- signed-cookie admin auth
- rate-limited login
- customer endpoint
- appointment cancel/complete/no-show
- existing booking.py cancel/reschedule logic reused
- Evolution WhatsApp disconnect
- real appointment schema statuses reflected in UI
- settings/profile/team/services/hours wired to the real backend

## Phase 3 — Live customer proof — READY, REQUIRES PHONE SCAN
This is not additional engineering. It is the physical authorization step:
1. log in to Maw3idi
2. add a demo/client business
3. scan the generated QR from the WhatsApp account that will act as the business bot
4. send the real test to +966596573391
5. reply from +966596573391
6. dashboard verifies the fresh same-phone inbound reply
7. message the connected business number and complete a booking

Stop here once this passes. At this point the core product is demo/sales ready.

## Later — only after first client
Do not block the demo on these:
- full conversation-history/messages table
- human handoff / Chatwoot
- n8n workflow builder
- LLM free-form FAQ layer
- billing/subscriptions
- official multi-user tenant accounts
- Evolution Go evaluation
- VPS/Caddy migration
- official WhatsApp Business Platform migration
