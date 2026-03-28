output "webhook_url" {
  description = "Paste this into Stripe -> Developers -> Webhooks -> Add endpoint"
  value       = "${aws_apigatewayv2_api.booking_api.api_endpoint}/webhook"
}

output "lambda_function_name" {
  description = "Lambda function name in AWS Console"
  value       = aws_lambda_function.booking_webhook.function_name
}

output "lambda_function_arn" {
  description = "Lambda function ARN"
  value       = aws_lambda_function.booking_webhook.arn
}
