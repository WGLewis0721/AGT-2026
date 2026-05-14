# SYSTEM CONTEXT — AGT Booking System

## Purpose
Reusable booking + payment system for service businesses.

## Stack
Frontend: GitHub Pages (vanilla JS — `index.html`, `booking.html`, `booking.js`, `success.html`)
Backend: AWS Lambda + API Gateway
Database: DynamoDB
Payments: Square (migrated from Stripe, May 2026)
Scheduling: Cal.com (optional, legacy path only — see below)
SMS: Textbelt
Infra: Terraform

## Core Rules
- DynamoDB = source of truth
- Square = payments only
- No business logic in frontend
- All pricing validated in backend
- SMS fires immediately on Square payment.updated — no Cal.com dependency

## Booking Flow (current — pre-appointment)

```
1. Customer opens booking.html
2. Selects appointment date + time (built-in calendar, 4 time slots)
3. Selects package (sm_detail / md_detail / lg_detail) and optional add-ons
4. Fills in customer info form (name, phone, email, address, vehicle year/make/model, notes)
5. Accepts service agreement waiver
6. booking.js POSTs all fields to POST /create-checkout
7. pricing_lambda.py recalculates price server-side, creates Square Payment Link
   → all booking context embedded in pipe-delimited payment_note
8. Customer pays deposit on Square checkout
9. Square fires payment.updated webhook (status COMPLETED)
10. lambda_function.py:
    a. Verifies HMAC-SHA256 signature
    b. Parses payment_note fields
    c. Writes full booking record to DynamoDB
    d. Sends detailer SMS immediately
    e. Sends customer SMS immediately (if phone present)
11. Square redirects to success.html → shows confirmation from sessionStorage
```

## Code Standards
- No duplicate logic
- No unused code
- No hardcoded secrets
- Validate all inputs
- Keep functions small

## Cost Constraint
< $10/month per client

## AI Rules
- Do not overengineer
- Do not introduce new services
- Prefer simple solutions

---

## Payment Provider: Square

**Current State (as of May 2026):**
TRA3 uses **Square** for payment processing. Stripe was fully replaced in May 2026.

### Square Integration Overview

**Pricing Lambda** (`pricing_lambda.py`):
- Creates Square Payment Links via the Square SDK v42+ (`squareup>=42.0.0`)
- Uses `client.checkout.payment_links.create()` API
- Supports sandbox and production environments via `SQUARE_ENVIRONMENT` env var (independent of AWS `ENVIRONMENT`)
- Receives customer fields from `booking.js` POST body; sanitizes all user input (strips `|` and `=`)
- Stores ALL booking context in pipe-delimited `payment_note` field (see format below)
- Returns checkout URL: `https://sandbox.square.link/...` (sandbox) or `https://squareup.com/checkout/...` (production)

**Webhook Lambda** (`lambda_function.py`):
- Verifies Square webhook signatures using HMAC-SHA256 (`x-square-hmacsha256-signature` header)
- Signature calculated over `notification_url + request_body`
- Listens for `payment.created` (ignored) and `payment.updated` (processed when `status == "COMPLETED"`)
- Extracts booking context from `payment.note` OR `payment.payment_note` OR `order.note` (checked in order)
- Logs `payment_note_debug` (note length + 200-char preview) on every processed payment
- SMS fires immediately — no Cal.com webhook needed

### payment_note Format

All fields pipe-delimited (`key=value|key=value|...`). User-supplied values are sanitized (no `|` or `=`).

```
package=sm_detail
addons=pet_hair,wax
total=200
deposit=40
balance=160
cal_url=https://cal.com/william-g.-lewis-ai51kb/mobile-detail-appointment-service-1
order_id=<uuid>
client=gentlemens-touch
environment=prod
appointment_date=2026-05-20         ← ISO date YYYY-MM-DD
appointment_time=09:00              ← 24-hour HH:MM
cal_event_id=                       ← reserved, usually empty
customer_name=John Smith
customer_phone=3345551234
customer_email=john@example.com
customer_address=123 Main St, City AL 36301
vehicle=2022 Toyota Camry
special_instructions=Please park in driveway
waiver=2026-05-14T12:00:00Z         ← ISO timestamp of waiver acceptance
```

### Display Name Mappings (lambda_function.py)

**PACKAGE_DISPLAY** (used when building SMS):

| Key | Display |
|---|---|
| `sm_detail` | Essential Detail |
| `md_detail` | Signature Detail |
| `lg_detail` | Executive Detail |

**ADDON_DISPLAY** (11 entries — comma-separated keys → human names):

