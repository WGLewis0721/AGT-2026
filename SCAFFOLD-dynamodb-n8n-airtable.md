# SCAFFOLD — DynamoDB + n8n + Airtable Integration Pipeline

> **Priority:** Phase 2 — after waiver capture ships. Not blocking for handoff, but needed for operations.
> **Goal:** Business owner can see/filter/export booking data in Airtable without touching AWS.

---

## Architecture Overview

```
DynamoDB (source of truth)
    │
    ├─── Real-time push (confirmed / canceled)
    │       │
    │       ▼
    │    n8n webhook node
    │       │
    │       ▼
    │    Airtable upsert (by booking_id)
    │
    └─── Weekly batch sync (all statuses)
            │
            ▼
         n8n scheduled workflow (Sunday night)
            │
            ├─── Airtable upsert (full delta)
            └─── S3 CSV archive (monthly)
```

**Key rule:** DynamoDB is the only database. Airtable is a read-only mirror. n8n is the glue. No business logic in n8n or Airtable.

---

## Current DynamoDB State

**Table:** `tra3-gentlemens-touch-prod-bookings`
**Billing:** PAY_PER_REQUEST (on-demand)
**Key:** `booking_id` (S) — hash key only
**GSI:** None (needs one)
**Encryption:** SSE enabled

### Current Fields Written by Webhook Lambda

| Field | Written When | Source |
|---|---|---|
| `booking_id` | Stripe webhook | Generated UUID |
| `status` | Stripe/Cal webhook | `"confirmed"`, etc. |
| `payment_status` | Stripe webhook | `"paid"` |
| `paid_at` | Stripe webhook | ISO timestamp |
| `stripe_session_id` | Stripe webhook | Stripe session ID |
| `stripe_payment_intent` | Stripe webhook | Stripe PI ID |
| `amount_paid` | Stripe webhook | Dollar amount |
| `package` | Stripe webhook | From Stripe metadata |
| `addons` | Stripe webhook | From Stripe metadata |
| `total` | Stripe webhook | From Stripe metadata |
| `deposit` | Stripe webhook | From Stripe metadata |
| `balance` | Stripe webhook | From Stripe metadata |
| `cal_url` | Stripe webhook | From Stripe metadata |
| `customer_name` | Cal webhook | Cal.com event data |
| `customer_email` | Cal webhook | Cal.com event data |
| `customer_phone` | Cal webhook | Cal.com event data |
| `appointment_time` | Cal webhook | Cal.com event data |
| `updated_at` | Every write | ISO timestamp |

### Fields to Add (Waiver — see SCAFFOLD-waiver-capture.md)

| Field | Type |
|---|---|
| `waiver_accepted` | BOOL |
| `waiver_accepted_at` | String (ISO) |
| `waiver_version` | String |
| `waiver_clauses_hash` | String (SHA-256) |
| `waiver_ip` | String |
| `waiver_user_agent` | String |

### Fields to Add (Operations / Sync)

| Field | Type | Purpose |
|---|---|---|
| `created_at` | String (ISO) | Record creation time |
| `last_synced_at` | String (ISO) | Last time synced to Airtable |
| `stripe_event_id` | String | Idempotency — ignore duplicate Stripe events |
| `cal_event_id` | String | Idempotency — ignore duplicate Cal events |

---

## Step 1: Add GSI to DynamoDB (Terraform)

**Why:** Currently you can only query by `booking_id`. To pull "all confirmed bookings this month" you need a scan — expensive and slow. A GSI lets you query by status + date range.

**File:** `backend-integration/terraform/dynamodb.tf`

```hcl
resource "aws_dynamodb_table" "bookings" {
  name         = local.booking_table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "booking_id"

  attribute {
    name = "booking_id"
    type = "S"
  }

  attribute {
    name = "status"
    type = "S"
  }

  attribute {
    name = "updated_at"
    type = "S"
  }

  global_secondary_index {
    name            = "status-updated_at-index"
    hash_key        = "status"
    range_key       = "updated_at"
    projection_type = "ALL"
  }

  server_side_encryption {
    enabled = true
  }

  tags = local.common_tags
}
```

