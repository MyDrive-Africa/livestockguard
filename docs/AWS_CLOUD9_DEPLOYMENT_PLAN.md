# LivestockGuard — AWS Cloud9 & IAM Deployment Plan

> Comprehensive plan for running the full LivestockGuard platform on AWS,
> from Cloud9 development through to production ECS Fargate deployment.

---

## Table of Contents

1. [Overview](#overview)
2. [Phase 1: IAM Foundation](#phase-1-iam-foundation)
3. [Phase 2: Secrets & Configuration](#phase-2-secrets--configuration)
4. [Phase 3: Cloud9 Development Environment](#phase-3-cloud9-development-environment)
5. [Phase 4: IDE Strategy — Kiro + Cloud9](#phase-4-ide-strategy--kiro--cloud9)
6. [Phase 5: Running the Full Stack on Cloud9](#phase-5-running-the-full-stack-on-cloud9)
7. [Phase 6: Simulators & Demo Mode](#phase-6-simulators--demo-mode)
8. [Phase 7: Testing on Cloud9](#phase-7-testing-on-cloud9)
9. [Phase 8: Code Changes for AWS Integration](#phase-8-code-changes-for-aws-integration)
10. [Phase 9: Production Deployment (ECS Fargate)](#phase-9-production-deployment-ecs-fargate)
11. [Phase 10: CI/CD Pipeline](#phase-10-cicd-pipeline)
12. [Phase 11: Monitoring & Operations](#phase-11-monitoring--operations)
13. [Cost Estimate](#cost-estimate)
14. [Execution Checklist](#execution-checklist)

---

## Overview

### What This Plan Covers

- Setting up AWS IAM roles and policies for LivestockGuard
- Cloud9 as the primary development environment (replaces local macOS)
- Running all services, simulators, and frontends on Cloud9
- Notification dispatch (SES email, FCM push, Africa's Talking SMS)
- Production deployment on ECS Fargate in af-south-1 (Cape Town)

### Architecture on AWS

```
┌─────────────────────────────────────────────────────────────────────┐
│                         AWS af-south-1                                │
│                                                                       │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────────┐   │
│  │  CloudFront  │    │     ALB      │    │   Secrets Manager    │   │
│  │  (Dashboard) │    │  (HTTPS→API) │    │   Parameter Store    │   │
│  └──────┬───────┘    └──────┬───────┘    └──────────────────────┘   │
│         │                    │                                        │
│  ┌──────┴───────┐    ┌──────┴───────────────────────────────┐       │
│  │  S3 Bucket   │    │           ECS Fargate Cluster         │       │
│  │  (Vite build)│    │  ┌─────────┐ ┌───────────┐ ┌──────┐ │       │
│  └──────────────┘    │  │API GW   │ │MQTT Writer│ │Alert │ │       │
│                       │  │(FastAPI)│ │           │ │Engine│ │       │
│                       │  └────┬────┘ └─────┬─────┘ └──┬───┘ │       │
│                       └───────┼─────────────┼──────────┼─────┘       │
│                               │             │          │              │
│  ┌────────────────────────────┼─────────────┼──────────┼──────┐     │
│  │              Private Subnet │             │          │      │     │
│  │  ┌─────────────┐  ┌───────┴───┐  ┌──────┴──┐             │     │
│  │  │RDS Postgres │  │ElastiCache│  │EMQX/IoT │             │     │
│  │  │+TimescaleDB │  │  Redis 7  │  │  Core   │             │     │
│  │  └─────────────┘  └───────────┘  └─────────┘             │     │
│  └────────────────────────────────────────────────────────────┘     │
│                                                                       │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                     Cloud9 (Development)                       │   │
│  │  Full stack running locally with Docker Compose                │   │
│  │  IAM role provides SES/Secrets Manager access automatically    │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Phase 1: IAM Foundation

### 1.1 Create IAM Policy

Create `LivestockGuardServicePolicy`:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "SESAlerts",
      "Effect": "Allow",
      "Action": [
        "ses:SendEmail",
        "ses:SendRawEmail",
        "ses:SendTemplatedEmail"
      ],
      "Resource": "arn:aws:ses:af-south-1:*:identity/*"
    },
    {
      "Sid": "SecretsRead",
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue",
        "secretsmanager:DescribeSecret"
      ],
      "Resource": "arn:aws:secretsmanager:af-south-1:*:secret:livestockguard/*"
    },
    {
      "Sid": "ParameterStoreRead",
      "Effect": "Allow",
      "Action": [
        "ssm:GetParameter",
        "ssm:GetParameters",
        "ssm:GetParametersByPath"
      ],
      "Resource": "arn:aws:ssm:af-south-1:*:parameter/livestockguard/*"
    },
    {
      "Sid": "CloudWatchLogs",
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:af-south-1:*:log-group:/ecs/livestockguard*"
    },
    {
      "Sid": "ECRPull",
      "Effect": "Allow",
      "Action": [
        "ecr:GetDownloadUrlForLayer",
        "ecr:BatchGetImage",
        "ecr:GetAuthorizationToken"
      ],
      "Resource": "*"
    }
  ]
}
```

### 1.2 Create IAM Role

Create `LivestockGuardServiceRole`:

- **Trust policy**: EC2 + ECS Tasks
- **Attached policies**: `LivestockGuardServicePolicy` (above)

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": ["ec2.amazonaws.com", "ecs-tasks.amazonaws.com"]
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
```

### 1.3 Create Instance Profile

```bash
aws iam create-instance-profile --instance-profile-name LivestockGuardCloud9
aws iam add-role-to-instance-profile \
  --instance-profile-name LivestockGuardCloud9 \
  --role-name LivestockGuardServiceRole
```

### 1.4 Verify SES Sender Identity

```bash
# Verify domain (preferred) or individual email
aws ses verify-domain-identity --domain livestockguard.co.za --region af-south-1

# Or verify single email for testing
aws ses verify-email-identity --email-address alerts@livestockguard.co.za --region af-south-1

# Check verification status
aws ses get-identity-verification-attributes \
  --identities livestockguard.co.za --region af-south-1
```

> Note: New SES accounts are in sandbox mode (can only send to verified addresses).
> Request production access once testing is complete.

---

## Phase 2: Secrets & Configuration

### 2.1 Store Secrets in Secrets Manager

```bash
# JWT signing secret (generate a strong random key)
aws secretsmanager create-secret \
  --name livestockguard/jwt-secret \
  --secret-string '{"value":"GENERATE_A_64_CHAR_RANDOM_STRING_HERE"}' \
  --region af-south-1

# Firebase Cloud Messaging service account
aws secretsmanager create-secret \
  --name livestockguard/firebase-credentials \
  --secret-string file://path/to/firebase-service-account.json \
  --region af-south-1

# Africa's Talking SMS credentials
aws secretsmanager create-secret \
  --name livestockguard/africastalking \
  --secret-string '{"api_key":"your_at_api_key","username":"your_at_username"}' \
  --region af-south-1

# Database credentials (for production RDS)
aws secretsmanager create-secret \
  --name livestockguard/postgres \
  --secret-string '{"host":"rds-endpoint","port":5432,"dbname":"livestockguard","username":"livestockguard","password":"STRONG_PASSWORD"}' \
  --region af-south-1

# Webhook URLs for external integrations
aws secretsmanager create-secret \
  --name livestockguard/webhooks \
  --secret-string '{"urls":["https://your-webhook-endpoint.com/alerts"]}' \
  --region af-south-1
```

### 2.2 Store Configuration in Parameter Store

```bash
aws ssm put-parameter \
  --name /livestockguard/ses-sender-email \
  --value "alerts@livestockguard.co.za" \
  --type String --region af-south-1

aws ssm put-parameter \
  --name /livestockguard/aws-region \
  --value "af-south-1" \
  --type String --region af-south-1

aws ssm put-parameter \
  --name /livestockguard/mqtt-broker \
  --value "emqx.internal" \
  --type String --region af-south-1

aws ssm put-parameter \
  --name /livestockguard/alert-cooldown-seconds \
  --value "300" \
  --type String --region af-south-1

aws ssm put-parameter \
  --name /livestockguard/sms-recipients \
  --value "+27821234567,+27829876543" \
  --type String --region af-south-1

aws ssm put-parameter \
  --name /livestockguard/email-recipients \
  --value "farmer@example.co.za,manager@example.co.za" \
  --type String --region af-south-1
```

---

## Phase 3: Cloud9 Development Environment

### 3.1 Create Cloud9 Environment

```bash
# Via AWS Console: Cloud9 → Create Environment
# Settings:
#   Name: livestockguard-dev
#   Instance type: t3.medium (4 GB RAM — needed for Docker stack)
#   Platform: Amazon Linux 2023
#   Timeout: 4 hours (or never for persistent dev)
#   Connection: SSM (no need for SSH key)
```

After creation, attach the IAM role:
1. Go to EC2 Console → find the Cloud9 instance
2. Actions → Security → Modify IAM Role
3. Select `LivestockGuardCloud9` instance profile

### 3.2 Disable Cloud9 Managed Credentials

Cloud9 has its own temporary credentials that override the instance role.
Disable them to use the IAM role instead:

1. Cloud9 → Preferences → AWS Settings
2. Turn OFF "AWS managed temporary credentials"

### 3.3 Install Development Toolchain

```bash
# Rust toolchain
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
source ~/.cargo/env

# Node.js 20 (via nvm — pre-installed on Cloud9)
nvm install 20
nvm use 20
nvm alias default 20

# Python 3.12
sudo dnf install -y python3.12 python3.12-pip
sudo alternatives --set python3 /usr/bin/python3.12

# Docker (usually pre-installed, just start it)
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker $USER
# Log out and back in for group to take effect

# Docker Compose plugin
sudo dnf install -y docker-compose-plugin

# Verify
docker --version
docker compose version
node --version
python3 --version
cargo --version
```

### 3.4 Increase Disk Space (Cloud9 default is 10 GB)

```bash
# Resize the EBS volume to 30 GB (Docker images need space)
# Run the official Cloud9 resize script:
curl -o resize.sh https://raw.githubusercontent.com/aws-samples/cloud9-resize/main/resize.sh
chmod +x resize.sh
./resize.sh 30
```

### 3.5 Clone & Initial Setup

```bash
git clone https://github.com/your-org/livestockguard.git
cd livestockguard

# Generate Cargo.lock files (the remaining gap from local dev!)
cd cloud/services/ingestion && cargo generate-lockfile && cd -
cd cloud/services/geofence_engine && cargo generate-lockfile && cd -

# Full backend setup
make setup

# Frontend setup (web only — no native mobile on Cloud9)
make setup-frontend --web
```

---

## Phase 4: IDE Strategy — Kiro + Cloud9

### 4.1 The Problem

Kiro is a desktop IDE (built on VS Code) that provides AI-powered development assistance.
Cloud9 is a browser-based IDE that runs on an EC2 instance with IAM credentials.
They are different products — Kiro cannot run *inside* the Cloud9 browser IDE.

### 4.2 Recommended Approach: Kiro + Remote-SSH (Best of Both Worlds)

Use Kiro locally on your Mac, connected to the Cloud9 EC2 instance via SSH.
This gives you:

- Full Kiro AI features (specs, steering, hooks, agent assistance)
- IAM credentials from the EC2 instance role (SES, Secrets Manager, etc.)
- Rust toolchain, Docker, and all dev tools running on the Cloud9 instance
- No credential files on your local machine

```
┌────────────────────────┐         SSH          ┌────────────────────────────┐
│   Your Mac (local)     │ ◄──────────────────► │  Cloud9 EC2 Instance       │
│                        │                       │                            │
│  Kiro IDE              │                       │  - IAM Role attached       │
│  - AI agent            │                       │  - Rust, Node, Python      │
│  - Specs & steering    │                       │  - Docker + Compose        │
│  - Hooks               │                       │  - Full project code       │
│  - Remote-SSH ext      │                       │  - SES/Secrets access      │
│                        │                       │                            │
└────────────────────────┘                       └────────────────────────────┘
```

### 4.3 Setup: Kiro Remote-SSH to Cloud9

**Step 1: Enable SSH on the Cloud9 EC2 instance**

```bash
# In AWS Console: EC2 → Security Groups for the Cloud9 instance
# Add inbound rule: SSH (port 22) from your IP address
```

**Step 2: Create an SSH key pair**

```bash
# On your Mac:
ssh-keygen -t ed25519 -C "kiro-cloud9" -f ~/.ssh/kiro-cloud9

# Copy public key to the instance (via Cloud9 browser terminal or SSM):
# On the EC2 instance:
echo "ssh-ed25519 AAAA... kiro-cloud9" >> ~/.ssh/authorized_keys
```

**Step 3: Configure SSH in Kiro**

Add to `~/.ssh/config` on your Mac:

```
Host livestockguard-cloud9
    HostName <ec2-public-ip-or-dns>
    User ec2-user
    IdentityFile ~/.ssh/kiro-cloud9
    ForwardAgent yes
```

**Step 4: Connect from Kiro**

1. Open Kiro
2. Command Palette → "Remote-SSH: Connect to Host"
3. Select `livestockguard-cloud9`
4. Open the project folder: `/home/ec2-user/livestockguard`

All Kiro features (AI chat, specs, hooks, steering) work normally over Remote-SSH.
Terminal commands execute on the Cloud9 instance with IAM credentials.

### 4.4 Alternative: AWS SSM Session Manager (No Public IP Needed)

If you don't want to expose SSH publicly, use SSM port forwarding:

```bash
# Install Session Manager plugin locally
# https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-working-with-install-plugin.html

# Create SSH tunnel via SSM (no inbound Security Group rule needed):
aws ssm start-session \
  --target <instance-id> \
  --document-name AWS-StartPortForwardingSession \
  --parameters '{"portNumber":["22"],"localPortNumber":["2222"]}'

# Then in ~/.ssh/config:
Host livestockguard-cloud9
    HostName localhost
    Port 2222
    User ec2-user
    IdentityFile ~/.ssh/kiro-cloud9
```

### 4.5 Alternative Options (Not Recommended)

| Option | Pros | Cons |
|--------|------|------|
| Cloud9 browser IDE only | Zero local setup | No Kiro AI features, no specs/hooks/steering |
| Kiro local + AWS CLI creds | No EC2 needed | Credentials in local files, no Rust toolchain |
| VS Code Remote-SSH (no Kiro) | Works fine | Loses Kiro's AI agent, specs, and hooks |

### 4.6 When to Use Which

| Task | Use |
|------|-----|
| Feature development, code review, AI-assisted coding | Kiro + Remote-SSH |
| Quick infra check, IAM policy edits, one-off commands | Cloud9 browser IDE |
| CI/CD, deployment scripts | GitHub Actions (no IDE needed) |
| Mobile app development (Expo) | Kiro locally (needs simulator/emulator) |

---

## Phase 5: Running the Full Stack on Cloud9

### 5.1 Start Backend Infrastructure

```bash
# Start all Docker services (Postgres, Redis, EMQX, API, MQTT Writer, Alert Engine)
make start

# Wait for health checks
make status

# Apply database migrations & seed data
make db-migrate
make db-seed
```

### 5.2 Start Dashboard (Web)

```bash
# Dashboard dev server (port 5173)
make dashboard

# Cloud9 Preview: click "Preview" → "Preview Running Application"
# Or open the Cloud9-provided URL: https://<env-id>.vfs.cloud9.<region>.amazonaws.com:5173
```

> **Note**: Cloud9 proxies ports through HTTPS. Update the dashboard `.env` to use
> the Cloud9 preview URL for API requests if needed.

### 5.3 Access the Stack

| Service | Access Method |
|---------|--------------|
| Dashboard | Cloud9 Preview (port 5173) |
| API Swagger | Cloud9 Preview (port 8000) → `/docs` |
| EMQX Dashboard | Cloud9 Preview (port 18083) |
| PostgreSQL | `make db-shell` (or port-forward for GUI tools) |

### 5.4 Port Forwarding for External Access

If you need to access from your local browser:

```bash
# From your local machine (requires AWS Session Manager plugin):
aws ssm start-session \
  --target <instance-id> \
  --document-name AWS-StartPortForwardingSession \
  --parameters '{"portNumber":["5173"],"localPortNumber":["5173"]}'
```

---

## Phase 6: Simulators & Demo Mode

### 6.1 Run Simulators on Cloud9

All simulators work identically to local development:

```bash
# GPS Collar Simulator (Boschhoek, 5 animals)
make simulate

# BLE Gateway Simulator (Loch Vaal, 10 animals)
make simulate-gateway

# Full demo mode (3 farms, 65 animals, all simulators + frontends)
make demo

# Demo with specific scenarios
make demo-theft          # Theft scenario at Loch Vaal
make demo-normal         # Peaceful day, no alerts
make demo-no-mobile      # Skip mobile app (Cloud9 can't run native)
```

### 6.2 Full Day Simulation (Accelerated)

```bash
# Full herdsman day — 12 hours compressed into ~6 minutes
make simulate-day

# Sibanyoni large farm (50 cattle)
make simulate-day-sibanyoni

# Continuous loop (both farms, runs forever)
make simulate-loop
```

### 6.3 Testing SES Email Alerts

With the IAM role attached, email alerts fire automatically when:
- A geofence breach is detected (`make simulate-breach`)
- A theft scenario triggers (`make simulate-theft`)

```bash
# Trigger a breach scenario and watch for SES email
make simulate-breach

# Check alert engine logs for dispatch confirmation
docker compose -f cloud/docker-compose.yml logs alert_engine --tail 50
```

### 6.4 Testing SMS Alerts

Requires Africa's Talking API key in Secrets Manager:

```bash
# Verify the SMS dispatcher can load credentials
docker compose -f cloud/docker-compose.yml exec alert_engine \
  python -c "from app.dispatchers.sms_africastalking import AfricasTalkingSMSDispatcher; print('OK')"

# Trigger a critical alert (critical severity = SMS + email + push + dashboard)
make simulate-theft
```

---

## Phase 7: Testing on Cloud9

### 7.1 Run All Tests

```bash
# Full test suite (same as CI)
make test
```

### 7.2 Individual Service Tests

```bash
# API Gateway (47+ tests, in-memory SQLite)
cd cloud/services/api_gateway
pip install -r requirements.txt -r requirements-test.txt
pytest -v
cd -

# Alert Engine
cd cloud/services/alert_engine
pip install -r requirements.txt -r requirements-test.txt
pytest -v
cd -

# MQTT Writer
cd cloud/services/mqtt_writer
pip install -r requirements.txt -r requirements-test.txt
pytest -v
cd -

# Rust services
cd cloud/services/ingestion && cargo test --verbose && cd -
cd cloud/services/geofence_engine && cargo test --verbose && cd -

# Dashboard (TypeScript type check + Vite build)
cd dashboard && npx tsc --noEmit && npm run build && cd -
```

### 7.3 E2E Tests (Playwright)

```bash
# Requires dashboard + full stack running
# Install Playwright browsers
cd e2e && npx playwright install --with-deps chromium && cd -

# Run E2E suite
make verify-e2e
```

### 7.4 API Verification

```bash
# Hit health endpoint
curl http://localhost:8000/health

# Run full API verification script
make verify-api

# Manual Swagger testing
# Open Cloud9 Preview → port 8000 → /docs
```

### 7.5 Integration Test: End-to-End Alert Flow

```bash
# 1. Start stack
make start && make db-seed

# 2. Start MQTT writer
make mqtt-writer

# 3. Trigger a theft alert via simulator
make simulate-theft

# 4. Verify the complete chain:
#    - MQTT Writer detects theft (check logs)
docker compose -f cloud/docker-compose.yml logs mqtt_writer --tail 20

#    - Alert stored in PostgreSQL
make db-shell
# SELECT * FROM alerts WHERE alert_type = 'theft_detected' ORDER BY created_at DESC LIMIT 5;

#    - Alert Engine dispatched notifications
docker compose -f cloud/docker-compose.yml logs alert_engine --tail 20

#    - SES email sent (check AWS Console → SES → Sending Statistics)
aws ses get-send-statistics --region af-south-1
```

---

## Phase 8: Code Changes for AWS Integration

### 8.1 AWS Configuration Loader

Create `cloud/shared/livestockguard_common/aws_config.py`:

```python
"""
AWS-aware configuration loader.

On AWS (Cloud9/ECS): reads from Secrets Manager + Parameter Store.
Locally: falls back to environment variables / .env files.
"""

import json
import os
from functools import lru_cache
from typing import Optional

def is_aws_environment() -> bool:
    """Detect if running on AWS infrastructure."""
    return (
        os.environ.get("AWS_EXECUTION_ENV") is not None
        or os.environ.get("ECS_CONTAINER_METADATA_URI") is not None
        or os.path.exists("/sys/hypervisor/uuid")
    )

@lru_cache()
def _get_secrets_client():
    import boto3
    return boto3.client("secretsmanager", region_name="af-south-1")

@lru_cache()
def _get_ssm_client():
    import boto3
    return boto3.client("ssm", region_name="af-south-1")

def get_secret(secret_name: str) -> dict:
    """
    Fetch a JSON secret from AWS Secrets Manager.

    Args:
        secret_name: Secret name without prefix (e.g., 'jwt-secret').
                     Automatically prefixed with 'livestockguard/'.

    Returns:
        Parsed JSON dict from the secret value.
    """
    client = _get_secrets_client()
    response = client.get_secret_value(SecretId=f"livestockguard/{secret_name}")
    return json.loads(response["SecretString"])

def get_parameter(param_name: str) -> str:
    """
    Fetch a config value from SSM Parameter Store.

    Args:
        param_name: Parameter name without prefix (e.g., 'ses-sender-email').
                    Automatically prefixed with '/livestockguard/'.

    Returns:
        String value of the parameter.
    """
    client = _get_ssm_client()
    response = client.get_parameter(Name=f"/livestockguard/{param_name}")
    return response["Parameter"]["Value"]

def load_jwt_secret() -> str:
    """Get JWT signing secret (AWS or env fallback)."""
    if is_aws_environment():
        return get_secret("jwt-secret")["value"]
    return os.environ.get("JWT_SECRET", "dev_secret_change_in_production")

def load_ses_config() -> dict:
    """Get SES email configuration."""
    if is_aws_environment():
        return {
            "sender_email": get_parameter("ses-sender-email"),
            "region": get_parameter("aws-region"),
            "recipients": get_parameter("email-recipients").split(","),
        }
    return {
        "sender_email": os.environ.get("SES_SENDER_EMAIL", "alerts@livestockguard.co.za"),
        "region": os.environ.get("AWS_REGION", "af-south-1"),
        "recipients": [e.strip() for e in os.environ.get("ALERT_EMAIL_RECIPIENTS", "").split(",") if e.strip()],
    }

def load_sms_config() -> dict:
    """Get Africa's Talking SMS configuration."""
    if is_aws_environment():
        creds = get_secret("africastalking")
        recipients = get_parameter("sms-recipients").split(",")
        return {
            "api_key": creds["api_key"],
            "username": creds["username"],
            "recipients": recipients,
        }
    return {
        "api_key": os.environ.get("AT_API_KEY", ""),
        "username": os.environ.get("AT_USERNAME", "sandbox"),
        "recipients": [p.strip() for p in os.environ.get("ALERT_SMS_RECIPIENTS", "").split(",") if p.strip()],
    }

def load_firebase_config() -> Optional[dict]:
    """Get Firebase FCM service account credentials."""
    if is_aws_environment():
        return get_secret("firebase-credentials")
    creds_file = os.environ.get("FIREBASE_CREDENTIALS_FILE", "./config/firebase-credentials.json")
    if os.path.exists(creds_file):
        with open(creds_file) as f:
            return json.load(f)
    return None

def load_database_url() -> str:
    """Get PostgreSQL connection URL."""
    if is_aws_environment():
        db = get_secret("postgres")
        return f"postgresql://{db['username']}:{db['password']}@{db['host']}:{db['port']}/{db['dbname']}"
    return os.environ.get(
        "DATABASE_URL",
        "postgresql://livestockguard:livestockguard_dev@localhost:5432/livestockguard"
    )
```

### 8.2 Wire Into Existing Services

Modify service startup to use the loader:

**API Gateway** (`dependencies.py`):
```python
from livestockguard_common.aws_config import load_jwt_secret
JWT_SECRET = load_jwt_secret()
```

**Alert Engine** (`app/main.py`):
```python
from livestockguard_common.aws_config import load_ses_config, load_sms_config
# Pass config to dispatchers at init time
```

**MQTT Writer** (`mqtt_writer.py`):
```python
from livestockguard_common.aws_config import load_database_url
DATABASE_URL = load_database_url()
```

---

## Phase 9: Production Deployment (ECS Fargate)

### 9.1 Infrastructure Resources

| Resource | Service | Configuration |
|----------|---------|---------------|
| VPC | Networking | 2 public + 2 private subnets in af-south-1 |
| ALB | Load Balancer | HTTPS (ACM cert for api.livestockguard.co.za) |
| ECS Cluster | Compute | Fargate, 3 services |
| RDS | Database | PostgreSQL 16, db.t3.medium, Multi-AZ |
| ElastiCache | Cache | Redis 7, cache.t3.micro |
| S3 | Static | Dashboard build artifacts |
| CloudFront | CDN | Dashboard distribution |
| ECR | Registry | Container images |
| EMQX Cloud | MQTT | Managed EMQX or AWS IoT Core |

### 9.2 ECS Task Definitions

**API Gateway**:
```json
{
  "family": "livestockguard-api",
  "taskRoleArn": "arn:aws:iam::ACCOUNT:role/LivestockGuardServiceRole",
  "executionRoleArn": "arn:aws:iam::ACCOUNT:role/ecsTaskExecutionRole",
  "containerDefinitions": [{
    "name": "api-gateway",
    "image": "ACCOUNT.dkr.ecr.af-south-1.amazonaws.com/livestockguard-api:latest",
    "portMappings": [{"containerPort": 8000}],
    "environment": [
      {"name": "REDIS_URL", "value": "redis://elasticache-endpoint:6379/0"}
    ],
    "secrets": [
      {"name": "DATABASE_URL", "valueFrom": "arn:aws:secretsmanager:af-south-1:ACCOUNT:secret:livestockguard/postgres"},
      {"name": "JWT_SECRET", "valueFrom": "arn:aws:secretsmanager:af-south-1:ACCOUNT:secret:livestockguard/jwt-secret"}
    ],
    "logConfiguration": {
      "logDriver": "awslogs",
      "options": {
        "awslogs-group": "/ecs/livestockguard",
        "awslogs-region": "af-south-1",
        "awslogs-stream-prefix": "api"
      }
    }
  }],
  "cpu": "512",
  "memory": "1024",
  "networkMode": "awsvpc"
}
```

**MQTT Writer**:
```json
{
  "family": "livestockguard-mqtt-writer",
  "cpu": "256",
  "memory": "512",
  "containerDefinitions": [{
    "name": "mqtt-writer",
    "image": "ACCOUNT.dkr.ecr.af-south-1.amazonaws.com/livestockguard-mqtt-writer:latest",
    "environment": [
      {"name": "MQTT_BROKER", "value": "emqx-endpoint"},
      {"name": "REDIS_URL", "value": "redis://elasticache-endpoint:6379/0"}
    ],
    "secrets": [
      {"name": "DATABASE_URL", "valueFrom": "arn:aws:secretsmanager:..."}
    ]
  }]
}
```

**Alert Engine**:
```json
{
  "family": "livestockguard-alert-engine",
  "cpu": "256",
  "memory": "512",
  "containerDefinitions": [{
    "name": "alert-engine",
    "image": "ACCOUNT.dkr.ecr.af-south-1.amazonaws.com/livestockguard-alert-engine:latest",
    "environment": [
      {"name": "REDIS_URL", "value": "redis://elasticache-endpoint:6379/0"}
    ],
    "secrets": [
      {"name": "FIREBASE_CREDENTIALS", "valueFrom": "arn:aws:secretsmanager:...:livestockguard/firebase-credentials"},
      {"name": "AT_API_KEY", "valueFrom": "arn:aws:secretsmanager:...:livestockguard/africastalking"}
    ]
  }]
}
```

### 9.3 Dashboard Deployment (S3 + CloudFront)

```bash
# Build production bundle
cd dashboard && npm run build

# Sync to S3
aws s3 sync dist/ s3://livestockguard-dashboard/ --delete

# Invalidate CloudFront cache
aws cloudfront create-invalidation \
  --distribution-id E1234ABCDEF \
  --paths "/*"
```

### 9.4 Database Migration (Production RDS)

```bash
# Connect to RDS via bastion/SSM and run migrations
export DATABASE_URL="postgresql://livestockguard:PASSWORD@rds-endpoint:5432/livestockguard"

for f in cloud/migrations/versions/*.sql; do
  psql "$DATABASE_URL" -f "$f"
  echo "Applied: $f"
done
```

---

## Phase 10: CI/CD Pipeline

### 10.1 GitHub Actions Updates

Add deployment steps to `.github/workflows/ci.yml`:

```yaml
  deploy:
    if: github.ref == 'refs/heads/main' && github.event_name == 'push'
    needs: [api-gateway-tests, alert-engine-tests, mqtt-writer-tests, rust-tests, dashboard-build]
    runs-on: ubuntu-latest
    permissions:
      id-token: write
      contents: read
    steps:
      - uses: actions/checkout@v4

      - name: Configure AWS credentials (OIDC)
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::ACCOUNT:role/GitHubActionsDeployRole
          aws-region: af-south-1

      - name: Login to ECR
        uses: aws-actions/amazon-ecr-login@v2

      - name: Build & push API Gateway
        run: |
          docker build -t livestockguard-api cloud/services/api_gateway/
          docker tag livestockguard-api:latest ACCOUNT.dkr.ecr.af-south-1.amazonaws.com/livestockguard-api:latest
          docker push ACCOUNT.dkr.ecr.af-south-1.amazonaws.com/livestockguard-api:latest

      - name: Update ECS services
        run: |
          aws ecs update-service --cluster livestockguard --service api-gateway --force-new-deployment
          aws ecs update-service --cluster livestockguard --service mqtt-writer --force-new-deployment
          aws ecs update-service --cluster livestockguard --service alert-engine --force-new-deployment

      - name: Deploy dashboard to S3
        run: |
          cd dashboard && npm ci && npm run build
          aws s3 sync dist/ s3://livestockguard-dashboard/ --delete
          aws cloudfront create-invalidation --distribution-id ${{ secrets.CF_DISTRIBUTION_ID }} --paths "/*"
```

### 10.2 GitHub OIDC for AWS (No Long-Lived Keys)

```bash
# Create OIDC provider in IAM (one-time)
aws iam create-open-id-connect-provider \
  --url https://token.actions.githubusercontent.com \
  --client-id-list sts.amazonaws.com \
  --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1

# Create deploy role trusting GitHub
# Condition: only from your repo's main branch
```

---

## Phase 11: Monitoring & Operations

### 11.1 CloudWatch Alarms

```bash
# API Gateway 5xx errors
aws cloudwatch put-metric-alarm \
  --alarm-name livestockguard-api-5xx \
  --metric-name HTTPCode_Target_5XX_Count \
  --namespace AWS/ApplicationELB \
  --threshold 10 --comparison-operator GreaterThanThreshold \
  --evaluation-periods 2 --period 300 \
  --alarm-actions arn:aws:sns:af-south-1:ACCOUNT:ops-alerts

# MQTT Writer error rate
# Alert Engine processing failures
# RDS CPU > 80%
# Redis memory > 75%
```

### 11.2 Log Groups

| Service | Log Group |
|---------|-----------|
| API Gateway | `/ecs/livestockguard/api` |
| MQTT Writer | `/ecs/livestockguard/mqtt-writer` |
| Alert Engine | `/ecs/livestockguard/alert-engine` |

### 11.3 Health Checks

| Endpoint | Expected |
|----------|----------|
| `GET /health` | `200 {"status": "ok"}` |
| `GET /docs` | Swagger UI loads |
| Redis PING | PONG |
| PostgreSQL `pg_isready` | accepting connections |

---

## Cost Estimate

### Cloud9 Development (Monthly)

| Resource | Spec | Cost (USD) |
|----------|------|-----------|
| EC2 (t3.medium) | 4 GB RAM, on-demand | ~$30/mo (or $0 if stopped) |
| EBS | 30 GB gp3 | ~$2.40/mo |
| **Total** | | **~$32/mo when running** |

### Production (Monthly, af-south-1)

| Resource | Spec | Cost (USD) |
|----------|------|-----------|
| ECS Fargate (3 tasks) | 0.25–0.5 vCPU each | ~$35/mo |
| RDS PostgreSQL | db.t3.micro, Single-AZ | ~$20/mo |
| ElastiCache Redis | cache.t3.micro | ~$15/mo |
| ALB | 1 ALB + processing | ~$20/mo |
| S3 + CloudFront | Dashboard hosting | ~$2/mo |
| Secrets Manager | 5 secrets | ~$2/mo |
| SES | 1000 emails/mo | ~$0.10/mo |
| EMQX Cloud (Basic) | Small instance | ~$20/mo |
| **Total** | | **~$115/mo** |

> af-south-1 pricing is ~15% higher than us-east-1. Costs decrease with reserved instances.

---

## Execution Checklist

### Week 1: Foundation

- [ ] Create AWS account (if needed) and enable af-south-1 region
- [ ] Create IAM policy `LivestockGuardServicePolicy`
- [ ] Create IAM role `LivestockGuardServiceRole`
- [ ] Create instance profile `LivestockGuardCloud9`
- [ ] Verify SES sender identity (domain or email)
- [ ] Store secrets in Secrets Manager (JWT, Firebase, AT, Postgres)
- [ ] Store config in Parameter Store (sender email, region, recipients)

### Week 2: Cloud9 Setup

- [ ] Create Cloud9 environment (t3.medium, Amazon Linux 2023)
- [ ] Attach IAM instance profile
- [ ] Disable Cloud9 managed credentials
- [ ] Install toolchain (Rust, Node 20, Python 3.12, Docker)
- [ ] Resize EBS to 30 GB
- [ ] Clone repo, run `make setup`
- [ ] Generate & commit Cargo.lock files
- [ ] Run `make test` — all green

### Week 3: Integration Testing

- [ ] Run `make demo` — full stack operational
- [ ] Trigger breach alert → verify SES email arrives
- [ ] Trigger theft alert → verify SMS arrives (if AT configured)
- [ ] Add `aws_config.py` loader to shared package
- [ ] Wire loader into API Gateway, MQTT Writer, Alert Engine
- [ ] Run `make test` again — still green
- [ ] Test WebSocket real-time updates through Cloud9 preview

### Week 4: Production Prep

- [ ] Create VPC with public/private subnets
- [ ] Create RDS PostgreSQL + TimescaleDB
- [ ] Create ElastiCache Redis cluster
- [ ] Create ECR repositories (api, mqtt-writer, alert-engine)
- [ ] Build & push Docker images to ECR
- [ ] Create ECS cluster + task definitions + services
- [ ] Create ALB with HTTPS (ACM certificate)
- [ ] Run database migrations on RDS
- [ ] Seed initial data (farms, admin user)

### Week 5: Go Live

- [ ] Deploy dashboard to S3 + CloudFront
- [ ] Configure DNS (api.livestockguard.co.za → ALB, app.livestockguard.co.za → CloudFront)
- [ ] Request SES production access (exit sandbox)
- [ ] Set up CloudWatch alarms
- [ ] Run E2E tests against production
- [ ] Enable GitHub Actions deployment (OIDC)
- [ ] Connect real GPS collar hardware
- [ ] Monitor for 48 hours before going fully live

---

## Appendix: Local Dev vs Cloud9 vs Production

| Concern | Local (macOS) | Cloud9 | Production (ECS) |
|---------|---------------|--------|-----------------|
| Credentials | `.env` file | IAM instance role | ECS task role |
| Database | Docker Postgres | Docker Postgres | RDS |
| Redis | Docker Redis | Docker Redis | ElastiCache |
| MQTT | Docker EMQX | Docker EMQX | EMQX Cloud / IoT Core |
| SES Email | Disabled (no creds) | Works (IAM role) | Works (task role) |
| SMS | Disabled | Works (AT sandbox) | Works (AT production) |
| FCM Push | Disabled (no creds) | Works (secret loaded) | Works (secret injected) |
| Dashboard | localhost:5173 | Cloud9 Preview | CloudFront |
| Mobile | Expo (localhost:8082) | Web only | App Store / Play Store |
| Rust build | Not available | `cargo build` works | CI builds image |

---

*Last updated: 2026-08-16*
