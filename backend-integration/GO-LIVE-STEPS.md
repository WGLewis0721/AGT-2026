# AGT Post-PR Go-Live Guide (Step-by-Step)

Use this checklist **after your PR is merged** to finish the app and make booking automation fully live.

---

## 0) Prerequisites (5–10 min)

You need active access to:

- GitHub repo admin (for merge + Pages)
- Cloudflare account (Workers)
- Cal.com account (event type + webhook settings)
- Airtable account (base + table + PAT)
- Twilio account (SMS sender)
- Resend account (email sender)

---

## 1) Merge PR + verify website deploy (2–5 min)

1. Merge the PR into `main`.
2. Confirm GitHub Pages still loads:
   - `https://wglewis0721.github.io/AGT-2026/`
3. Open the page and verify booking section still loads the Cal.com embed.

Success criteria:

- Website loads
- No broken layout
- Booking section visible and interactive

---

## 2) Create Airtable table exactly once (10 min)

1. In Airtable, create a base (or use existing) and table named: `Bookings`.
2. Add these fields exactly (recommended types in parentheses):
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
3. Generate Airtable PAT with write access to that base/table.
4. Copy and save:
   - `AIRTABLE_PAT`
   - `AIRTABLE_BASE_ID`
   - `AIRTABLE_TABLE_NAME` (usually `Bookings`)

Success criteria:

- You can manually add a row in Airtable.
- PAT has API write permission.

---

## 3) Prepare Twilio + Resend (10–20 min)

### Twilio (SMS)

1. Buy/select a Twilio number.
2. Confirm SMS capability for your region.
3. Save credentials:
   - `TWILIO_ACCOUNT_SID`
   - `TWILIO_AUTH_TOKEN`
   - `TWILIO_FROM` (Twilio number)
   - `LEAD_DETAILER_PHONE` (destination number in E.164, e.g., `+13345551234`)

### Resend (Email)

1. Verify sender domain or use a verified sender.
2. Save:
   - `RESEND_API_KEY`
   - `NOTIFY_EMAIL_FROM` (verified sender)
   - `NOTIFY_EMAIL_TO` (recipient inbox)

Success criteria:

- Twilio can send a test SMS from console.
- Resend can send a test email from console.

---

## 4) Deploy Cloudflare Worker (10 min)

From your local machine:

```bash
cd backend-integration
npm install -g wrangler
wrangler login
```

Create `wrangler.toml`:

```toml
name = "agt-booking-worker"
main = "worker.js"
compatibility_date = "2025-01-01"
```

Set secrets (you’ll be prompted for each value):

```bash
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

Deploy:

```bash
wrangler deploy
```

Check health:

```bash
curl https://<your-worker-subdomain>.workers.dev/health
```

Success criteria:

- Returns `{ "ok": true, "service": "agt-booking-worker" }`.

---

## 5) Connect Cal.com webhook (5–10 min)

In Cal.com:

1. Open your event type settings.
2. Add webhook URL:
   - `https://<your-worker-subdomain>.workers.dev/webhooks/cal`
3. Subscribe events:
   - `BOOKING_CREATED`
   - `BOOKING_RESCHEDULED`
   - `BOOKING_CANCELLED`
4. Copy webhook signing secret.
5. Ensure that exact value is stored in Worker secret:
   - `CALCOM_WEBHOOK_SECRET`

Success criteria:

- Cal.com webhook test (if available) returns 2xx.

---

## 6) Run end-to-end test booking (10 min)

1. Book a real test appointment via the live website booking flow.
2. Confirm:
   - Airtable gets a new row.
   - Lead detailer receives SMS.
   - Lead detailer receives email.
3. Reschedule same booking and verify rescheduled notification flow.
4. Cancel same booking and verify cancelled notification flow.

Success criteria:

- All three event types process without manual intervention.

---

## 7) Final production hardening (recommended)

1. Keep `ALLOW_UNSIGNED_WEBHOOKS` unset in production.
2. Rotate all secrets once after initial validation.
3. Limit who can edit webhook endpoints/secrets.
4. Add Airtable view filtered by today/upcoming jobs for operations.
5. Document owner + backup owner for each SaaS account.

---

## 8) What to tell your client once done

Use this message:

> “Your booking automation is now fully live. New Cal.com bookings are captured automatically, saved into Airtable, and sent to the lead detailer by SMS and email in real time. Reschedules and cancellations are also automated.”

If testing is still pending, use this instead:

> “The booking automation build is complete and deployed. We are in final live validation (test booking/reschedule/cancel) before production sign-off.”

---

## 9) Fast rollback plan (if needed)

If notifications misfire:

1. Temporarily disable Cal.com webhook.
2. Keep website live (no frontend downtime required).
3. Fix secrets/payload mapping.
4. Re-enable webhook and rerun one test booking.

---

## 10) Ownership checklist

- [ ] PR merged
- [ ] Worker deployed
- [ ] Secrets configured
- [ ] Webhook connected
- [ ] Booking created test passed
- [ ] Booking rescheduled test passed
- [ ] Booking cancelled test passed
- [ ] Client confirmation sent
