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
