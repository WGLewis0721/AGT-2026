locals {
  lambda_function_name = "rosie-${var.client_name}-${var.environment}-booking-webhook"

  common_tags = {
    Project     = "rosie"
    Client      = var.client_name
    Environment = var.environment
  }
}

resource "aws_iam_role" "lambda_role" {
  name = "rosie-${var.client_name}-${var.environment}-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = "sts:AssumeRole"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy_attachment" "lambda_basic_execution" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${local.lambda_function_name}"
  retention_in_days = 14

  tags = local.common_tags
}

resource "aws_lambda_function" "booking_webhook" {
  function_name = local.lambda_function_name
  role          = aws_iam_role.lambda_role.arn
  runtime       = var.lambda_runtime
  handler       = "lambda_function.lambda_handler"
  filename      = "../lambda/booking-lambda.zip"
  timeout       = var.lambda_timeout
  memory_size   = var.lambda_memory

  source_code_hash = filebase64sha256("../lambda/booking-lambda.zip")

  environment {
    variables = {
      STRIPE_SECRET_KEY     = var.stripe_secret_key
      STRIPE_WEBHOOK_SECRET = var.stripe_webhook_secret
      TEXTBELT_API_KEY      = var.textbelt_api_key
      DETAILER_PHONE        = var.detailer_phone_number
    }
  }

  tags = local.common_tags

  depends_on = [
    aws_cloudwatch_log_group.lambda,
    aws_iam_role_policy_attachment.lambda_basic_execution,
  ]
}

resource "aws_apigatewayv2_api" "booking_api" {
  name          = "rosie-${var.client_name}-${var.environment}-api"
  protocol_type = "HTTP"

  tags = local.common_tags
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.booking_api.id
  name        = "$default"
  auto_deploy = true

  tags = local.common_tags
}

resource "aws_apigatewayv2_integration" "booking_webhook" {
  api_id                 = aws_apigatewayv2_api.booking_api.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.booking_webhook.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "booking_webhook" {
  api_id    = aws_apigatewayv2_api.booking_api.id
  route_key = "POST /webhook"
  target    = "integrations/${aws_apigatewayv2_integration.booking_webhook.id}"
}

resource "aws_lambda_permission" "api_gateway_invoke" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.booking_webhook.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.booking_api.execution_arn}/*/*"

  lifecycle {
    replace_triggered_by = [aws_lambda_function.booking_webhook]
  }
}
