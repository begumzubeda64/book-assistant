output "jobs_table_name" {
  description = "Jobs table name (JOBS_TABLE_NAME for the backend)."
  value       = aws_dynamodb_table.jobs.name
}

output "jobs_table_arn" {
  description = "Jobs table ARN (for IAM policies)."
  value       = aws_dynamodb_table.jobs.arn
}
