# AGT — Wix Velo App

This directory contains the **Wix Velo multi-page application** for A Gentlemen's Touch, connected to Wix site ID `685cc33b-0e63-481d-9422-d4bafcc7f070`.

> Active development has moved to the static site at the repository root (`index.html`). This Wix app is kept here for reference.

---

## Directory Structure

```
wix/
├── wix.config.json          # Wix site ID and UI version
├── wix.lock                 # Wix CLI lock file
├── package.json             # Wix CLI dev dependencies
├── .eslintrc.json           # ESLint config (Wix plugin)
└── src/
    ├── pages/               # One .js file per Wix page
    │   ├── masterPage.js    # Global site code (all pages)
    │   ├── Home.cfspp.js
    │   ├── Book Online.c5pg0.js
    │   ├── Service Page.zapqr.js
    │   ├── Cart Page.u25lg.js
    │   ├── Booking Form.vqyyp.js
    │   ├── Booking Calendar.s9swq.js
    │   ├── Checkout.s8k0z.js
    │   ├── Thank You Page.w5kt1.js
    │   ├── Side Cart.o63p3.js
    │   ├── My Bookings.dv8my.js
    │   └── Account Settings.woh8q.js
    ├── public/
    │   └── cartManager.js   # Shared cart/session utilities
    └── backend/
        ├── bookingUtils.jsw # Web methods (backend)
        └── permissions.json # Web method permissions
```

---

## Page Overview

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

## Local Development

```bash
cd wix
npm install       # also runs `wix sync-types` via postinstall
npm run dev       # alias for `wix dev` — opens the Local Editor
npm run lint      # eslint .
```

## Publishing

```bash
wix release       # build and publish a preview release
```

Pushing to the default branch automatically syncs code changes to the connected Wix site.

---

## Booking Flow

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

## Known Issues

- `src/pages/Home.cfspp.js` has an unresolved git merge conflict — resolve before deploying
- `src/backend/permissions.json` grants anonymous invoke access to all web methods — tighten for production
