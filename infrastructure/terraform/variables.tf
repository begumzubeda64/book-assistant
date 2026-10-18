variable "aws_region" {
  description = "AWS region. Fixed to Frankfurt per tech steering."
  type        = string
  default     = "eu-central-1"
}

variable "environment" {
  description = "Deployment environment name (dev or prod)."
  type        = string

  validation {
    condition     = contains(["dev", "prod"], var.environment)
    error_message = "environment must be one of: dev, prod."
  }
}

variable "project" {
  description = "Project name used for resource naming and tagging."
  type        = string
  default     = "book-companion"
}

variable "app_port" {
  description = "Container port the FastAPI service listens on."
  type        = number
  default     = 8000
}

variable "image_tag" {
  description = "Image tag to deploy for the API/MCP/agent images."
  type        = string
  default     = "latest"
}

variable "deploy_agents" {
  description = <<-EOT
    Create the three AgentCore agent runtimes. Enable once the agent images are
    pushed to ECR (two-stage apply, like the ALB/ECS compute).
  EOT
  type        = bool
  default     = false
}

variable "graph_construction_model_arn" {
  description = <<-EOT
    ARN of the Bedrock model GraphRAG uses for chunk entity extraction during
    ingestion. In eu-central-1 the Anthropic Claude models are only invokable
    through an EU cross-Region inference profile (ARN prefix eu.), so this must
    be an inference-profile ARN, not a bare foundation-model ARN. Confirm the
    enabled profiles with:
      aws bedrock list-inference-profiles --region eu-central-1
  EOT
  type        = string
  default     = ""
}

variable "generation_model_id" {
  description = <<-EOT
    Bedrock generation model (EU inference-profile id) for the reading/discussion
    agents. Must be a profile whose underlying model is NOT retired.
  EOT
  type        = string
  default     = "eu.anthropic.claude-sonnet-4-6"
}

variable "certificate_arn" {
  description = <<-EOT
    ACM certificate ARN for the ALB HTTPS listener. When empty (and
    enable_http_only is false), the ALB and ECS services are not created
    (provision networking/registry/data layers first, then set this to bring up
    compute).
  EOT
  type        = string
  default     = ""
}

variable "enable_http_only" {
  description = <<-EOT
    Domain-free demo mode. Brings up the ALB + ECS without an ACM certificate:
    the ALB serves HTTP:80 and a CloudFront distribution (enable_api_cdn) gives
    the API a real HTTPS *.cloudfront.net URL. Lets the full stack run — browser
    UI, Cognito hosted login, GraphRAG, agents — without a custom domain. Not
    for production. Mutually exclusive in spirit with certificate_arn.
  EOT
  type        = bool
  default     = false
}

variable "enable_api_cdn" {
  description = <<-EOT
    Put a CloudFront distribution in front of the ALB so the API is reachable
    over HTTPS on a free *.cloudfront.net domain. Intended to accompany
    enable_http_only.
  EOT
  type        = bool
  default     = false
}

variable "cognito_hosted_ui_domain_prefix" {
  description = <<-EOT
    Globally-unique prefix for the Cognito hosted-UI domain
    (<prefix>.auth.<region>.amazoncognito.com). Enables the browser login flow
    without a custom domain. Empty = no hosted UI.
  EOT
  type        = string
  default     = ""
}
