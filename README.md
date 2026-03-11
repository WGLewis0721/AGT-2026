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

## Updating Payment Handles

Search `index.html` for the placeholders below and replace each one:

| Placeholder | Replace with |
|---|---|
| `$YOURHANDLE` | Your Cash App cashtag |
| `@YOURHANDLE` | Your Venmo username |
| `(334) 294-8228` | Your Zelle phone number (already set — update if needed) |

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

## Booking Backend Automation (Cal.com → Airtable → Notifications)

Production-ready integration scaffolding is included in [`backend-integration/`](./backend-integration/):

- Cloudflare Worker webhook receiver for Cal.com events
- Airtable record creation for each booking
- SMS notification support (Twilio)
- Email notification support (Resend)

See [`backend-integration/README.md`](./backend-integration/README.md) for setup and deployment.

---

## Known Issues / TODO

- [ ] Payment handles (`$YOURHANDLE`, `@YOURHANDLE`) in `index.html` Step 4 need to be replaced with real Cash App / Venmo handles

---

## Contact

Questions or updates? Reach out at **agentlemenstouch@gmail.com**
