# Next Session — "Take Everything to IAM/AWS" Kickoff

> Purpose: hand off cleanly to the follow-up session that moves LivestockGuard onto AWS,
> starting with IAM. The full plan already exists in
> [`AWS_CLOUD9_DEPLOYMENT_PLAN.md`](./AWS_CLOUD9_DEPLOYMENT_PLAN.md) (11 phases) and the
> scripts exist in [`cloud/aws/`](../cloud/aws/). This file records the **current starting
> state**, the **preflight gaps**, and the **exact order of operations** so the next
> session can execute without re-discovery.

**Prepared:** 2026-09-14 · **Local platform status:** fully running & verified (see [`LOCAL_RUN_STATUS.md`](./LOCAL_RUN_STATUS.md)).

---

## 1. What "to IAM" means here

The first, foundational step of the AWS migration is **Phase 1 — IAM Foundation**:
create the service policy, role, instance profile, and verify the SES sender identity.
Everything else (secrets, Cloud9, ECS) builds on it. The next session should run Phase 1,
then Phase 2 (secrets/config), and stop at a verified state before touching compute.

---

## 2. Preflight gaps found on this machine (do these FIRST)

| Gap | Evidence | Action for next session |
|-----|----------|--------------------------|
| **AWS CLI not installed** | `aws` → command not found | `brew install awscli` (Homebrew is at `/opt/homebrew`, on PATH via `~/.zprofile`) |
| **No `~/.aws/config` or `credentials`** | files absent | Configure access before running any `make aws-*` target |
| **SSO likely** | `~/.aws/sso/cache/` exists (incl. a token cache) but no profile config | Set up `aws configure sso` (IAM Identity Center) OR `aws configure` with admin keys. Confirm which model the org uses. Do **not** commit or echo tokens. |
| **Region access** | unverified | Phase 1 script checks `af-south-1` is enabled; enable it in the account if not |

> The `setup-iam.sh` script already fails fast if the CLI is missing or credentials
> aren't configured, so these gaps will block immediately — worth clearing up front.

---

## 3. Assets already in the repo (no need to author)

**Scripts** (`cloud/aws/`, all idempotent):
- `setup-iam.sh` — Phase 1: creates `LivestockGuardServicePolicy`, `LivestockGuardServiceRole`, instance profile `LivestockGuardCloud9`, verifies SES.
- `setup-secrets.sh` — Phase 2: Secrets Manager + SSM Parameter Store.
- `cloud9-bootstrap.sh` — Phase 3: run **on** the Cloud9 instance.
- `verify-setup.sh` — validates all phases.
- `policies/service-policy.json` — SES, Secrets Manager, SSM, CloudWatch Logs, ECR.
- `policies/trust-policy.json` — trust for `ec2.amazonaws.com` + `ecs-tasks.amazonaws.com`.

**Makefile targets:**
```
make aws-iam        # Phase 1 (setup-iam.sh)
make aws-secrets    # Phase 2 (setup-secrets.sh)
make aws-setup      # Phase 1 + 2 together
make cloud9-bootstrap  # Phase 3 (run on Cloud9)
make aws-verify     # verify-setup.sh
```

**Python integration (Phase 8, when wiring services to AWS):**
- `cloud/shared/livestockguard_common/aws_config.py` — loader that reads Secrets Manager /
  Parameter Store on AWS and falls back to env vars locally (spec'd in the plan).

---

## 4. Recommended order of operations (next session)

1. **Preflight**
   - `brew install awscli`
   - Configure auth (`aws configure sso` or `aws configure`); confirm with
     `aws sts get-caller-identity`.
   - Confirm `af-south-1` is enabled.
2. **Phase 1 — IAM** (`make aws-iam`)
   - Creates policy + role + instance profile; initiates SES domain (DKIM) + email verify.
   - Manual follow-up: click SES verification email and/or add DKIM CNAME records to DNS.
3. **Phase 2 — Secrets/Config** (`make aws-secrets`)
   - JWT secret, Firebase creds, Africa's Talking SMS, Postgres creds, webhook URLs → Secrets Manager.
   - Sender email, region, recipients, cooldown → Parameter Store.
   - Have the real secret values ready (don't invent placeholders in production).
4. **Verify** (`make aws-verify`) — confirm policy/role/instance profile/SES all present.
5. **STOP & review** before Phase 3+ (Cloud9 / ECS) — those incur cost and change compute.

---

## 5. Decisions to confirm with the user before running

- **Auth model:** SSO (IAM Identity Center) vs. IAM user access keys? (SSO cache suggests SSO.)
- **AWS account & region:** which account ID; `af-south-1` (Cape Town) as planned?
- **SES:** domain (`livestockguard.co.za`) DKIM vs. single-email verify; still in sandbox?
- **Real secret values:** who provides JWT/Firebase/Africa's Talking/DB/webhook secrets?
- **Scope for the session:** IAM + secrets only, or continue into Cloud9/ECS (cost + bigger blast radius)?

---

## 6. Guardrails

- IAM, Secrets Manager, and SES changes are **shared-account / higher-impact**. Get explicit
  confirmation before creating roles/policies or storing secrets, and never print secret
  values back in chat/logs.
- The `cloud/aws/*.sh` scripts are idempotent (they detect existing resources) — safe to re-run.
- Do not modify AWS billing/org settings.

---

## 7. Local carry-over notes (so AWS steps line up with local reality)

- **Corporate TLS:** Node/pip/npm need the corporate CA. `NODE_EXTRA_CA_CERTS=~/.certs/corp-ca-bundle.pem`
  is set in `~/.zprofile`. The AWS CLI (Python/botocore) may likewise need
  `AWS_CA_BUNDLE=~/.certs/corp-ca-bundle.pem` if it hits TLS errors behind the proxy.
- **DNS:** watch for transient OpenDNS/Umbrella interception (seen during npm installs);
  retry on `ENOTFOUND …opendns.com`.
- Backend runs on **colima** locally (aarch64). AWS builds are linux/amd64 or arm64 — build
  target arch matters when pushing images to ECR later (Phase 9).
