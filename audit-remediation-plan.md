# AGT-2026 Audit Remediation Plan
# Based on: GitHub Copilot Part A Audit — 2026-03-30
# Execution tool: VS Code Copilot
# Priority order: HIGH → MEDIUM → LOW

---

## SUMMARY OF FINDINGS

| # | Severity | Finding | File |
|---|----------|---------|------|
| 1 | HIGH | Terraform state lock missing | providers.tf |
| 2 | MEDIUM | API Gateway no rate limiting | apigw.tf |
| 3 | MEDIUM | SERVICE_PRICES substring matching logic flaw | lambda_function.py |
| 4 | MEDIUM | Dead SERVICE_PRICES keys | lambda_function.py |
| 5 | MEDIUM | Weak webhook routing logic (JSON parse before header check) | lambda_function.py |
| 6 | LOW | Phone number not validated for E.164 | lambda_function.py |
| 7 | LOW | price_cents division without type check | lambda_function.py |
| 8 | LOW | Stripe session null safety | lambda_function.py |
| 9 | LOW | Stale CloudWatch comment block | lambda_function.py |
| 10 | LOW | Redundant Terraform depends_on | lambda.tf |
| 11 | LOW | deploy.ps1 uploads zip without change detection | deploy.ps1 |
| 12 | LOW | bootstrap-layer.ps1 rebuilds without hash check | bootstrap-layer.ps1 |
| 13 | LOW | requests==2.31.0 has CVE-2024-35195 | requirements.txt |
| 14 | INVESTIGATE | s3_bucket output exposes account ID | outputs.tf |
| 15 | INVESTIGATE | Log injection via user input fields | lambda_function.py |

---

## EXECUTION PLAN

Run these prompts in order. Each is self-contained and safe to run independently.

### PROMPT 1 — HIGH — Terraform State Lock (manual + code)
### PROMPT 2 — MEDIUM — API Gateway Rate Limiting + Lambda fixes bundle
### PROMPT 3 — LOW — Dependency upgrade + script efficiency + Terraform cleanup

---

# ═══════════════════════════════════════════════════════════
# PROMPT 1 — HIGH — Terraform State Lock
# Tool: VS Code Copilot
# ═══════════════════════════════════════════════════════════

## CONTEXT

The Terraform S3 backend has no DynamoDB lock table. Without it, concurrent
terraform apply runs can corrupt the state file. This is the highest-risk
finding in the audit.

This is a 2-step fix:
  Step A — Create the DynamoDB table in AWS (manual CLI command)
  Step B — Update providers.tf to reference it (code change)

## STEP A — Run this in your terminal FIRST (one-time setup)

```powershell
aws dynamodb create-table `
  --table-name tra3-terraform-state-lock `
  --attribute-definitions AttributeName=LockID,AttributeType=S `
  --key-schema AttributeName=LockID,KeyType=HASH `
  --billing-mode PAY_PER_REQUEST `
  --region us-east-1

# Verify it was created
aws dynamodb describe-table `
  --table-name tra3-terraform-state-lock `
  --query "Table.TableStatus" `
  --output text
```

Expected output: `CREATING` then `ACTIVE` within 30 seconds.

## STEP B — Code change in providers.tf

You are editing backend-integration/terraform/providers.tf.
Make exactly this one change and nothing else.

Find the backend "s3" block. It currently looks like:

  backend "s3" {}

Replace it with:

  backend "s3" {
    dynamodb_table = "tra3-terraform-state-lock"
  }

IMPORTANT: Do NOT add region, bucket, or key to this block.
Those are injected at terraform init time via -backend-config flags.
Only add dynamodb_table.

After making the change, run terraform init to register the lock table:

```powershell
cd backend-integration\terraform

# Re-init with the lock table (will not destroy existing state)
terraform init `
  -backend-config="bucket=tra3-394281571385-deployments" `
  -backend-config="key=terraform-state/gentlemens-touch/prod/terraform.tfstate" `
  -backend-config="region=us-east-1" `
  -reconfigure

# Verify init succeeded
terraform validate
```

Then commit:

```powershell
cd ..\..
git add backend-integration\terraform\providers.tf
git commit -m "fix: add DynamoDB state lock to Terraform S3 backend (HIGH audit finding)"
git push origin main
```

DEFINITION OF DONE for PROMPT 1:
- [ ] DynamoDB table tra3-terraform-state-lock exists in us-east-1 with status ACTIVE
- [ ] providers.tf contains dynamodb_table = "tra3-terraform-state-lock"
- [ ] terraform init completes without error
- [ ] terraform validate passes
- [ ] Change committed and pushed

