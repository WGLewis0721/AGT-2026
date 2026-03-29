# A Gentlemen's Touch — AGT Mobile Detailing

https://wglewis0721.github.io/AGT-2026/

Static marketing and booking website for **A Gentlemen's Touch (AGT)**, a luxury mobile car detailing business.

**Design:** Deep black backgrounds (`#0a0a0a`), gold accents (`#C9A84C`), editorial luxury aesthetic.
Fonts: Cormorant Garamond (display/serif), Bebas Neue (logo/headings), Montserrat (body/UI).
Inspired by high-end automotive culture and white-glove service.

> **Wix Velo app** (the legacy multi-page Wix integration) has been moved to the [`wix/`](./wix/) directory and is kept for reference only. Active development continues here on the static site.

---

## Page Structure

| Section | ID | Purpose |
|---|---|---|
| Hero | `#home` | Full-screen hero with logo, tagline, and CTA |
| Who We Are | `#about` | Brand story and service area |
| What We Offer | `#services` | Service category overview |
| Full Luxury Detail Packages | `#packages` | Package cards with pricing |
| Add-On Services | `#addons` | À-la-carte add-on pills |
| Before & After | `#portfolio` | Photo portfolio gallery |
| Schedule Your Appointment | `#booking` | 4-step booking funnel |

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

### Replacing the Logo

Drop your new PNG into `images/` and update these `src` attributes in `index.html`:

```html
<!-- Nav logo -->
<img src="images/photo-10.png" style="height:48px;" alt="AGT Logo" />

<!-- Hero logo -->
<img src="images/photo-10.png" style="width:180px;" alt="AGT" />
```

---

## Booking Flow
Booking is handled via Cal.com with Stripe deposit payment built in.
Three separate Cal.com event types correspond to each vehicle size:
- Small: https://cal.com/william-g.-lewis-ai51kb/mobile-detail-appointment-service-1
- Medium: https://cal.com/william-g.-lewis-ai51kb/mobile-detail-appointment-service-2
- Large: https://cal.com/william-g.-lewis-ai51kb/mobile-detail-appointment-service-3

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

---

## Tech Stack

- **HTML5 / CSS3 / ES2020** — zero-dependency static site; no build step, no framework
- **[Cal.com](https://cal.com)** — scheduling embed (`mobile-detail-appointment`, `month_view` layout)
- **Google Fonts** — Cormorant Garamond, Bebas Neue, Montserrat
- **Infrastructure** — AWS Lambda, API Gateway, S3, CloudWatch · Terraform IaC · TRA3 booking automation

## Booking Backend Automation (TRA3)

Production-ready AWS serverless infrastructure in [`backend-integration/`](./backend-integration):

- **Stripe** — collects deposit at Cal.com booking time
- **AWS Lambda** — processes Stripe webhooks, calculates balance due
- **Textbelt** — sends SMS to detailer and customer on every booking
- **Terraform** — all infrastructure as code, dev/prod environments

See [`backend-integration/README.md`](./backend-integration/README.md) for setup and deployment.


## Contact

Questions or updates? Reach out at **agentlemenstouch@gmail.com**
