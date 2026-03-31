output "webhook_url" {
  description = "Paste this into Stripe -> Developers -> Webhooks -> Add endpoint"
  value       = "${trimsuffix(aws_apigatewayv2_stage.default.invoke_url, "/")}/webhook"
}

output "lambda_function_name" {
  description = "Lambda function name in AWS Console"
  value       = aws_lambda_function.booking_webhook.function_name
}

output "lambda_function_arn" {
  description = "Lambda function ARN"
  value       = aws_lambda_function.booking_webhook.arn
}

output "bookings_table_name" {
  description = "DynamoDB bookings table name"
  value       = aws_dynamodb_table.bookings.name
}

output "layer_arn" {
  description = "Lambda layer ARN"
  value       = aws_lambda_layer_version.dependencies.arn
}

output "s3_bucket" {
  description = "Shared deployment artifacts bucket"
  value       = local.s3_bucket
}

output "cloudwatch_log_group" {
  description = "Lambda CloudWatch log group"
  value       = aws_cloudwatch_log_group.booking_webhook.name
}

output "daily_cost_report_topic_arn" {
  description = "SNS topic ARN for the daily AWS cost report (prod only)"
  value       = local.billing_enabled ? aws_sns_topic.daily_cost_report[0].arn : null
}

output "daily_cost_report_email" {
  description = "Billing email recipient (prod only)"
  value       = local.billing_enabled ? var.billing_report_email : null
}
