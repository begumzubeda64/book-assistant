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
