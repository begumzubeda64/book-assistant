variable "name_prefix" {
  description = "Prefix for resource names (project-environment)."
  type        = string
}

variable "environment" {
  description = "Environment name (dev/prod), passed to agent runtimes."
  type        = string
  default     = "dev"
}

variable "embedding_model_arn" {
  description = "Bedrock embedding model ARN (must be available in eu-central-1)."
  type        = string
  default     = "arn:aws:bedrock:eu-central-1::foundation-model/amazon.titan-embed-text-v2:0"
}

variable "embedding_dimension" {
  description = "Vector dimension of the embedding model (Titan v2 = 1024)."
  type        = number
  default     = 1024
}

variable "neptune_memory_ncu" {
  description = "Neptune Analytics provisioned memory (m-NCUs)."
  type        = number
  default     = 16
}

variable "deletion_protection" {
  description = "Protect the Neptune Analytics graph from deletion."
  type        = bool
  default     = false
}

# --- AgentCore runtimes (one isolated image per agent) ---
variable "deploy_agents" {
  description = <<-EOT
    Create the three AgentCore runtimes. Requires the agent images to exist in
    ECR; set once images are pushed (two-stage apply, like the ALB/ECS compute).
  EOT
  type        = bool
  default     = false
}

variable "agent_image_uris" {
  description = "ECR image URIs for the agents (keys: ingestion, adaptive, discussion)."
  type        = map(string)
  default     = {}
}

variable "generation_model_id" {
  description = <<-EOT
    Bedrock model the reading/discussion agents use for generation (InvokeModel).
    In eu-central-1 the Anthropic Claude models are only invokable through an EU
    cross-Region inference profile, so this is the profile id (prefix eu.), e.g.
    eu.anthropic.claude-sonnet-4-6. Pick a profile whose UNDERLYING model is not
    retired: verify with
      aws bedrock get-foundation-model-availability --model-id <id> --region eu-central-1
    (a profile can be ACTIVE while the model it routes to is EOL). Sonnet 4
    (20250514) and Claude 3.5 Sonnet are retired and must not be used.
  EOT
  type        = string
  default     = "eu.anthropic.claude-sonnet-4-6"
}

variable "graph_construction_model_arn" {
  description = <<-EOT
    ARN of the Bedrock model GraphRAG uses to extract entities and relationships
    during ingestion (contextEnrichmentConfiguration). Two constraints apply in
    eu-central-1: (1) Claude models are only invokable through an EU cross-Region
    inference profile, so this must be an inference-profile ARN (prefix eu.), not
    a bare foundation-model ARN; (2) GraphRAG graph construction only accepts
    Claude Haiku-family models (Sonnet is rejected with "Invalid graph bedrock
    foundation model provided"). Confirm enabled profiles with:
      aws bedrock list-inference-profiles --region eu-central-1
  EOT
  type        = string

  validation {
    condition     = can(regex("^arn:aws:bedrock:[a-z0-9-]+:[0-9]+:inference-profile/", var.graph_construction_model_arn))
    error_message = "graph_construction_model_arn must be a Bedrock inference-profile ARN (arn:aws:bedrock:<region>:<account>:inference-profile/...)."
  }
}

variable "jobs_queue_arn" {
  description = "SQS job queue ARN the async agents consume (for the trigger role)."
  type        = string
  default     = ""
}

variable "uploads_bucket_arn" {
  description = "Uploads bucket ARN (agent content access)."
  type        = string
  default     = ""
}

variable "reading_results_bucket_arn" {
  description = "Reading-results bucket ARN (adaptive-reading output)."
  type        = string
  default     = ""
}

variable "jobs_table_arn" {
  description = "Jobs table ARN (agents update job status)."
  type        = string
  default     = ""
}

variable "conversations_table_arn" {
  description = "Conversations table ARN (discussion agent persistence)."
  type        = string
  default     = ""
}

variable "mcp_image_uri" {
  description = "ECR image URI for the MCP tool server (empty until pushed)."
  type        = string
  default     = ""
}

variable "uploads_bucket_name" {
  description = "Uploads bucket name (MCP content tool)."
  type        = string
  default     = ""
}

variable "reading_results_bucket_name" {
  description = "Reading-results bucket name (MCP reading-store tool)."
  type        = string
  default     = ""
}

variable "jobs_table_name" {
  description = "Jobs table name (agents update job status)."
  type        = string
  default     = ""
}
