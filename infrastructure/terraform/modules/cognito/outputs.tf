output "user_pool_id" {
  description = "Cognito User Pool ID (COGNITO_USER_POOL_ID for the backend)."
  value       = aws_cognito_user_pool.this.id
}

output "user_pool_client_id" {
  description = "Cognito app client ID (COGNITO_CLIENT_ID for the backend)."
  value       = aws_cognito_user_pool_client.this.id
}

output "user_pool_endpoint" {
  description = "Cognito User Pool endpoint (issuer host)."
  value       = aws_cognito_user_pool.this.endpoint
}
