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

They pick a package. They choose their date. They pay a deposit in one tap. Twenty seconds later, they get a text confirmation with every detail they need — no app download, no login, no friction.

The detailer gets a text too. Name, phone, address, service, deposit paid, balance due. Everything. Automatically. Before they've touched a sponge.

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

**Frontend** — A single `index.html`. Zero dependencies. No build step. Runs anywhere. The luxury aesthetic is pure CSS and considered typography — nothing is borrowed from a UI kit.

**Booking** — Cal.com handles scheduling. Square handles deposits. The customer never feels the seam between them.

**Automation (TRA3)** — When a booking completes, an AWS Lambda function fires. It reads the Square event, calculates the balance due, and sends a formatted SMS to both the detailer and the customer. The entire backend runs serverlessly for less than the cost of a car wash.

**Infrastructure as Code** — Every AWS resource is defined in Terraform. Deploy a new environment in minutes. Hand off to a new developer in an afternoon.

---

## Repository Structure

This repo has two independent layers. Do not mix code between them.

```
AGT-2026/
├── index.html              ← Static marketing + booking funnel (zero dependencies)
├── fleet.html              ← Commercial fleet washing page
├── success.html            ← Post-checkout success page
├── assets/                 ← Static images for the landing page
├── images/                 ← Photo assets (portfolio, logo)
├── wix/                    ← Wix Velo multi-page application (reference)
├── api/                    ← Lambda source for booking-intent and create-checkout
├── backend-integration/    ← TRA3 serverless backend (Terraform, Lambda, Stripe webhook)
├── docs/                   ← System context and AI skill definitions
└── scripts/                ← Developer utilities (ai_audit.py)
```

> The Wix Velo app (`wix/`) is kept for reference. Active development continues on the static site.

---

## Page Structure (`index.html`)

| Section | ID | Purpose |
|---|---|---|
| Hero | `#home` | Full-screen hero with logo, tagline, and CTA |
| Who We Are | `#about` | Brand story and service area |
| What We Offer | `#services` | Service category overview |
| Full Luxury Detail Packages | `#packages` | Package cards with pricing |
| Add-On Services | `#addons` | À-la-carte add-on pills |
| Fleet Washing | `#fleet` | Commercial fleet cleaning offering |
| Before & After | `#portfolio` | Photo portfolio gallery |
| Schedule Your Appointment | `#booking` | 4-step booking funnel |

---

## Services & Pricing

**Detail packages** (20% deposit collected at booking):

| Package | Full Price | Deposit |
|---|---|---|
| Small Vehicle Detail | $100 | $20 |
| Medium Vehicle Detail | $150 | $30 |
| Large Vehicle Detail | $200 | $40 |

**Add-ons:** Engine Bay Cleaning (+$40), Odor Elimination (+$30), Headlight Restoration (+$50), Tire Shine & Dressing (+$15), Pet Hair Removal (+$25).

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
Edit package cards and add-ons directly in `index.html` inside `#packages` and `#addons`.

**Booking links** (Cal.com, by vehicle size)
- Small → `service-1`
- Medium → `service-2`
- Large → `service-3`

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

Booking is handled via Cal.com with Square deposit payment.

Three Cal.com event types correspond to each vehicle size:
- Small: https://cal.com/william-g.-lewis-ai51kb/mobile-detail-appointment-service-1
- Medium: https://cal.com/william-g.-lewis-ai51kb/mobile-detail-appointment-service-2
- Large: https://cal.com/william-g.-lewis-ai51kb/mobile-detail-appointment-service-3

**Full booking lifecycle:**

```
Frontend → POST /booking-intent  → DynamoDB (draft booking created)
        → POST /create-checkout  → Square Payment Link returned
        → Customer pays deposit
        → Square webhook  ─┐
          Cal.com webhook  ─┴→ Lambda → DynamoDB (confirmed) → SMS to detailer + customer
```

---

## Adding or Updating Services

Package cards and add-ons are written directly in `index.html` inside `#packages` and `#addons`.

To add a new package card:

```html
<div class="pkg-card" onclick="selectPkg('Your Package Name', 00)">
  <h3>Your Package Name</h3>
  <div class="pkg-price">$00</div>
  <p>Short description of what's included.</p>
</div>
```

Pricing is also validated in the backend — update `PACKAGE_CATALOG` in `backend-integration/shared/booking_common.py` to match any price changes.

---

## Tech Stack

- **HTML5 / CSS3 / ES2020** — zero-dependency static site; no build step, no framework
- **[Cal.com](https://cal.com)** — scheduling embed (`mobile-detail-appointment`, `month_view` layout)
- **Google Fonts** — Cormorant Garamond, Bebas Neue, Montserrat
- **AWS Lambda (Python 3.11)** — booking intent, Square checkout creation, Square/Cal.com webhooks, cost reporting
- **AWS DynamoDB** — booking records (source of truth)
- **AWS API Gateway (HTTP)** — routes: `POST /booking-intent`, `POST /create-checkout`, `POST /webhook`
- **AWS SSM Parameter Store** — all secrets (Square keys, Textbelt key, phone numbers)
- **Square** — deposit checkout sessions + webhook confirmation
- **Textbelt** — SMS notifications to detailer and customer
- **Terraform** — all AWS infrastructure as code, isolated `dev` / `prod` environments

---

## Booking Backend (TRA3)

Production-ready AWS serverless infrastructure in [`backend-integration/`](./backend-integration):

| Component | Purpose |
|---|---|
| `lambda/lambda_function.py` | Square + Cal.com webhook handler — confirms booking, sends SMS |
| `lambda/pricing_lambda.py` | `POST /create-checkout` — builds Square Payment Links |
| `api/booking_intent.py` | `POST /booking-intent` — validates payload, writes draft to DynamoDB |
| `api/create_checkout_session.py` | `POST /create-checkout` — looks up booking, creates Square Payment Link |
| `cost-reporter/cost_reporter_handler.py` | Daily AWS cost report via SNS email (optional) |
| `shared/booking_common.py` | Shared pricing catalog, DynamoDB helpers, normalizers |
| `terraform/` | All AWS resources (Lambda, API Gateway, DynamoDB, IAM, CloudWatch, S3, SSM) |

See [`backend-integration/README.md`](./backend-integration/README.md) for full AWS setup, Stripe webhook configuration, and the operator runbook.

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
1. Customer selects package and add-ons on the booking page
2. Frontend calls `/create-checkout` API (pricing Lambda)
3. Lambda creates a Square Payment Link with 20% deposit amount
4. Customer redirects to Square checkout page
5. After payment, Square fires `payment.updated` webhook
6. Webhook Lambda verifies signature and logs booking confirmation
7. Customer redirects to `success.html` and schedules via Cal.com

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

---

## Contact

**agentlemenstouch@gmail.com**
