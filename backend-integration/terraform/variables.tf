variable "client_name" {
  description = "Client slug used in resource naming."
  type        = string
}

variable "environment" {
  description = "Deployment environment: dev or prod."
  type        = string
  default     = "prod"

  validation {
    condition     = contains(["dev", "prod"], var.environment)
    error_message = "environment must be either dev or prod."
  }
}

variable "stripe_secret_key" {
  description = "Stripe secret key for API access."
  type        = string
  sensitive   = true
}

variable "stripe_webhook_secret" {
  description = "Stripe webhook signing secret."
  type        = string
  sensitive   = true
}

variable "textbelt_api_key" {
  description = "Textbelt API key for SMS delivery."
  type        = string
  sensitive   = true
}

variable "detailer_phone_number" {
  description = "Business owner phone number in E.164 format."
  type        = string
}

variable "aws_region" {
  description = "AWS region for infrastructure."
  type        = string
  default     = "us-east-1"
}

variable "lambda_runtime" {
  description = "Lambda runtime."
  type        = string
  default     = "python3.11"
}

variable "lambda_timeout" {
  description = "Lambda timeout in seconds."
  type        = number
  default     = 30
}

variable "lambda_memory" {
  description = "Lambda memory size in MB."
  type        = number
  default     = 128
}

variable "log_retention" {
  description = "CloudWatch log retention in days."
  type        = number
  default     = 14
}
