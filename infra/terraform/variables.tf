variable "aws_region" {
  description = "AWS region for deployment"
  type        = string
  default     = "af-south-1"
}

variable "environment" {
  description = "Deployment environment (production, staging)"
  type        = string
  default     = "production"
}

variable "project_name" {
  description = "Project name used for resource naming"
  type        = string
  default     = "livestockguard"
}

# ─── VPC ──────────────────────────────────────────────

variable "vpc_cidr" {
  description = "VPC CIDR block"
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "AZs to use in af-south-1"
  type        = list(string)
  default     = ["af-south-1a", "af-south-1b", "af-south-1c"]
}

# ─── RDS ──────────────────────────────────────────────

variable "db_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t3.medium"
}

variable "db_name" {
  description = "PostgreSQL database name"
  type        = string
  default     = "livestockguard"
}

variable "db_username" {
  description = "Database master username"
  type        = string
  default     = "livestockguard"
  sensitive   = true
}

variable "db_password" {
  description = "Database master password"
  type        = string
  sensitive   = true
}

# ─── Redis ────────────────────────────────────────────

variable "redis_node_type" {
  description = "ElastiCache node type"
  type        = string
  default     = "cache.t3.micro"
}

# ─── ECS ──────────────────────────────────────────────

variable "api_gateway_cpu" {
  description = "CPU units for API Gateway task"
  type        = number
  default     = 512
}

variable "api_gateway_memory" {
  description = "Memory (MB) for API Gateway task"
  type        = number
  default     = 1024
}

variable "api_desired_count" {
  description = "Desired number of API Gateway tasks"
  type        = number
  default     = 2
}

# ─── Domain ───────────────────────────────────────────

variable "domain_name" {
  description = "Root domain name"
  type        = string
  default     = "livestockguard.co.za"
}

variable "certificate_arn" {
  description = "ACM certificate ARN for HTTPS"
  type        = string
  default     = ""
}