| Key | Display |
|---|---|
| `pet_hair` | Pet Hair Removal |
| `shampooing` | Interior Shampooing |
| `upholstery` | Upholstery Shampoo |
| `wax` | Hand Wax Upgrade |
| `steam` | Steam Cleaning |
| `polishing` | Machine Polishing |
| `headlights` | Headlight Restore |
| `odor` | Odor Elimination |
| `engine_bay` | Engine Bay Clean |
| `tire_dressing` | Tire Dressing |
| `leather` | Leather Treatment |

### Display Helpers (lambda_function.py)

| Function | Input | Output |
|---|---|---|
| `_format_iso_date(date_str)` | `"2026-05-20"` | `"Wed, May 20, 2026"` |
| `_format_24h_time(time_str)` | `"09:00"` | `"9:00 AM"` |
| `_format_addon_display(raw)` | `"pet_hair,wax"` | `"Pet Hair Removal, Hand Wax Upgrade"` |
| `_sanitize_note_value(v)` | any str | strips `\|` and `=` |

### Required Credentials (stored in AWS SSM)

```
/tra3/gentlemens-touch/prod/square_access_token          # Sandbox or Production Access Token
/tra3/gentlemens-touch/prod/square_location_id           # Square Location ID
/tra3/gentlemens-touch/prod/square_webhook_signature_key # Webhook signature key from Square Developer Console
```

**Current deployment uses production credentials** (`square_environment = "production"` in `prod.tfvars`).

### Square Developer Console Setup

1. Create application at `developer.squareup.com`
2. Get Access Token + Location ID from appropriate tab (Sandbox or Production)
3. Register webhook subscription:
   - URL: `https://c4eki550u8.execute-api.us-east-1.amazonaws.com/webhook`
   - Events: `payment.created`, `payment.updated`
   - Copy Signature Key after saving
4. Store all three values in SSM (see paths above)
5. Run `.\backend-integration\scripts\deploy.ps1` to deploy

### Lambda Layer Requirements

**Critical:** The Square SDK v42+ depends on `pydantic` v2, which has native Rust extensions (`pydantic_core`). When rebuilding the Lambda layer on Windows, the bootstrap script **must** force Linux-compatible wheel downloads:

```powershell
pip install -r requirements.txt -t $pythonDir `
  --platform manylinux2014_x86_64 `
  --implementation cp `
  --python-version 311 `
  --only-binary=:all:
```

Without these flags, Windows-compiled binaries are downloaded and Lambda fails with `No module named 'pydantic_core._pydantic_core'`.

The layer requirements file is `backend-integration/layer/requirements.txt` (NOT `pricing-requirements.txt`).

---

## DynamoDB Schema

Booking records are written by `lambda_function.py` on Square `payment.updated` (status COMPLETED).

Partition key: `booking_id` (= Square order UUID)

| Field | Type | Notes |
|---|---|---|
| `booking_id` | String | Square order UUID (partition key) |
| `status` | String | `"confirmed"` on payment |
| `payment_status` | String | `"paid"` on payment |
| `paid_at` | String | ISO timestamp |
| `updated_at` | String | ISO timestamp |
| `square_payment_id` | String | |
| `square_order_id` | String | |
| `square_amount_total_cents` | Number | Deposit in cents |
| `customer_name` | String | From payment_note |
| `customer_phone` | String | E.164 normalized (optional) |
| `customer_email` | String | From payment_note or Square buyer email |
| `service` | String | Display name e.g. "Essential Detail" |
| `addons` | String | Comma-separated display names (optional) |
| `address` | String | Service address (optional) |
| `appointment_date` | String | Formatted e.g. "Wed, May 20, 2026" |
| `deposit_paid` | Decimal | |
| `balance_due` | Decimal | Optional; omitted if null |
| `detailer_sms_status` | String | `"sent"` / `"failed"` / `"skipped"` |
| `customer_sms_status` | String | `"sent"` / `"failed"` / `"skipped"` |
| `source` | String | `"square"` |
| `environment` | String | `"dev"` or `"prod"` |
| `waiver_accepted_at` | String | ISO timestamp (optional) |

Cal.com `BOOKING_CREATED` webhooks (legacy path) can add these fields to an existing record:
`appointment_at`, `appointment_display`, `vehicle_make`, `vehicle_model`, `calcom_booking_uid`

---

## SMS Format

SMS fires immediately when Square `payment.updated` is received and status is `COMPLETED`.

**Detailer SMS:**
```
🚗 NEW DETAIL BOOKING
──────────────────────────────────
Name:     John Smith
Phone:    (334) 555-1234
Email:    john@example.com
──────────────────────────────────
Service:  Essential Detail
Add-Ons:  Pet Hair Removal, Hand Wax Upgrade
Address:  123 Main St, City AL 36301
Vehicle:  2022 Toyota Camry
Date:     Wed, May 20, 2026 at 9:00 AM
──────────────────────────────────
Deposit:  $28.00
Balance:  $112.00
```

