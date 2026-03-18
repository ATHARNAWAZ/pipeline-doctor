variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Deployment environment (dev/staging/prod)"
  type        = string
  default     = "prod"
}

variable "project_name" {
  description = "Project name used for resource naming"
  type        = string
  default     = "pipeline-doctor"
}

variable "anthropic_api_key" {
  description = "Anthropic API key for Claude"
  type        = string
  sensitive   = true
}

variable "database_url" {
  description = "PostgreSQL connection string with pgvector"
  type        = string
  sensitive   = true
}

variable "slack_webhook_url" {
  description = "Slack webhook URL for failure alerts (optional)"
  type        = string
  sensitive   = true
  default     = ""
}

variable "openai_api_key" {
  description = "OpenAI API key for embeddings (optional — falls back to local model)"
  type        = string
  sensitive   = true
  default     = ""
}

variable "lambda_memory_mb" {
  description = "Lambda memory allocation in MB"
  type        = number
  default     = 1024
}

variable "lambda_timeout_seconds" {
  description = "Lambda timeout — manifest analysis on large projects takes time"
  type        = number
  default     = 300
}

variable "alert_email" {
  description = "Email address for CloudWatch alarm notifications"
  type        = string
  default     = ""
}
