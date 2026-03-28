# Backend Integration

This backend provisions an AWS webhook pipeline for Stripe Payment Links. When a customer completes payment, Stripe sends a `checkout.session.completed` webhook to API Gateway, Lambda verifies the signature, calculates the remaining balance, and Textbelt sends SMS notifications to the detailer and customer. There is no database in this setup.

## Prerequisites

- Terraform >= 1.5.0
- AWS CLI configured
- Python 3.11+ with pip
- Stripe account (test mode)
- Textbelt account

## First-Time Setup

1. Copy `clients/example-client/` to `clients/your-client-name/`.
2. Fill in `clients/your-client-name/prod.tfvars`.
3. Run `.\scripts\deploy.ps1 -Client your-client-name`.
4. Copy the prod `webhook_url` output into Stripe Live mode Webhooks.
5. Add `stripe_webhook_secret` to `prod.tfvars`.
6. Re-run `.\scripts\deploy.ps1 -Client your-client-name`.
7. Fill in `clients/your-client-name/dev.tfvars`.
8. Run `.\scripts\deploy.ps1 -Client your-client-name -Environment dev`.
9. Copy the dev `webhook_url` output into Stripe Test mode Webhooks.
10. Add `stripe_webhook_secret` to `dev.tfvars`.
11. Re-run `.\scripts\deploy.ps1 -Client your-client-name -Environment dev`.

## Environments

Two Lambda environments exist per client: `dev` and `prod`. They are completely isolated with separate Lambda functions, separate API Gateways, separate Stripe webhook endpoints, and separate CloudWatch log groups. The deploy script also isolates Terraform state by workspace so `dev` does not overwrite `prod`.

| Environment | Stripe Mode | Use For |
|---|---|---|
| `prod` | Live | Real customer bookings |
| `dev` | Test | Stripe CLI testing, code changes |

**Deploy prod (default):**
`.\scripts\deploy.ps1 -Client gentlemens-touch`

**Deploy dev:**
`.\scripts\deploy.ps1 -Client gentlemens-touch -Environment dev`

Always test against `dev` before touching `prod`.
The Stripe CLI only works against `dev` with test mode keys.
Real Payment Link bookings always hit `prod`.

### Credentials files

- `clients/{client}/prod.tfvars` -> live Stripe keys, real phone numbers
- `clients/{client}/dev.tfvars` -> test Stripe keys, test phone numbers
- Both files are gitignored. Never commit real credentials.

### CloudWatch log groups

- `prod`: `/aws/lambda/rosie-{client}-prod-booking-webhook`
- `dev`: `/aws/lambda/rosie-{client}-dev-booking-webhook`

### Stripe webhook endpoints

- `prod`: register in Stripe Dashboard -> Live mode -> Webhooks
- `dev`: register in Stripe Dashboard -> Test mode -> Webhooks
- Each environment has its own signing secret. Never mix them.

## Stripe Payment Link Custom Fields

| Label | Key | Type |
|---|---|---|
| Service | `service` | Text |
| Date | `date` | Text |
| Location | `location` | Text |

## Example SMS Output

```text
🚗 NEW DETAIL BOOKING
──────────────────────
Name:     Jane Doe
Phone:    +15551234567
Email:    jane@example.com
──────────────────────
Service:  Full Detail
Date:     2026-04-02
Location: Downtown Birmingham
──────────────────────
Deposit:  $30.00
Balance:  $120.00
```

## Balance Collection

After service completion, the detailer sends the customer a Stripe invoice for the remaining balance directly from the Stripe mobile app or dashboard.

`Stripe app -> Invoices -> Create -> enter customer email + amount -> Send`

The booking SMS sent to the detailer includes the balance amount due so the detailer always knows the correct amount to invoice.
No custom infrastructure is required for balance collection.

## Troubleshooting

- Wrong environment receiving webhooks -> check the Stripe Dashboard mode toggle. Live mode webhooks go to the `prod` endpoint only. Test mode webhooks go to the `dev` endpoint only.
- Stripe CLI trigger failing with `Invalid token` -> you are using a live key. Run Stripe CLI against the `dev` environment only.
- Terraform wants to replace the other environment -> use `.\scripts\deploy.ps1` so the correct Terraform workspace is selected automatically.

## Teardown

From `backend-integration/terraform`, run:

```powershell
terraform workspace select dev
terraform destroy -var-file="../clients/your-client-name/dev.tfvars"

terraform workspace select default
terraform destroy -var-file="../clients/your-client-name/prod.tfvars"
```
