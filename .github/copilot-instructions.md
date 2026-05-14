# GitHub Copilot Instructions — AGT-2026

## Project Overview

This is the codebase for **A Gentlemen's Touch (AGT)**, a luxury mobile car detailing business.
The repo has three distinct layers:

1. **`index.html`** — standalone static marketing site (no build step, no framework)
2. **`booking.html` + `booking.js`** — standalone booking page and shared booking engine
3. **`wix/`** — a Wix Velo multi-page application (reference only, not actively developed)

Do **not** mix code between these layers.

---

## Tech Stack

### Static site (`index.html`, `booking.html`, `booking.js`, `success.html`)

- Vanilla HTML5 / CSS3 / ES2020 — zero dependencies, no bundler
- `index.html`: all CSS in `<style>`, all JS in inline `<script>` at bottom of `<body>`
- `booking.html`: all CSS in `<style>`, imports `booking.js` as external script
- `booking.js`: IIFE module; exposes named functions on `window` for HTML onclick handlers
- `success.html`: reads sessionStorage keys set by `booking.js` before Square redirect

### Booking backend (`backend-integration/`)

- `lambda/pricing_lambda.py` — `POST /create-checkout` — Square Payment Link creation
- `lambda/lambda_function.py` — `POST /webhook` / `GET /complete` — Square + Cal.com webhook handler
- Square SDK v42+ (`squareup>=42.0.0`) — used only in `pricing_lambda.py`
- Webhook Lambda uses raw `hmac`, `hashlib`, `base64` — no Square SDK
- Python 3.11, Terraform, DynamoDB, Textbelt SMS

### Wix Velo (`wix/`)

- Framework: Wix Velo — proprietary Wix JavaScript runtime
- Page code: one `.js` file per Wix page in `wix/src/pages/`
- Dev command: `npm run dev` (alias: `wix dev`) — opens Local Editor

---

## Design Language

- **Background:** deep black `#0a0a0a` (`--black`), card surfaces `#161616` (`--black-card`)
- **Accent:** gold `#C9A84C` (`--gold`), lighter gold `#E8C96B` (`--gold-light`)
- **Text:** white `#FFFFFF`, soft white `#F0EDE8` (`--white-soft`), muted `#9A9A9A` (`--white-muted`)
- **Error:** `#E74C3C` (red) — success: `#27AE60` (green)
- **Fonts:** Cormorant Garamond (display/serif), Bebas Neue (logo/headings), Montserrat (body/UI)
- **Tone:** luxury, minimal, editorial — "A Gentlemen's Touch"
- Inline `style` attributes are acceptable for one-off sizing tweaks; match the pattern already in the file

---

## Booking Flow

The full booking flow lives on `booking.html`. There is no inline booking funnel in `index.html`.

**Step sequence (booking.html):**
1. Customer picks date and time (built-in calendar + 4 time slots: 9 AM, 11 AM, 1 PM, 3 PM)
2. Customer picks package and optional add-ons (sections unlock sequentially)
3. Customer fills in info form (name, phone, email, address, vehicle year/make/model, notes) and accepts waiver
4. `initiateCheckoutWithSlot()` in `booking.js` POSTs all fields to `/create-checkout`
5. `pricing_lambda.py` recalculates price server-side, creates Square Payment Link, embeds all context in `payment_note`
6. Customer redirected to Square, pays deposit
7. Square fires `payment.updated` webhook → `lambda_function.py` → DynamoDB write + SMS (both detailer and customer, immediately)
8. Square redirects to `success.html` → reads sessionStorage keys written before Square redirect

**Fields sent to `/create-checkout` (from `booking.js`):**
`package`, `addons`, `appointment_date`, `appointment_time`, `cal_event_id`, `cal_url`,
`customer_name`, `customer_phone`, `customer_email`, `customer_address`,
`vehicle_year`, `vehicle_make`, `vehicle_model`, `special_instructions`, `waiver_accepted_at`

**sessionStorage keys written by `booking.js`** (available on `success.html`):
`agt_package`, `agt_addons`, `agt_deposit`, `agt_balance`, `agt_cal_url`,
`agt_customer_name`, `agt_customer_phone`, `agt_customer_email`, `agt_address`, `agt_vehicle`

---

## Conventions

### Static site

