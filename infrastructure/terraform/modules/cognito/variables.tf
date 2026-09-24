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
