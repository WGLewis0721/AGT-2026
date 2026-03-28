# TRA3 - Copilot Instructions
# backend-integration/ context for A Gentlemen's Touch (AGT)

## What This Is
AWS serverless booking + payment + SMS automation for a mobile detailing business.
Stripe collects deposits -> Lambda processes webhooks -> Textbelt sends SMS notifications.

## Environments
Ask which environment is being changed before deploying.
Default to `dev` unless the user explicitly says `prod`.

`dev` uses `clients/gentlemens-touch/dev.tfvars`.
`prod` uses `clients/gentlemens-touch/prod.tfvars`.

Deploy commands:
  .\scripts\deploy.ps1 -Client gentlemens-touch -Environment dev
  .\scripts\deploy.ps1 -Client gentlemens-touch -Environment prod

Use the deploy script so Terraform selects the correct workspace automatically.
`prod` is stored in the default workspace to preserve the existing stack.
`dev` is stored in the `dev` workspace.

## Lambda Function
File: `backend-integration/lambda/lambda_function.py`
Runtime: Python 3.11
Dependencies: `stripe`, `requests`
Package: `backend-integration/lambda/booking-lambda.zip`

After any change to `lambda_function.py`:
  1. Delete `booking-lambda.zip`
  2. Create `build\`
  3. Copy `lambda_function.py` into `build\`
  4. Run `pip install stripe requests -t build\`
  5. Compress `build\*` into `booking-lambda.zip`
  6. Delete `build\`
  7. Run Terraform with the correct environment

## SMS
Outbound SMS uses Textbelt, not Twilio.
API key is stored in the Lambda env var `TEXTBELT_API_KEY`.

Send two SMS messages per booking:
  1. Detailer SMS with booking details and balance due
  2. Customer confirmation SMS with deposit received and remaining balance guidance

Skip the customer SMS gracefully if there is no phone on file.
Only return `500` if the detailer SMS fails.

## Balance Collection
The detailer collects the remaining balance after service via Stripe dashboard.
Open the Stripe app -> Invoices -> Create Invoice -> enter customer email and balance amount -> Send.
Stripe emails the customer a professional invoice.

Lambda SMS shows the balance amount due so the detailer knows what to invoice.
Lambda does not send payment links via SMS.

## Service Prices
`SM Detail` = `$100`
`MD Detail` = `$150`
`LG Detail` = `$200`

Store prices in `SERVICE_PRICES`.
Balance is `full_price - deposit_paid`, never below zero.

## Terraform
Tag all resources with `Project`, `Client`, and `Environment`.
Resource naming pattern:
  `rosie-{client}-{environment}-{resource}`

Do not hardcode credentials in tracked Terraform files.
Do not commit `prod.tfvars` or `dev.tfvars`.
Do not modify `index.html`, `images/`, or `wix/` while working in `backend-integration/`.

## CloudWatch
Log group pattern:
  `/aws/lambda/rosie-{client}-{environment}-booking-webhook`

Keep logs structured JSON with `level` and `event`.
Logs Insights queries live at the top of `lambda_function.py`.

## Testing
Use Stripe CLI only against the `dev` environment with test mode keys.
Real Payment Link bookings always hit `prod`.

After every deploy:
  1. Run `stripe trigger checkout.session.completed` against `dev`
  2. Check CloudWatch for `stripe_webhook_received`
  3. Check CloudWatch for `balance_calculated`
  4. Check CloudWatch for `detailer_sms_sent`
  5. Check CloudWatch for `booking_processed`

## Client Info
Client: A Gentlemen's Touch Mobile Detailing
Location: Montgomery, Alabama
Detailer phone (test): +13346522601
Business phone: (334) 294-8228
Business email: gentlemenstouch5@gmail.com
