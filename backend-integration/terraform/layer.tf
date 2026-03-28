resource "aws_lambda_layer_version" "dependencies" {
  layer_name          = "tra3-${var.client_name}-dependencies"
  s3_bucket           = local.s3_bucket
  s3_key              = "layers/dependencies/layer.zip"
  compatible_runtimes = [var.lambda_runtime]
  description         = "stripe + requests — TRA3 platform"

  lifecycle { create_before_destroy = true }
}
