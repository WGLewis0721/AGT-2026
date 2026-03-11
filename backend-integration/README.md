# AGT Booking Notification Backend (Cal.com → Airtable → SMS/Email)

This is a **fully automatic**, low-cost backend workflow you can run on the Cloudflare free tier.

## What this does

1. Receives Cal.com webhook events (`BOOKING_CREATED`, `BOOKING_RESCHEDULED`, `BOOKING_CANCELLED`).
2. Verifies the webhook signature (HMAC SHA-256).
3. Saves booking/customer details into Airtable.
4. Sends your lead mobile detailer an SMS (Twilio) and/or email (Resend).

---

## Low/Freemium Stack

- **Cloudflare Workers** (free tier) for webhook endpoint logic
- **Airtable** (free tier) as CRM/bookings DB
- **Resend** (free tier) for email notifications
- **Twilio** (pay-as-you-go) for SMS notifications

> If you want 100% free, disable SMS and keep email.

---

## New: post-PR execution guide

Use [`GO-LIVE-STEPS.md`](./GO-LIVE-STEPS.md) for the exact step-by-step sequence to finish setup after PR merge.

---

## Airtable setup

Create a base with one table named `Bookings` and these fields:

- `Booking Status` (single line text)
- `Provider` (single line text)
- `Event Type` (single line text)
- `External Booking ID` (single line text)
- `Event Type ID` (single line text)
- `Customer Name` (single line text)
- `Customer Email` (email)
- `Customer Phone` (phone)
- `Start Time (UTC)` (single line text or date/time)
- `End Time (UTC)` (single line text or date/time)
- `Timezone` (single line text)
- `Service` (single line text)
- `Location` (long text)
- `Notes` (long text)
- `Created At` (date/time)

Create a personal access token with access to this base/table.

---

## Deploy Worker

### 1) Install Wrangler

```bash
npm install -g wrangler
```

### 2) Create `wrangler.toml`

In `backend-integration/wrangler.toml`:

```toml
name = "agt-booking-worker"
main = "worker.js"
compatibility_date = "2025-01-01"
```

### 3) Set secrets

```bash
cd backend-integration
wrangler secret put CALCOM_WEBHOOK_SECRET
wrangler secret put AIRTABLE_PAT
wrangler secret put AIRTABLE_BASE_ID
wrangler secret put AIRTABLE_TABLE_NAME
wrangler secret put LEAD_DETAILER_PHONE
wrangler secret put TWILIO_ACCOUNT_SID
wrangler secret put TWILIO_AUTH_TOKEN
wrangler secret put TWILIO_FROM
wrangler secret put RESEND_API_KEY
wrangler secret put NOTIFY_EMAIL_TO
wrangler secret put NOTIFY_EMAIL_FROM
```

Optional (local/dev only):

```bash
wrangler secret put ALLOW_UNSIGNED_WEBHOOKS
```

Set value to `true` only for temporary testing.

### 4) Deploy

```bash
wrangler deploy
```

Endpoint:

`https://agt-booking-worker.<subdomain>.workers.dev/webhooks/cal`

---

## Cal.com webhook setup

In Cal.com:

1. Open your event type(s) and go to webhook settings.
2. Add webhook URL: `https://...workers.dev/webhooks/cal`
3. Subscribe to events:
   - `BOOKING_CREATED`
   - `BOOKING_RESCHEDULED`
   - `BOOKING_CANCELLED`
4. Copy the webhook signing secret into `CALCOM_WEBHOOK_SECRET`.

---

## How close to 100% this is

What is already implemented in code:

- End-to-end processing path (webhook → Airtable → SMS/email)
- Signature verification and event filtering
- Support for created/rescheduled/cancelled booking events
- Safe fallbacks for missing optional fields

What still requires your account-level setup:

- Cloudflare Worker deployment
- Airtable table creation + token permissions
- Cal.com webhook subscription + secret
- Twilio/Resend sender verification and live credentials

Once those four are done and one live booking succeeds, your automation is effectively production-ready.

---

## 15-minute go-live checklist

- [ ] Worker deployed and `/health` returns `{ ok: true }`
- [ ] Airtable receives test booking row
- [ ] SMS received by lead detailer
- [ ] Email received by lead detailer
- [ ] Cancel/reschedule events correctly update status flow in notifications

---

## Example SMS

```text
🚘 AGT SCHEDULED
John Smith (+13345551234)
Premium Interior + Exterior Detail
Start: 2026-03-14T15:00:00Z
Location: 555 Main St, Montgomery, AL
Email: john@example.com
Notes: vehicleType: SUV | addons: Engine Bay
```
