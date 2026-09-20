# Claude Handoff — Rebuild Maw3idi / WhatsApp Booking Dashboard

## Mission

Take the existing WhatsApp booking product in this folder and turn it into a genuinely high-end, client-ready SaaS dashboard.

Do **not** merely reskin the existing HTML. The current dashboard works as a functional control panel but looks like a prototype. Rebuild the UX, information architecture, onboarding, WhatsApp connection flow, QR experience, empty states, client management, and visual system while preserving the working booking/WhatsApp backend.

The goal is something that feels closer to a polished modern SaaS product than an internal admin page.

## Source of truth

Repository:
`hsndm566/hermes-agent-template`

Branch:
`cf-dns-once-20260919`

Product folder:
`whatsapp-bot/`

A complete concatenated source copy is available in:
`whatsapp-bot/FULL_SOURCE_EXPORT.md`

Do not modify unrelated Hermes, Broast, Cloudflare, or repository files outside `whatsapp-bot/`.

## Current deployment

The current product runs on Railway as one memory-optimized Docker service.

Runtime components:
- FastAPI backend
- Evolution API v2.3.7 / Baileys
- PostgreSQL
- Redis
- reminder scheduler
- static dashboard frontend
- automatic remote PostgreSQL snapshot backup/restore via Supabase RPC

The stack has already passed deployed tests for:
- Arabic and English booking flows
- explicit first-message language selection
- customer language memory
- service selection
- availability generation
- appointment creation
- rescheduling and cancellation
- location / prices / hours / appointment lookup
- reminders
- Evolution instance creation
- QR / pairing payload generation
- persistence restore across a fresh Railway redeploy

Preserve those capabilities.

## Why this redesign is needed

The current frontend is plain HTML/CSS/JavaScript and feels basic.

Observed UX failures:
1. After adding a business, the user does not clearly land in a dedicated WhatsApp connection step.
2. The QR code is not visually central to onboarding and can feel like it disappeared or was never created.
3. Business creation and WhatsApp pairing feel like unrelated actions instead of one guided setup journey.
4. The dashboard lacks a high-end design system, visual hierarchy, motion, spacing, polished typography, loading states, skeletons, and premium empty states.
5. There is no strong “business workspace” concept after selecting a client.
6. The current status checklist is functional but visually primitive.
7. Client setup does not give enough confidence about what will happen before going live.
8. The bot personality setup needs an actual live preview.
9. The admin should immediately understand: connected number, bot state, last inbound message, upcoming bookings, backup status, and whether the client is genuinely ready.
10. Mobile UX needs to be first-class, not just responsive desktop.
11. The existing frontend should not be treated as sacred. Replace it if necessary.

## Critical QR / onboarding requirement

This is the biggest UX problem.

Rebuild onboarding as an explicit wizard:

### Step 1 — Business
Collect:
- Arabic business name
- English business name
- WhatsApp/business phone
- Google Maps URL
- optional VAT / CR

### Step 2 — Bot identity
Collect:
- Arabic bot name
- English bot name
- tone/personality
- optional Arabic welcome
- optional English welcome

Show a live chat preview on the right side.

### Step 3 — Services
Create/edit multiple services:
- Arabic name
- English name
- duration
- price SAR
- buffer

### Step 4 — Schedule
Let user visually set normal weekly working hours.
Provide Ramadan schedule as a separate expandable mode.
Show prayer-buffer controls clearly.

### Step 5 — Connect WhatsApp
This step must be impossible to miss.

After business creation:
- keep the wizard open
- create the Evolution instance
- display a large QR card
- show instructions:
  WhatsApp > Linked Devices > Link a Device
- allow Refresh QR
- show connection polling in real time
- show “Waiting for scan”
- transition automatically to “Connected”
- never close the wizard before connection unless user explicitly chooses “Finish later”

QR states:
- creating instance
- QR available
- waiting for scan
- QR expired / refresh
- connected
- failed with actionable retry

### Step 6 — Real test
Once connected:
- recipient field
- language selector
- Send real test
- tell user to reply from the recipient phone
- Check reply / automatically poll
- only mark the client READY after a fresh reply from the same phone after test start