---

# ═══════════════════════════════════════════════════════════
# PROMPT 2 — MEDIUM — API Gateway + Lambda Code Fixes
# Tool: VS Code Copilot
# Files: apigw.tf + lambda_function.py
# Deploy: YES — requires terraform apply after changes
# ═══════════════════════════════════════════════════════════

## CONTEXT

This prompt fixes all 4 MEDIUM findings in one pass:
  Finding #2 — API Gateway rate limiting
  Finding #3 — SERVICE_PRICES substring matching
  Finding #4 — Dead SERVICE_PRICES keys
  Finding #5 — Weak webhook routing logic

Make all changes, validate, then deploy both environments.
Do NOT modify any other files.
Do NOT touch index.html, images/, or wix/.

---

## CHANGE 1 — apigw.tf — Add rate limiting (Finding #2)

File: backend-integration/terraform/apigw.tf

Find the aws_apigatewayv2_stage resource block. It currently has
a stage_variables or similar block. Add this block INSIDE the
aws_apigatewayv2_stage resource, before the closing brace:

  default_route_settings {
    throttle_burst_limit = 100
    throttle_rate_limit  = 50
  }

This limits the webhook endpoint to 50 requests/second sustained
with bursts up to 100. More than sufficient for ~100 bookings/month
while protecting against cost abuse attacks.

---

## CHANGE 2 — lambda_function.py — Fix SERVICE_PRICES (Findings #3 and #4)

File: backend-integration/lambda/lambda_function.py

### Change 2A — Remove dead keys (Finding #4)

Find the SERVICE_PRICES dict. It currently contains:

  SERVICE_PRICES = {
      "sm detail": 100.00,
      "md detail": 150.00,
      "lg detail": 200.00,
      "small": 100.00,
      "medium": 150.00,
      "large": 200.00,
      "full detail": 150.00,
  }

Replace it with:

  SERVICE_PRICES = {
      "sm detail": 100.00,
      "md detail": 150.00,
      "lg detail": 200.00,
      "full detail": 150.00,
  }

REASON: "small", "medium", "large" are never sent by Cal.com. Cal.com
sends "SM Detail", "MD Detail", "LG Detail" which become "sm detail" etc.
after .lower(). The dead keys cause maintenance confusion and ambiguous
substring matching.

### Change 2B — Fix substring matching logic (Finding #3)

There are TWO places in the file where SERVICE_PRICES matching occurs —
one in the Cal.com handler and one in the Stripe handler. Find both.
They currently look like this in both places:

  service_lower = <variable>.lower()
  full_price = next(
      (price for key, price in SERVICE_PRICES.items() if key in service_lower),
      None,
  )

Replace BOTH occurrences with:

  service_lower = <variable>.lower().strip()
  # Exact match first — fastest and most accurate
  full_price = SERVICE_PRICES.get(service_lower)
  if full_price is None:
      # Fallback: longest-key substring match to avoid ambiguity
      matched_keys = [k for k in SERVICE_PRICES if k in service_lower]
      if matched_keys:
          full_price = SERVICE_PRICES[max(matched_keys, key=len)]

Keep the variable name (service_lower) whatever it is in each location.
Do not change any surrounding code.

---

## CHANGE 3 — lambda_function.py — Fix webhook routing (Finding #5)

File: backend-integration/lambda/lambda_function.py

Find the lambda_handler routing logic. It currently looks like:

  is_calcom = False
  if not has_stripe_sig:
      try:
          parsed = json.loads(body)
          if "triggerEvent" in parsed:
              is_calcom = True
      except Exception:
          pass

  if is_calcom or has_cal_sig:
      return _handle_calcom_webhook(event, body)
  else:
      return _handle_stripe_webhook(event, body)

Replace it with:

  # Prefer header-based detection — avoids JSON parsing on unrecognized requests
  is_calcom = has_cal_sig
  if not has_stripe_sig and not has_cal_sig:
      # Only attempt JSON parse when no signature headers present
      try:
          parsed = json.loads(body)
          if "triggerEvent" in parsed:
              is_calcom = True
      except Exception:
          pass

  if is_calcom:
      return _handle_calcom_webhook(event, body)
  else:
      return _handle_stripe_webhook(event, body)

REASON: Moving JSON parse after header detection prevents CPU waste
from malformed JSON payloads sent without signature headers.

---

## VALIDATION

After all 3 changes:

