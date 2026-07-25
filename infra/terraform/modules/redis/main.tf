# ─── ElastiCache Redis Module ─────────────────────────

variable "project_name" { type = string }
variable "environment" { type = string }
variable "vpc_id" { type = string }
variable "subnet_ids" { type = list(string) }
variable "node_type" { type = string }
variable "allowed_security_groups" { type = list(string) default = [] }

resource "aws_elasticache_subnet_group" "main" {
  name       = "${var.project_name}-${var.environment}-redis-subnet"
  subnet_ids = var.subnet_ids
}

resource "aws_security_group" "redis" {
  name_prefix = "${var.project_name}-redis-"
  vpc_id      = var.vpc_id

  ingress {
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = var.allowed_security_groups
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.project_name}-redis-sg" }
}

resource "aws_elasticache_replication_group" "main" {
  replication_group_id = "${var.project_name}-${var.environment}"
  description          = "LivestockGuard Redis cluster"

  engine         = "redis"
  engine_version = "7.0"
  node_type      = var.node_type

  num_cache_clusters   = var.environment == "production" ? 2 : 1
  port                 = 6379
  subnet_group_name    = aws_elasticache_subnet_group.main.name
  security_group_ids   = [aws_security_group.redis.id]

  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  automatic_failover_enabled = var.environment == "production"

  snapshot_retention_limit = var.environment == "production" ? 3 : 0

  tags = { Name = "${var.project_name}-redis" }
}

output "endpoint" { value = aws_elasticache_replication_group.main.primary_endpoint_address }
output "port" { value = aws_elasticache_replication_group.main.port }
output "security_group_id" { value = aws_security_group.redis.id }
