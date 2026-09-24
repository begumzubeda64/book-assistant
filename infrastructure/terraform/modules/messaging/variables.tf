variable "name_prefix" {
  description = "Prefix for resource names (project-environment)."
  type        = string
}

variable "visibility_timeout_seconds" {
  description = "How long a job message stays invisible while an agent processes it."
  type        = number
  default     = 900
}

variable "max_receive_count" {
  description = "Deliveries attempted before a message moves to the DLQ."
  type        = number
  default     = 5
}
