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

variable "stripe_secret_key_parameter_name" {
  description = "SSM Parameter Store name for the Stripe secret key."
  type        = string
}

variable "stripe_webhook_secret_parameter_name" {
  description = "SSM Parameter Store name for the Stripe webhook signing secret."
  type        = string
}

variable "calcom_webhook_secret_parameter_name" {
  description = "Optional SSM Parameter Store name for the Cal.com webhook signing secret."
  type        = string
  default     = ""
}

variable "textbelt_api_key_parameter_name" {
  description = "SSM Parameter Store name for the Textbelt API key."
  type        = string
}

variable "detailer_phone_number_parameter_name" {
  description = "SSM Parameter Store name for the business owner phone number."
  type        = string
}

variable "domain_url" {
  description = "Frontend URL used for Stripe checkout success and cancel redirects."
  type        = string
}

variable "billing_report_email" {
  description = "Daily billing report email recipient. Leave blank to disable billing emails."
  type        = string
  default     = ""

  validation {
    condition = (
      var.billing_report_email == ""
      || can(regex("^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$", var.billing_report_email))
    )
    error_message = "billing_report_email must be blank or a valid email address."
  }
}

variable "billing_schedule_expression" {
  description = "EventBridge schedule expression for the daily billing report."
  type        = string
  default     = "rate(1 day)"
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
