# Prompt 01 — Write Terraform Files
# Tool: GitHub.com Copilot
# Repo: WGLewis0721/AGT-2026
# No AWS calls. No deploys. File writing only.

---

## SCOPE

Write all Terraform files inside backend-integration/terraform/.
Replace everything currently in that folder.
Do not touch any other files in the repo.

---

## NAMING CONVENTION

All AWS resource names follow this pattern:
  tra3-{client_name}-{environment}-{resource}

Examples:
  tra3-gentlemens-touch-prod-booking-webhook   (Lambda)
  tra3-gentlemens-touch-dev-api                (API Gateway)
  /aws/lambda/tra3-gentlemens-touch-prod-booking-webhook  (CloudWatch)
  tra3-{account_id}-deployments                (S3 bucket — shared, no env suffix)

NEVER use "rosie" anywhere.

---

## FILE: terraform/providers.tf

```hcl
terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    # Injected at init time via -backend-config in deploy.ps1
    # Never hardcode bucket, key, or region here
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "tra3"
      Client      = var.client_name
      ManagedBy   = "terraform"
      Environment = var.environment
    }
  }
}

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}
```

---

## FILE: terraform/variables.tf

```hcl
variable "client_name" {
  description = "Client slug — lowercase hyphens only (e.g. gentlemens-touch)"
  type        = string
}

variable "environment" {
  description = "Deployment environment: dev or prod"
  type        = string
  validation {
    condition     = contains(["dev", "prod"], var.environment)
    error_message = "environment must be dev or prod"
  }
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "stripe_secret_key" {
  description = "Stripe secret key"
  type        = string
  sensitive   = true
}

variable "stripe_webhook_secret" {
  description = "Stripe webhook signing secret"
  type        = string
  sensitive   = true
}

variable "textbelt_api_key" {
  description = "Textbelt API key for SMS"
  type        = string
  sensitive   = true
}

variable "detailer_phone_number" {
  description = "Business owner phone number — E.164 format"
  type        = string
}

variable "lambda_runtime" {
  type    = string
  default = "python3.11"
}

variable "lambda_timeout" {
  type    = number
  default = 30
}

variable "lambda_memory" {
  type    = number
  default = 128
}

variable "log_retention" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 14
}

locals {
  account_id    = data.aws_caller_identity.current.account_id
  s3_bucket     = "tra3-${local.account_id}-deployments"
  name_prefix   = "tra3-${var.client_name}-${var.environment}"
  function_name = "${local.name_prefix}-booking-webhook"
}
```

---

## FILE: terraform/s3.tf

```hcl
resource "aws_s3_bucket" "deployments" {
  bucket = local.s3_bucket
  lifecycle { prevent_destroy = true }
}

resource "aws_s3_bucket_versioning" "deployments" {
  bucket = aws_s3_bucket.deployments.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "deployments" {
  bucket = aws_s3_bucket.deployments.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
  }
}

resource "aws_s3_bucket_public_access_block" "deployments" {
  bucket                  = aws_s3_bucket.deployments.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "deployments" {
  bucket = aws_s3_bucket.deployments.id

  rule {
    id     = "expire-old-function-versions"
    status = "Enabled"
    filter { prefix = "functions/" }
    noncurrent_version_expiration { noncurrent_days = 30 }
  }

  rule {
    id     = "expire-old-layer-versions"
    status = "Enabled"
    filter { prefix = "layers/" }
    noncurrent_version_expiration { noncurrent_days = 90 }
  }
}
```

---

## FILE: terraform/iam.tf

```hcl
resource "aws_iam_role" "lambda_exec" {
  name = "${local.name_prefix}-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "lambda_inline" {
  name = "${local.name_prefix}-lambda-policy"
  role = aws_iam_role.lambda_exec.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "arn:aws:logs:${var.aws_region}:${local.account_id}:log-group:/aws/lambda/${local.function_name}:*"
      },
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject"]
        Resource = "arn:aws:s3:::${local.s3_bucket}/*"
      }
    ]
  })
}
```

---

## FILE: terraform/layer.tf

```hcl
resource "aws_lambda_layer_version" "dependencies" {
  layer_name          = "tra3-${var.client_name}-dependencies"
  s3_bucket           = local.s3_bucket
  s3_key              = "layers/dependencies/layer.zip"
  compatible_runtimes = [var.lambda_runtime]
  description         = "stripe + requests — TRA3 platform"

  lifecycle { create_before_destroy = true }
}
```

