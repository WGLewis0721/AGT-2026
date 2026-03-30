resource "aws_cloudwatch_log_group" "booking_webhook" {
  name              = "/aws/lambda/${local.function_name}"
  retention_in_days = var.log_retention

  tags = local.common_tags
}

resource "aws_cloudwatch_log_group" "api_access" {
  name              = "/tra3/${var.client_name}/${var.environment}/api-access"
  retention_in_days = var.log_retention

  tags = local.common_tags
}
