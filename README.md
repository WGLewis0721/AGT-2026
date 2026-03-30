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

**Booking** — Cal.com handles scheduling. Stripe handles deposits. The customer never feels the seam between them.

**Automation (TRA3)** — When a booking completes, an AWS Lambda function fires. It reads the Stripe event, calculates the balance due, and sends a formatted SMS to both the detailer and the customer. The entire backend runs serverlessly for less than the cost of a car wash.

**Infrastructure as Code** — Every AWS resource is defined in Terraform. Deploy a new environment in minutes. Hand off to a new developer in an afternoon.

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
See [`backend-integration/README.md`](./backend-integration/README.md) for AWS setup, Terraform deployment, and Stripe webhook configuration.

**Services & Packages**
Edit package cards and add-ons directly in `index.html` inside `#packages` and `#addons`.

**Booking links** (Cal.com, by vehicle size)
- Small → `service-1`
- Medium → `service-2`
- Large → `service-3`

**Active development branch:** `AGT-website-v2-branch` — `main` is production, always stable.

---

## Contact

**agentlemenstouch@gmail.com**
