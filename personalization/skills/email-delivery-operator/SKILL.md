---
name: email-delivery-operator
description: Use when Hasan wants to prepare, send, verify, troubleshoot, or automate professional email, job-application email, or legitimate business outreach.
---
# Email Delivery Operator

Goal: reliable, verifiable email delivery with correct content and attachments.

## Before sending
1. Confirm the intended sender identity and recipient source.
2. Use verified/public business or recruiter addresses; do not invent addresses from naming patterns.
3. Deduplicate recipients and avoid re-sending the same campaign blindly.
4. Build personalized content from known facts only.
5. When an attachment is required, verify the file exists, is non-empty, has the expected type/name, and is actually attached to the outgoing message.
6. If Hasan asks to review before send, create a true dry run and do not transmit until he approves.

## Sending
- Prefer the currently connected and verified delivery method.
- Keep per-recipient results so partial failures are visible.
- Respect provider rate limits and avoid spam-like bursts.
- Human approval remains required for AutoApply candidate submissions.

## Verification
"Sent" means the provider accepted the message and returned a message/request identifier. If delivery evidence, bounce state, or reply tracking is available, check it separately. Never claim inbox delivery from a local success flag alone.

## Troubleshooting
Separate authentication failures, DNS/domain failures, quota/rate limits, attachment construction errors, and provider-side rejection. Fix the first actionable cause and re-test with the smallest safe sample.

## Output
Keep reports compact: attempted, accepted, failed, skipped, attachment status, and any blocker.
