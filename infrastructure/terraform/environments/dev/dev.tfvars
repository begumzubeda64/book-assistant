environment = "dev"
aws_region  = "eu-central-1"
project     = "book-companion"

# GraphRAG graph-construction model: Claude Haiku 4.5 via the EU cross-Region
# inference profile. GraphRAG chunk entity extraction only accepts Claude
# Haiku-family models (Sonnet is rejected with "Invalid graph bedrock foundation
# model provided"); Haiku 4.5 is the model AWS uses in its official GraphRAG
# example. Bare foundation-model ARNs are not invokable in eu-central-1, so this
# is the EU inference-profile ARN.
graph_construction_model_arn = "arn:aws:bedrock:eu-central-1:169424236454:inference-profile/eu.anthropic.claude-haiku-4-5-20251001-v1:0"

# Generation model (reading/discussion). Sonnet 4.6 — verified invokable; Sonnet
# 4 (20250514) is retired (EOL 2026-06-15) and caused InvokeModel to fail.
generation_model_id = "eu.anthropic.claude-sonnet-4-6"

# --- Domain-free demo: full stack over real HTTPS without a custom domain ---
# ALB serves HTTP:80; a CloudFront distribution gives the API a real HTTPS
# *.cloudfront.net URL (no mixed content, valid Cognito callback origin).
enable_http_only = true
enable_api_cdn   = true

# Cognito hosted-UI login domain (browser login flow). Prefix must be globally
# unique; the account id keeps it collision-free.
cognito_hosted_ui_domain_prefix = "book-companion-dev-169424236454"