```powershell
# Syntax check
python -m py_compile backend-integration\lambda\lambda_function.py
Write-Host "Lambda syntax: OK"

# Terraform format check
cd backend-integration\terraform
terraform fmt -check
terraform validate
cd ..\..
Write-Host "Terraform: OK"
```

---

## REDEPLOY

Rebuild zip and deploy both environments:

```powershell
# Rebuild Lambda zip
$BuildDir = "backend-integration\lambda\build"
New-Item -ItemType Directory -Force -Path $BuildDir | Out-Null
Copy-Item backend-integration\lambda\lambda_function.py $BuildDir\
pip install stripe requests -t $BuildDir --quiet --break-system-packages
Compress-Archive -Path "$BuildDir\*" -DestinationPath "backend-integration\lambda\lambda_function.zip" -Force
Remove-Item -Recurse -Force $BuildDir

# Deploy dev
.\backend-integration\scripts\deploy.ps1 -Client gentlemens-touch -Environment dev

# Deploy prod
.\backend-integration\scripts\deploy.ps1 -Client gentlemens-touch -Environment prod
```

Verify both Lambdas show Active + LastUpdateStatus: Successful.

---

## COMMIT

```powershell
git add backend-integration\terraform\apigw.tf
git add backend-integration\lambda\lambda_function.py
git add backend-integration\lambda\lambda_function.zip
git commit -m "fix: API Gateway rate limiting + SERVICE_PRICES cleanup + routing hardening (MEDIUM audit findings #2-5)"
git push origin main
```

DEFINITION OF DONE for PROMPT 2:
- [ ] apigw.tf has default_route_settings with throttle_burst_limit=100 and throttle_rate_limit=50
- [ ] SERVICE_PRICES has 4 keys only (no "small", "medium", "large")
- [ ] Both Cal.com and Stripe price matching use exact-first + longest-match-fallback
- [ ] lambda_handler routing checks headers before attempting JSON parse
- [ ] python -m py_compile passes
- [ ] terraform fmt passes
- [ ] terraform validate passes
- [ ] Dev deployed Active + Successful
- [ ] Prod deployed Active + Successful
- [ ] Changes committed and pushed

---

# ═══════════════════════════════════════════════════════════
# PROMPT 3 — LOW — Cleanup Bundle
# Tool: VS Code Copilot
# Files: requirements.txt, lambda.tf, deploy.ps1, bootstrap-layer.ps1
# Deploy: YES for requirements change (layer rebuild needed)
# ═══════════════════════════════════════════════════════════

## CONTEXT

This prompt addresses all LOW findings in one pass:
  Finding #6  — Phone number E.164 validation
  Finding #7  — price_cents division safety
  Finding #8  — Stripe session null safety
  Finding #9  — Stale CloudWatch comment block
  Finding #10 — Redundant Terraform depends_on
  Finding #11 — deploy.ps1 no change detection
  Finding #12 — bootstrap-layer.ps1 no hash check
  Finding #13 — requests CVE upgrade

---

## CHANGE 1 — requirements.txt — Upgrade requests (Finding #13)

File: backend-integration/lambda/requirements.txt

Find:
  requests==2.31.0

Replace with:
  requests==2.32.3

REASON: requests 2.31.0 has CVE-2024-35195 (SSRF via proxy handling).
2.32.3 is the patched version. Lambda doesn't use proxies so risk is low,
but this is a clean fix.

NOTE: This requires a layer rebuild and redeploy — handled at end of prompt.

---

## CHANGE 2 — lambda_function.py — Phone validation (Finding #6)

File: backend-integration/lambda/lambda_function.py

Find the _parse_calcom_booking() function. After the customer_phone
extraction block (the lines that set customer_phone from responses),
add this normalization:

  # Normalize phone to E.164 format for Textbelt compatibility
  if customer_phone:
      # Strip all non-digit characters except leading +
      digits_only = ''.join(c for c in customer_phone if c.isdigit())
      if len(digits_only) == 10:
          customer_phone = f"+1{digits_only}"
      elif len(digits_only) == 11 and digits_only.startswith('1'):
          customer_phone = f"+{digits_only}"
      elif not customer_phone.startswith('+'):
          customer_phone = None  # Unrecognized format — skip SMS
          print(json.dumps({"level": "WARN", "event": "invalid_phone_format",
                            "detail": "phone not E.164 compatible"}))

Also add the same block to the Stripe handler after customer_phone is
extracted from customer_details. The logic is identical.

---

## CHANGE 3 — lambda_function.py — Division safety (Finding #7)

File: backend-integration/lambda/lambda_function.py

