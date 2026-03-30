# The shared TRA3 S3 bucket is bootstrapped by scripts/bootstrap-layer.ps1.
# It stores Terraform remote state, Lambda code archives, and the shared
# dependency layer artifact. Managing it outside Terraform avoids a circular
# dependency because the same bucket is used as the Terraform backend.

locals {
  account_id                    = data.aws_caller_identity.current.account_id
  name_prefix                   = "tra3-${var.client_name}-${var.environment}"
  function_name                 = "${local.name_prefix}-booking-webhook"
  booking_intent_function_name  = "${local.name_prefix}-booking-intent"
  create_checkout_function_name = "${local.name_prefix}-create-checkout-session"
  booking_table_name            = "${local.name_prefix}-bookings"
  cost_reporter_name            = "${local.name_prefix}-cost-report"
  s3_bucket                     = "tra3-${local.account_id}-deployments"
  lambda_artifact_key           = "functions/${var.client_name}/${var.environment}/lambda_function.zip"
  booking_intent_artifact_key   = "functions/${var.client_name}/${var.environment}/booking_intent.zip"
  create_checkout_artifact_key = (
    "functions/${var.client_name}/${var.environment}/create_checkout_session.zip"
  )
  cost_reporter_artifact_key = (
    "functions/${var.client_name}/${var.environment}/cost_reporter.zip"
  )
  layer_artifact_key = "layers/dependencies/layer.zip"
  billing_enabled    = var.environment == "prod" && var.billing_report_email != ""
  frontend_origin    = join("", regexall("^https?://[^/]+", var.domain_url))

  common_tags = {
    Project     = "tra3"
    Client      = var.client_name
    Environment = var.environment
  }
}
