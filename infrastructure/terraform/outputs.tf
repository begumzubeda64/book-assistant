# Root outputs.
#
# Populated incrementally as modules are enabled. Additional outputs (API
# endpoint, ECR repository URLs, AgentCore endpoints) are added in the
# infrastructure task group (see spec tasks.md group 3.7).

output "cognito_user_pool_id" {
  description = "Cognito User Pool ID for the backend (COGNITO_USER_POOL_ID)."
  value       = module.cognito.user_pool_id
}

output "cognito_client_id" {
  description = "Cognito app client ID for the backend (COGNITO_CLIENT_ID)."
  value       = module.cognito.user_pool_client_id
}

output "uploads_bucket_name" {
  description = "Private uploads bucket name (UPLOADS_BUCKET_NAME)."
  value       = module.storage.uploads_bucket_name
}

output "jobs_queue_url" {
  description = "Job queue URL (JOBS_QUEUE_URL)."
  value       = module.messaging.jobs_queue_url
}

output "jobs_table_name" {
  description = "Jobs table name (JOBS_TABLE_NAME)."
  value       = module.database.jobs_table_name
}

output "progress_table_name" {
  description = "Progress table name (PROGRESS_TABLE_NAME)."
  value       = module.database.progress_table_name
}

output "knowledge_base_id" {
  description = "Bedrock Knowledge Base ID (KNOWLEDGE_BASE_ID)."
  value       = module.ai.knowledge_base_id
}

output "kb_chunk_bucket_name" {
  description = "Prepared-chunk bucket name (KB_CHUNK_BUCKET_NAME)."
  value       = module.ai.kb_chunk_bucket_name
}

output "reading_results_bucket_name" {
  description = "Reading-results bucket name (READING_RESULTS_BUCKET_NAME)."
  value       = module.storage.reading_results_bucket_name
}

output "ecr_repository_urls" {
  description = "ECR repository URLs (api, mcp, agent-*)."
  value       = module.ecr.repository_urls
}

output "api_url" {
  description = "Public API base URL (ALB DNS). Null until certificate_arn is set."
  value       = try("https://${module.alb[0].alb_dns_name}", null)
}

output "frontend_url" {
  description = "Public frontend URL (CloudFront)."
  value       = "https://${module.storage.frontend_cloudfront_domain}"
}

output "frontend_bucket_name" {
  description = "Bucket to upload the built SPA to."
  value       = module.storage.frontend_bucket_name
}

output "agent_runtime_arns" {
  description = "AgentCore runtime ARNs (empty until deploy_agents=true)."
  value       = module.ai.agent_runtime_arns
}

output "ecs_cluster_name" {
  description = "ECS cluster name (for CI deploy). Null until compute is created."
  value       = try(module.ecs[0].cluster_name, null)
}

output "ecs_api_service_name" {
  description = "API ECS service name (for CI deploy). Null until compute is created."
  value       = try(module.ecs[0].api_service_name, null)
}

output "conversations_table_name" {
  description = "Conversations table name (CONVERSATIONS_TABLE_NAME)."
  value       = module.database.conversations_table_name
}