**Query example — "all confirmed bookings in March 2026":**

```python
table.query(
    IndexName="status-updated_at-index",
    KeyConditionExpression="status = :s AND updated_at BETWEEN :start AND :end",
    ExpressionAttributeValues={
        ":s": "confirmed",
        ":start": "2026-03-01T00:00:00Z",
        ":end": "2026-03-31T23:59:59Z",
    },
)
```

---

## Step 2: Status Progression

Enforce a clean state machine in Lambda writes:

```
initiated
    │
    ▼
payment_pending
    │
    ▼
payment_confirmed  ←── Stripe checkout.session.completed
    │
    ▼
appointment_confirmed  ←── Cal.com booking.created
    │
    ▼
completed  ←── Manual or future automation
    │
    ▼
canceled  (can happen from any state)
```

**Implementation:** Use DynamoDB conditional update expressions to prevent invalid transitions:

```python
# Example: only allow payment_confirmed if current status is payment_pending or initiated
table.update_item(
    Key={"booking_id": booking_id},
    UpdateExpression="SET #s = :new_status, payment_confirmed_at = :ts",
    ConditionExpression="#s IN (:s1, :s2)",
    ExpressionAttributeNames={"#s": "status"},
    ExpressionAttributeValues={
        ":new_status": "payment_confirmed",
        ":ts": datetime.utcnow().isoformat() + "Z",
        ":s1": "initiated",
        ":s2": "payment_pending",
    },
)
```

---

## Step 3: Real-Time Push — Lambda → n8n (Confirmed/Canceled Only)

**Why real-time for these two?** Business owner needs to know immediately when money comes in or a booking drops.

### 3a. Add Outbound Webhook to Webhook Lambda

**File:** `backend-integration/lambda/lambda_function.py`

After writing confirmed/canceled status to DynamoDB, POST to n8n:

```python
import hmac
import hashlib
import urllib.request

N8N_WEBHOOK_URL = os.environ.get("N8N_WEBHOOK_URL", "")
N8N_WEBHOOK_SECRET = os.environ.get("N8N_WEBHOOK_SECRET", "")

def _notify_n8n(event_type: str, booking: dict):
    """Send signed event to n8n for Airtable sync + notifications."""
    if not N8N_WEBHOOK_URL:
        return

    payload = json.dumps({
        "event_type": event_type,        # "booking_confirmed" or "booking_canceled"
        "booking_id": booking["booking_id"],
        "status": booking.get("status", ""),
        "payment_status": booking.get("payment_status", ""),
        "customer_name": booking.get("customer_name", ""),
        "customer_phone": booking.get("customer_phone", ""),
        "customer_email": booking.get("customer_email", ""),
        "appointment_time": booking.get("appointment_time", ""),
        "package": booking.get("package", ""),
        "addons": booking.get("addons", ""),
        "total": booking.get("total", ""),
        "deposit": booking.get("deposit", ""),
        "balance": booking.get("balance", ""),
        "updated_at": booking.get("updated_at", ""),
    }).encode()

    # HMAC signature for security
    signature = hmac.new(
        N8N_WEBHOOK_SECRET.encode(), payload, hashlib.sha256
    ).hexdigest()

    req = urllib.request.Request(
        N8N_WEBHOOK_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "X-Webhook-Signature": signature,
        },
    )

    try:
        urllib.request.urlopen(req, timeout=5)
    except Exception as e:
        print(json.dumps({"level": "WARN", "event": "n8n_notify_failed", "error": str(e)}))
```

### 3b. Store n8n Webhook URL in SSM

```bash
aws ssm put-parameter \
  --name "/tra3/gentlemens-touch/prod/n8n_webhook_url" \
  --type "SecureString" \
  --value "https://your-n8n-instance.com/webhook/agt-booking"

aws ssm put-parameter \
  --name "/tra3/gentlemens-touch/prod/n8n_webhook_secret" \
  --type "SecureString" \
  --value "$(openssl rand -hex 32)"
```

