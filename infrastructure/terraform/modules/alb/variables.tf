variable "name_prefix" {
  description = "Prefix for resource names (project-environment)."
  type        = string
}

variable "vpc_id" {
  description = "VPC id for the target group."
  type        = string
}

variable "public_subnet_ids" {
  description = "Public subnets for the ALB."
  type        = list(string)
}

variable "alb_security_group_id" {
  description = "Security group for the ALB."
  type        = string
}

variable "certificate_arn" {
  description = "ACM certificate ARN for the HTTPS listener."
  type        = string
}

variable "app_port" {
  description = "Target container port."
  type        = number
  default     = 8000
}
