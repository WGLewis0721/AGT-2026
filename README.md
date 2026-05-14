# A Gentlemen's Touch

### Luxury Mobile Detailing — Built from the Ground Up

**[Live Site →](https://wglewis0721.github.io/AGT-2026/)**

---

## This isn't a template. It's a system.

Wix gives everyone the same box to decorate. Squarespace gives you beautiful constraints. Booksy puts your business next to every competitor in a zip code.

This is none of those things.

AGT is a **fully custom** presence and booking system designed to do one thing: make every person who finds this business feel like they've discovered something rare. Because they have.

---

## What it feels like

A client lands on the site. Deep black. A soft gold glow. Not a theme — a mood. The kind of restraint that signals confidence. They don't feel like they're on a booking platform. They feel like they've arrived somewhere.

They pick a date. They pick a package. They fill in their info. They pay a deposit in one tap. Twenty seconds later, they get a text confirmation with every detail they need — no app download, no login, no friction.

The detailer gets a text too. Name, phone, address, vehicle, service, deposit paid, balance due. Everything. Automatically. Before they've touched a sponge.

That's the experience. End to end.

---

## What makes it different

| | Wix / Squarespace | Booksy | **AGT** |
|---|---|---|---|
| Brand | Constrained by templates | Generic marketplace UI | Every pixel is intentional |
| Ownership | You rent the platform | Your data lives on their platform | You own everything — code, data, domain |
| Competition | You're a page on their platform | You're listed next to rivals | No one else is here |
| Automation | Basic form notifications | Basic reminders | Deposit collected → both parties texted → balance tracked, automatically |
| Cost | $15–50/month forever | Commission + monthly fees | Under $10/month in infrastructure |
| Feel | Built for everyone | Built for the industry | Built for *this* business |

---

## Under the hood

For developers and future owners — the system is simple by design.

**Frontend** — `index.html` (marketing) + `booking.html` (booking flow). Zero dependencies. No build step. Runs anywhere. The luxury aesthetic is pure CSS and considered typography — nothing is borrowed from a UI kit.

**Booking** — The customer picks their date and time, selects a package, enters their info, and pays a deposit — all on `booking.html`. No third-party scheduling redirect. The appointment is locked in before they ever reach the payment page.

**Automation (TRA3)** — When Square confirms the deposit payment, an AWS Lambda function fires immediately. It reads the Square event, parses all booking context from the payment note, calculates the balance due, and sends a formatted SMS to both the detailer and the customer. The entire backend runs serverlessly for less than the cost of a car wash.

**Infrastructure as Code** — Every AWS resource is defined in Terraform. Deploy a new environment in minutes. Hand off to a new developer in an afternoon.

---

## Repository Structure

This repo has two independent layers. Do not mix code between them.

```
AGT-2026/
├── index.html              ← Static marketing site (zero dependencies)
├── booking.html            ← Standalone booking page (date/time → package → customer info → deposit)
├── booking.js              ← Shared booking engine (pricing, calendar, checkout)
├── success.html            ← Post-checkout confirmation page
├── fleet.html              ← Commercial fleet washing page
├── assets/                 ← Static images for the landing page
├── images/                 ← Photo assets (portfolio, logo)
├── wix/                    ← Wix Velo multi-page application (reference only)
├── backend-integration/    ← TRA3 serverless backend (Terraform, Lambda, Square webhook)
├── docs/                   ← System context and AI skill definitions
└── scripts/                ← Developer utilities (ai_audit.py)
```

> The Wix Velo app (`wix/`) is kept for reference. Active development continues on the static site.

---

## Page Structure

### `index.html` — Marketing site

| Section | ID | Purpose |
|---|---|---|
| Hero | `#home` | Full-screen hero with logo, tagline, and CTA |
| Who We Are | `#about` | Brand story and service area |
| What We Offer | `#services` | Service category overview |
| Full Luxury Detail Packages | `#packages` | Package cards with pricing (link to `booking.html?package=...`) |
| Add-On Services | `#addons` | À-la-carte add-on pills |
| Fleet Washing | `#fleet` | Commercial fleet cleaning offering |
| Before & After | `#portfolio` | Photo portfolio gallery |
| Client Reviews | `#testimonials` | Customer testimonials |
| FAQ | `#faq` | Frequently asked questions |
| Book Your Services | *(CTA section)* | Single CTA button → `booking.html` |

**Navigation (dropdown):**
- About ▾ → Services, Packages
- How It Works ▾ → Portfolio, Client Reviews, FAQ
- Contact → `booking.html`
- Book Now (CTA) → `booking.html`

### `booking.html` — Booking flow

Three sequential sections (each unlocks after the previous is completed):

1. **Date & Time** — inline calendar + time slot selector (9 AM / 11 AM / 1 PM / 3 PM)
2. **Service Package** — package cards (Essential / Signature / Executive) + add-on pills
3. **Review & Pay** — customer info form + booking summary + waiver checkbox + deposit button

Customer info form fields (all required except Special Instructions):
- Full Name, Phone Number, Email Address
- Service Address
- Vehicle Year, Vehicle Make, Vehicle Model
- Special Instructions (optional)

---

## Services & Pricing

**Detail packages** (20% deposit collected at booking, server-side only):

| Key | Package | Full Price | Deposit |
|---|---|---|---|
| `sm_detail` | Essential Detail (Small Vehicle) | $140 | $28 |
| `md_detail` | Signature Detail (Mid-Size Vehicle) | $175 | $35 |
| `lg_detail` | Executive Detail (Large / SUV) | $220 | $44 |

**Add-ons** (booking.html add-on pills):

| Key | Display Name | Price |
|---|---|---|
| `pet_hair` | Pet Hair Removal | $30 |
| `wax` | Hand Wax Upgrade | $50 |
| `odor` | Odor Elimination | $25 |
| `engine_bay` | Engine Bay Clean | $40 |
| `tire_dressing` | Tire Dressing | $20 |
| `headlights` | Headlight Restore | $35 |
| `shampooing` | Interior Shampooing | $15 |
| `upholstery` | Upholstery Shampoo | $15 |
| `steam` | Steam Cleaning | $10 |
| `polishing` | Machine Polishing | $20 |
| `leather` | Leather Treatment | $15 |

> Prices in `booking.js` (display) and `pricing_lambda.py` (server-side) must stay in sync.

**Fleet Washing** — commercial fleet cleaning; contact directly to book.

---

## For developers

```bash
# No build step required — open directly in a browser
open index.html        # macOS
start index.html       # Windows
```

**Publishing to GitHub Pages**
1. Push to GitHub → **Settings → Pages** → select `main` branch, root `/`
2. Live at `https://yourusername.github.io/AGT-2026/`

**Booking backend (TRA3)**
See [`backend-integration/README.md`](./backend-integration/README.md) for AWS setup, Terraform deployment, and Square webhook configuration.

**Services & Packages**
Edit package cards and add-ons directly in `booking.html` inside `#section-package`.
Mirror any price changes in `REAL_PACKAGES`/`REAL_ADDONS` in both `booking.js` and `pricing_lambda.py`.

---

## Asset Setup

All images live in the `images/` folder.

| File | Used in |
|---|---|
| `images/photo-10.png` | Favicon, nav logo, hero logo |
| `images/photo-9.jpeg` | About section background |
| `images/photo-1.jpeg` | Portfolio — Before & After Full Detail |
| `images/photo-2.jpeg` | Portfolio — Interior Deep Clean |
| `images/photo-3.jpeg` | Portfolio — Exterior Polish and Shine |
| `images/photo-4.jpeg` | Portfolio — Wheel and Tire Detail |
| `images/photo-5.jpeg` | Portfolio — Engine Bay Clean |

Fleet placeholder images expected in `assets/` — see [`assets/README.md`](./assets/README.md).

---

## Booking Flow

Booking is fully self-contained on `booking.html`. No external scheduling service is required to lock in an appointment.

```
Customer fills out booking.html
  ↓
booking.js POSTs to POST /create-checkout (pricing_lambda.py)
  Fields: package, addons, appointment_date, appointment_time,
          customer_name, customer_phone, customer_email,
          customer_address, vehicle_year, vehicle_make, vehicle_model,
          special_instructions, waiver_accepted_at, cal_url
  ↓
pricing_lambda.py recalculates price server-side
  → creates Square Payment Link
  → embeds ALL booking context in pipe-delimited payment_note
  → returns { "url": "https://squareup.com/checkout/..." }
  ↓
Customer redirected to Square checkout → pays deposit
  ↓
Square fires payment.updated webhook (status == "COMPLETED")
  ↓
lambda_function.py
  → verifies HMAC-SHA256 signature
  → parses payment_note fields
  → writes full booking record to DynamoDB
  → sends detailer SMS immediately
  → sends customer SMS immediately (if phone present)
  ↓
Square redirects customer to success.html
  → shows appointment date/time and package from sessionStorage
```

### payment_note format (pipe-delimited key=value)

```
package=sm_detail|addons=pet_hair,wax|total=200|deposit=40|balance=160|
cal_url=https://cal.com/...|order_id=<uuid>|client=gentlemens-touch|
environment=prod|appointment_date=2026-05-20|appointment_time=09:00|
cal_event_id=|customer_name=John Smith|customer_phone=3345551234|
customer_email=john@example.com|customer_address=123 Main St, City AL|
vehicle=2022 Toyota Camry|special_instructions=|waiver=2026-05-14T12:00:00Z
```

All user-supplied values are sanitized: `|` and `=` characters are stripped before embedding.

---

## Adding or Updating Services

Package cards and add-ons live in `booking.html` inside `#section-package`.

To add a new package card:

```html
<article class="pkg-card" data-pkg="new_detail" onclick="selectPackage('new_detail')">
  <div class="package-name">New Package</div>
  <div class="package-size">Vehicle Size</div>
  <div class="package-price">$000</div>
  <div class="package-deposit">$00 deposit</div>
</article>
```

Then add the key to `REAL_PACKAGES` in both `booking.js` and `pricing_lambda.py`, add a display name to `PACKAGE_DISPLAY` in `lambda_function.py`, and add a price entry to `REAL_SERVICE_PRICES` in `lambda_function.py`.

---

## Tech Stack

- **HTML5 / CSS3 / ES2020** — zero-dependency static site; no build step, no framework
- **Google Fonts** — Cormorant Garamond, Bebas Neue, Montserrat
- **AWS Lambda (Python 3.11)** — pricing API (Square checkout creation) + webhook handler (Square payment confirmation + SMS)
- **AWS DynamoDB** — booking records (source of truth)
- **AWS API Gateway (HTTP)** — routes: `POST /create-checkout`, `POST /webhook`, `GET /complete`
- **AWS SSM Parameter Store** — all secrets (Square keys, Textbelt key, phone numbers)
- **Square** — deposit checkout sessions + `payment.updated` webhook confirmation
- **Textbelt** — SMS notifications to detailer and customer
- **Terraform** — all AWS infrastructure as code, isolated `dev` / `prod` environments

---

## Booking Backend (TRA3)

Production-ready AWS serverless infrastructure in [`backend-integration/`](./backend-integration):

| Component | Purpose |
|---|---|
| `lambda/lambda_function.py` | Square `payment.updated` webhook handler — confirms booking in DynamoDB, sends SMS; also handles Cal.com `BOOKING_CREATED` (attaches scheduling info to existing record) |
| `lambda/pricing_lambda.py` | `POST /create-checkout` — server-side price calculation + Square Payment Link creation |
| `cost-reporter/cost_reporter_handler.py` | Daily AWS cost report via SNS email (optional) |
| `terraform/` | All AWS resources (Lambda, API Gateway, DynamoDB, IAM, CloudWatch, S3, SSM) |

See [`backend-integration/README.md`](./backend-integration/README.md) for full AWS setup, Square webhook configuration, and the operator runbook.

---

## DynamoDB Booking Record

All fields written to DynamoDB on Square `payment.updated` (status COMPLETED):

| Field | Value |
|---|---|
| `booking_id` | Square order UUID (used as partition key) |
| `status` | `"confirmed"` |
| `payment_status` | `"paid"` |
| `paid_at` | ISO timestamp |
| `updated_at` | ISO timestamp |
| `square_payment_id` | Square payment ID |
| `square_order_id` | Square order ID |
| `square_amount_total_cents` | Deposit in cents |
| `customer_name` | From payment_note |
| `customer_phone` | From payment_note (E.164 normalized) |
| `customer_email` | From payment_note or Square buyer email |
| `service` | Display name (e.g. "Essential Detail") |
| `addons` | Comma-separated display names |
| `address` | From payment_note |
| `appointment_date` | Formatted date string (e.g. "Wed, May 20, 2026") |
| `deposit_paid` | Decimal |
| `balance_due` | Decimal (optional) |
| `detailer_sms_status` | `"sent"` / `"failed"` / `"skipped"` |
| `customer_sms_status` | `"sent"` / `"failed"` / `"skipped"` |
| `source` | `"square"` |
| `environment` | `"dev"` or `"prod"` |

---

## Wix Velo App (`wix/`)

A full multi-page Wix application connected to Wix site `685cc33b-0e63-481d-9422-d4bafcc7f070`, kept here for reference.

```bash
cd wix
npm install       # also runs `wix sync-types` via postinstall
npm run dev       # opens the Wix Local Editor
npm run lint      # eslint .
```

See [`wix/README.md`](./wix/README.md) for full page inventory and booking flow details.

---

## System Docs

| File | Purpose |
|---|---|
| `docs/system-context.md` | Core architecture rules and constraints |
| `docs/skills/frontend.md` | Frontend conventions |
| `docs/skills/lambda.md` | Lambda conventions |
| `docs/skills/stripe.md` | Legacy Stripe conventions (archived — Square is now active) |

---

## Payment Processing

TRA3 uses **Square** for secure payment processing.

**Deposit Flow:**
1. Customer fills out booking form on `booking.html` (date, package, customer info)
2. `booking.js` calls `/create-checkout` API (`pricing_lambda.py`)
3. Lambda recalculates price server-side and creates a Square Payment Link with all booking context embedded in `payment_note`
4. Customer redirects to Square checkout page and pays deposit
5. Square fires `payment.updated` webhook (status `"COMPLETED"`)
6. Webhook Lambda verifies HMAC-SHA256 signature, parses `payment_note`, writes booking record to DynamoDB, sends SMS to both detailer and customer immediately
7. Square redirects customer to `success.html` — shows confirmation with date/time from sessionStorage

**Credentials:**
- Square Access Token (sandbox or production)
- Square Location ID
- Square Webhook Signature Key

All stored in AWS SSM Parameter Store under `/tra3/gentlemens-touch/prod/square_*`.

**Switching from Sandbox to Production:**
1. Get production Square credentials from client
2. Update SSM parameters with production values
3. Set `square_environment = "production"` in `backend-integration/clients/gentlemens-touch/prod.tfvars`
4. Register production webhook in Square Developer Console
5. Deploy via `.\backend-integration\scripts\deploy.ps1`

**TEST_MODE (pre-launch validation):**

A `test_mode` Terraform variable swaps the whole stack to micro prices so
the live Square production wiring can be validated end-to-end with real
cards but minimal real-money risk:

- Packages: SM $0.01 / MD $0.10 / LG $1.00 — all add-ons: $0.01
- Deposit: 100% of total (full charge upfront)
- `booking.js` rewrites displayed prices on page load so the customer sees
  what they'll actually be charged

To enable: `test_mode = true` in `prod.tfvars` **and** `const TEST_MODE = true`
in `booking.js` (top of file). Deploy backend with `deploy.ps1`,
push frontend to `main`. Reverse both before public launch.

---

## Contact

**agentlemenstouch@gmail.com**
