output "jobs_queue_url" {
  description = "Job queue URL (JOBS_QUEUE_URL for the backend)."
  value       = aws_sqs_queue.jobs.url
}

output "jobs_queue_arn" {
  description = "Job queue ARN (for IAM policies and agent event sources)."
  value       = aws_sqs_queue.jobs.arn
}

output "jobs_dlq_arn" {
  description = "Dead-letter queue ARN."
  value       = aws_sqs_queue.jobs_dlq.arn
}
