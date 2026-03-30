resource "aws_apigatewayv2_api" "booking_api" {
  name          = "${local.name_prefix}-api"
  protocol_type = "HTTP"

  cors_configuration {
    allow_headers = ["content-type"]
    allow_methods = ["OPTIONS", "POST"]
    allow_origins = [local.frontend_origin]
  }

  tags = local.common_tags
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.booking_api.id
  name        = "$default"
  auto_deploy = true

  default_route_settings {
    throttling_burst_limit = 100
    throttling_rate_limit  = 50
  }

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api_access.arn
    format = jsonencode({
      requestId      = "$context.requestId"
      ip             = "$context.identity.sourceIp"
      httpMethod     = "$context.httpMethod"
      path           = "$context.path"
      status         = "$context.status"
      responseLength = "$context.responseLength"
    })
  }

  tags = local.common_tags
}

resource "aws_apigatewayv2_integration" "lambda" {
  api_id                 = aws_apigatewayv2_api.booking_api.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.booking_webhook.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_integration" "booking_intent" {
  api_id                 = aws_apigatewayv2_api.booking_api.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.booking_intent.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_integration" "create_checkout_session" {
  api_id                 = aws_apigatewayv2_api.booking_api.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.create_checkout_session.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "webhook" {
  api_id    = aws_apigatewayv2_api.booking_api.id
  route_key = "POST /webhook"
  target    = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}

resource "aws_apigatewayv2_route" "booking_intent" {
  api_id    = aws_apigatewayv2_api.booking_api.id
  route_key = "POST /booking-intent"
  target    = "integrations/${aws_apigatewayv2_integration.booking_intent.id}"
}

resource "aws_apigatewayv2_route" "create_checkout_session" {
  api_id    = aws_apigatewayv2_api.booking_api.id
  route_key = "POST /create-checkout-session"
  target    = "integrations/${aws_apigatewayv2_integration.create_checkout_session.id}"
}

resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.booking_webhook.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.booking_api.execution_arn}/*/*"

  lifecycle {
    replace_triggered_by = [aws_lambda_function.booking_webhook]
  }
}

resource "aws_lambda_permission" "api_gateway_booking_intent" {
  statement_id  = "AllowAPIGatewayInvokeBookingIntent"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.booking_intent.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.booking_api.execution_arn}/*/*"

  lifecycle {
    replace_triggered_by = [aws_lambda_function.booking_intent]
  }
}

resource "aws_lambda_permission" "api_gateway_create_checkout_session" {
  statement_id  = "AllowAPIGatewayInvokeCreateCheckoutSession"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.create_checkout_session.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.booking_api.execution_arn}/*/*"

  lifecycle {
    replace_triggered_by = [aws_lambda_function.create_checkout_session]
  }
}
