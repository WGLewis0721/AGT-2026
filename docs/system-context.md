# SYSTEM CONTEXT — AGT Booking System

## Purpose
Reusable booking + payment system for service businesses.

## Stack
Frontend: GitHub Pages (vanilla JS)
Backend: AWS Lambda + API Gateway
Database: DynamoDB
Payments: Square (migrated from Stripe, May 2026)
Scheduling: Cal.com API
SMS: Textbelt
Infra: Terraform

## Core Rules
- DynamoDB = source of truth
- Square = payments only
- Cal.com = scheduling only
- No business logic in frontend
- All pricing validated in backend

## Booking Flow
1. Frontend builds booking
2. Backend creates booking record
3. User selects time
4. Square Payment Link created
5. Payment completed
6. Webhook confirms booking
7. SMS sent

## Code Standards
- No duplicate logic
- No unused code
- No hardcoded secrets
- Validate all inputs
- Keep functions small

## Cost Constraint
< $10/month per client

## AI Rules
- Do not overengineer
- Do not introduce new services
- Prefer simple solutions

## Payment Provider: Square

**Current State (as of May 2026):**
TRA3 uses **Square** for payment processing. Stripe was fully replaced in May 2026.

### Square Integration Overview

**Pricing Lambda** (`pricing_lambda.py`):
- Creates Square Payment Links via the Square SDK v42+ (`squareup>=42.0.0`)
- Uses `client.checkout.payment_links.create()` API
- Supports sandbox and production environments via `SQUARE_ENVIRONMENT` env var (independent of AWS `ENVIRONMENT`)
- Stores booking context in pipe-delimited `payment_note` field (format: `package=X|addons=Y|total=Z|...`)
- Returns checkout URL: `https://sandbox.square.link/...` (sandbox) or `https://squareup.com/checkout/...` (production)

**Webhook Lambda** (`lambda_function.py`):
- Verifies Square webhook signatures using HMAC-SHA256 (`x-square-hmacsha256-signature` header)
- Signature calculated over `notification_url + request_body`
- Listens for `payment.created` (ignored) and `payment.updated` (processed when `status == "COMPLETED"`)
- Extracts booking context from `payment.note` field
- No Square SDK imported in webhook handler — uses raw `hmac`, `hashlib`, `base64`

### Required Credentials (stored in AWS SSM)

```
/tra3/gentlemens-touch/prod/square_access_token          # Sandbox or Production Access Token
/tra3/gentlemens-touch/prod/square_location_id           # Square Location ID
/tra3/gentlemens-touch/prod/square_webhook_signature_key # Webhook signature key from Square Developer Console
```

**Current deployment uses sandbox credentials** — when AGT provides production Square credentials, update SSM values and flip `square_environment = "production"` in `prod.tfvars`.

### Square Developer Console Setup

1. Create application at `developer.squareup.com`
2. Get Sandbox Access Token + Location ID from Sandbox tab
3. Register webhook subscription:
   - URL: `https://c4eki550u8.execute-api.us-east-1.amazonaws.com/webhook`
   - Events: `payment.created`, `payment.updated`
   - Copy Signature Key after saving
4. Store all three values in SSM (see paths above)
5. Run `.\backend-integration\scripts\deploy.ps1` to deploy

### Lambda Layer Requirements

**Critical:** The Square SDK v42+ depends on `pydantic` v2, which has native Rust extensions (`pydantic_core`). When rebuilding the Lambda layer on Windows, the bootstrap script **must** force Linux-compatible wheel downloads:

```powershell
pip install -r requirements.txt -t $pythonDir `
  --platform manylinux2014_x86_64 `
  --implementation cp `
  --python-version 311 `
  --only-binary=:all:
```

Without these flags, Windows-compiled binaries are downloaded and Lambda fails with `No module named 'pydantic_core._pydantic_core'`.

The layer requirements file is `backend-integration/layer/requirements.txt` (NOT `pricing-requirements.txt`).

### Key Files Changed in Migration

- `pricing_lambda.py` — replaced Stripe SDK with Square SDK v42+
- `lambda_function.py` — replaced Stripe webhook verification with Square HMAC-SHA256
- `pricing-requirements.txt` — reference only (not used by layer)
- `layer/requirements.txt` — actual layer deps: `squareup>=42.0.0`, `requests`
- `bootstrap-layer.ps1` — added cross-platform pip flags for Linux wheels
- `variables.tf` — added `square_environment` variable, bumped `pricing_lambda_timeout` to 30s
- `pricing-lambda.tf` — added `SQUARE_ENVIRONMENT` env var
- `prod.tfvars` — added `square_environment = "sandbox"`
- `ssm.tf` — replaced Stripe SSM data sources with Square
- `index.html` — updated FAQ to reference Square instead of Stripe

### Stripe Removal Checklist (completed May 2026)

- [x] Pricing Lambda rewritten for Square Payment Links
- [x] Webhook Lambda rewritten for Square signature verification
- [x] Lambda layer rebuilt with `squareup>=42.0.0` and cross-platform wheels
- [x] Terraform SSM data sources migrated from Stripe to Square
- [x] `SQUARE_ENVIRONMENT` decoupled from AWS `ENVIRONMENT`
- [x] Webhook registered in Square Developer Console (sandbox)
- [x] End-to-end tested: checkout → payment → webhook → confirmation
- [x] FAQ copy updated on frontend
- [x] All Stripe references removed from codebase
