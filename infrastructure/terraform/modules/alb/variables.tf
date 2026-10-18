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
  description = <<-EOT
    ACM certificate ARN for the HTTPS (443) listener. Required unless
    enable_http_only is true. When set, the ALB serves HTTPS directly and
    HTTP:80 redirects to it.
  EOT
  type        = string
  default     = ""
}

variable "enable_http_only" {
  description = <<-EOT
    Domain-free demo mode: serve the API over an HTTP:80 listener that forwards
    to the target group (no ACM cert, no 443 listener, no HTTP->HTTPS redirect).
    Pair with enable_api_cdn so browsers still reach the API over HTTPS via a
    CloudFront *.cloudfront.net URL (avoids mixed-content and gives Cognito a
    valid HTTPS callback origin). Do not use for production.
  EOT
  type        = bool
  default     = false
}

variable "enable_api_cdn" {
  description = <<-EOT
    Create a CloudFront distribution in front of the ALB so the API is reachable
    over HTTPS on a free *.cloudfront.net domain. Intended for the HTTP-only
    demo; the distribution terminates TLS and forwards to the ALB over HTTP.
  EOT
  type        = bool
  default     = false
}

variable "app_port" {
  description = "Target container port."
  type        = number
  default     = 8000
}
