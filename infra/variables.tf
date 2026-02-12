variable "aws_region" {
  type        = string
  description = "AWS region for all resources."
  default     = "us-east-1"
}

variable "project_name" {
  type        = string
  description = "Base name for resources."
  default     = "me-microservice"
}

variable "melhor_envio_base_url" {
  type        = string
  description = "Melhor Envio base URL."
  default     = "https://sandbox.melhorenvio.com.br"
}

variable "melhor_envio_client_id" {
  type        = string
  description = "Melhor Envio OAuth client_id."
  default     = ""
  sensitive   = true
}

variable "melhor_envio_client_secret" {
  type        = string
  description = "Melhor Envio OAuth client_secret."
  default     = ""
  sensitive   = true
}

variable "melhor_envio_default_scope" {
  type        = string
  description = "Default scope used for authorize URL (optional)."
  default     = ""
}

variable "http_timeout_seconds" {
  type        = number
  description = "HTTP timeout for Melhor Envio requests."
  default     = 15
}

variable "user_agent" {
  type        = string
  description = "User-Agent used on outbound requests."
  default     = "me-microservice/1.0"
}