Find ALL occurrences of this pattern (there are 2 — Cal.com and Stripe handlers):

  price_cents = payload.get("price") or 0
  deposit_paid = price_cents / 100

And also:

  amount_total = session.get("amount_total") or 0
  deposit_paid = amount_total / 100

For each one, replace with a safe version:

  # Cal.com version:
  price_cents = payload.get("price")
  try:
      deposit_paid = float(price_cents) / 100 if price_cents is not None else 0.0
  except (TypeError, ValueError):
      deposit_paid = 0.0
      print(json.dumps({"level": "WARN", "event": "invalid_price_value",
                        "detail": str(price_cents)}))

  # Stripe version:
  amount_total = session.get("amount_total")
  try:
      deposit_paid = float(amount_total) / 100 if amount_total is not None else 0.0
  except (TypeError, ValueError):
      deposit_paid = 0.0
      print(json.dumps({"level": "WARN", "event": "invalid_amount_value",
                        "detail": str(amount_total)}))

---

## CHANGE 4 — lambda_function.py — Stripe null safety (Finding #8)

File: backend-integration/lambda/lambda_function.py

Find the Stripe session parsing block in _handle_stripe_webhook().
It extracts customer_details and then calls .get() on it.

Ensure customer_details is always a dict before calling .get() on it.
Find the line:

  customer_details = session.get("customer_details") or {}

Confirm it already uses `or {}`. If not, add the `or {}` fallback.

Then find the individual field extractions from customer_details.
Ensure each one has a safe fallback:

  customer_name = customer_details.get("name") or "Unknown"
  customer_email = customer_details.get("email") or "No email"
  customer_phone = customer_details.get("phone") or None

If these already use fallbacks, no change needed — just verify and note.

---

## CHANGE 5 — lambda_function.py — Stale comment block (Finding #9)

File: backend-integration/lambda/lambda_function.py

Find the CloudWatch Logs Insights comment block near the top of the file
(approximately lines 1-33). It contains sample queries with log group
pattern references.

Update any log group patterns in the comment block to match the actual
naming convention: /aws/lambda/tra3-gentlemens-touch-{environment}-booking-webhook

If the existing patterns already match this format, no change needed.
If they reference old patterns (rosie-*, or different format), update them.

---

## CHANGE 6 — lambda.tf — Remove redundant depends_on (Finding #10)

File: backend-integration/terraform/lambda.tf

Find the aws_lambda_function resource block. It likely has a depends_on
block that lists the CloudWatch log group and/or IAM role:

  depends_on = [
    aws_cloudwatch_log_group.lambda_log_group,
    aws_iam_role_policy_attachment.lambda_logs,
  ]

Remove the entire depends_on block. Terraform infers these dependencies
automatically from the resource references already present in the block
(the role ARN and log group name are already referenced, making explicit
depends_on redundant).

EXCEPTION: Keep depends_on if there is a lifecycle { replace_triggered_by }
block — that is needed and must stay. Only remove the standalone depends_on.

---

## CHANGE 7 — deploy.ps1 — Add change detection (Finding #11)

File: backend-integration/scripts/deploy.ps1

Find the section where the Lambda zip is uploaded to S3. It likely uses
aws s3 cp or aws s3api put-object.

Before the upload command, add an ETag comparison:

```powershell
# Check if Lambda zip has changed before uploading
$LocalHash = (Get-FileHash -Path $LambdaZipPath -Algorithm MD5).Hash.ToLower()
$RemoteETag = (aws s3api head-object `
    --bucket $S3Bucket `
    --key $LambdaS3Key `
    --query ETag `
    --output text 2>$null) -replace '"', ''

if ($LocalHash -eq $RemoteETag) {
    Write-Host "  Lambda zip unchanged — skipping S3 upload" -ForegroundColor DarkGray
} else {
    Write-Host "  Lambda zip changed — uploading to S3..." -ForegroundColor DarkGray
    # [existing upload command here]
}
```

Replace $LambdaZipPath, $S3Bucket, $LambdaS3Key with whatever variable
names are already used in the script for those values.

---

## CHANGE 8 — bootstrap-layer.ps1 — Add hash check (Finding #12)

File: backend-integration/scripts/bootstrap-layer.ps1

Find the beginning of the script where it starts building the layer.
Before the pip install or zip commands, add a requirements hash check:

