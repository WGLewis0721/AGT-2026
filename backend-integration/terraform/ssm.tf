data "aws_ssm_parameter" "stripe_secret_key" {
  name            = var.stripe_secret_key_parameter_name
  with_decryption = true
}

data "aws_ssm_parameter" "stripe_webhook_secret" {
  name            = var.stripe_webhook_secret_parameter_name
  with_decryption = true
}

data "aws_ssm_parameter" "textbelt_api_key" {
  name            = var.textbelt_api_key_parameter_name
  with_decryption = true
}

data "aws_ssm_parameter" "detailer_phone_number" {
  name            = var.detailer_phone_number_parameter_name
  with_decryption = true
}

data "aws_ssm_parameter" "calcom_webhook_secret" {
  count           = var.calcom_webhook_secret_parameter_name == "" ? 0 : 1
  name            = var.calcom_webhook_secret_parameter_name
  with_decryption = true
}

locals {
  calcom_webhook_secret = (
    var.calcom_webhook_secret_parameter_name == ""
    ? ""
    : data.aws_ssm_parameter.calcom_webhook_secret[0].value
  )
}