### 3c. Add SSM References to Terraform

**File:** `backend-integration/terraform/ssm.tf` — add parameters
**File:** `backend-integration/terraform/lambda.tf` — add env vars `N8N_WEBHOOK_URL`, `N8N_WEBHOOK_SECRET`

---

## Step 4: n8n Workflow — Real-Time Confirmed/Canceled

```
[Webhook Node] ──▶ [Verify HMAC Signature] ──▶ [Switch: event_type]
                                                    │
                                    ┌───────────────┼───────────────┐
                                    ▼                               ▼
                          booking_confirmed                 booking_canceled
                                    │                               │
                                    ▼                               ▼
                        [Airtable: Upsert Row]          [Airtable: Update Row]
                        (key: booking_id)               (status → "canceled")
```

### Airtable Field Map

| Airtable Column | DynamoDB Field | Type |
|---|---|---|
| Booking ID | `booking_id` | Single line text (primary) |
| Status | `status` | Single select |
| Customer Name | `customer_name` | Single line text |
| Phone | `customer_phone` | Phone |
| Email | `customer_email` | Email |
| Package | `package` | Single select |
| Add-ons | `addons` | Multiple select |
| Appointment | `appointment_time` | Date |
| Total | `total` | Currency |
| Deposit Paid | `deposit` | Currency |
| Balance Due | `balance` | Currency |
| Payment Status | `payment_status` | Single select |
| Waiver Signed | `waiver_accepted` | Checkbox |
| Waiver Date | `waiver_accepted_at` | Date |
| Last Updated | `updated_at` | Date |

### Airtable Views (for Business Owner)

| View | Filter | Sort |
|---|---|---|
| **Today's Jobs** | `Appointment = TODAY()` AND `Status != "canceled"` | Appointment ASC |
| **This Week** | `Appointment = THISWEEK()` | Appointment ASC |
| **Unpaid Balances** | `Balance Due > 0` AND `Status = "completed"` | Updated DESC |
| **All Confirmed** | `Status = "confirmed"` | Updated DESC |
| **Canceled** | `Status = "canceled"` | Updated DESC |

---

## Step 5: Weekly Batch Sync (Full Delta)

**When:** Sunday night, 11 PM CT
**What:** Pulls all bookings changed since `last_synced_at` and upserts to Airtable
**Why:** Catches any missed real-time events, syncs enrichment fields, keeps Airtable consistent

### n8n Weekly Workflow

```
[Cron: Sunday 23:00 CT]
      │
      ▼
[AWS Lambda: Invoke query function]
  └─ Query GSI: status-updated_at-index
  └─ Filter: updated_at > last_sync_timestamp
      │
      ▼
[Loop: For each booking]
      │
      ▼
[Airtable: Upsert by booking_id]
      │
      ▼
[Update last_synced_at in DynamoDB]
      │
      ▼
[Log: sync report — count created/updated/failed]
```

### Query Lambda (New — Minimal)

**File:** `backend-integration/lambda/sync_query.py` (new, ~40 lines)

```python
"""Weekly sync query — returns bookings changed since last sync."""

import json
import os
import boto3
from datetime import datetime, timedelta

dynamodb = boto3.resource("dynamodb")
TABLE_NAME = os.environ.get("BOOKING_TABLE_NAME", "")

def lambda_handler(event, context):
    table = dynamodb.Table(TABLE_NAME)
    since = event.get("since", (datetime.utcnow() - timedelta(days=7)).isoformat() + "Z")

    # Query each active status
    results = []
    for status in ["payment_confirmed", "appointment_confirmed", "completed", "canceled"]:
        resp = table.query(
            IndexName="status-updated_at-index",
            KeyConditionExpression="status = :s AND updated_at >= :since",
            ExpressionAttributeValues={":s": status, ":since": since},
        )
        results.extend(resp.get("Items", []))

    return {"count": len(results), "bookings": results}
```

