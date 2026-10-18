output "repository_urls" {
  description = "Map of logical name -> repository URL."
  value       = { for k, r in aws_ecr_repository.this : k => r.repository_url }
}
