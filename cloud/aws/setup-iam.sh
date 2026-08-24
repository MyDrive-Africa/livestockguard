#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# LivestockGuard — Phase 1: IAM Foundation Setup
#
# Creates IAM policy, role, instance profile, and verifies SES sender identity.
# Run this from your local machine with AWS CLI configured (admin credentials).
#
# Usage:
#   cd cloud/aws
#   chmod +x setup-iam.sh
#   ./setup-iam.sh
#
# Prerequisites:
#   - AWS CLI v2 installed and configured
#   - Admin-level IAM permissions
#   - af-south-1 region enabled in your account
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

# ─── Configuration ────────────────────────────────────────────────────────────

AWS_REGION="${AWS_REGION:-af-south-1}"
POLICY_NAME="LivestockGuardServicePolicy"
ROLE_NAME="LivestockGuardServiceRole"
INSTANCE_PROFILE_NAME="LivestockGuardCloud9"
SES_SENDER_EMAIL="${SES_SENDER_EMAIL:-alerts@livestockguard.co.za}"
SES_DOMAIN="${SES_DOMAIN:-livestockguard.co.za}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
POLICIES_DIR="${SCRIPT_DIR}/policies"

# ─── Helpers ──────────────────────────────────────────────────────────────────

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info() { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
fail() { echo -e "${RED}[✗]${NC} $1"; exit 1; }

check_prereqs() {
    echo "═══════════════════════════════════════════════════════════════"
    echo "  LivestockGuard — Phase 1: IAM Foundation"
    echo "═══════════════════════════════════════════════════════════════"
    echo ""

    command -v aws >/dev/null 2>&1 || fail "AWS CLI not found. Install: brew install awscli"

    # Verify caller identity
    CALLER=$(aws sts get-caller-identity --output text --query 'Arn' 2>/dev/null) \
        || fail "AWS credentials not configured. Run: aws configure"
    info "Authenticated as: ${CALLER}"

    # Verify region is enabled
    aws ec2 describe-regions --region-names "${AWS_REGION}" --output text >/dev/null 2>&1 \
        || fail "Region ${AWS_REGION} not enabled. Enable it in AWS Console → Account Settings."
    info "Region ${AWS_REGION} is available"

    ACCOUNT_ID=$(aws sts get-caller-identity --query 'Account' --output text)
    info "Account ID: ${ACCOUNT_ID}"
    echo ""
}

# ─── Step 1: Create IAM Policy ────────────────────────────────────────────────

create_policy() {
    echo "── Step 1: IAM Policy ──────────────────────────────────────────"

    # Check if policy already exists
    EXISTING=$(aws iam list-policies --scope Local --query \
        "Policies[?PolicyName=='${POLICY_NAME}'].Arn" --output text 2>/dev/null)

    if [[ -n "${EXISTING}" && "${EXISTING}" != "None" ]]; then
        warn "Policy '${POLICY_NAME}' already exists: ${EXISTING}"
        POLICY_ARN="${EXISTING}"
    else
        POLICY_ARN=$(aws iam create-policy \
            --policy-name "${POLICY_NAME}" \
            --policy-document "file://${POLICIES_DIR}/service-policy.json" \
            --description "LivestockGuard service permissions: SES, Secrets Manager, SSM, CloudWatch, ECR" \
            --query 'Policy.Arn' --output text) \
            || fail "Failed to create IAM policy"
        info "Created policy: ${POLICY_ARN}"
    fi
    echo ""
}

# ─── Step 2: Create IAM Role ──────────────────────────────────────────────────

create_role() {
    echo "── Step 2: IAM Role ────────────────────────────────────────────"

    # Check if role already exists
    EXISTING_ROLE=$(aws iam get-role --role-name "${ROLE_NAME}" \
        --query 'Role.Arn' --output text 2>/dev/null || true)

    if [[ -n "${EXISTING_ROLE}" && "${EXISTING_ROLE}" != "None" ]]; then
        warn "Role '${ROLE_NAME}' already exists: ${EXISTING_ROLE}"
    else
        aws iam create-role \
            --role-name "${ROLE_NAME}" \
            --assume-role-policy-document "file://${POLICIES_DIR}/trust-policy.json" \
            --description "LivestockGuard service role for Cloud9 and ECS tasks" \
            --output text >/dev/null \
            || fail "Failed to create IAM role"
        info "Created role: ${ROLE_NAME}"
    fi

    # Attach policy to role
    aws iam attach-role-policy \
        --role-name "${ROLE_NAME}" \
        --policy-arn "${POLICY_ARN}" 2>/dev/null \
        || warn "Policy may already be attached"
    info "Attached ${POLICY_NAME} → ${ROLE_NAME}"
    echo ""
}

# ─── Step 3: Create Instance Profile ──────────────────────────────────────────

create_instance_profile() {
    echo "── Step 3: Instance Profile ────────────────────────────────────"

    # Check if instance profile exists
    EXISTING_IP=$(aws iam get-instance-profile \
        --instance-profile-name "${INSTANCE_PROFILE_NAME}" \
        --query 'InstanceProfile.Arn' --output text 2>/dev/null || true)

    if [[ -n "${EXISTING_IP}" && "${EXISTING_IP}" != "None" ]]; then
        warn "Instance profile '${INSTANCE_PROFILE_NAME}' already exists"
    else
        aws iam create-instance-profile \
            --instance-profile-name "${INSTANCE_PROFILE_NAME}" \
            --output text >/dev/null \
            || fail "Failed to create instance profile"
        info "Created instance profile: ${INSTANCE_PROFILE_NAME}"
    fi

    # Add role to instance profile (idempotent — AWS ignores if already added)
    aws iam add-role-to-instance-profile \
        --instance-profile-name "${INSTANCE_PROFILE_NAME}" \
        --role-name "${ROLE_NAME}" 2>/dev/null \
        || warn "Role may already be attached to instance profile"
    info "Attached ${ROLE_NAME} → ${INSTANCE_PROFILE_NAME}"
    echo ""
}

# ─── Step 4: Verify SES Sender Identity ───────────────────────────────────────

verify_ses() {
    echo "── Step 4: SES Sender Identity ─────────────────────────────────"

    # Try domain verification first
    echo "  Verifying domain: ${SES_DOMAIN}"
    DKIM_TOKENS=$(aws ses verify-domain-dkim \
        --domain "${SES_DOMAIN}" \
        --region "${AWS_REGION}" \
        --query 'DkimTokens' --output text 2>/dev/null || true)

    if [[ -n "${DKIM_TOKENS}" ]]; then
        info "Domain verification initiated for ${SES_DOMAIN}"
        echo "  Add these DKIM CNAME records to your DNS:"
        for token in ${DKIM_TOKENS}; do
            echo "    ${token}._domainkey.${SES_DOMAIN} → ${token}.dkim.amazonses.com"
        done
    else
        warn "Domain verification failed — trying email instead"
    fi

    # Also verify individual email (works immediately for sandbox testing)
    aws ses verify-email-identity \
        --email-address "${SES_SENDER_EMAIL}" \
        --region "${AWS_REGION}" 2>/dev/null \
        || warn "Email verification request may have already been sent"
    info "Verification email sent to ${SES_SENDER_EMAIL}"
    echo "  Check inbox and click the verification link."
    echo ""
}

# ─── Verification ─────────────────────────────────────────────────────────────

verify_setup() {
    echo "── Verification ────────────────────────────────────────────────"

    # Verify policy
    aws iam get-policy --policy-arn "${POLICY_ARN}" --output text >/dev/null 2>&1 \
        && info "Policy exists: ${POLICY_NAME}" \
        || fail "Policy verification failed"

    # Verify role
    aws iam get-role --role-name "${ROLE_NAME}" --output text >/dev/null 2>&1 \
        && info "Role exists: ${ROLE_NAME}" \
        || fail "Role verification failed"

    # Verify instance profile
    aws iam get-instance-profile --instance-profile-name "${INSTANCE_PROFILE_NAME}" \
        --output text >/dev/null 2>&1 \
        && info "Instance profile exists: ${INSTANCE_PROFILE_NAME}" \
        || fail "Instance profile verification failed"

    # Check SES identity status
    SES_STATUS=$(aws ses get-identity-verification-attributes \
        --identities "${SES_SENDER_EMAIL}" \
        --region "${AWS_REGION}" \
        --query "VerificationAttributes.\"${SES_SENDER_EMAIL}\".VerificationStatus" \
        --output text 2>/dev/null || echo "NotStarted")
    if [[ "${SES_STATUS}" == "Success" ]]; then
        info "SES sender verified: ${SES_SENDER_EMAIL}"
    else
        warn "SES sender status: ${SES_STATUS} (verify email inbox or DNS)"
    fi

    echo ""
    echo "═══════════════════════════════════════════════════════════════"
    echo "  Phase 1 Complete!"
    echo ""
    echo "  Next steps:"
    echo "    1. Verify the SES email (check inbox for ${SES_SENDER_EMAIL})"
    echo "    2. Add DKIM DNS records if using domain verification"
    echo "    3. Run: ./setup-secrets.sh  (Phase 2)"
    echo "═══════════════════════════════════════════════════════════════"
}

# ─── Main ─────────────────────────────────────────────────────────────────────

check_prereqs
create_policy
create_role
create_instance_profile
verify_ses
verify_setup
