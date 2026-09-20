# Maw3idi — Demo Runbook

## Live product
https://cloudflare-github-runner-production.up.railway.app

## Login
The live credentials are held in Railway environment variables:
- ADMIN_USERNAME
- ADMIN_PASSWORD

Do not commit them to GitHub.

## Before a sales demo
You need two WhatsApp identities:
- Sender/business account: the WhatsApp account the store owner scans into Maw3idi.
- Test/customer account: +966596573391.

The sender and recipient must be different accounts for a meaningful send/reply test.

## Setup
1. Open the live URL and sign in.
2. Click New business / منشأة جديدة.
3. Business details: add Arabic/English name, the store WhatsApp number, and Maps link.
4. Bot identity: choose bot names, tone, and optional greetings.
5. Services: add at least one service, duration, price, and buffer.
6. Hours: configure the weekly schedule.
7. Create business. Do not leave the wizard: it moves directly to Connect WhatsApp.

## Connect WhatsApp
On the store's WhatsApp phone:
WhatsApp > Settings > Linked Devices > Link a Device

Scan the large QR shown in Maw3idi.
The dashboard polls every 3 seconds and changes to Connected automatically.

## Real test
The test field is configured to prefill:
+966596573391

1. Select Arabic or English.
2. Send Test.
3. On +966596573391, reply to the WhatsApp message.
4. Maw3idi checks the inbound webhook automatically.
5. A pass requires the SAME phone to reply AFTER the test started.

## Customer conversation
From +966596573391 message the connected store number.

Expected first response:
اختر اللغة / Choose your language:
1. العربية
2. English

Arabic:
- reply ١
- choose a service
- choose a slot
- provide a name
- verify booking confirmation

Useful Arabic commands:
- الموقع
- الأسعار
- ساعات العمل
- موعدي
- إلغاء
- تغيير
- لغة

English equivalents are also supported.

## Definition of demo-ready
- /ready returns 200
- Postgres healthy
- Redis healthy
- Evolution healthy
- WhatsApp connection shows Connected
- real test passes
- Arabic or English booking reaches confirmation
- booking appears in Appointments
- customer appears in Customers

## Rollback
The pre-premium production commit was:
51c032ca97577bc270e3dc70bf49cbee966818e7

Do not roll back unless the new production build becomes unhealthy.
