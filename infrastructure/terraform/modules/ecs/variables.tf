variable "name_prefix" {
  description = "Prefix for resource names (project-environment)."
  type        = string
}

# Networking
variable "private_subnet_ids" {
  type = list(string)
}

variable "tasks_security_group_id" {
  type = string
}

# ALB
variable "api_target_group_arn" {
  type = string
}

# Images
variable "api_image" {
  description = "Full ECR image reference for the API."
  type        = string
}

# Ports / sizing
variable "app_port" {
  type    = number
  default = 8000
}

variable "api_cpu" {
  type    = number
  default = 512
}

variable "api_memory" {
  type    = number
  default = 1024
}

variable "api_desired_count" {
  type    = number
  default = 2
}

variable "api_max_count" {
  type    = number
  default = 6
}

# App config + least-privilege resource ARNs
variable "api_environment" {
  description = "Environment variables for the API/MCP containers."
  type        = map(string)
  default     = {}
}

variable "log_group_name" {
  description = "CloudWatch log group for container logs."
  type        = string
}

variable "dynamodb_table_arns" {
  type    = list(string)
  default = ["*"]
}

variable "app_bucket_arns" {
  description = "S3 bucket ARNs the app/MCP may access (uploads, results, chunks)."
  type        = list(string)
  default     = []
}

variable "jobs_queue_arn" {
  type    = string
  default = ""
}

# Dispatcher (SQS -> AgentCore bridge)
variable "dispatcher_image" {
  description = "ECR image for the dispatcher. Empty disables the service."
  type        = string
  default     = ""
}

variable "dispatcher_environment" {
  description = "Environment variables for the dispatcher container."
  type        = map(string)
  default     = {}
}

variable "agent_runtime_arns" {
  description = "AgentCore runtime ARNs the dispatcher may invoke."
  type        = list(string)
  default     = ["*"]
}

variable "api_invoke_runtime_arns" {
  description = "AgentCore runtime ARNs the API may invoke (e.g. discussion)."
  type        = list(string)
  default     = []
}

variable "api_secret_arns" {
  description = "Secrets Manager ARNs the API task role may read."
  type        = list(string)
  default     = []
}

variable "dispatcher_secret_arns" {
  description = "Secrets Manager ARNs the dispatcher task role may read."
  type        = list(string)
  default     = []
}

variable "scope_secret_arn" {
  description = "Scope-signing secret ARN, injected into API/dispatcher as SCOPE_SIGNING_SECRET."
  type        = string
  default     = ""
}

variable "enable_agent_integration" {
  description = <<-EOT
    Statically-known flag (= deploy_agents) that gates the agent/MCP integration
    IAM (invoke-runtime, secret read/injection). Separate from the ARN inputs so
    count is known at plan time even though the ARNs are created in the same
    apply.
  EOT
  type        = bool
  default     = false
}
