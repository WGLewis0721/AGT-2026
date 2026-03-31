# SCAFFOLD — Waiver Agreement Capture (BLOCKING for Handoff)

> **Priority:** FULL STOP — site is NOT live-ready until this ships.
> **Goal:** Legally defensible waiver capture (ESIGN Act / UETA compliant).

---

## Current State (Broken)

| Component | What Happens Now | Problem |
|---|---|---|
| `index.html` → `agreeAndBook()` | Closes modal, calls `initiateCheckout()` | **Captures nothing** — no timestamp, no hash, no record |
| `index.html` → `initiateCheckout()` | POSTs `{package, addons, cal_url, client}` to pricing Lambda | **No waiver data sent** |
| `pricing_lambda.py` | Calculates price, creates Stripe session, returns URL | **No waiver fields in Stripe metadata** |
| `lambda_function.py` (webhook) | On `checkout.session.completed`, writes booking to DynamoDB | **No waiver fields written** |
| `booking_intent.py` | Hardcodes `waiver_accepted: True` — no timestamp/IP/hash | **Not even called by frontend** |

**Bottom line:** A customer clicks "I Agree" and nothing is recorded anywhere.

---

## Target State — 6 Waiver Fields in DynamoDB

| Field | Type | Source | Example |
|---|---|---|---|
| `waiver_accepted` | BOOL | Frontend click event | `true` |
| `waiver_accepted_at` | String (ISO 8601) | Frontend `new Date().toISOString()` | `"2026-03-31T14:22:07.123Z"` |
| `waiver_version` | String | Hardcoded constant, bumped on any clause edit | `"1.0.0"` |
| `waiver_clauses_hash` | String (SHA-256) | Frontend computed hash of clause text | `"a3f8c2..."` |
| `waiver_ip` | String | API Gateway `requestContext.http.sourceIp` | `"72.134.55.12"` |
| `waiver_user_agent` | String | Request header `user-agent` | `"Mozilla/5.0..."` |

These 6 fields satisfy ESIGN Act / UETA requirements: **identity + intent + timestamp + what they agreed to**.

---

## Implementation Plan — 4 Files, 4 Changes

### 1. Frontend: `index.html`

**File:** `index.html` (lines ~3560–3810)

**Change A — Add waiver version constant and hash function (near top of `<script>`):**

```js
// ─── WAIVER TRACKING ────────────────────────────────────────────────────
const WAIVER_VERSION = '1.0.0';

async function computeWaiverHash() {
  const clauseEls = document.querySelectorAll('.waiver-clauses li');
  const text = Array.from(clauseEls).map(li => li.textContent.trim()).join('|');
  const encoded = new TextEncoder().encode(text);
  const hashBuffer = await crypto.subtle.digest('SHA-256', encoded);
  return Array.from(new Uint8Array(hashBuffer)).map(b => b.toString(16).padStart(2, '0')).join('');
}
```

**Change B — Capture waiver data in `agreeAndBook()`:**

```js
let waiverData = null; // module-level variable

async function agreeAndBook() {
  // Capture waiver acceptance BEFORE closing modal
  waiverData = {
    waiver_accepted: true,
    waiver_accepted_at: new Date().toISOString(),
    waiver_version: WAIVER_VERSION,
    waiver_clauses_hash: await computeWaiverHash(),
  };

  const modal = document.getElementById('waiver-modal');
  if (modal) modal.classList.remove('open');
  pendingCalUrl    = '';
  pendingStripeUrl = '';
  document.body.style.overflow = '';

  if (selectedPackage) {
    initiateCheckout();
  }
}
```

**Change C — Send waiver data in `initiateCheckout()`:**

```js
body: JSON.stringify({
  package: selectedPackage,
  addons:  [...selectedAddons],
  cal_url: CAL_URLS[selectedPackage],
  client:  'gentlemens-touch',
  // Waiver acceptance data
  waiver_accepted:    waiverData?.waiver_accepted || false,
  waiver_accepted_at: waiverData?.waiver_accepted_at || null,
  waiver_version:     waiverData?.waiver_version || null,
  waiver_clauses_hash: waiverData?.waiver_clauses_hash || null,
}),
```

**Validation rule:** If `waiverData` is null (user somehow bypassed modal), `initiateCheckout()` should refuse to proceed.

---

### 2. Pricing Lambda: `backend-integration/lambda/pricing_lambda.py`

**File:** `pricing_lambda.py` (lines ~200–270)

**Change A — Extract waiver fields from request body (after `cal_url` extraction):**

```python
# Waiver acceptance fields (passed through to Stripe metadata → webhook → DynamoDB)
waiver_accepted     = body.get("waiver_accepted", False)
waiver_accepted_at  = body.get("waiver_accepted_at", "")
waiver_version      = body.get("waiver_version", "")
waiver_clauses_hash = body.get("waiver_clauses_hash", "")
```

**Change B — Validate waiver before creating checkout session:**

```python
if not waiver_accepted:
    return _response(400, {"error": "Waiver agreement is required"}, origin)
```

**Change C — Extract IP + User-Agent from API Gateway context:**

```python
# Server-side capture (cannot be faked by browser)
request_context = event.get("requestContext", {})
waiver_ip = request_context.get("http", {}).get("sourceIp", "unknown")
waiver_user_agent = (event.get("headers") or {}).get("user-agent", "unknown")
```

**Change D — Pass all 6 waiver fields into Stripe session metadata:**

Update `_create_checkout_session()` to accept and include waiver fields:

