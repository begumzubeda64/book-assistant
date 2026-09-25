output "jobs_table_name" {
  description = "Jobs table name (JOBS_TABLE_NAME for the backend)."
  value       = aws_dynamodb_table.jobs.name
}

output "jobs_table_arn" {
  description = "Jobs table ARN (for IAM policies)."
  value       = aws_dynamodb_table.jobs.arn
}

output "progress_table_name" {
  description = "Progress table name (PROGRESS_TABLE_NAME for the backend)."
  value       = aws_dynamodb_table.progress.name
}

output "progress_table_arn" {
  description = "Progress table ARN (for IAM policies)."
  value       = aws_dynamodb_table.progress.arn
}

output "conversations_table_name" {
  description = "Conversations table name (CONVERSATIONS_TABLE_NAME)."
  value       = aws_dynamodb_table.conversations.name
}

output "conversations_table_arn" {
  description = "Conversations table ARN (for IAM policies)."
  value       = aws_dynamodb_table.conversations.arn
}
