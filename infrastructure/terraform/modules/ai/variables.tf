variable "name_prefix" {
  description = "Prefix for resource names (project-environment)."
  type        = string
}

variable "embedding_model_arn" {
  description = "Bedrock embedding model ARN (must be available in eu-central-1)."
  type        = string
  default     = "arn:aws:bedrock:eu-central-1::foundation-model/amazon.titan-embed-text-v2:0"
}

variable "embedding_dimension" {
  description = "Vector dimension of the embedding model (Titan v2 = 1024)."
  type        = number
  default     = 1024
}

variable "neptune_memory_ncu" {
  description = "Neptune Analytics provisioned memory (m-NCUs)."
  type        = number
  default     = 16
}

variable "deletion_protection" {
  description = "Protect the Neptune Analytics graph from deletion."
  type        = bool
  default     = false
}
