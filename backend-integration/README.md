# TRA3 Backend Integration — Operator Reference

## 1. What This Is

AWS serverless pipeline: customer books on `booking.html` → Square deposit payment → Lambda (Python 3.11) → Textbelt SMS.
SMS fires immediately on Square `payment.updated` (COMPLETED). No manual steps. No Cal.com dependency for SMS.

For the consolidated rollout history, deployment sequence, and operator runbook, see `backend-integration/DEPLOYMENT-GUIDE.md`.

---

## 2. Architecture

```
Customer fills out booking.html
  → booking.js POSTs to POST /create-checkout (pricing_lambda.py)
  → Square Payment Link created; all booking context in pipe-delimited payment_note
  → Customer pays deposit on Square checkout
  ↓
Square fires payment.updated webhook
  ↓
AWS API Gateway (HTTP) → lambda_function.py (Python 3.11)
  ↓
DynamoDB ← full booking record written
Textbelt SMS → detailer (booking details + balance due)
Textbelt SMS → customer (confirmation + balance due)
  ↓
Square redirects customer to success.html
```

**S3 bucket layout** (`tra3-{account_id}-deployments`):

```
tra3-{account_id}-deployments/
├── layers/dependencies/layer.zip          ← squareup + requests (built once)
├── functions/{client}/{env}/lambda_function.zip  ← 3KB code only
└── terraform-state/{client}/{env}/terraform.tfstate
```

**AWS resources per environment:**

```
tra3-{client}-{env}-booking-webhook              Lambda (webhook handler + complete link)
tra3-{client}-{env}-pricing-api                  Lambda (Square Payment Link creation)
tra3-{client}-{env}-api                          API Gateway (HTTP)
tra3-{client}-{env}-lambda-role                  IAM role
/aws/lambda/tra3-{client}-{env}-booking-webhook  CloudWatch log group
```

---

## 3. Environments

| Environment | Square Mode | Purpose |
|-------------|-------------|---------|
| dev | Sandbox | Local testing, code changes |
| prod | Production | Real customer bookings |

Always test against dev. Never run against prod until dev is verified.

---

## 4. Prerequisites

- Terraform >= 1.6.0
- AWS CLI configured
- Python 3.11+ with pip (layer bootstrap only)
- Square account (sandbox + production)
- Textbelt API key

---

## 5. First-Time Setup

1. Bootstrap S3 and layer (once per AWS account):
   ```powershell
   .\backend-integration\scripts\bootstrap-layer.ps1
   ```

2. Fill credentials in dev.tfvars:
   ```
   backend-integration\clients\gentlemens-touch\dev.tfvars
   ```

3. Deploy dev:
   ```powershell
   .\backend-integration\scripts\deploy.ps1 -Client gentlemens-touch -Environment dev
   ```

4. Register dev webhook in Square **Sandbox** mode:
   - Square Developer Console → Sandbox → Webhooks → Add subscription
   - URL: (from terraform output)
   - Events: `payment.created`, `payment.updated`
   - Copy Signature Key → update `dev.tfvars` → `square_webhook_signature_key`

5. Redeploy dev with webhook secret:
   ```powershell
   .\backend-integration\scripts\deploy.ps1 -Client gentlemens-touch -Environment dev
   ```

6. Test by completing a sandbox payment and verifying:
   - CloudWatch log shows `booking_processed`
   - SMS received on detailer phone
   - DynamoDB record created with all fields

7. Repeat steps 2–5 for prod using `prod.tfvars` and Square **Production** mode.
   Set `square_environment = "production"` in `prod.tfvars`.

---

## 6. Adding a New Client

1. Copy example client folder:
   ```powershell
   Copy-Item -Recurse backend-integration\clients\example-client backend-integration\clients\new-client-slug
   ```
2. Fill credentials in `dev.tfvars` and `prod.tfvars`
3. Run `bootstrap-layer.ps1` (if first client on this AWS account)
4. Deploy:
   ```powershell
   .\backend-integration\scripts\deploy.ps1 -Client new-client-slug -Environment dev
   .\backend-integration\scripts\deploy.ps1 -Client new-client-slug -Environment prod
   ```

---

## 7. Routine Deploy (Code Change)

```powershell
# Always dev first
.\backend-integration\scripts\deploy.ps1 -Client gentlemens-touch -Environment dev
# Verify, then prod
.\backend-integration\scripts\deploy.ps1 -Client gentlemens-touch -Environment prod
```

---

## 8. Updating the Layer

When `squareup` or `requests` versions change:

1. Update `backend-integration\layer\requirements.txt`
2. Run `bootstrap-layer.ps1`
3. Deploy both environments

**Critical:** Use `--platform manylinux2014_x86_64` flags in `bootstrap-layer.ps1` when running on Windows.
Without them Lambda fails with `No module named 'pydantic_core._pydantic_core'`.

---

## 9. SMS Format

SMS fires immediately when Square `payment.updated` (COMPLETED) is received.

