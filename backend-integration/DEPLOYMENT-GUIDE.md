# TRA3 Deployment Guide

This guide consolidates the rollout notes, update summaries, and operator docs for the current AGT backend. It reflects the live TRA3 deployment that is now running in AWS and replaces the older scattered summary files as the main deployment reference.

## Current State

The backend is an AWS serverless Stripe webhook flow for A Gentlemen's Touch:

1. Customer pays a Stripe Payment Link deposit.
2. Stripe sends `checkout.session.completed` to API Gateway.
3. API Gateway invokes a Python 3.11 Lambda.
4. Lambda verifies the Stripe signature.
5. Lambda calculates deposit and balance due.
6. Lambda sends:
   - a detailer SMS with booking details, deposit, and balance due
   - a customer confirmation SMS when a phone number is present

Current production design decisions:

- Resource prefix is `tra3-`, not `rosie-`
- Environments are isolated: `dev` and `prod`
- AWS S3 stores Terraform state, Lambda artifacts, and the shared dependency layer
- SMS uses Textbelt, not Twilio
- SMS messages contain no URLs
- Remaining balance is collected manually through Stripe Invoices, not a payment link

## Live Resource Naming

Per environment, the deployed AWS resources follow this pattern:

- Lambda: `tra3-{client}-{environment}-booking-webhook`
- API Gateway: `tra3-{client}-{environment}-api`
- IAM role: `tra3-{client}-{environment}-lambda-role`
- Lambda log group: `/aws/lambda/tra3-{client}-{environment}-booking-webhook`
- API access log group: `/tra3/{client}/{environment}/api-access`
- Shared S3 bucket: `tra3-{account_id}-deployments`

For `gentlemens-touch`, the current deployed names are:

- `tra3-gentlemens-touch-dev-booking-webhook`
- `tra3-gentlemens-touch-prod-booking-webhook`
- `tra3-gentlemens-touch-dev-api`
- `tra3-gentlemens-touch-prod-api`

## Repo Layout

The deployment logic lives under `backend-integration/`:

```text
backend-integration/
├── clients/
├── lambda/
├── layer/
├── scripts/
├── terraform/
├── DEPLOYMENT-GUIDE.md
└── README.md
```

Key files:

- `backend-integration/lambda/lambda_function.py`
- `backend-integration/layer/requirements.txt`
- `backend-integration/scripts/bootstrap-layer.ps1`
- `backend-integration/scripts/deploy.ps1`
- `backend-integration/terraform/providers.tf`
- `backend-integration/terraform/s3.tf`
- `backend-integration/terraform/iam.tf`
- `backend-integration/terraform/layer.tf`
- `backend-integration/terraform/lambda.tf`
- `backend-integration/terraform/apigw.tf`
- `backend-integration/terraform/cloudwatch.tf`
- `backend-integration/terraform/outputs.tf`

## Deployment Model

### Shared S3 bucket

The shared bucket is:

- `tra3-{account_id}-deployments`

It is used for:

- Terraform remote state
- Lambda zip artifacts
- Lambda dependency layer zip

Object layout:

```text
tra3-{account_id}-deployments/
├── layers/dependencies/layer.zip
├── functions/{client}/{env}/lambda_function.zip
└── terraform-state/{client}/terraform.tfstate
```

### Shared dependency layer

The Lambda runtime dependencies are built into a Lambda layer from:

- `backend-integration/layer/requirements.txt`

That layer currently packages:

- `stripe`
- `requests`

### Lambda packaging

The Lambda deployment zip now contains code only:

- `lambda_function.py`

Dependencies are not bundled into the Lambda zip anymore because they come from the shared layer.

## First-Time Deployment

### 1. Bootstrap the shared layer and S3 bucket

Run from repo root:

```powershell
.\backend-integration\scripts\bootstrap-layer.ps1
```

What this does:

- gets the AWS account ID
- creates the shared S3 bucket if needed
- enables bucket versioning and encryption
- builds the dependency layer zip
- uploads `layers/dependencies/layer.zip` to S3

### 2. Configure client secrets

Fill in:

- `backend-integration/clients/gentlemens-touch/dev.tfvars`
- `backend-integration/clients/gentlemens-touch/prod.tfvars`

Required values include:

- `stripe_secret_key`
- `stripe_webhook_secret`
- `textbelt_api_key`
- `detailer_phone_number`

### 3. Deploy dev first

```powershell
.\backend-integration\scripts\deploy.ps1 -Client gentlemens-touch -Environment dev
```

What this does:

- packages `lambda_function.py` into `lambda_function.zip`
- uploads the zip to S3
- initializes Terraform with the S3 backend
- selects the `dev` workspace
- applies the TRA3 Terraform stack
- prints the `webhook_url`

### 4. Point Stripe TEST mode to dev

Register the dev webhook URL in Stripe TEST mode for:

- `checkout.session.completed`

Then update:

- `backend-integration/clients/gentlemens-touch/dev.tfvars`

with the Stripe signing secret if needed, and redeploy dev:

```powershell
.\backend-integration\scripts\deploy.ps1 -Client gentlemens-touch -Environment dev
```

### 5. Test dev

Run:

```powershell
stripe trigger checkout.session.completed
```

Expected Lambda log chain:

- `stripe_webhook_received`
- `balance_calculated`
- `detailer_sms_sent`
- `customer_sms_skipped` or `customer_sms_sent`
- `booking_processed`

### 6. Deploy prod

```powershell
.\backend-integration\scripts\deploy.ps1 -Client gentlemens-touch -Environment prod
```

### 7. Point Stripe LIVE mode to prod

