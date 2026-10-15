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

variable "certificate_arn" {
  description = <<-EOT
    ACM certificate ARN for the ALB HTTPS listener. When empty, the ALB and ECS
    services are not created (provision networking/registry/data layers first,
    then set this to bring up compute).
  EOT
  type        = string
  default     = ""
}