**Terraform:** Small Lambda with DynamoDB read-only policy, no public API route (invoked directly by n8n via AWS credentials or a signed URL).

---

## Step 6: Monthly S3 Archive

**When:** 1st of each month
**What:** Export previous month's Airtable data to S3 as CSV
**Why:** Keeps Airtable base small, provides long-term archive

```
[Cron: 1st of month, 02:00 CT]
      │
      ▼
[n8n: Get Airtable rows where updated_at < 1st of last month]
      │
      ▼
[n8n: Convert to CSV]
      │
      ▼
[n8n: Upload to S3]
  └─ s3://tra3-gentlemens-touch-prod-data/archives/bookings-2026-03.csv
      │
      ▼
[n8n: Delete archived rows from Airtable (optional)]
```

S3 lifecycle policy (already in Terraform `s3.tf`):
- Standard → IA after 30 days
- IA → Glacier after 90 days

---

## Cost Estimate

| Component | Monthly Cost | Notes |
|---|---|---|
| DynamoDB | ~$0.25 | PAY_PER_REQUEST, <100 bookings/month |
| DynamoDB GSI | +$0.00 | Same billing mode, marginal read cost |
| Lambda (sync query) | ~$0.00 | 4 invocations/month, 128MB, <1s each |
| n8n | $0–$20 | Cloud starter plan, or $0 self-hosted |
| Airtable | $0 | Free tier: 1,000 records, 1 base |
| S3 archive | ~$0.01 | Tiny CSVs, lifecycle to Glacier |
| **Total** | **~$0.25–$20** | Depends on n8n hosting choice |

---

## Security Checklist

| Requirement | Implementation |
|---|---|
| Webhook signing | HMAC-SHA256 on all Lambda → n8n payloads |
| Secret storage | SSM Parameter Store (SecureString) for n8n URL + secret |
| Minimal PII in transit | Only send needed fields to n8n (no raw Stripe tokens) |
| Airtable access | API key scoped to one base, stored in n8n credentials |
| S3 encryption | SSE-S3 (already enabled in Terraform) |
| n8n auth | Webhook node validates HMAC before processing |

---

## Implementation Sequence

| Phase | What | Depends On |
|---|---|---|
| **A** | Add GSI to `dynamodb.tf` + `terraform apply` | Nothing |
| **B** | Add `_notify_n8n()` to `lambda_function.py` | SSM params created |
| **C** | Create n8n account + real-time webhook workflow | Phase B |
| **D** | Create Airtable base + field schema + views | Nothing |
| **E** | Connect n8n → Airtable upsert | Phases C + D |
| **F** | Create `sync_query.py` Lambda + Terraform | Phase A (GSI) |
| **G** | Create n8n weekly batch workflow | Phases E + F |
| **H** | Create n8n monthly S3 archive workflow | Phase G |

**Phases A and D can start immediately and in parallel.**
**Waiver capture (SCAFFOLD-waiver-capture.md) should ship FIRST — it populates the waiver fields that flow through this pipeline.**

---

## n8n Hosting Options

| Option | Cost | Reliability | Setup |
|---|---|---|---|
| **n8n Cloud (Starter)** | $20/mo | Managed, 99.9% SLA | 5 min |
| **Self-host on EC2 t3.micro** | ~$8/mo | You own uptime | 1–2 hours |
| **Self-host on Railway/Render** | $5–7/mo | Decent, auto-restart | 30 min |
| **Zapier (alternative)** | $20+/mo | Managed | 10 min, but task-based cost grows |

**Recommendation:** Start with n8n Cloud Starter. Move to self-host later if cost matters.

---

## What This Replaces

| Old Way | New Way |
|---|---|
| Google Forms → Google Sheets for waivers | DynamoDB waiver fields → Airtable mirror |
| Manual DynamoDB console lookups | Airtable views (Today's Jobs, Unpaid, etc.) |
| No export capability | S3 CSV monthly archives |
| No real-time ops visibility | n8n → Airtable push on confirm/cancel |
| Stale spreadsheets | Always-current Airtable synced from source of truth |
