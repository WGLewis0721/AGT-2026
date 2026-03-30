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
      STRIPE_SECRET_KEY     = data.aws_ssm_parameter.stripe_secret_key.value
      STRIPE_WEBHOOK_SECRET = data.aws_ssm_parameter.stripe_webhook_secret.value
      CALCOM_WEBHOOK_SECRET = local.calcom_webhook_secret
      TEXTBELT_API_KEY      = data.aws_ssm_parameter.textbelt_api_key.value
      DETAILER_PHONE        = data.aws_ssm_parameter.detailer_phone_number.value
      BOOKING_TABLE         = aws_dynamodb_table.bookings.name
      ENVIRONMENT           = var.environment
    }
  }

  tags = local.common_tags
}

resource "aws_lambda_function" "booking_intent" {
  function_name = local.booking_intent_function_name
  role          = aws_iam_role.lambda_exec.arn
  handler       = "booking_intent.lambda_handler"
  runtime       = var.lambda_runtime
  timeout       = var.lambda_timeout
  memory_size   = var.lambda_memory

  s3_bucket = local.s3_bucket
  s3_key    = local.booking_intent_artifact_key

  source_code_hash = filebase64sha256("../../api/booking_intent.zip")

  environment {
    variables = {
      BOOKING_TABLE = aws_dynamodb_table.bookings.name
      ENVIRONMENT   = var.environment
    }
  }

  tags = local.common_tags
}

resource "aws_lambda_function" "create_checkout_session" {
  function_name = local.create_checkout_function_name
  role          = aws_iam_role.lambda_exec.arn
  handler       = "create_checkout_session.lambda_handler"
  runtime       = var.lambda_runtime
  timeout       = var.lambda_timeout
  memory_size   = var.lambda_memory

  s3_bucket = local.s3_bucket
  s3_key    = local.create_checkout_artifact_key

  source_code_hash = filebase64sha256("../../api/create_checkout_session.zip")

  layers = [aws_lambda_layer_version.dependencies.arn]

  environment {
    variables = {
      STRIPE_SECRET_KEY = data.aws_ssm_parameter.stripe_secret_key.value
      DOMAIN_URL        = var.domain_url
      BOOKING_TABLE     = aws_dynamodb_table.bookings.name
      ENVIRONMENT       = var.environment
    }
  }

  tags = local.common_tags
}
