# A Gentlemen's Touch — AGT Mobile Detailing

Luxury mobile car detailing site for **A Gentlemen's Touch (AGT)**. The repo has two distinct layers:

| Layer | Path | What it is |
|---|---|---|
| Static marketing site | `index.html` | Single-page HTML/CSS/JS site — no build step required |
| Wix Velo app | `src/` | Multi-page Wix site (siteId `685cc33b-0e63-481d-9422-d4bafcc7f070`) |

---

## Repository Layout

```
AGT-2026/
├── index.html                           # Standalone marketing + booking funnel
├── images/                              # Local image assets for index.html
│   ├── photo-10.png                     # Logo / favicon
│   ├── photo-9.jpeg                     # About section background
│   ├── photo-1.jpeg … photo-5.jpeg      # Portfolio (Before & After) photos
│   └── photo-6.jpeg … photo-8.jpeg, photo-11.png   # Additional assets
├── src/
│   ├── pages/                           # Wix Velo page code (one file per page)
│   │   ├── masterPage.js                # Global — runs on every page
│   │   ├── Home.cfspp.js                # Home page
│   │   ├── Book Online.c5pg0.js         # Service listing / menu
│   │   ├── Service Page.zapqr.js        # Individual service detail
│   │   ├── Cart Page.u25lg.js           # Cart review + promo codes
│   │   ├── Booking Form.vqyyp.js        # Step 1 — customer & vehicle info
│   │   ├── Booking Calendar.s9swq.js    # Step 2 — date & time picker
│   │   ├── Checkout.s8k0z.js            # Step 3 — review & confirm
│   │   ├── Thank You Page.w5kt1.js      # Booking confirmation + tracker
│   │   ├── Side Cart.o63p3.js           # Slide-in cart panel
│   │   ├── My Bookings.dv8my.js         # Member bookings list
│   │   ├── Account Settings.woh8q.js    # Member account
│   │   ├── Privacy Policy.c1qxt.js      # Privacy policy
│   │   ├── Refund Policy.nvn5b.js       # Refund policy
│   │   ├── Terms & Conditions.j1vkb.js  # Terms & Conditions
│   │   └── Accessibility Statement.d3989.js
│   ├── public/
│   │   └── cartManager.js               # Shared cart + booking-info helpers
│   └── backend/
│       ├── bookingUtils.jsw             # Web module: slots, submit, lookup
│       └── permissions.json             # Web-method permission config
├── package.json                         # Dev deps + npm scripts
├── wix.config.json                      # Wix site ID + UI version
├── .eslintrc.json                       # ESLint (Wix CLI recommended rules)
└── wix.lock                             # Wix dependency lock file
```

---

## Stack

| Concern | Technology |
|---|---|
| Wix site framework | [Wix Velo](https://dev.wix.com/docs/develop-websites/articles/wix-velo/frameworks-and-tools/about-velo) |
| Static page | Vanilla HTML 5 / CSS 3 / ES2020 |
| Backend data | Wix Data (`wix-data`) — `Bookings` collection |
| Session state | `wix-storage` session module |
| Scheduling embed | [Cal.com](https://cal.com) — namespace `mobile-detail-appointment`, `month_view` layout |
| Fonts | Google Fonts — Cormorant Garamond, Bebas Neue, Montserrat |
| Linting | ESLint 8 + `@wix/eslint-plugin-cli` |
| CLI | `@wix/cli` |

---

## Local Development (Wix Velo)

**Prerequisites:** Git, Node ≥ 14.8, npm, SSH key added to GitHub.

```bash
git clone <your-repository-url>
cd AGT-2026
npm install        # also runs `wix sync-types` via postinstall
npm run dev        # alias for `wix dev` — opens the Local Editor
```

### Lint

```bash
npm run lint       # eslint .
```

---

## Deploy / Publish

```bash
wix release        # build and publish a preview release
```

Pushing to the default branch automatically syncs code changes to the connected Wix site.

---

## `index.html` — Static Site

`index.html` is a **self-contained** single-page site. Open it directly in a browser or deploy to any static host — no build step required.

### Sections

| Section ID | Heading |
|---|---|
| `#home` | Hero |
| `#about` | Who We Are |
| `#services` | What We Offer |
| `#packages` | Full Luxury Detail Packages |
| `#addons` | Add-On Services |
| `#portfolio` | Before & After |
| `#booking` | Schedule Your Appointment |

### JS Behaviors (inline `<script>`)

- **Sticky nav** — `scroll` listener adds `.scrolled` to `#mainNav` after 60 px; reveals `#navPhone`
- **Mobile menu toggle** — `toggleMenu()` shows/hides `.nav-links`
- **Scroll animations** — `IntersectionObserver` adds `.visible` for fade-in on section entry
- **Booking funnel** — 4-step state machine via `goToStep(n)` with field validation
- **Package selection** — `selectPkg()` (funnel cards) / `selectPackage()` (packages section shortcut)
- **Add-on toggle** — `toggleAddonPill()` / `toggleAddon()`
- **Vehicle condition** — `selectCondition()`
- **Payment method** — `selectPayMethod()` (Cash App, Zelle, Venmo) with per-method instructions
- **Booking confirm** — `confirmBooking()` → reveals `#stepConfirm` panel; hides progress bar
- **Record ID** — auto-generated `AGT-<timestamp36>-<rand4>` on page load (stored in `booking.recordId`)
- **Cal.com embed** — `mobile-detail-appointment` namespace, `month_view` layout (Step 2 of funnel)

### Asset Map

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

**Prices** are stored and calculated as dollar amounts (not cents).

---

## Known Issues / TODO

- [ ] `src/pages/Home.cfspp.js` has an unresolved git merge conflict — resolve before deploying
- [ ] `src/backend/permissions.json` grants anonymous invoke access to all web methods — tighten for production
- [ ] Payment handles (`$YOURHANDLE`, `@YOURHANDLE`) in `index.html` Step 4 need to be replaced with real Cash App / Venmo / Zelle handles
