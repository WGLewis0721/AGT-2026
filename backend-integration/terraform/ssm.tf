data "aws_ssm_parameter" "square_access_token" {
  name = "/tra3/${var.client_name}/${var.environment}/square_access_token"
}

data "aws_ssm_parameter" "square_location_id" {
  name = "/tra3/${var.client_name}/${var.environment}/square_location_id"
}

data "aws_ssm_parameter" "square_webhook_signature_key" {
  name = "/tra3/${var.client_name}/${var.environment}/square_webhook_signature_key"
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

data "aws_ssm_parameter" "mark_complete_secret" {
  name            = "/tra3/${var.client_name}/${var.environment}/mark_complete_secret"
  with_decryption = true
}

locals {
  calcom_webhook_secret = (
    var.calcom_webhook_secret_parameter_name == ""
    ? ""
    : data.aws_ssm_parameter.calcom_webhook_secret[0].value
  )
}
