# TRA3 — Copilot Instructions
# A Gentlemen's Touch Mobile Detailing (AGT)
# Last updated: 2026-03-28

## What This Is
AWS serverless booking + payment + SMS automation for a mobile detailing business.
Stripe collects deposits at Cal.com booking → Lambda processes webhooks
→ Textbelt sends SMS to detailer and customer.
No manual steps. No URLs in SMS. Balance collected via Stripe invoices.

## Project Name
TRA3. Never use "Rosie" — that name is retired. Search and replace if found.

## Repo
WGLewis0721/AGT-2026
backend-integration/ — all infrastructure lives here
DO NOT touch: index.html, images/, wix/

## Environments
Default to dev. Always confirm before deploying prod.

| Env  | Stripe mode | tfvars file |
|------|-------------|-------------|
| dev  | Test        | clients/{client}/dev.tfvars |
| prod | Live        | clients/{client}/prod.tfvars |

Deploy commands:
  .\scripts\deploy.ps1 -Client gentlemens-touch -Environment dev
  .\scripts\deploy.ps1 -Client gentlemens-touch -Environment prod

## AWS Resource Naming
Pattern: tra3-{client}-{environment}-{resource}
S3 bucket: tra3-{account_id}-deployments (shared, no env suffix)
NEVER use "rosie" in any resource name, variable, tag, or comment.

## Lambda Architecture
Layer: stripe + requests (built by bootstrap-layer.ps1, uploaded to S3)
Function zip: lambda_function.py ONLY (~3KB)
S3 paths:
  layers/dependencies/layer.zip
  functions/{client}/{env}/lambda_function.zip

After ANY change to lambda_function.py:
  Compress-Archive lambda_function.py → lambda_function.zip
  deploy.ps1 uploads it automatically

After ANY change to layer/requirements.txt:
  Run bootstrap-layer.ps1

## SMS Rules
Provider: Textbelt (outbound only)
NEVER put URLs in SMS — Textbelt blocks them
Two SMS per booking:
  1. Detailer: booking details + deposit + balance due
  2. Customer: confirmation + balance due
Skip customer SMS gracefully if no phone on file.
Customer SMS failure = log + continue (return 200)
Detailer SMS failure = return 500

## Balance Collection
Detailer uses Stripe app after service:
  Stripe → Invoices → Create → email + amount → Send
Lambda shows balance amount in SMS. No links. No automation needed.

## Service Prices
SM Detail / Small  = $100
MD Detail / Medium = $150
LG Detail / Large  = $200
Dict: SERVICE_PRICES in lambda_function.py
Balance = max(full_price - deposit_paid, 0)

## Stripe Fields
Custom fields from Payment Link:
  service  = what was booked
  date     = requested date
  location = service address
Use .get() with "Not specified" fallback — test events won't have these.

## Client: A Gentlemen's Touch
Slug:        gentlemens-touch
City:        Montgomery, Alabama
Phone:       (334) 294-8228
Email:       gentlemenstouch5@gmail.com
Test phone:  +13346522601

Cal.com booking links:
  SM: https://cal.com/william-g.-lewis-ai51kb/mobile-detail-appointment-service-1
  MD: https://cal.com/william-g.-lewis-ai51kb/mobile-detail-appointment-service-2
  LG: https://cal.com/william-g.-lewis-ai51kb/mobile-detail-appointment-service-3

## Testing
Test only against dev. Never trigger against prod.
  stripe trigger checkout.session.completed  →  hits dev Lambda

After every deploy confirm CloudWatch shows:
  stripe_webhook_received → balance_calculated →
  detailer_sms_sent → customer_sms_skipped/sent → booking_processed

## CloudWatch Log Groups
  dev:  /aws/lambda/tra3-gentlemens-touch-dev-booking-webhook
  prod: /aws/lambda/tra3-gentlemens-touch-prod-booking-webhook

## Common Mistakes to Avoid
- Never bundle stripe/requests in Lambda zip — layers only
- Never put URLs in SMS
- Never commit prod.tfvars or dev.tfvars
- Never use "rosie" in any name
- Never deploy prod without testing dev first
- Never run stripe trigger without --api-key for live mode (don't — use dev)
