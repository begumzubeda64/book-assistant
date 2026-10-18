variable "name_prefix" {
  description = "Prefix for resource names (project-environment)."
  type        = string
}

variable "allowed_upload_origins" {
  description = "Frontend origins allowed to PUT directly to S3 via presigned URLs."
  type        = list(string)
  default     = ["http://localhost:5173"]
}
