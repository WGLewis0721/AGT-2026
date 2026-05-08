resource "aws_dynamodb_table" "bookings" {
  name         = local.booking_table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "booking_id"

  attribute {
    name = "booking_id"
    type = "S"
  }

  server_side_encryption {
    enabled = true
  }

  tags = local.common_tags
}
