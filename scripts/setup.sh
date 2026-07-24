#!/bin/bash
# LivestockGuard — First-time development setup
# Run: make setup (or bash scripts/setup.sh)

set -e

GREEN='\033[32m'
YELLOW='\033[33m'
CYAN='\033[36m'
RED='\033[31m'
RESET='\033[0m'

echo -e "${CYAN}"
echo "╔══════════════════════════════════════════╗"
echo "║   LivestockGuard Development Setup       ║"
echo "╚══════════════════════════════════════════╝"
echo -e "${RESET}"

# ─── Check Prerequisites ─────────────────────────────

echo -e "${CYAN}Checking prerequisites...${RESET}"

check_cmd() {
    if command -v "$1" &> /dev/null; then
        echo -e "  ✅ $1 $(command -v $1)"
    else
        echo -e "  ${RED}❌ $1 not found${RESET}"
        MISSING+=("$1")
    fi
}

MISSING=()

check_cmd docker
check_cmd docker
check_cmd node
check_cmd npm
check_cmd python3
check_cmd pip3
check_cmd git

echo ""

if [ ${#MISSING[@]} -ne 0 ]; then
    echo -e "${RED}Missing prerequisites: ${MISSING[*]}${RESET}"
    echo ""
    echo "Install them:"
    echo "  brew install docker node python3 git   (macOS with Homebrew)"
    echo "  Docker Desktop: https://www.docker.com/products/docker-desktop/"
    echo ""
    exit 1
fi

# Check Docker is running
if ! docker info &> /dev/null; then
    echo -e "${RED}Docker is installed but not running. Please start Docker Desktop.${RESET}"
    exit 1
fi
echo -e "  ✅ Docker daemon running"
echo ""

# ─── Setup Python Environment ─────────────────────────

echo -e "${CYAN}Setting up Python environment...${RESET}"

if [ ! -d "tools/simulator/.venv" ]; then
    python3 -m venv tools/simulator/.venv
    echo "  Created virtual environment"
fi

source tools/simulator/.venv/bin/activate
pip install -q -r tools/simulator/requirements.txt
echo -e "  ✅ Python dependencies installed"
echo ""

# ─── Setup Dashboard ──────────────────────────────────

echo -e "${CYAN}Setting up dashboard...${RESET}"

cd dashboard
if [ ! -d "node_modules" ]; then
    npm install --silent
    echo -e "  ✅ Node modules installed"
else
    echo -e "  ✅ Node modules already present"
fi
cd ..
echo ""

# ─── Start Cloud Stack ────────────────────────────────

echo -e "${CYAN}Starting cloud stack (Docker Compose)...${RESET}"

cd cloud
docker compose up -d --quiet-pull 2>/dev/null || docker-compose up -d --quiet-pull
cd ..

echo -e "  ✅ PostgreSQL + TimescaleDB running (port 5432)"
echo -e "  ✅ Redis running (port 6379)"
echo -e "  ✅ EMQX MQTT broker running (port 1883)"
echo ""

# ─── Wait for PostgreSQL ──────────────────────────────

echo -e "${CYAN}Waiting for PostgreSQL to be ready...${RESET}"
for i in {1..30}; do
    if docker compose -f cloud/docker-compose.yml exec -T postgres pg_isready -U livestockguard &> /dev/null; then
        echo -e "  ✅ PostgreSQL ready"
        break
    fi
    sleep 1
done
echo ""

# ─── Run Migrations ───────────────────────────────────

echo -e "${CYAN}Running database migrations...${RESET}"
docker compose -f cloud/docker-compose.yml exec -T postgres \
    psql -U livestockguard -d livestockguard \
    -f /dev/stdin < cloud/migrations/versions/001_initial_schema.sql 2>/dev/null && \
    echo -e "  ✅ Schema created" || \
    echo -e "  ${YELLOW}⚠️  Schema may already exist (that's OK)${RESET}"
echo ""

# ─── Create .env file ─────────────────────────────────

if [ ! -f ".env" ]; then
    cat > .env << 'EOF'
# LivestockGuard Development Environment
DATABASE_URL=postgresql+asyncpg://livestockguard:dev_password@localhost:5432/livestockguard
REDIS_URL=redis://localhost:6379
MQTT_BROKER=localhost
MQTT_PORT=1883
SECRET_KEY=dev-secret-key-change-in-production
ENVIRONMENT=development
EOF
    echo -e "  ✅ Created .env file"
else
    echo -e "  ✅ .env already exists"
fi
echo ""

# ─── Done ─────────────────────────────────────────────

echo -e "${GREEN}"
echo "╔══════════════════════════════════════════╗"
echo "║   Setup Complete! 🎉                     ║"
echo "╠══════════════════════════════════════════╣"
echo "║                                          ║"
echo "║   Start developing:                      ║"
echo "║                                          ║"
echo "║   Terminal 1:  make start                ║"
echo "║   Terminal 2:  make dashboard            ║"
echo "║   Terminal 3:  make simulate             ║"
echo "║                                          ║"
echo "║   Then open: http://localhost:3000       ║"
echo "║                                          ║"
echo "║   Other commands: make help              ║"
echo "║                                          ║"
echo "╚══════════════════════════════════════════╝"
echo -e "${RESET}"