- `booking.js` is an IIFE; all state (`selectedPackage`, `selectedAddons`, `capturedSlot`, `customerInfo`, `waiverAgreed`) lives inside the IIFE
- Functions needed by HTML `onclick=` are explicitly attached to `window` at the bottom of the IIFE
- Use `document.getElementById()` for DOM access (no jQuery or other libraries)
- CSS custom properties (e.g. `var(--gold)`) must be used for all theme colors
- Do not add external JS libraries or CDN script tags
- `_updateBookingReadiness()` gates the checkout button on ALL 11 required fields: `selectedPackage`, `capturedSlot.appointment_date`, `capturedSlot.appointment_time`, `waiverAgreed`, plus 7 customer info fields
- Prices displayed via `_renderPriceDisplay()` — reads `data-pkg` / `data-addon` attributes; do not hardcode prices in markup
- `TEST_MODE` flag at top of `booking.js` mirrors the Lambda `TEST_MODE` — keep in sync with `prod.tfvars`

### index.html nav structure

```html
<nav id="mainNav">
  <ul class="nav-links">
    <li class="nav-dropdown">About ▾ → [#services, #packages]</li>
    <li class="nav-dropdown">How It Works ▾ → [#portfolio, #testimonials, #faq]</li>
    <li><a href="booking.html">Contact</a></li>
  </ul>
  <a href="booking.html" class="nav-cta">Book Now</a>
</nav>
```

All "Book Now" / "Select Package" CTAs link to `booking.html` (or `booking.html?package=<key>`).
There is no inline booking funnel in `index.html`.

---

## Common Tasks

### Add a new service package

1. Add `<article class="pkg-card" data-pkg="new_detail" onclick="selectPackage('new_detail')">` to `booking.html` `#section-package`
2. Add to `REAL_PACKAGES` in `booking.js`
3. Add to `REAL_PACKAGES` in `pricing_lambda.py`
4. Add to `PACKAGE_DISPLAY` in `lambda_function.py`
5. Add to `REAL_SERVICE_PRICES` in `lambda_function.py`
6. Add `TEST_*` entries to test tables in all three files if TEST_MODE is relevant

### Add a new add-on

1. Add `<button class="addon-pill" data-addon="new_key" onclick="toggleAddon('new_key')">` to `booking.html`
2. Add to `REAL_ADDONS` in `booking.js`
3. Add to `REAL_ADDONS` in `pricing_lambda.py`
4. Add to `ADDON_DISPLAY` in `lambda_function.py`

### Update pricing

Edit `REAL_PACKAGES` / `REAL_ADDONS` in **both** `booking.js` and `pricing_lambda.py`.
`booking.js` values are display-only; `pricing_lambda.py` values are the authoritative server-side prices.

### Update SERVICE_PRICES in webhook lambda

If the detailer SMS balance shows "Not mapped", add the service key and price to `REAL_SERVICE_PRICES` in `lambda_function.py`.

### Add a new backend function

Add to `lambda_function.py` for webhook logic, or `pricing_lambda.py` for pricing/checkout logic.
Keep both Lambdas independently deployable — they share no imports.

---

## Out of Scope

- **Do not** add a booking funnel back into `index.html` — it routes to `booking.html`
- **Do not** add a Cal.com redirect to `success.html` — the appointment is confirmed pre-payment
- **Do not** add a build step, bundler, or npm dependencies to the static site — zero-dependency is a hard constraint
- **Do not** add Stripe imports or references anywhere — Square is the active payment provider
- **Do not** import the Square SDK in `lambda_function.py` — webhook signature verification uses raw `hmac`/`hashlib`
- **Do not** hardcode prices in HTML markup — use `data-pkg`/`data-addon` hooks and `_renderPriceDisplay()`
- **Do not** trust browser-submitted amounts — `pricing_lambda.py` always recalculates from server-side tables

---

## AGT Booking System Rules

Always read:
- `docs/system-context.md`
- `docs/skills/`

Constraints:
- DynamoDB is the only database
- No frontend business logic
- Keep cost minimal
- No unnecessary dependencies

Internet usage:
- Only official docs (AWS, Square)
- No random blog code

Output:
- clean
- minimal
- production-ready

---

## Payment Provider: Square

**TRA3 uses Square for payments (not Stripe).** Stripe was fully removed in May 2026.

### Key Implementation Details

