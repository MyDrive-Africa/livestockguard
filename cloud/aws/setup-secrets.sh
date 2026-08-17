#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# LivestockGuard — Phase 2: Secrets & Configuration Setup
#
# Stores secrets in AWS Secrets Manager and configuration in SSM Parameter Store.
# Prompts interactively for sensitive values (won't store them in shell history).
#
# Usage:
#   cd cloud/aws
#   chmod +x setup-secrets.sh
#   ./setup-secrets.sh
#
# Prerequisites:
#   - Phase 1 complete (IAM role can access these resources)
#   - AWS CLI configured with admin permissions
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

# ─── Configuration ────────────────────────────────────────────────────────────

AWS_REGION="${AWS_REGION:-af-south-1}"
SECRET_PREFIX="livestockguard"
PARAM_PREFIX="/livestockguard"

# ─── Helpers ──────────────────────────────────────────────────────────────────

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

info() { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
fail() { echo -e "${RED}[✗]${NC} $1"; exit 1; }
prompt() { echo -e "${CYAN}[?]${NC} $1"; }

# Read secret input (no echo)
read_secret() {
    local var_name="$1"
    local prompt_msg="$2"
    local default_val="${3:-}"

    if [[ -n "${default_val}" ]]; then
        prompt "${prompt_msg} [default: ${default_val}]: "
    else
        prompt "${prompt_msg}: "
    fi
    read -rs INPUT
    echo ""

    if [[ -z "${INPUT}" && -n "${default_val}" ]]; then
        eval "${var_name}='${default_val}'"
    elif [[ -z "${INPUT}" ]]; then
        warn "Empty value for ${var_name} — skipping"
        eval "${var_name}=''"
    else
        eval "${var_name}='${INPUT}'"
    fi
}

# Read regular input (with echo)
read_value() {
    local var_name="$1"
    local prompt_msg="$2"
    local default_val="${3:-}"

    if [[ -n "${default_val}" ]]; then
        prompt "${prompt_msg} [default: ${default_val}]: "
    else
        prompt "${prompt_msg}: "
    fi
    read -r INPUT

    if [[ -z "${INPUT}" && -n "${default_val}" ]]; then
        eval "${var_name}='${default_val}'"
    elif [[ -z "${INPUT}" ]]; then
        eval "${var_name}=''"
    else
        eval "${var_name}='${INPUT}'"
    fi
}

# Create or update a secret
upsert_secret() {
    local name="$1"
    local value="$2"
    local description="${3:-}"

    local full_name="${SECRET_PREFIX}/${name}"

    # Check if secret exists
    if aws secretsmanager describe-secret --secret-id "${full_name}" \
        --region "${AWS_REGION}" >/dev/null 2>&1; then
        aws secretsmanager put-secret-value \
            --secret-id "${full_name}" \
            --secret-string "${value}" \
            --region "${AWS_REGION}" >/dev/null
        info "Updated secret: ${full_name}"
    else
        aws secretsmanager create-secret \
            --name "${full_name}" \
            --secret-string "${value}" \
            --description "${description}" \
            --region "${AWS_REGION}" >/dev/null
        info "Created secret: ${full_name}"
    fi
}

# Create or update a parameter
upsert_parameter() {
    local name="$1"
    local value="$2"
    local type="${3:-String}"

    local full_name="${PARAM_PREFIX}/${name}"

    aws ssm put-parameter \
        --name "${full_name}" \
        --value "${value}" \
        --type "${type}" \
        --overwrite \
        --region "${AWS_REGION}" >/dev/null 2>&1
    info "Set parameter: ${full_name} = ${value}"
}

# ─── Main ─────────────────────────────────────────────────────────────────────

echo "═══════════════════════════════════════════════════════════════"
echo "  LivestockGuard — Phase 2: Secrets & Configuration"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "  This script stores secrets in AWS Secrets Manager and"
echo "  configuration in SSM Parameter Store."
echo ""
echo "  Region: ${AWS_REGION}"
echo "  Secret prefix: ${SECRET_PREFIX}/"
echo "  Parameter prefix: ${PARAM_PREFIX}/"
echo ""

# Verify AWS access
aws sts get-caller-identity >/dev/null 2>&1 \
    || fail "AWS credentials not configured"
info "AWS credentials verified"
echo ""

# ─── Secrets Manager ──────────────────────────────────────────────────────────

echo "── Secrets Manager ─────────────────────────────────────────────"
echo ""

# 1. JWT Secret
echo "  1/5: JWT Signing Secret"
JWT_DEFAULT=$(openssl rand -hex 32 2>/dev/null || python3 -c "import secrets; print(secrets.token_hex(32))")
read_secret JWT_SECRET "Enter JWT secret (or press Enter for auto-generated)" "${JWT_DEFAULT}"
if [[ -n "${JWT_SECRET}" ]]; then
    upsert_secret "jwt-secret" "{\"value\":\"${JWT_SECRET}\"}" \
        "JWT signing key for API Gateway auth tokens"
fi
echo ""

# 2. Database credentials
echo "  2/5: PostgreSQL Database Credentials"
read_value DB_HOST "Database host (RDS endpoint)" "localhost"
read_value DB_PORT "Database port" "5432"
read_value DB_NAME "Database name" "livestockguard"
read_value DB_USER "Database username" "livestockguard"
read_secret DB_PASS "Database password" "livestockguard_dev"
if [[ -n "${DB_HOST}" ]]; then
    upsert_secret "postgres" \
        "{\"host\":\"${DB_HOST}\",\"port\":${DB_PORT},\"dbname\":\"${DB_NAME}\",\"username\":\"${DB_USER}\",\"password\":\"${DB_PASS}\"}" \
        "PostgreSQL connection credentials"
fi
echo ""

# 3. Firebase credentials
echo "  3/5: Firebase Cloud Messaging"
read_value FIREBASE_FILE "Path to Firebase service account JSON (or 'skip')" "skip"
if [[ "${FIREBASE_FILE}" != "skip" && -f "${FIREBASE_FILE}" ]]; then
    FIREBASE_JSON=$(cat "${FIREBASE_FILE}")
    upsert_secret "firebase-credentials" "${FIREBASE_JSON}" \
        "Firebase Admin SDK service account for push notifications"
else
    warn "Firebase credentials skipped — push notifications won't work until configured"
fi
echo ""

# 4. Africa's Talking credentials
echo "  4/5: Africa's Talking SMS"
read_value AT_USERNAME "Africa's Talking username (or 'skip')" "skip"
if [[ "${AT_USERNAME}" != "skip" ]]; then
    read_secret AT_API_KEY "Africa's Talking API key" ""
    read_value AT_SENDER "Sender ID" "LGGUARD"
    if [[ -n "${AT_API_KEY}" ]]; then
        upsert_secret "africastalking" \
            "{\"api_key\":\"${AT_API_KEY}\",\"username\":\"${AT_USERNAME}\",\"sender_id\":\"${AT_SENDER}\"}" \
            "Africa's Talking SMS gateway credentials"
    fi
else
    warn "Africa's Talking skipped — SMS alerts won't work until configured"
fi
echo ""

# 5. Webhook URLs
echo "  5/5: Webhook URLs"
read_value WEBHOOK_URLS "Webhook URLs (comma-separated, or 'skip')" "skip"
if [[ "${WEBHOOK_URLS}" != "skip" && -n "${WEBHOOK_URLS}" ]]; then
    # Convert comma-separated to JSON array
    WEBHOOK_JSON=$(echo "${WEBHOOK_URLS}" | python3 -c "
import sys, json
urls = [u.strip() for u in sys.stdin.read().split(',') if u.strip()]
print(json.dumps({'urls': urls}))
")
    upsert_secret "webhooks" "${WEBHOOK_JSON}" \
        "External webhook URLs for alert notifications"
else
    warn "Webhook URLs skipped"
fi
echo ""

# ─── Parameter Store ──────────────────────────────────────────────────────────

echo "── Parameter Store (Configuration) ─────────────────────────────"
echo ""

read_value SES_SENDER "SES sender email" "alerts@livestockguard.co.za"
read_value EMAIL_RECIPIENTS "Alert email recipients (comma-separated)" ""
read_value SMS_RECIPIENTS "Alert SMS recipients (E.164, comma-separated)" ""
read_value ALERT_COOLDOWN "Alert cooldown seconds" "300"
read_value REDIS_URL "Redis URL (for ElastiCache in prod)" "redis://localhost:6379/0"
read_value MQTT_BROKER "MQTT broker host" "localhost"
read_value MQTT_PORT "MQTT broker port" "1883"

echo ""
upsert_parameter "ses-sender-email" "${SES_SENDER}"
upsert_parameter "aws-region" "${AWS_REGION}"
[[ -n "${EMAIL_RECIPIENTS}" ]] && upsert_parameter "email-recipients" "${EMAIL_RECIPIENTS}"
[[ -n "${SMS_RECIPIENTS}" ]] && upsert_parameter "sms-recipients" "${SMS_RECIPIENTS}"
upsert_parameter "alert-cooldown-seconds" "${ALERT_COOLDOWN}"
upsert_parameter "redis-url" "${REDIS_URL}"
upsert_parameter "mqtt-broker" "${MQTT_BROKER}"
upsert_parameter "mqtt-port" "${MQTT_PORT}"

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  Phase 2 Complete!"
echo ""
echo "  Stored:"
echo "    • Secrets Manager: jwt-secret, postgres, firebase, africastalking, webhooks"
echo "    • Parameter Store: ses-sender, region, recipients, cooldown, redis, mqtt"
echo ""
echo "  Next steps:"
echo "    1. Run: ./cloud9-bootstrap.sh  (Phase 3)"
echo "    2. Or proceed to Phase 8 code integration"
echo "═══════════════════════════════════════════════════════════════"
