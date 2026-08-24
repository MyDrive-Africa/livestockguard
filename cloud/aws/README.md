# LivestockGuard — AWS Infrastructure Scripts

Executable scripts for deploying LivestockGuard on AWS (Phases 1–3 of the [deployment plan](../../docs/AWS_CLOUD9_DEPLOYMENT_PLAN.md)).

## Structure

```
cloud/aws/
├── README.md               ← You are here
├── setup-iam.sh            ← Phase 1: IAM policy, role, instance profile, SES
├── setup-secrets.sh        ← Phase 2: Secrets Manager + Parameter Store
├── cloud9-bootstrap.sh     ← Phase 3: Cloud9 toolchain + project setup
├── verify-setup.sh         ← Validate all phases are configured correctly
└── policies/
    ├── service-policy.json ← IAM permissions (SES, Secrets, SSM, CloudWatch, ECR)
    └── trust-policy.json   ← Trust relationship (EC2 + ECS Tasks)
```

## Quick Start

```bash
cd cloud/aws
chmod +x *.sh

# Phase 1 — Run from local machine with admin credentials
./setup-iam.sh

# Phase 2 — Store secrets (interactive prompts)
./setup-secrets.sh

# Phase 3 — Run INSIDE Cloud9 after instance profile is attached
./cloud9-bootstrap.sh

# Verify everything
./verify-setup.sh
```

## Prerequisites

| Script | Where to Run | Requires |
|--------|-------------|----------|
| `setup-iam.sh` | Local (admin creds) | AWS CLI, IAM admin permissions |
| `setup-secrets.sh` | Local (admin creds) | AWS CLI, secrets ready |
| `cloud9-bootstrap.sh` | Cloud9 instance | Instance profile attached, managed creds OFF |
| `verify-setup.sh` | Cloud9 or local | LivestockGuard IAM role or admin |

## Environment Variables

All scripts respect these env vars for customization:

| Variable | Default | Purpose |
|----------|---------|---------|
| `AWS_REGION` | `af-south-1` | Target AWS region |
| `SES_SENDER_EMAIL` | `alerts@livestockguard.co.za` | SES sender to verify |
| `SES_DOMAIN` | `livestockguard.co.za` | Domain for DKIM verification |
| `REPO_URL` | (your repo) | Git clone URL for Cloud9 setup |

## Related

- [AWS Cloud9 Deployment Plan](../../docs/AWS_CLOUD9_DEPLOYMENT_PLAN.md) — Full 11-phase plan
- [Improvement Roadmap Sprint 7](../../docs/IMPROVEMENT_ROADMAP.md) — Where this fits
- [`livestockguard_common/aws_config.py`](../shared/livestockguard_common/aws_config.py) — Python config loader (Phase 8)