- **Pricing Lambda:** Uses Square SDK v42+ (`from square import Square`)
- **Webhook Lambda:** Verifies HMAC-SHA256 signatures, no Square SDK imported
- **Environment:** `SQUARE_ENVIRONMENT` env var controls sandbox/production (independent of AWS `ENVIRONMENT`)
- **Current environment:** production (`square_environment = "production"` in `prod.tfvars`)
- **Layer:** Must use `--platform manylinux2014_x86_64` pip flags on Windows to download Linux wheels
- **Events:** Listens for `payment.updated` with `status == "COMPLETED"`, ignores `payment.created`
- **Note field:** Lambda reads `payment.note` OR `payment.payment_note` OR `order.note` (checked in order)

### payment_note Parsing

`pricing_lambda.py` writes the note; `lambda_function.py` reads it.
Format: `key=value|key=value|...`
All user values sanitized via `_sanitize_note_value()` — strips `|` and `=`.

Keys written to `payment_note`:
`package`, `addons`, `total`, `deposit`, `balance`, `cal_url`, `order_id`, `client`, `environment`,
`appointment_date` (YYYY-MM-DD), `appointment_time` (HH:MM 24-hour), `cal_event_id`,
`customer_name`, `customer_phone`, `customer_email`, `customer_address`,
`vehicle` (year make model combined), `special_instructions`, `waiver`

### SMS Trigger

SMS fires **immediately** on Square `payment.updated` (COMPLETED) — not on Cal.com webhook.
Both detailer SMS and customer SMS are sent in `_handle_square_webhook` after `_mark_booking_confirmed`.
`detailer_sms_status` and `customer_sms_status` are set to `"sent"` / `"failed"` / `"skipped"` in DynamoDB.

### When Working on Payment Code

- Never add Stripe imports or references
- Square credentials are in SSM under `/tra3/.../square_*`
- Lambda layer requirements are in `backend-integration/layer/requirements.txt` (NOT `pricing-requirements.txt`)
- If layer rebuild fails with `No module named 'pydantic_core._pydantic_core'`, the pip flags are missing in `bootstrap-layer.ps1`
- Sandbox vs production is controlled by `square_environment` in `prod.tfvars`, not by AWS environment

### TEST_MODE Flag

`test_mode` (Terraform variable) wires through to `TEST_MODE` env var on
both Lambdas and `const TEST_MODE` in `booking.js`. When enabled:

- Packages charge $0.01 / $0.10 / $1.00, add-ons $0.01, deposit = 100%
- `booking.js` rewrites `.package-price` and `.addon-pill-price` text on `DOMContentLoaded`

When working on pricing code:
- Don't hardcode 0.20 — read `DEPOSIT_RATE` (Python/JS) which is flag-aware
- Both Lambdas have `REAL_*` and `TEST_*` price tables; keep them in sync

### Useful References

- Square SDK docs: `https://developer.squareup.com/docs/sdks/python`
- Square Checkout API: `https://developer.squareup.com/reference/square/checkout-api`
- Webhook signature verification: `https://developer.squareup.com/docs/webhooks/step3validate`

---

## Cal.com Webhook (Legacy)

Cal.com `BOOKING_CREATED` webhooks are still handled but are **not** the primary SMS trigger.
They attach scheduling metadata to an existing DynamoDB record via `_attach_calcom_to_booking`.

- Trigger: `BOOKING_CREATED`
- `payload.price` is **ignored** — deposit is always derived from package full price × `DEPOSIT_RATE`
- Signature: HMAC-SHA256 via `x-cal-signature-256` header
- If Cal.com fires and a matching phone number is found in DynamoDB, it updates: `appointment_at`, `appointment_display`, `vehicle_make`, `vehicle_model`, `calcom_booking_uid`

---

## Wix Velo (`wix/`)

Reference only — not actively developed.

- **Page code:** one `.js` file per Wix page in `wix/src/pages/`; `masterPage.js` runs globally
- **Shared utilities:** `wix/src/public/` — import with `'public/<filename>'` (not relative paths)
- **Element selection:** `$w('#elementId')` (Velo API — not DOM)
- **Dev command:** `npm run dev` (alias: `wix dev`) in `wix/` directory
- Do **not** rename `wix/src/pages/*.js` files — Wix maps pages by filename
- Do **not** use DOM APIs in Velo page code — use `$w()`
