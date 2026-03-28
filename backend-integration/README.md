# Backend Integration

This backend provisions a lightweight AWS webhook pipeline for Stripe Payment Links. When a customer completes payment, Stripe sends a `checkout.session.completed` webhook to API Gateway, Lambda verifies the signature, and Textbelt sends an SMS notification to the business owner. There is no database in this setup.

## Prerequisites

- Terraform >= 1.5.0
- AWS CLI configured
- Python 3.11+ with pip
- Stripe account (test mode)
- Textbelt account

## First Deploy

1. Copy `clients/example-client/` to `clients/your-client-name/`.
2. Fill in `clients/your-client-name/terraform.tfvars`.
3. Run `.\scripts\deploy.ps1 -Client your-client-name`.
4. Copy the `webhook_url` output into Stripe Webhooks.
5. Add `stripe_webhook_secret` to `terraform.tfvars`.
6. Re-run `.\scripts\deploy.ps1 -Client your-client-name`.

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
Paid:     $175.00
```

## Teardown

From `backend-integration/terraform`, run:

```powershell
terraform destroy -var-file="../clients/your-client-name/terraform.tfvars"
```
