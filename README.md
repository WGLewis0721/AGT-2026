# A Gentlemen's Touch — AGT Mobile Detailing

Production-ready website for **A Gentlemen's Touch (AGT)**, a luxury mobile car detailing business.
The repo has two distinct layers: a standalone static marketing + booking funnel (`index.html`) and
a Wix Velo multi-page application connected to site ID `685cc33b-0e63-481d-9422-d4bafcc7f070`.

**Design:** Deep black backgrounds (`#0a0a0a`), gold accents (`#C9A84C`), editorial luxury aesthetic.
Fonts: Cormorant Garamond (display/serif), Bebas Neue (logo/headings), Montserrat (body/UI).
Inspired by high-end automotive culture and white-glove service.

---

## Page Structure

### Static Site (`index.html`)

| Section | ID | Purpose |
|---|---|---|
| Hero | `#home` | Full-screen hero with logo, tagline, and CTA |
| Who We Are | `#about` | Brand story and service area |
| What We Offer | `#services` | Service category overview |
| Full Luxury Detail Packages | `#packages` | Package cards with pricing |
| Add-On Services | `#addons` | À-la-carte add-on pills |
| Before & After | `#portfolio` | Photo portfolio gallery |
| Schedule Your Appointment | `#booking` | 4-step booking funnel |

### Wix Velo App (`src/pages/`)

| Page | File | Purpose |
|---|---|---|
| Home | `Home.cfspp.js` | Landing page |
| Book Online | `Book Online.c5pg0.js` | Service listing / menu |
| Service Page | `Service Page.zapqr.js` | Individual service detail + add-ons |
| Cart Page | `Cart Page.u25lg.js` | Cart review + promo codes |
| Booking Form | `Booking Form.vqyyp.js` | Step 1 — customer & vehicle info |
| Booking Calendar | `Booking Calendar.s9swq.js` | Step 2 — date & time picker |
| Checkout | `Checkout.s8k0z.js` | Step 3 — review & confirm |
| Thank You Page | `Thank You Page.w5kt1.js` | Booking confirmation + tracker |
| Side Cart | `Side Cart.o63p3.js` | Slide-in cart panel |
| My Bookings | `My Bookings.dv8my.js` | Member bookings list |
| Account Settings | `Account Settings.woh8q.js` | Member account |

---

## Running Locally

```bash
# Option 1 — Static site only (no build step)
open index.html        # macOS
start index.html       # Windows

# Option 2 — Wix Velo local development
git clone <your-repository-url>
cd AGT-2026
npm install            # also runs `wix sync-types` via postinstall
npm run dev            # alias for `wix dev` — opens the Local Editor

# Lint
npm run lint           # eslint .
```

---

## Publishing

### Static Site (`index.html`)

1. Push this repository to GitHub.
2. Go to **Settings → Pages** in your repository.
3. Under **Branch**, select `main` and the root folder `/`.
4. Click **Save**.
5. GitHub will provide a URL like `https://yourusername.github.io/AGT-2026/` within a minute or two.

> **Tip:** Make sure `index.html` is in the root of the repository (it is, by default).

### Wix Velo App

```bash
wix release        # build and publish a preview release
```

Pushing to the default branch automatically syncs code changes to the connected Wix site.

---

## Asset Setup

All images used by the static site live in the `images/` folder.

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

To swap out the logo, drop your new PNG into `images/` and update the corresponding `src` attributes in `index.html`:

```html
<!-- Nav logo -->
<img src="images/photo-10.png" style="height:48px;" alt="AGT Logo" />

<!-- Hero logo -->
<img src="images/photo-10.png" style="width:180px;" alt="AGT" />
```

---

## Updating Payment Handles

The payment instructions in `index.html` Step 4 use placeholder handles.
Search `index.html` for these values and replace both occurrences of each:

| Placeholder | Replace with |
|---|---|
| `$YOURHANDLE` | Your Cash App cashtag |
| `@YOURHANDLE` | Your Venmo username |
| `(334) 294-8228` | Your Zelle phone number (already set — update if needed) |

---

## Adding or Updating Services

### Static Site

Package cards and add-ons are written directly in `index.html` inside `#packages` and `#addons`.
To add a new package card:

```html
<div class="pkg-card" onclick="selectPkg('Your Package Name', 00)">
  <h3>Your Package Name</h3>
  <div class="pkg-price">$00</div>
  <p>Short description of what's included.</p>
</div>
```

### Wix Velo App

Edit the `ALL_SERVICES` array in `src/pages/Book Online.c5pg0.js`. Each entry requires:

```js
{
  id: 'unique-id',
  category: 'Category Name',
  name: 'Service Name',
  description: 'Short description.',
  price: 00,        // dollars — not cents
  duration: 60,     // minutes
  image: 'https://…'
}
```

To add a new service add-on, edit the `ADD_ONS` array in `src/pages/Service Page.zapqr.js`.
To add a new promo code, edit the `PROMO_CODES` object in `src/pages/Cart Page.u25lg.js`.

---

## Wix Velo — Booking Flow

```
Book Online → (Service Page) → Cart Page → Booking Form → Booking Calendar → Checkout → Thank You Page
```

**Session storage keys** (`wix-storage` session):

| Key | Value |
|---|---|
| `agt_cart` | JSON array of cart items |
| `agt_booking_info` | JSON object — address, vehicle, contact |
| `agt_selected_date` | ISO date string, e.g. `"2026-03-15"` |
| `agt_selected_time` | 24-hour time string, e.g. `"10:00"` |

Prices are stored and calculated as dollar amounts (not cents).

---

## Tech Stack

- **Wix Velo** — proprietary Wix JavaScript runtime for the multi-page app (`src/`)
- **HTML5 / CSS3 / ES2020** — zero-dependency static site (`index.html`)
- **Wix Data** (`wix-data`) — backend database, primary `Bookings` collection
- **`wix-storage` session** — cart and booking state scoped to the browser tab
- **[Cal.com](https://cal.com)** — scheduling embed (`mobile-detail-appointment`, `month_view` layout)
- **Google Fonts** — Cormorant Garamond, Bebas Neue, Montserrat
- **ESLint 8** + `@wix/eslint-plugin-cli` — linting
- No external frameworks, no bundler required for `index.html`

---

## Known Issues / TODO

- [ ] `src/pages/Home.cfspp.js` has an unresolved git merge conflict — resolve before deploying
- [ ] `src/backend/permissions.json` grants anonymous invoke access to all web methods — tighten for production
- [ ] Payment handles (`$YOURHANDLE`, `@YOURHANDLE`) in `index.html` Step 4 need to be replaced with real Cash App / Venmo handles

---

## Contact

Questions or updates? Reach out at **agentlemenstouch@gmail.com**