```python
metadata={
    "package":     package_key,
    "addons":      ",".join(addon_keys),
    "total":       str(price_data["total"]),
    "deposit":     str(price_data["deposit"]),
    "balance":     str(price_data["balance"]),
    "cal_url":     cal_url,
    "client":      "gentlemens-touch",
    "environment": ENVIRONMENT,
    # ─── Waiver fields ───
    "waiver_accepted":     str(waiver_accepted),
    "waiver_accepted_at":  waiver_accepted_at,
    "waiver_version":      waiver_version,
    "waiver_clauses_hash": waiver_clauses_hash,
    "waiver_ip":           waiver_ip,
    "waiver_user_agent":   waiver_user_agent[:500],  # Stripe metadata 500 char limit
},
```

> **Note:** Stripe metadata values must be strings, max 500 chars each.

---

### 3. Webhook Lambda: `backend-integration/lambda/lambda_function.py`

**File:** `lambda_function.py` (inside `_handle_stripe_webhook` or `_mark_booking_confirmed`)

**Change — When processing `checkout.session.completed`, extract waiver fields from Stripe session metadata and write to DynamoDB:**

```python
metadata = session.get("metadata", {})

# Extract waiver fields from Stripe metadata
waiver_fields = {
    "waiver_accepted":     metadata.get("waiver_accepted") == "True",
    "waiver_accepted_at":  metadata.get("waiver_accepted_at", ""),
    "waiver_version":      metadata.get("waiver_version", ""),
    "waiver_clauses_hash": metadata.get("waiver_clauses_hash", ""),
    "waiver_ip":           metadata.get("waiver_ip", ""),
    "waiver_user_agent":   metadata.get("waiver_user_agent", ""),
}

# Include in DynamoDB update expression alongside existing fields
```

These fields get written to the booking record alongside `payment_status`, `paid_at`, etc.

---

### 4. Terraform: No Schema Change Needed

DynamoDB is schemaless — new attributes are added automatically on write. No `dynamodb.tf` change required for these fields. The GSI addition (`status-updated_at-index`) is a separate task.

---

## Data Flow (After Implementation)

```
User clicks "I Agree & Continue"
  │
  ├─ Frontend captures: timestamp, version, clauses_hash
  │
  ▼
POST /create-checkout
  { package, addons, cal_url, client,
    waiver_accepted, waiver_accepted_at,
    waiver_version, waiver_clauses_hash }
  │
  ├─ Pricing Lambda captures: IP, User-Agent (server-side)
  ├─ Pricing Lambda validates: waiver_accepted == true (else 400)
  ├─ All 6 fields → Stripe session metadata
  │
  ▼
Stripe Checkout (customer pays deposit)
  │
  ▼
Stripe webhook → checkout.session.completed
  │
  ├─ Webhook Lambda reads metadata
  ├─ Writes all 6 waiver fields to DynamoDB booking record
  │
  ▼
DynamoDB booking record:
  { booking_id, status, payment_status, ...,
    waiver_accepted: true,
    waiver_accepted_at: "2026-03-31T14:22:07.123Z",
    waiver_version: "1.0.0",
    waiver_clauses_hash: "a3f8c2...",
    waiver_ip: "72.134.55.12",
    waiver_user_agent: "Mozilla/5.0..." }
```

---

## Waiver Clause Text (Current — v1.0.0)

For reference, these are the 7 clauses in the current modal:

1. I authorize A Gentlemen's Touch to perform the selected detailing services on my vehicle.
2. A Gentlemen's Touch is not liable for pre-existing damage. We will document the vehicle's condition before beginning service.
3. A 20% deposit is required to secure your appointment. The deposit is non-refundable. The remaining balance is due upon service completion.
4. Cancellations made less than 24 hours before the appointment forfeit the deposit. Reschedules with 24+ hours notice carry the deposit forward to the new date.
5. In the event of weather requiring rescheduling, you will be notified at least 24 hours in advance. Your deposit is fully transferred to the rescheduled date.
6. Please remove all personal valuables from your vehicle before service. A Gentlemen's Touch is not responsible for lost or missing items.
7. We stand behind our work with a satisfaction guarantee. If you are not satisfied, contact us within 24 hours and we will make it right at no additional charge.

**When any clause changes → bump `WAIVER_VERSION` and the hash auto-updates.**

---

## Versioning Policy

| When | Action |
|---|---|
| Edit clause wording | Bump `WAIVER_VERSION` (e.g. `1.0.0` → `1.1.0`) |
| Add/remove clause | Bump minor (e.g. `1.1.0` → `1.2.0`) |
| Legal restructure | Bump major (e.g. `1.2.0` → `2.0.0`) |

The SHA-256 hash provides a machine-verifiable proof that the exact text the user saw matches the version on record.

---

## Deployment Sequence

1. **Update `pricing_lambda.py`** — add waiver extraction, validation, metadata pass-through
2. **Update `lambda_function.py`** — add waiver field extraction from Stripe metadata → DynamoDB write
3. **Rebuild + deploy both Lambda zips** (`deploy.ps1` or manual S3 upload + Terraform apply)
4. **Update `index.html`** — add hash function, capture in `agreeAndBook()`, send in `initiateCheckout()`
5. **Push `index.html`** to GitHub Pages
6. **Test end-to-end** — complete a booking, verify 6 waiver fields appear in DynamoDB record

---

## Risk & Edge Cases

| Risk | Mitigation |
|---|---|
| Browser lacks `crypto.subtle` (HTTP context) | Site is HTTPS — `crypto.subtle` is always available |
| User bypasses modal (direct API call) | Pricing Lambda validates `waiver_accepted == true`, returns 400 if missing |
| Stripe metadata 500-char limit | Truncate `waiver_user_agent` to 500 chars |
| Clock skew between browser and server | Timestamp is informational; server IP/UA are authoritative |
| Modal JS error prevents hash computation | Wrap in try/catch, fall back to `"hash_error"` — booking still proceeds, logged for review |
