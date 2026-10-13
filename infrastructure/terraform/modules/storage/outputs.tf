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

output "reading_results_bucket_arn" {
  description = "Reading-results bucket ARN (for IAM policies)."
  value       = aws_s3_bucket.reading_results.arn
}

output "frontend_bucket_name" {
  description = "Frontend hosting bucket (upload the built SPA here)."
  value       = aws_s3_bucket.frontend.id
}

output "frontend_cloudfront_domain" {
  description = "CloudFront domain serving the frontend."
  value       = aws_cloudfront_distribution.frontend.domain_name
}

output "frontend_cloudfront_distribution_id" {
  description = "CloudFront distribution id (for cache invalidation on deploy)."
  value       = aws_cloudfront_distribution.frontend.id
}
