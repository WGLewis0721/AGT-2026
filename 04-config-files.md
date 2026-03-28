# Prompt 04 — Write Config Files and Update .gitignore
# Tool: GitHub.com Copilot
# Repo: WGLewis0721/AGT-2026
# No AWS calls. No deploys. File writing only.

---

## SCOPE

Write or update these files:
  backend-integration/clients/gentlemens-touch/prod.tfvars
  backend-integration/clients/gentlemens-touch/dev.tfvars
  backend-integration/clients/example-client/dev.tfvars
  .gitignore (root — add TRA3 patterns only, do not remove existing entries)

---

## FILE: clients/gentlemens-touch/prod.tfvars

```hcl
# TRA3 — A Gentlemen's Touch — PROD
# Live Stripe keys — real customer bookings
# ⚠️  NEVER commit this file — it is gitignored

client_name           = "gentlemens-touch"
environment           = "prod"
stripe_secret_key     = "REPLACE_WITH_LIVE_KEY"
stripe_webhook_secret = "REPLACE_AFTER_DEPLOY"
textbelt_api_key      = "27fd57601cc3f15573cfff642f9d9d67cde862dboWYRRbQmQTfogoWQpghnmO9WT"
detailer_phone_number = "+13346522601"
aws_region            = "us-east-1"
```

---

## FILE: clients/gentlemens-touch/dev.tfvars

```hcl
# TRA3 — A Gentlemen's Touch — DEV
# Test Stripe keys — Stripe CLI testing only
# ⚠️  NEVER commit this file — it is gitignored

client_name           = "gentlemens-touch"
environment           = "dev"
stripe_secret_key     = "sk_test_51TFmE8LDZQ9SODzC2Wf7Oa2qgjOVlvIntqWnzqfUZsKsgMFMA1Q6X8rUcni7g3NVAdmMVV3et5T1tsqFvLshy0Tb002Br8TTCW"
stripe_webhook_secret = "REPLACE_AFTER_DEPLOY"
textbelt_api_key      = "27fd57601cc3f15573cfff642f9d9d67cde862dboWYRRbQmQTfogoWQpghnmO9WT"
detailer_phone_number = "+13346522601"
aws_region            = "us-east-1"
```

---

## FILE: clients/example-client/dev.tfvars

```hcl
# TRA3 — Example Client Template
# Copy this folder for each new client
# Rename the folder to the client slug
# Fill in all REPLACE_ME values before deploying
# ⚠️  This file IS committed — it contains only placeholders

client_name           = "your-client-slug"
environment           = "dev"
stripe_secret_key     = "sk_test_REPLACE_ME"
stripe_webhook_secret = "REPLACE_AFTER_DEPLOY"
textbelt_api_key      = "REPLACE_ME"
detailer_phone_number = "+1REPLACE"
aws_region            = "us-east-1"
```

---

## .gitignore UPDATE

Find the root .gitignore and ADD these entries.
Do NOT remove any existing entries.
Add a clearly labeled section:

```gitignore
# ─── TRA3 Infrastructure ───────────────────────────────────

# Terraform state and working directories
**/.terraform/
*.tfstate
*.tfstate.backup
*.tfstate.lock.info
.terraform.lock.hcl

# Lambda build artifacts
backend-integration/lambda/lambda_function.zip
backend-integration/layer/layer-build/
backend-integration/layer/layer.zip

# Client credentials — NEVER commit real credentials
backend-integration/clients/*/prod.tfvars
backend-integration/clients/*/dev.tfvars
!backend-integration/clients/example-client/dev.tfvars
```

---

## DEFINITION OF DONE

- [ ] prod.tfvars written with REPLACE placeholders for live keys
- [ ] dev.tfvars written with real test Stripe key
- [ ] example-client/dev.tfvars written with all placeholders
- [ ] .gitignore updated with TRA3 section
- [ ] prod.tfvars and dev.tfvars are gitignored
- [ ] example-client/dev.tfvars is NOT gitignored (exception rule present)
- [ ] No real live Stripe keys committed anywhere
- [ ] No "rosie" anywhere in any file
