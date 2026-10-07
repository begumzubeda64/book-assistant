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

variable "mcp_image" {
  description = "Full ECR image reference for the MCP tool server."
  type        = string
}

# Ports / sizing
variable "app_port" {
  type    = number
  default = 8000
}

variable "mcp_port" {
  type    = number
  default = 8080
}

variable "api_cpu" {
  type    = number
  default = 512
}

variable "api_memory" {
  type    = number
  default = 1024
}

variable "mcp_cpu" {
  type    = number
  default = 256
}

variable "mcp_memory" {
  type    = number
  default = 512
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
