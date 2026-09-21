# Messaging module (skeleton).
#
# Responsibility: SQS queue(s) that durably trigger the LangGraph agents on
# AgentCore Runtime, with a dead-letter queue and redrive policy. SQS plus the
# DynamoDB job record form the durable async boundary (at-least-once delivery).
#
# Resources are added in the async job / ingestion task groups.
