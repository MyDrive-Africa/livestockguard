# LivestockGuard Terraform Infrastructure

Infrastructure as Code for deploying LivestockGuard to AWS af-south-1 (Cape Town).

## Architecture

```
Internet → ALB → ECS Fargate (API Gateway, Alert Engine, MQTT Writer)
                     ↓
              RDS PostgreSQL (TimescaleDB) + ElastiCache Redis
```

## Prerequisites

- AWS CLI configured with af-south-1 access
- Terraform >= 1.5.0
- S3 bucket for state: `livestockguard-terraform-state`
- DynamoDB table for locks: `livestockguard-terraform-locks`

## Usage

```bash
cd infra/terraform

# Initialize
terraform init

# Plan (review changes)
terraform plan -var-file=environments/production/terraform.tfvars

# Apply
terraform apply -var-file=environments/production/terraform.tfvars
```

## Secrets

Pass sensitive values via environment variables:

```bash
export TF_VAR_db_password="your-secure-password"
export TF_VAR_certificate_arn="arn:aws:acm:af-south-1:..."
```

## Modules

| Module | Resources |
|--------|-----------|
| `vpc` | VPC, subnets (public/private), IGW, NAT, route tables |
| `rds` | PostgreSQL 15, subnet group, security group, backups |
| `redis` | ElastiCache Redis 7, replication group, encryption |
| `ecs` | Cluster, ALB, target group, task definition, service, IAM roles |

## Environments

| Environment | Config |
|-------------|--------|
| Production | `environments/production/terraform.tfvars` |
| Staging | `environments/staging/terraform.tfvars` (TODO) |

## Estimated Costs (af-south-1)

| Resource | Monthly |
|----------|---------|
| ECS Fargate (2 tasks, 0.5 vCPU, 1GB) | ~$35 |
| RDS db.t3.medium (Multi-AZ) | ~$90 |
| ElastiCache cache.t3.micro | ~$15 |
| NAT Gateway | ~$35 |
| ALB | ~$20 |
| **Total** | **~$195/month** |
