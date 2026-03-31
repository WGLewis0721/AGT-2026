# ─── TRA3 Pricing API Lambda ─────────────────────────────────────────────────
# Separate from the webhook Lambda. Handles Stripe Checkout Session creation.
# Reuses the existing API Gateway (booking_api) — additive route only.

# ─── IAM Role ────────────────────────────────────────────────────────────────

resource "aws_iam_role" "pricing_lambda_role" {
  name = "${local.name_prefix}-pricing-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy_attachment" "pricing_lambda_logs" {
  role       = aws_iam_role.pricing_lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# ─── CloudWatch Log Group ─────────────────────────────────────────────────────

resource "aws_cloudwatch_log_group" "pricing_lambda_log_group" {
  name              = "/aws/lambda/${local.pricing_function_name}"
  retention_in_days = var.log_retention

  tags = local.common_tags
}

# ─── Lambda Function ─────────────────────────────────────────────────────────

resource "aws_lambda_function" "pricing_api" {
  function_name = local.pricing_function_name
  role          = aws_iam_role.pricing_lambda_role.arn
  handler       = var.pricing_lambda_handler
  runtime       = var.pricing_lambda_runtime
  timeout       = var.pricing_lambda_timeout
  memory_size   = var.pricing_lambda_memory

  s3_bucket        = local.s3_bucket
  s3_key           = local.pricing_zip_s3_key
  source_code_hash = filebase64sha256("../lambda/pricing_lambda.zip")

  layers = [aws_lambda_layer_version.dependencies.arn]

  environment {
    variables = {
      STRIPE_SECRET_KEY = data.aws_ssm_parameter.stripe_secret_key.value
      ENVIRONMENT       = var.environment
      ALLOWED_ORIGIN    = var.allowed_origin
    }
  }

  tags = local.common_tags
}

# ─── API Gateway Integration ──────────────────────────────────────────────────

resource "aws_apigatewayv2_integration" "pricing_integration" {
  api_id                 = aws_apigatewayv2_api.booking_api.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.pricing_api.invoke_arn
  payload_format_version = "2.0"
}

# POST /create-checkout route
resource "aws_apigatewayv2_route" "create_checkout" {
  api_id    = aws_apigatewayv2_api.booking_api.id
  route_key = "POST /create-checkout"
  target    = "integrations/${aws_apigatewayv2_integration.pricing_integration.id}"
}

# OPTIONS /create-checkout route (CORS preflight)
resource "aws_apigatewayv2_route" "create_checkout_options" {
  api_id    = aws_apigatewayv2_api.booking_api.id
  route_key = "OPTIONS /create-checkout"
  target    = "integrations/${aws_apigatewayv2_integration.pricing_integration.id}"
}

# Lambda permission for API Gateway
resource "aws_lambda_permission" "pricing_api_gateway" {
  statement_id  = "AllowAPIGatewayInvokePricing"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.pricing_api.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.booking_api.execution_arn}/*/*"
}

# ─── Outputs ─────────────────────────────────────────────────────────────────

output "pricing_api_url" {
  description = "URL for the TRA3 Pricing API create-checkout endpoint"
  value       = "${trimsuffix(aws_apigatewayv2_stage.default.invoke_url, "/")}/create-checkout"
}

output "pricing_lambda_name" {
  description = "Pricing Lambda function name"
  value       = aws_lambda_function.pricing_api.function_name
}
