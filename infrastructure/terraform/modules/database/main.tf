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