**Customer SMS:**
```
🚗 Booking Confirmed!
A Gentlemen's Touch
──────────────────────────────────
Hi John! Your detail is confirmed.
──────────────────────────────────
Service:  Essential Detail
Add-Ons:  Pet Hair Removal, Hand Wax Upgrade
Address:  123 Main St, City AL 36301
Vehicle:  2022 Toyota Camry
Date:     Wed, May 20, 2026 at 9:00 AM
──────────────────────────────────
Deposit:  $28.00 received
Balance:  $112.00 due after service
──────────────────────────────────
Questions? Call (334) 294-8228
```

Add-Ons, Address, and Vehicle lines are omitted if absent.

---

## TEST_MODE Flag

A `test_mode` Terraform variable wires through to a `TEST_MODE` env var
on both Lambdas and `const TEST_MODE` in `booking.js`. When enabled:

- Packages: SM **$0.01** / MD **$0.10** / LG **$1.00**
- All add-ons: **$0.01**
- Deposit charged: **100%** of total (full upfront)
- `booking.js` rewrites the displayed prices on `DOMContentLoaded` so the
  customer sees what they'll actually be charged

The flag exists so the live Square production wiring can be validated
end-to-end with real cards but minimal real-money risk before public
launch. To flip off:

1. `test_mode = false` in `backend-integration/clients/gentlemens-touch/prod.tfvars`
2. `const TEST_MODE = false` in `booking.js` (top of file)
3. `deploy.ps1` + push to `main` (GitHub Pages auto-deploys frontend)

The webhook Lambda's `_calculate_balance_due` honors the flag, so SMS
messages reflect the test deposit and $0 balance during test mode.

---

## Cal.com Webhook (Legacy Path)

Cal.com `BOOKING_CREATED` webhooks are still handled by `lambda_function.py` but are **not required** for SMS to fire. They are used to attach scheduling metadata (Cal.com booking UID, vehicle make/model if captured) to an existing DynamoDB record via `_attach_calcom_to_booking`.

- Trigger: `BOOKING_CREATED` (not `BOOKING_PAYMENT_INITIATED`)
- `payload.price` is ignored — deposit is always derived from package full price × `DEPOSIT_RATE`
- Cal.com SMS path (`_handle_calcom_webhook`) still sends SMS if triggered, but the primary SMS path is the Square webhook

Cal.com booking links (retained for legacy use):
- SM: `https://cal.com/william-g.-lewis-ai51kb/mobile-detail-appointment-service-1`
- MD: `https://cal.com/william-g.-lewis-ai51kb/mobile-detail-appointment-service-2`
- LG: `https://cal.com/william-g.-lewis-ai51kb/mobile-detail-appointment-service-3`

---

## Key Files Changed in Square Migration (May 2026)

- `pricing_lambda.py` — replaced Stripe SDK with Square SDK v42+; added full customer field embedding
- `lambda_function.py` — replaced Stripe webhook verification with Square HMAC-SHA256; added PACKAGE_DISPLAY, ADDON_DISPLAY, display helpers, immediate SMS on Square webhook
- `booking.html` — new standalone booking page with customer info form
- `booking.js` — new shared booking engine (calendar, pricing, checkout)
- `success.html` — removed Cal.com redirect; shows booking confirmation from sessionStorage
- `index.html` — removed inline booking funnel; all CTAs route to `booking.html`
- `layer/requirements.txt` — actual layer deps: `squareup>=42.0.0`, `requests`
- `bootstrap-layer.ps1` — added cross-platform pip flags for Linux wheels
- `variables.tf` — added `square_environment` variable
- `prod.tfvars` — `square_environment = "production"`
- `ssm.tf` — replaced Stripe SSM data sources with Square

### Stripe Removal Checklist (completed May 2026)

- [x] Pricing Lambda rewritten for Square Payment Links
- [x] Webhook Lambda rewritten for Square signature verification
- [x] Lambda layer rebuilt with `squareup>=42.0.0` and cross-platform wheels
- [x] Terraform SSM data sources migrated from Stripe to Square
- [x] `SQUARE_ENVIRONMENT` decoupled from AWS `ENVIRONMENT`
- [x] Webhook registered in Square Developer Console (production)
- [x] End-to-end tested: checkout → payment → webhook → confirmation → SMS
- [x] All Stripe references removed from codebase
- [x] Cal.com redirect removed from success.html
- [x] Inline booking funnel removed from index.html