Show a satisfying completion state:
“Your WhatsApp receptionist is live.”

## First-customer behavior

A new WhatsApp customer must receive:

اختر اللغة / Choose your language

1. العربية
2. English

Accept:
- 1
- ١
- Arabic text
- 2
- ٢
- English text

Persist their choice.

The rest of their messages, confirmations, reminders, cancellation/rescheduling messages, and follow-up should respect that saved language.

## Bot personality

Per business:
- Friendly
- Professional
- Premium
- Concise

Allow custom Arabic and English welcome text.

Add a preview panel that shows:
- language-choice message
- greeting
- service menu
- example booking confirmation

The user should understand exactly what customers will see before connecting WhatsApp.

## New dashboard information architecture

Replace the current tab-heavy prototype with a polished app shell.

Suggested desktop structure:

Left sidebar:
- Overview
- Inbox / Conversations
- Appointments
- Customers
- Services
- Team
- Availability
- Bot & WhatsApp
- Automations
- Settings

Business switcher at top of sidebar.

Mobile:
- compact top bar
- bottom nav for key areas
- sheet/drawer for secondary settings

## Overview page

Show:
- WhatsApp connection status
- “Client ready” status
- today’s appointments
- upcoming appointments
- total customers
- no-shows
- messages handled
- latest inbound customer interaction
- backup freshness
- connection uptime/status
- onboarding completion progress if setup is incomplete

Add a premium activity feed.

## WhatsApp page

Must feel like a dedicated integration page.

Cards:
1. Connection
2. Linked business number
3. QR reconnect panel
4. Latest inbound event
5. Send test
6. Live receive test
7. Connection health
8. Disconnect / reconnect controls

Never bury QR behind an ambiguous button.

## Inbox / Conversations

The current system tracks last inbound state but does not provide a true inbox.

Build a conversation-oriented screen using available data, and if backend changes are needed, add a tenant-safe messages table.

Desired layout:
- conversation list
- customer name/phone
- last message
- language badge
- appointment status
- conversation pane
- system/bot messages visually distinct
- timestamps
- search

Do not expose another business’s data.

## Appointments

Modern calendar + list:
- day/week view where practical
- status filters
- upcoming
- completed
- cancelled
- no-show
- customer
- service
- staff
- time
- actions

Actions:
- reschedule
- cancel
- mark complete
- mark no-show

## Customers

Customer CRM-lite:
- name
- phone
- preferred language
- visits
- next appointment
- last visit
- no-show count
- conversation link

## Design direction

Premium Saudi SaaS.

Avoid:
- generic Bootstrap-looking dashboard
- huge gradients everywhere
- toy-like rounded cards
- excessive glassmorphism
- overly bright startup clichés
- emoji as primary UI icons

Aim for:
- sophisticated neutral palette
- warm off-white / charcoal / subtle green accent or another restrained palette
- excellent Arabic typography
- proper RTL and LTR mirroring
- Lucide-style iconography
- strong spacing rhythm
- compact but readable cards
- refined shadows/borders
- smooth micro-interactions
- excellent mobile behavior
- accessible contrast
- deliberate empty/loading/error states

Arabic should feel native, not translated afterthought.

## Frontend architecture

You may replace the current frontend completely.

Preferred approach:
- React + Vite + TypeScript
- Tailwind CSS
- high-quality accessible component primitives
- build static assets and serve them from the existing FastAPI container

Why:
- keeps the existing Railway architecture
- avoids introducing a second production service
- preserves memory constraints
- allows modern componentized UI

Do not introduce Next.js unless there is a strong operational reason.

Keep API calls behind a single typed client module.

## Backend contracts to preserve

Current important route families include:

- /health
- /ready
- /api/businesses
- /api/businesses/{id}
- /api/businesses/{id}/connection
- /api/businesses/{id}/qr
- /api/businesses/{id}/test-message
- /api/businesses/{id}/conversation-test-status
- /api/businesses/{id}/services
- /api/businesses/{id}/hours
- /api/businesses/{id}/staff
- /api/businesses/{id}/settings
- /api/businesses/{id}/profile
- /api/businesses/{id}/appointments
- /api/client-defaults
- /webhook/whatsapp

