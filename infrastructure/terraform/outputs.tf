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
