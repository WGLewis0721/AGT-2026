# TRA3 Backend Integration — Operator Reference

## 1. What This Is

AWS serverless pipeline: Stripe Payment Link deposits → Lambda (Python 3.11) → Textbelt SMS.
No database. No manual steps. Fires on every `checkout.session.completed` webhook.

---

## 2. Architecture

```
Cal.com booking → customer pays deposit via Stripe Payment Link
    ↓
Stripe fires checkout.session.completed webhook
    ↓
AWS API Gateway (HTTP) → Lambda (Python 3.11)
    ↓
Textbelt SMS → detailer (booking details + balance due)
Textbelt SMS → customer (confirmation + balance due)
```

**S3 bucket layout** (`tra3-{account_id}-deployments`):

```
tra3-{account_id}-deployments/
├── layers/dependencies/layer.zip          ← stripe + requests (built once)
├── functions/{client}/{env}/lambda_function.zip  ← 3KB code only
└── terraform-state/{client}/{env}/terraform.tfstate
```

**AWS resources per environment:**

```
tra3-{client}-{env}-booking-webhook              Lambda function
tra3-{client}-{env}-api                          API Gateway (HTTP)
tra3-{client}-{env}-lambda-role                  IAM role
/aws/lambda/tra3-{client}-{env}-booking-webhook  CloudWatch log group
```

---

## 3. Environments

| Environment | Stripe Mode | Purpose |
|-------------|-------------|---------|
| dev | Test | Stripe CLI testing, code changes |
| prod | Live | Real customer bookings |

Always test against dev. Never run `stripe trigger` against prod.

---

## 4. Prerequisites

- Terraform >= 1.6.0
- AWS CLI configured
- Python 3.11+ with pip (layer bootstrap only)
- Stripe account (test + live)
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

4. Register dev webhook in Stripe **TEST mode**:
   - Stripe → TEST mode → Developers → Webhooks → Add endpoint
   - URL: (from terraform output)
   - Event: `checkout.session.completed`
   - Copy signing secret → update `dev.tfvars` → `stripe_webhook_secret`

5. Redeploy dev with webhook secret:
   ```powershell
   .\backend-integration\scripts\deploy.ps1 -Client gentlemens-touch -Environment dev
   ```

6. Test:
   ```powershell
   stripe trigger checkout.session.completed
   ```
   Verify CloudWatch + SMS on +13346522601.

7. Repeat steps 2–5 for prod using `prod.tfvars` and Stripe **LIVE mode**.

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

When `stripe` or `requests` versions change:

1. Update `backend-integration\layer\requirements.txt`
2. Run `bootstrap-layer.ps1`
3. Deploy both environments

---

## 9. SMS Format

**Detailer SMS:**
```
🚗 NEW DETAIL BOOKING
──────────────────────
Name:     Marcus Johnson
Phone:    +13346522601
Email:    marcus@gmail.com
──────────────────────
Service:  MD Detail
Date:     04-05-2026
Location: 131 Kentucky Oaks St
──────────────────────
Deposit:  $30.00
Balance:  $120.00
```

**Customer SMS:**
```
🚗 Booking Confirmed!
A Gentlemen's Touch
──────────────────────
Hi Marcus! Your detail is booked.
──────────────────────
Service:  MD Detail
Date:     04-05-2026
Location: 131 Kentucky Oaks St
──────────────────────
Deposit:  $30.00 received
Balance:  $120.00 due after service
──────────────────────
Questions? Call (334) 294-8228
```

> **No URLs in any SMS.** Textbelt blocks them.

---

## 10. Balance Collection

After service, detailer sends customer a Stripe invoice:

```
Stripe app → Invoices → Create → customer email + amount → Send
```

Lambda SMS shows balance amount. No payment links in SMS.

---

## 11. Service Prices

| Cal.com Event | Service Label | Full Price | Deposit (20%) |
|---------------|---------------|------------|---------------|
| service-1 | SM Detail | $100 | $20 |
| service-2 | MD Detail | $150 | $30 |
| service-3 | LG Detail | $200 | $40 |

Cal.com booking links:
- SM: https://cal.com/william-g.-lewis-ai51kb/mobile-detail-appointment-service-1
- MD: https://cal.com/william-g.-lewis-ai51kb/mobile-detail-appointment-service-2
- LG: https://cal.com/william-g.-lewis-ai51kb/mobile-detail-appointment-service-3

---

## 12. Stripe Payment Link Custom Fields

| Label | Key | Type |
|-------|-----|------|
| Service | service | Text |
| Date | date | Text |
| Location | location | Text |

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

**All Stripe events:**
```
fields @timestamp, @message
| filter @message like /stripe_webhook_received/
| sort @timestamp desc
```

---

## 14. Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| Lambda not invoked | Webhook not registered | Register in Stripe Dashboard |
| Signature verification failed | Wrong webhook secret | Update tfvars, redeploy |
| SMS not received | Textbelt key issue | Check CloudWatch for `sms_failed` |
| Balance shows None | Service name not in `SERVICE_PRICES` | Add key to `SERVICE_PRICES` dict |
| Wrong env receiving events | Stripe mode mismatch | Check live/test toggle in Stripe |
| `stripe trigger` fails | Running against prod | Always trigger against dev |

---

## 15. Teardown

```powershell
cd backend-integration\terraform
terraform destroy -var-file="..\clients\gentlemens-touch\prod.tfvars" -auto-approve
terraform workspace select dev
terraform destroy -var-file="..\clients\gentlemens-touch\dev.tfvars" -auto-approve
```

> **Note:** S3 bucket has `prevent_destroy = true`. Remove that lifecycle block before destroying the bucket.
