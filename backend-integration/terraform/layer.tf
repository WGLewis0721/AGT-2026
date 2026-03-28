resource "aws_lambda_layer_version" "dependencies" {
  layer_name          = "tra3-${var.client_name}-dependencies"
  description         = "stripe + requests layer for TRA3"
  s3_bucket           = local.s3_bucket
  s3_key              = local.layer_artifact_key
  compatible_runtimes = [var.lambda_runtime]
  source_code_hash    = filebase64sha256("../layer/layer.zip")

  lifecycle {
    create_before_destroy = true
  }
}
