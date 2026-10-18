variable "name_prefix" {
  description = "Prefix for resource names (project-environment)."
  type        = string
}

variable "callback_urls" {
  description = "Allowed OAuth callback URLs for the web app client."
  type        = list(string)
  default     = ["http://localhost:5173/auth/callback"]
}

variable "logout_urls" {
  description = "Allowed sign-out redirect URLs for the web app client."
  type        = list(string)
  default     = ["http://localhost:5173"]
}

variable "extra_callback_urls" {
  description = "Additional callback URLs (e.g. the deployed CloudFront SPA)."
  type        = list(string)
  default     = []
}

variable "extra_logout_urls" {
  description = "Additional sign-out redirect URLs (e.g. the deployed SPA)."
  type        = list(string)
  default     = []
}

variable "hosted_ui_domain_prefix" {
  description = <<-EOT
    Prefix for the Cognito hosted-UI domain on the free
    *.auth.<region>.amazoncognito.com namespace (globally unique). Empty = no
    hosted UI (local dev / token-only). Set it to enable the browser login flow.
  EOT
  type        = string
  default     = ""
}
