# GitHub Copilot Instructions — AGT-2026

## Project Overview

This is the codebase for **A Gentlemen's Touch (AGT)**, a luxury mobile car detailing business.
The repo has two distinct, independent layers:

1. **`index.html`** — standalone static marketing + booking funnel (no build step, no framework)
2. **`src/`** — a Wix Velo multi-page application connected to Wix site `685cc33b-0e63-481d-9422-d4bafcc7f070`

Do **not** mix code from these two layers.

---

## Tech Stack

### Wix Velo (`src/`)

- **Framework:** Wix Velo — proprietary Wix JavaScript runtime
- **Page code:** one `.js` file per Wix page in `src/pages/`; `masterPage.js` runs globally on every page
- **Shared utilities:** `src/public/` — import with `'public/<filename>'` (not relative paths)
- **Backend web modules:** `src/backend/*.jsw` — callable from frontend with `'backend/<filename>'`
- **Data:** Wix Data API (`wix-data`) — primary collection is `Bookings`
- **Session state:** `wix-storage` session module (keys defined in `cartManager.js`)
- **Element selection:** `$w('#elementId')` (Velo API — not DOM)
- **Navigation:** `wixLocation.to('/route')`
- **Geolocation:** `wixWindow.getCurrentGeolocation()`
- **Dev command:** `npm run dev` (alias: `wix dev`) — opens Local Editor
- **Lint:** `npm run lint` (`eslint .` with `@wix/eslint-plugin-cli`)

### Static site (`index.html`)

- Vanilla HTML 5 / CSS 3 / ES2020 — zero dependencies, no bundler
- All CSS in a single inline `<style>` block in `<head>`
- All JS in a single inline `<script>` block at the bottom of `<body>`
- Cal.com embed for Step 2 of the booking funnel

---

## Design Language

- **Background:** deep black `#0a0a0a` (`--black`), card surfaces `#161616` (`--black-card`)
- **Accent:** gold `#C9A84C` (`--gold`), lighter gold `#E8C96B` (`--gold-light`)
- **Text:** white `#FFFFFF`, soft white `#F0EDE8` (`--white-soft`), muted `#9A9A9A` (`--white-muted`)
- **Active/selected (Velo pages):** dark navy `#1A1A2E` for buttons/pills
- **Error:** `#E74C3C` (red) — success: `#27AE60` (green)
- **Fonts:** Cormorant Garamond (display/serif), Bebas Neue (logo/headings), Montserrat (body/UI)
- **Tone:** luxury, minimal, editorial — "A Gentlemen's Touch"
- Inline `style` attributes are acceptable in `index.html` for one-off sizing tweaks; match this pattern

---

## Conventions

### Wix Velo

**Check element existence before manipulating optional elements:**

```js
if ($w('#elementId').length) {
    $w('#elementId').show();
}
```

**Session storage keys** (defined in `src/public/cartManager.js`):

| Key | Description |
|---|---|
| `'agt_cart'` | JSON array of cart items |
| `'agt_booking_info'` | JSON object — address, vehicle, contact info |
| `'agt_selected_date'` | ISO date string, e.g. `"2026-03-15"` |
| `'agt_selected_time'` | 24-hour time string, e.g. `"10:00"` |

**Import paths — always use Velo-style, not relative:**

```js
import { getCart, addItem } from 'public/cartManager';
import { submitBooking }    from 'backend/bookingUtils';
import { refreshCartBadge } from 'masterPage';
```

**After any cart mutation, refresh the header badge:**

```js
refreshCartBadge(); // imported from 'masterPage'
```

**Prices:** stored and calculated as **dollar amounts** (not cents). Use `formatPrice(dollars)` from `cartManager.js` for display strings.

**Page file names:** do **not** rename `src/pages/*.js` files — Wix maps pages by filename.

**Code style:**
- JSDoc comments on all exported functions
- Section separator comments: `// ─── Section name ─────────────────`
- `$w.onReady()` at the top; helper functions below

### Static site (`index.html`)

- Booking state lives in the `booking` object (in-memory, no persistence)
- `goToStep(n)` validates before advancing; never call `goToStep` without completing validation
- Use `document.getElementById()` for DOM access (no jQuery or other libraries)
- CSS custom properties (e.g. `var(--gold)`) must be used for all theme colors
- Do not add external JS libraries or CDN script tags

---

## Common Tasks

### Add a new service (Wix — Book Online page)

Edit `ALL_SERVICES` in `src/pages/Book Online.c5pg0.js`. Each entry requires:
`id`, `category`, `name`, `description`, `price` (dollars), `duration`, `image`.

### Add a new service add-on (Wix — Service Page)

Edit the `ADD_ONS` array in `src/pages/Service Page.zapqr.js`.

### Add a new promo code (Wix — Cart Page)

Edit the `PROMO_CODES` object in `src/pages/Cart Page.u25lg.js`. Value is the discount fraction (e.g. `0.15` for 15%).