**Detailer SMS:**
```
🚗 NEW DETAIL BOOKING
──────────────────────────────────
Name:     John Smith
Phone:    (334) 555-1234
Email:    john@example.com
──────────────────────────────────
Service:  Essential Detail
Add-Ons:  Pet Hair Removal
Address:  123 Main St, City AL 36301
Vehicle:  2022 Toyota Camry
Date:     Wed, May 20, 2026 at 9:00 AM
──────────────────────────────────
Deposit:  $28.00
Balance:  $112.00
```

**Customer SMS:**
```
🚗 Booking Confirmed!
A Gentlemen's Touch
──────────────────────────────────
Hi John! Your detail is confirmed.
──────────────────────────────────
Service:  Essential Detail
Add-Ons:  Pet Hair Removal
Address:  123 Main St, City AL 36301
Vehicle:  2022 Toyota Camry
Date:     Wed, May 20, 2026 at 9:00 AM
──────────────────────────────────
Deposit:  $28.00 received
Balance:  $112.00 due after service
──────────────────────────────────
Questions? Call (334) 294-8228
```

Add-Ons, Address, and Vehicle lines are omitted when absent.

The detailer SMS may include a "Mark complete" link (`GET /complete?id=...&t=...`) if `MARK_COMPLETE_SECRET` is configured.

---

## 10. Balance Collection

After service, the detailer collects the remaining balance directly from the customer on-site. The balance amount is shown in the detailer SMS.

---

## 11. Service Packages & Pricing

| Key | Display Name | Full Price | Deposit (20%) |
|-----|-------------|------------|---------------|
| `sm_detail` | Essential Detail (Small Vehicle) | $140 | $28 |
| `md_detail` | Signature Detail (Mid-Size Vehicle) | $175 | $35 |
| `lg_detail` | Executive Detail (Large / SUV) | $220 | $44 |

Prices are server-side authoritative in `pricing_lambda.py` `REAL_PACKAGES`. Mirror any changes in `booking.js` `REAL_PACKAGES` and `lambda_function.py` `REAL_SERVICE_PRICES`.

---

## 12. payment_note Fields

All booking context is embedded in the Square `payment_note` as pipe-delimited `key=value` pairs.
Written by `pricing_lambda.py`, parsed by `lambda_function.py`.

| Key | Example Value |
|-----|--------------|
| `package` | `sm_detail` |
| `addons` | `pet_hair,wax` |
| `total` | `200` |
| `deposit` | `40` |
| `balance` | `160` |
| `cal_url` | `https://cal.com/...` |
| `order_id` | UUID |
| `client` | `gentlemens-touch` |
| `environment` | `prod` |
| `appointment_date` | `2026-05-20` |
| `appointment_time` | `09:00` |
| `customer_name` | `John Smith` |
| `customer_phone` | `3345551234` |
| `customer_email` | `john@example.com` |
| `customer_address` | `123 Main St` |
| `vehicle` | `2022 Toyota Camry` |
| `special_instructions` | `Park in driveway` |
| `waiver` | `2026-05-14T12:00:00Z` |

---

## 13. CloudWatch Queries

Copy into **AWS Console → CloudWatch → Logs Insights**.
Log group: `/aws/lambda/tra3-gentlemens-touch-{env}-booking-webhook`

**All processed bookings:**
```
fields @timestamp, @message
| filter @message like /booking_processed/
| sort @timestamp desc
| limit 50
```

**Failed SMS:**
```
fields @timestamp, @message
| filter @message like /sms_failed/
| sort @timestamp desc
```

**All Square webhook events:**
```
fields @timestamp, @message
| filter @message like /square_webhook_received/
| sort @timestamp desc
```

**payment_note debug (check note was received):**
```
fields @timestamp, @message
| filter @message like /payment_note_debug/
| sort @timestamp desc
```

---

## 14. Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| Lambda not invoked | Webhook not registered | Register in Square Developer Console |
| Signature verification failed | Wrong webhook signature key | Update SSM `square_webhook_signature_key`, redeploy |
| SMS not received | Textbelt key issue | Check CloudWatch for `sms_failed` |
| Balance shows "Not mapped" | Service key not in `REAL_SERVICE_PRICES` | Add key + price to `lambda_function.py` |
| payment_note empty | note field location differs by Square API version | Check `payment_note_debug` log; `_extract_square_booking` checks `payment.note`, `payment.payment_note`, `order.note` |
| Wrong env receiving events | Square environment mismatch | Check `square_environment` in `prod.tfvars` |
| Layer error: pydantic_core | Windows pip downloaded Windows wheels | Re-run `bootstrap-layer.ps1` with `--platform manylinux2014_x86_64` flags |

---

## 15. Teardown

```powershell
cd backend-integration\terraform
terraform destroy -var-file="..\clients\gentlemens-touch\prod.tfvars" -auto-approve
terraform workspace select dev
terraform destroy -var-file="..\clients\gentlemens-touch\dev.tfvars" -auto-approve
```

> **Note:** S3 bucket has `prevent_destroy = true`. Remove that lifecycle block before destroying the bucket.
