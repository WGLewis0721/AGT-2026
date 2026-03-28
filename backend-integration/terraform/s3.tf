resource "aws_s3_bucket" "deployments" {
  bucket    = local.s3_bucket
  lifecycle { prevent_destroy = true }
}

resource "aws_s3_bucket_versioning" "deployments" {
  bucket = aws_s3_bucket.deployments.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "deployments" {
  bucket = aws_s3_bucket.deployments.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
  }
}

resource "aws_s3_bucket_public_access_block" "deployments" {
  bucket                  = aws_s3_bucket.deployments.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "deployments" {
  bucket = aws_s3_bucket.deployments.id

  rule {
    id     = "expire-old-function-versions"
    status = "Enabled"
    filter { prefix = "functions/" }
    noncurrent_version_expiration { noncurrent_days = 30 }
  }

  rule {
    id     = "expire-old-layer-versions"
    status = "Enabled"
    filter { prefix = "layers/" }
    noncurrent_version_expiration { noncurrent_days = 90 }
  }
}
