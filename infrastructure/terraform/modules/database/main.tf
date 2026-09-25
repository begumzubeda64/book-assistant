# Database module.
#
# DynamoDB tables for application state and job status, designed around the
# access patterns in design.md. Tables are added as the feature groups that own
# each access pattern are implemented.
#
# Jobs table (owned by the upload/async-job group): partition key job_id, with a
# GSI on idempotency_key so job creation can be made idempotent (requirement
# 8.3). PAY_PER_REQUEST keeps the MVP simple and cost-proportional.

resource "aws_dynamodb_table" "jobs" {
  name         = "${var.name_prefix}-jobs"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "job_id"

  attribute {
    name = "job_id"
    type = "S"
  }

  attribute {
    name = "idempotency_key"
    type = "S"
  }

  global_secondary_index {
    name            = "idempotency-index"
    hash_key        = "idempotency_key"
    projection_type = "ALL"
  }

  point_in_time_recovery {
    enabled = true
  }
}

# Conversations table (owned by the discussion group): partition key user_id,
# sort key conversation_id — user-scoped threads with embedded messages.
resource "aws_dynamodb_table" "conversations" {
  name         = "${var.name_prefix}-conversations"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "user_id"
  range_key    = "conversation_id"

  attribute {
    name = "user_id"
    type = "S"
  }

  attribute {
    name = "conversation_id"
    type = "S"
  }

  point_in_time_recovery {
    enabled = true
  }
}

# Progress table (owned by the reading-progress group): partition key user_id,
# sort key book_id — one item per (user, book), so writes are idempotent upserts.
resource "aws_dynamodb_table" "progress" {
  name         = "${var.name_prefix}-progress"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "user_id"
  range_key    = "book_id"

  attribute {
    name = "user_id"
    type = "S"
  }

  attribute {
    name = "book_id"
    type = "S"
  }

  point_in_time_recovery {
    enabled = true
  }
}