```powershell
# Only rebuild layer if requirements.txt has changed
$RequirementsPath = "backend-integration\lambda\requirements.txt"
$HashFile = "backend-integration\lambda\.requirements.hash"
$CurrentHash = (Get-FileHash -Path $RequirementsPath -Algorithm SHA256).Hash

if (Test-Path $HashFile) {
    $StoredHash = Get-Content $HashFile -Raw
    if ($CurrentHash.Trim() -eq $StoredHash.Trim()) {
        Write-Host "requirements.txt unchanged — skipping layer rebuild" -ForegroundColor DarkGray
        exit 0
    }
}

# [existing layer build code continues here]

# Save hash after successful build
$CurrentHash | Set-Content $HashFile
```

Add .requirements.hash to .gitignore if not already present.

---

## VALIDATION

```powershell
# Syntax check
python -m py_compile backend-integration\lambda\lambda_function.py
Write-Host "Lambda syntax: OK"

# Terraform format and validate
cd backend-integration\terraform
terraform fmt -check
terraform validate
cd ..\..
Write-Host "Terraform: OK"
```

---

## LAYER REBUILD AND REDEPLOY

Because requirements.txt changed (requests upgrade), rebuild the layer:

```powershell
# Rebuild bootstrap layer with updated requests
.\backend-integration\scripts\bootstrap-layer.ps1

# Rebuild Lambda zip
$BuildDir = "backend-integration\lambda\build"
New-Item -ItemType Directory -Force -Path $BuildDir | Out-Null
Copy-Item backend-integration\lambda\lambda_function.py $BuildDir\
Compress-Archive -Path "$BuildDir\*" -DestinationPath "backend-integration\lambda\lambda_function.zip" -Force
Remove-Item -Recurse -Force $BuildDir

# Deploy both environments
.\backend-integration\scripts\deploy.ps1 -Client gentlemens-touch -Environment dev
.\backend-integration\scripts\deploy.ps1 -Client gentlemens-touch -Environment prod
```

---

## COMMIT

```powershell
git add backend-integration\lambda\lambda_function.py
git add backend-integration\lambda\requirements.txt
git add backend-integration\lambda\lambda_function.zip
git add backend-integration\terraform\lambda.tf
git add backend-integration\scripts\deploy.ps1
git add backend-integration\scripts\bootstrap-layer.ps1
git commit -m "fix: LOW audit findings — phone validation, division safety, CVE-2024-35195 patch, Terraform cleanup, script efficiency"
git push origin main
```

DEFINITION OF DONE for PROMPT 3:
- [ ] requests upgraded to 2.32.3 in requirements.txt
- [ ] Phone normalization added to both Cal.com and Stripe handlers
- [ ] price_cents and amount_total division is type-safe
- [ ] Stripe customer_details null safety verified
- [ ] CloudWatch comment block patterns match tra3-* naming
- [ ] depends_on removed from lambda.tf (lifecycle block kept if present)
- [ ] deploy.ps1 has ETag comparison before S3 upload
- [ ] bootstrap-layer.ps1 has requirements hash check
- [ ] Layer rebuilt with requests 2.32.3
- [ ] Dev deployed Active + Successful
- [ ] Prod deployed Active + Successful
- [ ] Changes committed and pushed

---

# ═══════════════════════════════════════════════════════════
# INVESTIGATE ITEMS — No code changes, decisions needed
# ═══════════════════════════════════════════════════════════

## Finding #14 — s3_bucket output exposes account ID

The s3_bucket output in outputs.tf exposes the bucket name which
contains your AWS account ID (tra3-394281571385-deployments).

Decision: For internal tooling this is acceptable. If you ever make
this repo public, add sensitive = true to that output.

Current recommendation: No change needed. Document as accepted risk.

## Finding #15 — Log injection via user input

The _sanitize_value() function focuses on redacting secrets but doesn't
explicitly strip newlines from customer-supplied fields. JSON encoding
handles this in structured logs, but it's worth a manual review.

Decision: JSON serialization via json.dumps() automatically escapes
newlines (\n becomes \\n in JSON), so injection is already mitigated.
No code change needed. Document as accepted risk.

---

# ═══════════════════════════════════════════════════════════
# FINAL AUDIT CLOSE-OUT
# ═══════════════════════════════════════════════════════════

After all 3 prompts complete, commit the final audit report:

```powershell
git add backend-integration/AUDIT-2026-03-30.md
git commit -m "docs: add Part A audit report and remediation completion"
git push origin main
```

Then update memory: all audit findings have been addressed. The
codebase is production-ready pending go-live checklist items:
  - Swap $1 test deposits to real prices in Cal.com
  - Swap DETAILER_PHONE to real client phone number
  - Rotate darkfury-superclean-goldclass to machine-generated secret
  - Verify SMS received on real client phone before launch