### Add a new backend function

Add to `src/backend/bookingUtils.jsw`. Update `src/backend/permissions.json` if the function needs non-default permissions.

### Change available booking time slots

Edit the `allSlots` array in `src/backend/bookingUtils.jsw` (`getAvailableSlots`) **and** the fallback array in `src/pages/Booking Calendar.s9swq.js` (`_loadSlots`).

### Add a new page to the Wix site

Create the page in the Wix editor (browser), then sync to the IDE with `wix dev`. A new `src/pages/<Page Name>.<id>.js` file will appear automatically.

### Update static site packages or add-ons (`index.html`)

Edit the `.pick-card` elements inside `#step1` and the `selectPkg()` calls in the booking funnel section of `index.html`.

### Update payment handles (`index.html`)

Search `index.html` for `$YOURHANDLE` and `@YOURHANDLE`; replace with real Cash App / Venmo handles. The Zelle number is `(334) 294-8228`.

---

## Out of Scope

- **Do not** install frontend frameworks (React, Vue, Angular) in the Wix Velo project — Velo is a self-contained runtime
- **Do not** create `src/pages/*.js` files manually from the IDE — page files must be created through the Wix editor
- **Do not** add a build step, bundler, or npm dependencies to `index.html` — it must remain zero-dependency
- **Do not** convert `wix-storage` session to `localStorage` — session scoping is intentional (cart clears on tab close)
- **Do not** change `wix.config.json` `siteId` — it identifies the live Wix production site
- **Do not** use DOM APIs (`document.getElementById`, `querySelector`, etc.) in Velo page code — use `$w()`
- **Do not** hardcode prices in Velo page code outside of `ALL_SERVICES`/`ADD_ONS` data arrays

## AGT Booking System Rules

Always read:
- docs/system-context.md
- docs/skills/

Constraints:
- DynamoDB is the only database
- No frontend business logic
- Keep cost minimal
- No unnecessary dependencies

Internet usage:
- Only official docs (AWS, Square, Cal.com)
- No random blog code

Output:
- clean
- minimal
- production-ready

## Payment Provider: Square

**TRA3 uses Square for payments (not Stripe).** Stripe was fully removed in May 2026.

### Key Implementation Details

- **Pricing Lambda:** Uses Square SDK v42+ (`from square import Square`)
- **Webhook Lambda:** Verifies HMAC-SHA256 signatures, no Square SDK imported
- **Environment:** `SQUARE_ENVIRONMENT` env var controls sandbox/production (independent of AWS `ENVIRONMENT`)
- **Layer:** Must use `--platform manylinux2014_x86_64` pip flags on Windows to download Linux wheels
- **Events:** Listens for `payment.updated` with `status == "COMPLETED"`, ignores `payment.created`

### When Working on Payment Code

- Never add Stripe imports or references
- Square credentials are in SSM under `/tra3/.../square_*`
- Lambda layer requirements are in `backend-integration/layer/requirements.txt` (NOT `pricing-requirements.txt`)
- If layer rebuild fails with `No module named 'pydantic_core._pydantic_core'`, the pip flags are missing in `bootstrap-layer.ps1`
- Sandbox vs production is controlled by `square_environment` in `prod.tfvars`, not by AWS environment

### Useful References

- Square SDK docs: `https://developer.squareup.com/docs/sdks/python`
- Square Checkout API: `https://developer.squareup.com/reference/square/checkout-api`
- Webhook signature verification: `https://developer.squareup.com/docs/webhooks/step3validate`

### TEST_MODE Flag

`test_mode` (Terraform variable) wires through to `TEST_MODE` env var on
both Lambdas and `const TEST_MODE` in `index.html`. When enabled:

- Packages charge $0.01 / $0.10 / $1.00, add-ons $0.01, deposit = 100%
- Frontend rewrites `.package-price` and `.addon-pill-price` text on
  `DOMContentLoaded` to match what's actually charged

When working on pricing code:
- Don't hardcode 0.20 — read `DEPOSIT_RATE` (Python) / `DEPOSIT_RATE`
  (JS) which are flag-aware
- Both Lambdas have `REAL_*` and `TEST_*` price tables; pick via
  `TEST_MODE`. Keep them in sync if you change either side.
- Frontend's `_renderPriceDisplay()` is the single source of truth for
  on-page prices — don't re-hardcode prices in markup; use
  `data-pkg-display` / `data-pkg` / `data-addon` hooks.

### Cal.com Webhook

- Trigger is `BOOKING_CREATED` (not `BOOKING_PAYMENT_INITIATED` — that
  legacy trigger only fired when Cal.com initiated the payment itself
  via its built-in Stripe integration)
- `payload.price` is **ignored** — it reflects whatever is configured on
  the Cal.com event type, not what Square actually charged. Deposit is
  always derived from the package's full price × `DEPOSIT_RATE`