---

## FILE: terraform/lambda.tf

```hcl
resource "aws_lambda_function" "booking_webhook" {
  function_name = local.function_name
  role          = aws_iam_role.lambda_exec.arn
  handler       = "lambda_function.lambda_handler"
  runtime       = var.lambda_runtime
  timeout       = var.lambda_timeout
  memory_size   = var.lambda_memory

  s3_bucket = local.s3_bucket
  s3_key    = "functions/${var.client_name}/${var.environment}/lambda_function.zip"

  layers = [aws_lambda_layer_version.dependencies.arn]

  environment {
    variables = {
      STRIPE_SECRET_KEY     = var.stripe_secret_key
      STRIPE_WEBHOOK_SECRET = var.stripe_webhook_secret
      TEXTBELT_API_KEY      = var.textbelt_api_key
      DETAILER_PHONE        = var.detailer_phone_number
      ENVIRONMENT           = var.environment
    }
  }

  depends_on = [
    aws_cloudwatch_log_group.booking_webhook,
    aws_iam_role.lambda_exec
  ]
}
```

---

## FILE: terraform/apigw.tf

```hcl
resource "aws_apigatewayv2_api" "booking_api" {
  name          = "${local.name_prefix}-api"
  protocol_type = "HTTP"
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.booking_api.id
  name        = "$default"
  auto_deploy = true

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api_access.arn
    format = jsonencode({
      requestId      = "$context.requestId"
      ip             = "$context.identity.sourceIp"
      httpMethod     = "$context.httpMethod"
      path           = "$context.path"
      status         = "$context.status"
      responseLength = "$context.responseLength"
    })
  }
}

resource "aws_apigatewayv2_integration" "lambda" {
  api_id                 = aws_apigatewayv2_api.booking_api.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.booking_webhook.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "webhook" {
  api_id    = aws_apigatewayv2_api.booking_api.id
  route_key = "POST /webhook"
  target    = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}

resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.booking_webhook.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.booking_api.execution_arn}/*/*"

  lifecycle {
    replace_triggered_by = [aws_lambda_function.booking_webhook]
  }
}
```

---

## FILE: terraform/cloudwatch.tf

```hcl
resource "aws_cloudwatch_log_group" "booking_webhook" {
  name              = "/aws/lambda/${local.function_name}"
  retention_in_days = var.log_retention
}

resource "aws_cloudwatch_log_group" "api_access" {
  name              = "/tra3/${var.client_name}/${var.environment}/api-access"
  retention_in_days = var.log_retention
}
```

---

## FILE: terraform/outputs.tf

```hcl
output "webhook_url" {
  description = "Paste into Stripe → Developers → Webhooks → Add endpoint"
  value       = "${aws_apigatewayv2_stage.default.invoke_url}/webhook"
}

output "lambda_function_name" {
  value = aws_lambda_function.booking_webhook.function_name
}

output "lambda_function_arn" {
  value = aws_lambda_function.booking_webhook.arn
}

output "layer_arn" {
  value = aws_lambda_layer_version.dependencies.arn
}

output "s3_bucket" {
  value = local.s3_bucket
}

output "cloudwatch_log_group" {
  description = "Use this in CloudWatch Logs Insights for debugging"
  value       = aws_cloudwatch_log_group.booking_webhook.name
}
```

---

## VALIDATION

After writing all files run:
  - terraform fmt (from backend-integration/terraform/)
  - terraform validate (from backend-integration/terraform/ — will fail on missing
    backend but that is expected without real S3 state bucket)

Report any fmt or validate errors and fix them.

## DEFINITION OF DONE

- [ ] providers.tf written and formatted
- [ ] variables.tf written with locals block
- [ ] s3.tf written
- [ ] iam.tf written with least-privilege inline policy
- [ ] layer.tf written
- [ ] lambda.tf written
- [ ] apigw.tf written with access logging
- [ ] cloudwatch.tf written
- [ ] outputs.tf written
- [ ] terraform fmt passes with no changes
- [ ] No "rosie" string anywhere in any .tf file
- [ ] No hardcoded credentials anywhere
