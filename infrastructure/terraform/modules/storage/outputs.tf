output "uploads_bucket_name" {
  description = "Private uploads bucket name (UPLOADS_BUCKET_NAME for the backend)."
  value       = aws_s3_bucket.uploads.id
}

output "uploads_bucket_arn" {
  description = "Private uploads bucket ARN (for IAM policies)."
  value       = aws_s3_bucket.uploads.arn
}
