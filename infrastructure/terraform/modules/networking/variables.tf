variable "name_prefix" {
  description = "Prefix for resource names (project-environment)."
  type        = string
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC."
  type        = string
  default     = "10.0.0.0/16"
}

variable "app_port" {
  description = "Container port the ECS tasks listen on."
  type        = number
  default     = 8000
}
