variable "aws_region" {
  type        = string
  description = "AWS region for all resources."
  default     = "us-east-1"
}

variable "project_name" {
  type        = string
  description = "Base name prefix; prod uses this as-is; dev uses \"{project_name}-dev\" to avoid clashes in the same AWS account."
  default     = "melhorenvio-ms"
}

variable "stage" {
  type        = string
  description = "Deployment stage: dev (branch dev) or prod (branch main). Drives resource naming and CI backend config. CI always sets this explicitly."
  default     = "dev"
  validation {
    condition     = contains(["dev", "prod"], var.stage)
    error_message = "stage must be \"dev\" or \"prod\"."
  }
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

variable "melhor_envio_oauth_redirect_uri" {
  type        = string
  description = "OAuth redirect_uri (URL da página de callback do backoffice). Deve coincidir com o app no Melhor Envio. Vazio = Lambda usa fallback interno (dev)."
  default     = ""
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

