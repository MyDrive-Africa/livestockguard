# ─── LivestockGuard Infrastructure ─────────────────────
# AWS af-south-1 (Cape Town) deployment
#
# Architecture:
#   VPC → ECS Fargate (API Gateway, Alert Engine, MQTT Writer)
#       → RDS PostgreSQL (TimescaleDB)
#       → ElastiCache Redis
#       → ALB (public-facing)
#       → EMQX on ECS (MQTT broker)
#       → S3 + CloudFront (dashboard static assets)

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.30"
    }
  }

  backend "s3" {
    bucket         = "livestockguard-terraform-state"
    key            = "production/terraform.tfstate"
    region         = "af-south-1"
    dynamodb_table = "livestockguard-terraform-locks"
    encrypt        = true
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "LivestockGuard"
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }
}
