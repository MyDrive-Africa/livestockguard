#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# LivestockGuard — Phase 3: Cloud9 Development Environment Bootstrap
#
# Sets up a Cloud9 EC2 instance with all required toolchain:
#   - Rust stable (for ingestion + geofence_engine)
#   - Node.js 20 LTS (for dashboard + mobile)
#   - Python 3.12 (for backend services + simulators)
#   - Docker + Compose (for infrastructure containers)
#   - Disk resize (Cloud9 default 10 GB → 30 GB)
#
# Run this INSIDE the Cloud9 environment after:
#   1. Cloud9 instance is created (t3.medium, Amazon Linux 2023)
#   2. IAM instance profile attached (LivestockGuardCloud9)
#   3. Cloud9 managed credentials DISABLED
#
# Usage:
#   chmod +x cloud9-bootstrap.sh
#   ./cloud9-bootstrap.sh
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

# ─── Configuration ────────────────────────────────────────────────────────────

NODE_VERSION="20"
PYTHON_VERSION="3.12"
DISK_SIZE_GB=30
REPO_URL="${REPO_URL:-https://github.com/your-org/livestockguard.git}"
PROJECT_DIR="${HOME}/livestockguard"

# ─── Helpers ──────────────────────────────────────────────────────────────────

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info() { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
fail() { echo -e "${RED}[✗]${NC} $1"; exit 1; }
step() { echo -e "\n── $1 ──────────────────────────────────────────────────────"; }

# ─── Step 1: Resize Disk ──────────────────────────────────────────────────────

resize_disk() {
    step "Step 1: Resize EBS Volume to ${DISK_SIZE_GB} GB"

    CURRENT_SIZE=$(df -BG / | awk 'NR==2 {print $2}' | tr -d 'G')
    if (( CURRENT_SIZE >= DISK_SIZE_GB - 2 )); then
        info "Disk already ${CURRENT_SIZE} GB — skipping resize"
        return
    fi

    # Get instance ID and volume ID
    INSTANCE_ID=$(curl -s http://169.254.169.254/latest/meta-data/instance-id)
    REGION=$(curl -s http://169.254.169.254/latest/meta-data/placement/region)
    VOLUME_ID=$(aws ec2 describe-instances \
        --instance-id "${INSTANCE_ID}" \
        --region "${REGION}" \
        --query 'Reservations[0].Instances[0].BlockDeviceMappings[0].Ebs.VolumeId' \
        --output text)

    info "Instance: ${INSTANCE_ID}, Volume: ${VOLUME_ID}, Region: ${REGION}"

    # Modify volume size
    aws ec2 modify-volume \
        --volume-id "${VOLUME_ID}" \
        --size "${DISK_SIZE_GB}" \
        --region "${REGION}" >/dev/null 2>&1 \
        || warn "Volume modification may already be in progress"

    # Wait for volume modification
    echo "  Waiting for volume resize to complete..."
    sleep 10

    # Grow the partition and filesystem
    DEVICE=$(lsblk -npo PKNAME $(findmnt -n -o SOURCE /) 2>/dev/null || echo "/dev/xvda")
    PARTITION=$(findmnt -n -o SOURCE /)

    if command -v growpart >/dev/null 2>&1; then
        sudo growpart "${DEVICE}" 1 2>/dev/null || true
    fi

    if [[ $(df -T / | awk 'NR==2 {print $2}') == "xfs" ]]; then
        sudo xfs_growfs / 2>/dev/null || true
    else
        sudo resize2fs "${PARTITION}" 2>/dev/null || true
    fi

    NEW_SIZE=$(df -BG / | awk 'NR==2 {print $2}' | tr -d 'G')
    info "Disk resized: ${CURRENT_SIZE} GB → ${NEW_SIZE} GB"
}

# ─── Step 2: Install Rust ─────────────────────────────────────────────────────

install_rust() {
    step "Step 2: Install Rust Stable"

    if command -v cargo >/dev/null 2>&1; then
        RUST_VER=$(rustc --version)
        info "Rust already installed: ${RUST_VER}"
        rustup update stable 2>/dev/null || true
        return
    fi

    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
    source "${HOME}/.cargo/env"

    info "Rust installed: $(rustc --version)"
}

# ─── Step 3: Install Node.js ──────────────────────────────────────────────────

install_node() {
    step "Step 3: Install Node.js ${NODE_VERSION} LTS"

    # Use nvm (typically pre-installed on Cloud9)
    export NVM_DIR="${HOME}/.nvm"
    if [[ -s "${NVM_DIR}/nvm.sh" ]]; then
        source "${NVM_DIR}/nvm.sh"
    elif command -v nvm >/dev/null 2>&1; then
        : # nvm already available
    else
        # Install nvm
        curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
        source "${NVM_DIR}/nvm.sh"
    fi

    nvm install "${NODE_VERSION}"
    nvm use "${NODE_VERSION}"
    nvm alias default "${NODE_VERSION}"

    info "Node.js installed: $(node --version)"
    info "npm installed: $(npm --version)"
}

# ─── Step 4: Install Python 3.12 ──────────────────────────────────────────────

install_python() {
    step "Step 4: Install Python ${PYTHON_VERSION}"

    if python3 --version 2>&1 | grep -q "${PYTHON_VERSION}"; then
        info "Python ${PYTHON_VERSION} already installed"
        return
    fi

    # Amazon Linux 2023
    if command -v dnf >/dev/null 2>&1; then
        sudo dnf install -y "python${PYTHON_VERSION}" "python${PYTHON_VERSION}-pip" \
            "python${PYTHON_VERSION}-devel" 2>/dev/null || true
        sudo alternatives --set python3 "/usr/bin/python${PYTHON_VERSION}" 2>/dev/null || true
    # Amazon Linux 2 / older
    elif command -v yum >/dev/null 2>&1; then
        sudo amazon-linux-extras install -y "python${PYTHON_VERSION}" 2>/dev/null || true
    fi

    info "Python installed: $(python3 --version)"
    info "pip installed: $(pip3 --version 2>/dev/null || echo 'not found')"
}

# ─── Step 5: Install Docker & Compose ─────────────────────────────────────────

install_docker() {
    step "Step 5: Docker & Docker Compose"

    if command -v docker >/dev/null 2>&1; then
        info "Docker already installed: $(docker --version)"
    else
        if command -v dnf >/dev/null 2>&1; then
            sudo dnf install -y docker
        else
            sudo yum install -y docker
        fi
    fi

    # Start and enable Docker
    sudo systemctl start docker 2>/dev/null || true
    sudo systemctl enable docker 2>/dev/null || true

    # Add current user to docker group (avoids sudo for docker commands)
    sudo usermod -aG docker "${USER}" 2>/dev/null || true

    # Docker Compose plugin
    if ! docker compose version >/dev/null 2>&1; then
        if command -v dnf >/dev/null 2>&1; then
            sudo dnf install -y docker-compose-plugin 2>/dev/null || true
        else
            # Manual install
            COMPOSE_VERSION="v2.24.6"
            sudo mkdir -p /usr/local/lib/docker/cli-plugins
            sudo curl -SL "https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}/docker-compose-linux-x86_64" \
                -o /usr/local/lib/docker/cli-plugins/docker-compose
            sudo chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
        fi
    fi

    info "Docker: $(docker --version 2>/dev/null || echo 'installed')"
    info "Compose: $(docker compose version 2>/dev/null || echo 'installed')"
    warn "You may need to log out and back in for docker group to take effect"
}

# ─── Step 6: Install Additional Tools ─────────────────────────────────────────

install_extras() {
    step "Step 6: Additional Tools"

    # Git (usually pre-installed)
    if ! command -v git >/dev/null 2>&1; then
        sudo dnf install -y git 2>/dev/null || sudo yum install -y git
    fi
    info "Git: $(git --version)"

    # jq for JSON processing
    if ! command -v jq >/dev/null 2>&1; then
        sudo dnf install -y jq 2>/dev/null || sudo yum install -y jq
    fi
    info "jq: $(jq --version 2>/dev/null || echo 'installed')"

    # Make
    if ! command -v make >/dev/null 2>&1; then
        sudo dnf install -y make 2>/dev/null || sudo yum install -y make
    fi
    info "make: $(make --version | head -1)"
}

# ─── Step 7: Verify IAM Role ──────────────────────────────────────────────────

verify_iam() {
    step "Step 7: Verify IAM Credentials"

    IDENTITY=$(aws sts get-caller-identity --output json 2>/dev/null) || \
        fail "AWS credentials not available. Did you:\n  1. Attach LivestockGuardCloud9 instance profile?\n  2. Disable Cloud9 managed credentials?"

    ROLE_ARN=$(echo "${IDENTITY}" | python3 -c "import sys, json; print(json.load(sys.stdin)['Arn'])")
    info "IAM identity: ${ROLE_ARN}"

    # Quick check: can we read from Parameter Store?
    aws ssm get-parameter --name "/livestockguard/aws-region" \
        --region af-south-1 >/dev/null 2>&1 \
        && info "SSM Parameter Store access: OK" \
        || warn "SSM access failed — run setup-secrets.sh first or check IAM policy"

    # Quick check: SES access
    aws ses get-send-quota --region af-south-1 >/dev/null 2>&1 \
        && info "SES access: OK" \
        || warn "SES access failed — check IAM policy"
}

# ─── Step 8: Clone & Setup Project ────────────────────────────────────────────

setup_project() {
    step "Step 8: Clone & Setup LivestockGuard"

    if [[ -d "${PROJECT_DIR}" ]]; then
        info "Project directory exists: ${PROJECT_DIR}"
        cd "${PROJECT_DIR}"
        git pull origin main 2>/dev/null || warn "Git pull failed (maybe uncommitted changes)"
    else
        git clone "${REPO_URL}" "${PROJECT_DIR}" 2>/dev/null || \
            fail "Clone failed. Set REPO_URL env var to your repo URL."
        cd "${PROJECT_DIR}"
        info "Cloned repo to ${PROJECT_DIR}"
    fi

    # Generate Cargo.lock files if missing
    if [[ ! -f "cloud/services/ingestion/Cargo.lock" ]]; then
        cd cloud/services/ingestion && cargo generate-lockfile && cd -
        info "Generated Cargo.lock for ingestion service"
    fi
    if [[ ! -f "cloud/services/geofence_engine/Cargo.lock" ]]; then
        cd cloud/services/geofence_engine && cargo generate-lockfile && cd -
        info "Generated Cargo.lock for geofence_engine service"
    fi

    # Run project setup (Docker + migrations + seeds)
    # Use newgrp to pick up docker group without re-login
    sg docker -c "make setup" 2>/dev/null || \
        warn "make setup may require docker group. Try: newgrp docker && make setup"

    # Frontend setup (web only — no native mobile on Cloud9)
    make setup-frontend --web 2>/dev/null || \
        warn "Frontend setup may need manual intervention"
}

# ─── Summary ──────────────────────────────────────────────────────────────────

summary() {
    echo ""
    echo "═══════════════════════════════════════════════════════════════"
    echo "  Phase 3 Complete! Cloud9 Environment Ready."
    echo "═══════════════════════════════════════════════════════════════"
    echo ""
    echo "  Installed:"
    echo "    • Rust:   $(rustc --version 2>/dev/null || echo 'check PATH')"
    echo "    • Node:   $(node --version 2>/dev/null || echo 'check nvm')"
    echo "    • Python: $(python3 --version 2>/dev/null || echo 'not found')"
    echo "    • Docker: $(docker --version 2>/dev/null || echo 'check service')"
    echo "    • Disk:   $(df -BG / | awk 'NR==2 {print $2}') available"
    echo ""
    echo "  Quick start:"
    echo "    cd ${PROJECT_DIR}"
    echo "    make start          # Start Docker stack"
    echo "    make demo           # Full demo with simulators"
    echo "    make test           # Run all tests"
    echo ""
    echo "  For Kiro IDE access (Remote-SSH):"
    echo "    See docs/AWS_CLOUD9_DEPLOYMENT_PLAN.md Phase 4"
    echo ""
    echo "  Next steps:"
    echo "    Phase 5: make start && make db-seed && make dashboard"
    echo "    Phase 6: make demo (simulators)"
    echo "    Phase 7: make test"
    echo "═══════════════════════════════════════════════════════════════"
}

# ─── Main ─────────────────────────────────────────────────────────────────────

echo "═══════════════════════════════════════════════════════════════"
echo "  LivestockGuard — Phase 3: Cloud9 Bootstrap"
echo "═══════════════════════════════════════════════════════════════"
echo ""

resize_disk
install_rust
install_node
install_python
install_docker
install_extras
verify_iam
setup_project
summary