Register the prod webhook URL in Stripe LIVE mode for:

- `checkout.session.completed`

Then redeploy prod if the live webhook secret changes:

```powershell
.\backend-integration\scripts\deploy.ps1 -Client gentlemens-touch -Environment prod
```

## Routine Deploys

For code changes:

1. Deploy `dev`
2. Test with Stripe CLI
3. Check CloudWatch and SMS behavior
4. Deploy `prod`

Commands:

```powershell
.\backend-integration\scripts\deploy.ps1 -Client gentlemens-touch -Environment dev
stripe trigger checkout.session.completed
.\backend-integration\scripts\deploy.ps1 -Client gentlemens-touch -Environment prod
```

If layer dependencies change:

```powershell
.\backend-integration\scripts\bootstrap-layer.ps1
.\backend-integration\scripts\deploy.ps1 -Client gentlemens-touch -Environment dev
.\backend-integration\scripts\deploy.ps1 -Client gentlemens-touch -Environment prod
```

## SMS Behavior

### Detailer SMS

The detailer receives:

- customer name
- customer phone
- customer email
- service
- date
- location
- deposit amount
- balance due when the service matches the price map

### Customer SMS

The customer receives:

- booking confirmation
- service
- date
- location
- deposit received
- balance due after service when known

If the customer phone is missing, the customer SMS is skipped without failing the booking.

### Important constraints

- No payment links are sent in SMS
- No TinyURL or URL-shortening flow remains
- No Twilio logic remains
- Textbelt is the active SMS provider

## Balance Collection

Balance collection is manual through Stripe Invoices.

The detailer uses:

- Stripe app -> Invoices -> Create -> customer email + amount -> Send

The Lambda only calculates and reports the balance. It does not send payment links.

## Service Price Mapping

Balance calculation uses these service matches:

- `sm detail` -> `$100`
- `md detail` -> `$150`
- `lg detail` -> `$200`
- `small` -> `$100`
- `medium` -> `$150`
- `large` -> `$200`
- `full detail` -> `$150`

If the service text does not match one of those keys, the deposit is still reported but the balance line is omitted.

## Logging and Validation

The Lambda uses structured JSON logs. Important events include:

- `stripe_webhook_received`
- `balance_calculated`
- `detailer_sms_sent`
- `detailer_sms_failed`
- `customer_sms_sent`
- `customer_sms_skipped`
- `customer_sms_failed`
- `booking_processed`

CloudWatch Logs Insights starting point:

```text
Log group: /aws/lambda/tra3-gentlemens-touch-{environment}-booking-webhook
```

Useful checks after deploy:

- Lambda state is `Active`
- Lambda `LastUpdateStatus` is `Successful`
- `terraform validate` passes
- `stripe trigger checkout.session.completed` succeeds in dev
- CloudWatch shows the expected event chain

## Known Historical Changes

These are the major backend changes that were rolled into the current guide:

### Initial AWS scaffold

The old notes-only backend was replaced with Terraform, Lambda, a deploy script, client config, and backend docs.

### Twilio removed

Twilio was replaced with Textbelt after toll-free verification blocked SMS delivery.

### Pay link flow removed

The earlier payment-link-in-SMS approach was removed. The current design keeps balance calculation but does not send URLs in texts.

### Environment isolation added

The backend was split into:

- `dev` for Stripe test mode and Stripe CLI work
- `prod` for live customer bookings

### TRA3 rename completed

The deployment was migrated from `rosie-*` naming to `tra3-*`, the old `rosie` AWS resources were destroyed, and the new TRA3 stacks were deployed successfully.

### Live validation completed

The current TRA3 deployment has already been validated with:

- bootstrapped S3 + layer upload
- successful `dev` deploy
- successful `prod` deploy
- successful `stripe trigger checkout.session.completed` in `dev`
- CloudWatch confirmation of the expected log chain

## Troubleshooting

### Stripe CLI trigger fails

Make sure you are testing against `dev`, not `prod`.

### Signature verification fails

Check that the Stripe endpoint is pointed at the correct environment URL and that the matching `stripe_webhook_secret` is in the correct tfvars file.

### SMS not received

Check CloudWatch for:

- `detailer_sms_failed`
- `customer_sms_failed`

### Wrong environment is receiving events

Check the Stripe dashboard mode:

- TEST mode -> `dev`
- LIVE mode -> `prod`

### Balance is missing

The service text from Stripe did not match any key in `SERVICE_PRICES`.

## Teardown

From `backend-integration/terraform`:

```powershell
terraform workspace select default
terraform destroy -var-file="..\clients\gentlemens-touch\prod.tfvars" -auto-approve
terraform workspace select dev
terraform destroy -var-file="..\clients\gentlemens-touch\dev.tfvars" -auto-approve
terraform workspace select default
```

If the shared bucket must be removed, do that after Terraform teardown because it is shared infrastructure.

## Source Notes Compiled Into This Guide

This guide was compiled from:

- `artifacts/summaries/codex-updates-372026-v1`
- `artifacts/summaries/github-copilot-updates-v1.txt`
- `artifacts/summaries/copilot-updates-3282026-v1.txt`
- `artifacts/summaries/copilote-updates-3282026-v1.txt`
- `artifacts/summaries/prompt-07-summary.txt`
- the current `backend-integration/README.md`

## Version 2 Architecture

Version 2 introduces:

- DynamoDB as source of truth for bookings
- Backend-driven booking flow
- Stripe dynamic checkout sessions
- Reduced dependency on Cal.com for business logic

Deployment flow remains the same, but backend logic will evolve.
