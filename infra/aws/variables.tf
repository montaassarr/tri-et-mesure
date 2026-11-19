variable "region" {
  description = "AWS region (Paris keeps the data in France)"
  type        = string
  default     = "eu-west-3"
}

variable "aws_profile" {
  description = "AWS CLI profile (SSO) used by Terraform"
  type        = string
  default     = "default"
}

variable "name" {
  description = "Prefix for every resource name"
  type        = string
  default     = "tri-mesure"
}

variable "instance_type" {
  description = "Graviton burstable instance. t4g.micro (1 GiB) is enough for the demo; t4g.small if memory gets tight."
  type        = string
  default     = "t4g.micro"
}

variable "volume_size_gb" {
  description = "Encrypted gp3 root volume (OS, Docker images, PostgreSQL data)"
  type        = number
  default     = 20
}

variable "llm_provider" {
  description = "Default AI provider at start-up: rules | anthropic | openai_compat (the AI team can switch at runtime)"
  type        = string
  default     = "rules"
}

variable "daily_budget_eur" {
  description = "Hard daily cap on model spend; above it the app falls back to rules"
  type        = number
  default     = 1.0
}

variable "anthropic_api_key" {
  description = "Optional. Pass with TF_VAR_anthropic_api_key, never in a committed file."
  type        = string
  default     = ""
  sensitive   = true
}

variable "openai_compat_api_key" {
  description = "Optional (Groq, Mistral…). Pass with TF_VAR_openai_compat_api_key."
  type        = string
  default     = ""
  sensitive   = true
}

variable "budget_alert_email" {
  description = "Optional. If set, AWS Budgets e-mails this address at 80 % of monthly_budget_usd."
  type        = string
  default     = ""
}

variable "monthly_budget_usd" {
  description = "Monthly cost alert threshold"
  type        = number
  default     = 15
}
