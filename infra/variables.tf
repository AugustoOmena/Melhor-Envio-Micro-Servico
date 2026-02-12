variable "aws_region" {
  type        = string
  description = "AWS region for all resources."
  default     = "us-east-1"
}

variable "project_name" {
  type        = string
  description = "Project prefix for resource naming."
  default     = "melhorenvio-ms"
}

variable "melhor_envio_env" {
  type        = string
  description = "Melhor Envio environment: sandbox or production."
  default     = "sandbox"
}

variable "melhor_envio_client_id" {
  type        = string
  description = "Melhor Envio OAuth client_id."
  sensitive   = true
}

variable "melhor_envio_client_secret" {
  type        = string
  description = "Melhor Envio OAuth client_secret."
  sensitive   = true
}

variable "supabase_url" {
  type        = string
  description = "Supabase project URL (e.g., https://xxxx.supabase.co)."
  sensitive   = true
}

variable "supabase_key" {
  type        = string
  description = "Supabase service role key used by the backend to persist tokens."
  sensitive   = true
}

variable "lambda_timeout_seconds" {
  type        = number
  description = "Lambda timeout in seconds."
  default     = 20
}

variable "lambda_memory_mb" {
  type        = number
  description = "Lambda memory in MB."
  default     = 256
}

