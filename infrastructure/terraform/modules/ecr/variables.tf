variable "name_prefix" {
  description = "Prefix for resource names (project-environment)."
  type        = string
}

variable "force_delete" {
  description = "Allow deleting repos that still contain images (dev convenience)."
  type        = bool
  default     = false
}
