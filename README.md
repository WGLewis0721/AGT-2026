# A Gentlemen's Touch — AGT Mobile Detailing

**[Live Site →](https://wglewis0721.github.io/AGT-2026/)**

Static marketing and booking website for **A Gentlemen's Touch (AGT)**, a luxury mobile car detailing business.

**Design:** Deep black backgrounds (`#0a0a0a`), gold accents (`#C9A84C`), editorial luxury aesthetic.
Fonts: Cormorant Garamond (display/serif), Bebas Neue (logo/headings), Montserrat (body/UI).

---

## Repository Structure

This repo has two independent layers. Do not mix code between them.

```
AGT-2026/
├── index.html              ← Static marketing + booking funnel (zero dependencies)
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

## Running Locally

```bash
# No build step required — open the file directly
open index.html        # macOS
start index.html       # Windows
```

---

## Publishing (GitHub Pages)

1. Push this repository to GitHub.
2. Go to **Settings → Pages** in your repository.
3. Under **Branch**, select `main` and the root folder `/`.
4. Click **Save**.
5. GitHub will provide a URL like `https://yourusername.github.io/AGT-2026/` within a minute or two.

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

---

## Booking Flow

Booking is handled via Cal.com with Stripe deposit payment.

Three Cal.com event types correspond to each vehicle size:
- Small: https://cal.com/william-g.-lewis-ai51kb/mobile-detail-appointment-service-1
- Medium: https://cal.com/william-g.-lewis-ai51kb/mobile-detail-appointment-service-2
- Large: https://cal.com/william-g.-lewis-ai51kb/mobile-detail-appointment-service-3

**Full booking lifecycle:**

```
Frontend → POST /booking-intent  → DynamoDB (draft booking created)
        → POST /create-checkout  → Stripe Checkout Session returned
        → Customer pays deposit
        → Stripe webhook  ─┐
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
- **AWS Lambda (Python 3.11)** — booking intent, Stripe checkout creation, Stripe/Cal.com webhooks, cost reporting
- **AWS DynamoDB** — booking records (source of truth)
- **AWS API Gateway (HTTP)** — routes: `POST /booking-intent`, `POST /create-checkout`, `POST /webhook`
- **AWS SSM Parameter Store** — all secrets (Stripe keys, Textbelt key, phone numbers)
- **Stripe** — deposit checkout sessions + webhook confirmation
- **Textbelt** — SMS notifications to detailer and customer
- **Terraform** — all AWS infrastructure as code, isolated `dev` / `prod` environments

---

## Booking Backend (TRA3)

Production-ready AWS serverless infrastructure in [`backend-integration/`](./backend-integration):

| Component | Purpose |
|---|---|
| `lambda/lambda_function.py` | Stripe + Cal.com webhook handler — confirms booking, sends SMS |
| `lambda/pricing_lambda.py` | `POST /create-checkout` — builds Stripe Checkout sessions |
| `api/booking_intent.py` | `POST /booking-intent` — validates payload, writes draft to DynamoDB |
| `api/create_checkout_session.py` | `POST /create-checkout` — looks up booking, creates Stripe session |
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
| `docs/skills/stripe.md` | Stripe conventions |

---

## Contact

Questions or updates? Reach out at **agentlemenstouch@gmail.com**
