output "webhook_url" {
  description = "Paste this into Stripe -> Developers -> Webhooks -> Add endpoint"
  value       = "${trimsuffix(aws_apigatewayv2_stage.default.invoke_url, "/")}/webhook"
}

output "booking_intent_url" {
  description = "Booking intent endpoint"
  value       = "${trimsuffix(aws_apigatewayv2_stage.default.invoke_url, "/")}/booking-intent"
}

output "create_checkout_session_url" {
  description = "Create checkout session endpoint"
  value       = "${trimsuffix(aws_apigatewayv2_stage.default.invoke_url, "/")}/create-checkout-session"
}

output "lambda_function_name" {
  description = "Lambda function name in AWS Console"
  value       = aws_lambda_function.booking_webhook.function_name
}

output "booking_intent_function_name" {
  description = "Booking intent Lambda function name"
  value       = aws_lambda_function.booking_intent.function_name
}

output "create_checkout_session_function_name" {
  description = "Create checkout session Lambda function name"
  value       = aws_lambda_function.create_checkout_session.function_name
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