Inspect the actual FastAPI source before changing contracts.

If endpoints need to change, update frontend and self-tests together.

## Multi-tenancy requirement

This is mandatory.

Every business-owned table has `businessId`.

Every query must filter by `businessId`.

Never make a frontend or backend shortcut that can expose data across businesses.

## Persistence

Do not remove the current remote persistence mechanism until a better durable store is installed and tested.

Current runtime:
- local PostgreSQL inside Railway container
- continuous compressed snapshots to Supabase
- automatic restore on fresh deployment

It has been explicitly tested across redeployment.

If you replace this:
1. migrate existing data safely
2. prove persistence across a fresh redeploy
3. preserve Evolution session data
4. keep rollback possible

## Authentication

The current demo dashboard has authentication intentionally bypassed because the old username/password login failed for the owner.

Do not leave this permanently public for production.

For redesign:
- keep local/demo friction low
- introduce a proper secure admin-access solution
- never reintroduce a brittle hardcoded password UX

Possible options:
- one secure owner session
- magic-link style access
- proper auth provider

But do not block the UX redesign on auth.

## Current important environment variables

Never hardcode real values.

Use placeholders for:
- DATABASE_URL
- REDIS_URL
- EVOLUTION_INTERNAL_URL
- EVOLUTION_API_KEY
- EVOLUTION_WEBHOOK_URL
- WHATSAPP_WEBHOOK_SECRET
- APP_PUBLIC_URL
- SESSION_SECRET
- TZ
- DEFAULT_TEST_PHONE
- WA_PERSIST_URL
- WA_PERSIST_KEY
- WA_BACKUP_SECRET
- WA_BACKUP_INTERVAL_SECONDS

Do not print live secrets.

## Deployment constraints

Current Railway Free plan is memory constrained.

The optimized production service has previously stabilized around 0.35–0.4 GB RAM.

Do not introduce:
- another Node production server
- heavyweight SSR
- unnecessary background processes

Frontend Node tooling is fine at build time.

Production should ideally remain:
- one runtime service
- FastAPI serves compiled frontend
- Evolution API
- Redis
- PostgreSQL
- backup scheduler

## Existing automated tests

Preserve and extend:
- selftest.py
- persistence_probe.py
- /health
- /ready

Before declaring success, test:

1. business creation
2. QR generation
3. QR refresh
4. connection state polling
5. real send test
6. fresh same-phone inbound reply
7. Arabic first conversation
8. English first conversation
9. language persistence
10. service menu
11. availability
12. appointment creation
13. reschedule
14. cancel
15. location intent
16. working-hours intent
17. prices intent
18. upcoming appointment lookup
19. reminders
20. persistence across redeploy
21. mobile layout
22. RTL layout
23. empty state
24. loading state
25. Evolution unavailable state

## Definition of done

Do not tell me it is finished because pages render.

It is done when:

- the dashboard looks like a premium commercial SaaS
- onboarding is genuinely easy for a nontechnical business owner
- QR connection is obvious and reliable
- user never wonders “where is the QR?”
- business workspace feels complete
- Arabic is first-class RTL
- English is polished LTR
- mobile feels intentional
- real WhatsApp send/reply proof works
- existing booking engine still passes
- tenant isolation remains intact
- persistent restore still works
- frontend has a maintainable component architecture
- no secrets are committed
- production memory remains within Railway constraints

## How to work

First audit the existing codebase.

Then propose:
1. architecture changes
2. new frontend component tree
3. backend changes required
4. data-model changes if any
5. migration plan
6. rollout plan

Then implement.

Do not ask me to manually rewrite files one by one.

Make the changes directly in the codebase.

Prioritize a polished end-to-end experience over preserving the existing frontend implementation.

## Owner feedback that triggered this rebuild

The owner personally tried the current product and reported:

- “I added my business and then it somehow didn't work.”
- “There's no place to put in the QR code.”
- “This looks like a basic HTML website.”
- “It doesn't seem high-end.”
- “I want something a lot better than this.”

Treat that as product feedback, not merely visual feedback.

The redesign must fix the product journey, especially the post-business-creation QR experience.
