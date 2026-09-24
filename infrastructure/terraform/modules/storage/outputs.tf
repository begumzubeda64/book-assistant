output "uploads_bucket_name" {
  description = "Private uploads bucket name (UPLOADS_BUCKET_NAME for the backend)."
  value       = aws_s3_bucket.uploads.id
}

output "uploads_bucket_arn" {
  description = "Private uploads bucket ARN (for IAM policies)."
  value       = aws_s3_bucket.uploads.arn
}

output "reading_results_bucket_name" {
  description = "Reading-results bucket name (READING_RESULTS_BUCKET_NAME)."
  value       = aws_s3_bucket.reading_results.id
}
