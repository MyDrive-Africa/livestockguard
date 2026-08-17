#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# LivestockGuard — AWS Setup Verification
#
# Validates that Phases 1-3 are correctly configured. Run from Cloud9 or any
# machine with the LivestockGuard IAM role.
#
# Usage:
#   chmod +x verify-setup.sh
#   ./verify-setup.sh
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

AWS_REGION="${AWS_REGION:-af-south-1}"
PASS=0
FAIL=0
WARN=0

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

pass() { echo -e "  ${GREEN}✓${NC} $1"; ((PASS++)); }
fail_check() { echo -e "  ${RED}✗${NC} $1"; ((FAIL++)); }
warn_check() { echo -e "  ${YELLOW}!${NC} $1"; ((WARN++)); }

echo "═══════════════════════════════════════════════════════════════"
echo "  LivestockGuard — AWS Setup Verification"
echo "  Region: ${AWS_REGION}"
echo "═══════════════════════════════════════════════════════════════"
echo ""

# ─── IAM ──────────────────────────────────────────────────────────────────────

echo "── IAM (Phase 1) ───────────────────────────────────────────────"

# Identity
IDENTITY=$(aws sts get-caller-identity --output text --query 'Arn' 2>/dev/null || echo "")
if [[ -n "${IDENTITY}" ]]; then
    pass "Authenticated: ${IDENTITY}"
else
    fail_check "Not authenticated — check IAM role or credentials"
fi

# Policy exists
POLICY_ARN=$(aws iam list-policies --scope Local \
    --query "Policies[?PolicyName=='LivestockGuardServicePolicy'].Arn" \
    --output text 2>/dev/null || echo "")
if [[ -n "${POLICY_ARN}" && "${POLICY_ARN}" != "None" ]]; then
    pass "IAM policy exists: LivestockGuardServicePolicy"
else
    fail_check "IAM policy 'LivestockGuardServicePolicy' not found"
fi

# Role exists
if aws iam get-role --role-name LivestockGuardServiceRole >/dev/null 2>&1; then
    pass "IAM role exists: LivestockGuardServiceRole"
else
    fail_check "IAM role 'LivestockGuardServiceRole' not found"
fi

# Instance profile
if aws iam get-instance-profile --instance-profile-name LivestockGuardCloud9 >/dev/null 2>&1; then
    pass "Instance profile exists: LivestockGuardCloud9"
else
    fail_check "Instance profile 'LivestockGuardCloud9' not found"
fi

echo ""

# ─── Secrets Manager ──────────────────────────────────────────────────────────

echo "── Secrets Manager (Phase 2) ──────────────────────────────────"

SECRETS=("jwt-secret" "postgres" "firebase-credentials" "africastalking" "webhooks")
for secret in "${SECRETS[@]}"; do
    if aws secretsmanager describe-secret --secret-id "livestockguard/${secret}" \
        --region "${AWS_REGION}" >/dev/null 2>&1; then
        pass "Secret exists: livestockguard/${secret}"
    else
        warn_check "Secret missing: livestockguard/${secret}"
    fi
done

echo ""

# ─── Parameter Store ──────────────────────────────────────────────────────────

echo "── Parameter Store (Phase 2) ──────────────────────────────────"

PARAMS=("ses-sender-email" "aws-region" "email-recipients" "sms-recipients"
        "alert-cooldown-seconds" "redis-url" "mqtt-broker" "mqtt-port")
for param in "${PARAMS[@]}"; do
    VALUE=$(aws ssm get-parameter --name "/livestockguard/${param}" \
        --region "${AWS_REGION}" --query 'Parameter.Value' --output text 2>/dev/null || echo "")
    if [[ -n "${VALUE}" ]]; then
        pass "Parameter: /livestockguard/${param} = ${VALUE}"
    else
        warn_check "Parameter missing: /livestockguard/${param}"
    fi
done

echo ""

# ─── SES ──────────────────────────────────────────────────────────────────────

echo "── SES Email ───────────────────────────────────────────────────"

# Check send quota (verifies SES access)
QUOTA=$(aws ses get-send-quota --region "${AWS_REGION}" \
    --query 'Max24HourSend' --output text 2>/dev/null || echo "")
if [[ -n "${QUOTA}" ]]; then
    pass "SES accessible (daily quota: ${QUOTA})"
else
    fail_check "SES not accessible — check IAM permissions"
fi

# Check if sender email is verified
SENDER=$(aws ssm get-parameter --name "/livestockguard/ses-sender-email" \
    --region "${AWS_REGION}" --query 'Parameter.Value' --output text 2>/dev/null || echo "alerts@livestockguard.co.za")
SES_STATUS=$(aws ses get-identity-verification-attributes \
    --identities "${SENDER}" --region "${AWS_REGION}" \
    --query "VerificationAttributes.\"${SENDER}\".VerificationStatus" \
    --output text 2>/dev/null || echo "NotStarted")
if [[ "${SES_STATUS}" == "Success" ]]; then
    pass "SES sender verified: ${SENDER}"
else
    warn_check "SES sender not verified (status: ${SES_STATUS})"
fi

echo ""

# ─── Toolchain (Cloud9 only) ──────────────────────────────────────────────────

echo "── Toolchain (Phase 3) ─────────────────────────────────────────"

command -v rustc >/dev/null 2>&1 && pass "Rust: $(rustc --version)" || warn_check "Rust not installed"
command -v node >/dev/null 2>&1 && pass "Node: $(node --version)" || warn_check "Node.js not installed"
command -v python3 >/dev/null 2>&1 && pass "Python: $(python3 --version)" || warn_check "Python not installed"
command -v docker >/dev/null 2>&1 && pass "Docker: $(docker --version 2>/dev/null)" || warn_check "Docker not installed"
command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1 && \
    pass "Compose: $(docker compose version)" || warn_check "Docker Compose not available"

echo ""

# ─── Summary ──────────────────────────────────────────────────────────────────

echo "═══════════════════════════════════════════════════════════════"
echo -e "  Results: ${GREEN}${PASS} passed${NC}, ${RED}${FAIL} failed${NC}, ${YELLOW}${WARN} warnings${NC}"
echo "═══════════════════════════════════════════════════════════════"

if (( FAIL > 0 )); then
    echo ""
    echo "  Some checks failed. Review the output above and re-run"
    echo "  the relevant setup script."
    exit 1
elif (( WARN > 0 )); then
    echo ""
    echo "  Warnings are non-blocking but indicate optional config"
    echo "  is missing (Firebase, Africa's Talking, etc.)."
    exit 0
else
    echo ""
    echo "  All checks passed! Environment is fully configured."
    exit 0
fi
