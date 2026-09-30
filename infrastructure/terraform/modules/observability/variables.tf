variable "name_prefix" {
  description = "Prefix for resource names (project-environment)."
  type        = string
}

variable "log_retention_days" {
  description = "CloudWatch log retention."
  type        = number
  default     = 30
}

variable "app_error_threshold" {
  description = "App errors per 5 min before alarming."
  type        = number
  default     = 10
}

variable "alb_5xx_threshold" {
  description = "ALB target 5xx per 5 min before alarming."
  type        = number
  default     = 10
}

variable "job_failure_threshold" {
  description = "Async job failures per 5 min before alarming."
  type        = number
  default     = 3
}

variable "alb_arn_suffix" {
  description = "ALB ARN suffix for the 5xx alarm dimension (empty disables it)."
  type        = string
  default     = ""
}
