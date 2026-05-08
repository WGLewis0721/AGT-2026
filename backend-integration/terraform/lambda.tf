resource "aws_lambda_function" "booking_webhook" {
  function_name    = local.function_name
  role             = aws_iam_role.lambda_exec.arn
  handler          = "lambda_function.lambda_handler"
  runtime          = var.lambda_runtime
  timeout          = var.lambda_timeout
  memory_size      = var.lambda_memory
  s3_bucket        = local.s3_bucket
  s3_key           = local.lambda_artifact_key
  source_code_hash = filebase64sha256("../lambda/lambda_function.zip")
  layers           = [aws_lambda_layer_version.dependencies.arn]

  environment {
    variables = {
      SQUARE_ACCESS_TOKEN          = data.aws_ssm_parameter.square_access_token.value
      SQUARE_LOCATION_ID           = data.aws_ssm_parameter.square_location_id.value
      SQUARE_WEBHOOK_SIGNATURE_KEY = data.aws_ssm_parameter.square_webhook_signature_key.value
      CALCOM_WEBHOOK_SECRET        = local.calcom_webhook_secret
      TEXTBELT_API_KEY             = data.aws_ssm_parameter.textbelt_api_key.value
      DETAILER_PHONE               = data.aws_ssm_parameter.detailer_phone_number.value
      BOOKING_TABLE                = aws_dynamodb_table.bookings.name
      ENVIRONMENT                  = var.environment
      TEST_MODE                    = var.test_mode ? "true" : "false"
    }
  }

  tags = local.common_tags
}
