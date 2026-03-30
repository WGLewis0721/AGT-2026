resource "aws_sns_topic" "daily_cost_report" {
  count = local.billing_enabled ? 1 : 0
  name  = "${local.name_prefix}-daily-cost-report"

  tags = local.common_tags
}

resource "aws_sns_topic_subscription" "daily_cost_report_email" {
  count     = local.billing_enabled ? 1 : 0
  topic_arn = aws_sns_topic.daily_cost_report[0].arn
  protocol  = "email"
  endpoint  = var.billing_report_email
}

resource "aws_iam_role" "cost_reporter" {
  count = local.billing_enabled ? 1 : 0
  name  = "${local.name_prefix}-cost-report-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy_attachment" "cost_reporter_basic_execution" {
  count      = local.billing_enabled ? 1 : 0
  role       = aws_iam_role.cost_reporter[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "cost_reporter" {
  count = local.billing_enabled ? 1 : 0
  name  = "${local.name_prefix}-cost-report-policy"
  role  = aws_iam_role.cost_reporter[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["ce:GetCostAndUsage"]
        Resource = "*"
      },
      {
        Effect   = "Allow"
        Action   = ["sns:Publish"]
        Resource = aws_sns_topic.daily_cost_report[0].arn
      }
    ]
  })
}

resource "aws_cloudwatch_log_group" "cost_reporter" {
  count             = local.billing_enabled ? 1 : 0
  name              = "/aws/lambda/${local.cost_reporter_name}"
  retention_in_days = var.log_retention

  tags = local.common_tags
}

resource "aws_lambda_function" "cost_reporter" {
  count         = local.billing_enabled ? 1 : 0
  function_name = local.cost_reporter_name
  role          = aws_iam_role.cost_reporter[0].arn
  handler       = "cost_reporter_handler.lambda_handler"
  runtime       = var.lambda_runtime
  timeout       = 30
  memory_size   = 128

  s3_bucket = local.s3_bucket
  s3_key    = local.cost_reporter_artifact_key

  source_code_hash = try(
    filebase64sha256("../cost-reporter/cost_reporter.zip"),
    filebase64sha256("../cost-reporter/cost_reporter_handler.py"),
  )

  environment {
    variables = {
      SNS_TOPIC_ARN = aws_sns_topic.daily_cost_report[0].arn
      REPORT_SCOPE  = var.client_name
    }
  }

  tags = local.common_tags
}

resource "aws_cloudwatch_event_rule" "daily_cost_report" {
  count               = local.billing_enabled ? 1 : 0
  name                = "${local.name_prefix}-daily-cost-report"
  schedule_expression = var.billing_schedule_expression

  tags = local.common_tags
}

resource "aws_cloudwatch_event_target" "daily_cost_report" {
  count     = local.billing_enabled ? 1 : 0
  rule      = aws_cloudwatch_event_rule.daily_cost_report[0].name
  target_id = "cost-reporter"
  arn       = aws_lambda_function.cost_reporter[0].arn
}

resource "aws_lambda_permission" "cost_report_schedule" {
  count         = local.billing_enabled ? 1 : 0
  statement_id  = "AllowDailyCostReportInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.cost_reporter[0].function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.daily_cost_report[0].arn
}
