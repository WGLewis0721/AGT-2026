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
