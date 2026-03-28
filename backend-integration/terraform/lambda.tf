resource "aws_lambda_function" "booking_webhook" {
  function_name = local.function_name
  role          = aws_iam_role.lambda_exec.arn
  handler       = "lambda_function.lambda_handler"
  runtime       = var.lambda_runtime
  timeout       = var.lambda_timeout
  memory_size   = var.lambda_memory

  s3_bucket = local.s3_bucket
  s3_key    = local.lambda_artifact_key

  source_code_hash = filebase64sha256("../lambda/lambda_function.zip")

  layers = [aws_lambda_layer_version.dependencies.arn]

  environment {
    variables = {
      STRIPE_SECRET_KEY     = var.stripe_secret_key
      STRIPE_WEBHOOK_SECRET = var.stripe_webhook_secret
      TEXTBELT_API_KEY      = var.textbelt_api_key
      DETAILER_PHONE        = var.detailer_phone_number
      ENVIRONMENT           = var.environment
    }
  }

  tags = local.common_tags

  depends_on = [
    aws_cloudwatch_log_group.booking_webhook,
    aws_iam_role_policy_attachment.lambda_basic_execution,
  ]
}
