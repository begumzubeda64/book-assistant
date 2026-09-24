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
