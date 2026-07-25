# Production environment configuration
# AWS af-south-1 (Cape Town)

aws_region         = "af-south-1"
environment        = "production"
project_name       = "livestockguard"

vpc_cidr           = "10.0.0.0/16"
availability_zones = ["af-south-1a", "af-south-1b", "af-south-1c"]

db_instance_class  = "db.t3.medium"
db_name            = "livestockguard"
db_username        = "livestockguard"
# db_password sourced from TF_VAR_db_password env var

redis_node_type    = "cache.t3.micro"

api_gateway_cpu    = 512
api_gateway_memory = 1024
api_desired_count  = 2

domain_name        = "livestockguard.co.za"
# certificate_arn sourced from env or AWS console
