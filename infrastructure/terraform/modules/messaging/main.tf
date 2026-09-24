# Messaging module.
#
# SQS queue that durably triggers the LangGraph agents, plus a dead-letter queue
# with a redrive policy. SQS + the DynamoDB job record are the durable async
# boundary (at-least-once delivery, retry). Agents are idempotent so redelivery
# does not produce duplicate expensive results.

resource "aws_sqs_queue" "jobs_dlq" {
  name                      = "${var.name_prefix}-jobs-dlq"
  message_retention_seconds = 1209600 # 14 days
}

resource "aws_sqs_queue" "jobs" {
  name                       = "${var.name_prefix}-jobs"
  visibility_timeout_seconds = var.visibility_timeout_seconds
  message_retention_seconds  = 345600 # 4 days

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.jobs_dlq.arn
    maxReceiveCount     = var.max_receive_count
  })
}
