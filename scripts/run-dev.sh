#!/usr/bin/env bash
#
# LivestockGuard — Development Mode (No Simulators)
#
# Starts the platform for real development or real hardware:
#   1. Docker cloud stack (Postgres, Redis, EMQX, API, MQTT Writer, Alert Engine)
#   2. Database migrations
#   3. Web Dashboard (http://localhost:5173)
#   4. Mobile App — web mode (http://localhost:8082)
#
# NO simulators are started — use this when:
#   - Working on frontend/backend code
#   - Connected to real GPS collars / BLE gateways
#   - You only need the infrastructure running
#
# Usage:
#   bash scripts/run-dev.sh              # Backend + Dashboard + Mobile
#   bash scripts/run-dev.sh --no-mobile  # Backend + Dashboard only
#   bash scripts/run-dev.sh --backend    # Backend only (no frontends)
#
# Stop: Ctrl+C (gracefully kills all processes)

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$ROOT_DIR"

# ─── Parse Arguments ──────────────────────────────────────────────────────────

SKIP_MOBILE=false
BACKEND_ONLY=false

for arg in "$@"; do
  case "$arg" in
    --no-mobile) SKIP_MOBILE=true ;;
    --backend) BACKEND_ONLY=true ;;
    --help|-h)
      echo "Usage: bash scripts/run-dev.sh [--no-mobile] [--backend]"
      echo "  (no flags)   Backend + Dashboard (:5173) + Mobile (:8082)"
      echo "  --no-mobile  Backend + Dashboard only"
      echo "  --backend    Backend infrastructure only (no frontends)"
      exit 0
      ;;
  esac
done

# ─── Colours & Logging ────────────────────────────────────────────────────────

GREEN='\033[32m'
YELLOW='\033[33m'
CYAN='\033[36m'
RED='\033[31m'
BOLD='\033[1m'
DIM='\033[2m'
RESET='\033[0m'

mkdir -p "$ROOT_DIR/logs"
LOG_FILE="$ROOT_DIR/logs/dev.log"
: > "$LOG_FILE"

START_TIME=$(date +%s)

log() {
  local timestamp
  timestamp="$(date '+%Y-%m-%d %H:%M:%S')"
  echo "[$timestamp] $*" >> "$LOG_FILE"
}

# ─── Cleanup on Exit ──────────────────────────────────────────────────────────

PIDS=()

cleanup() {
  echo ""
  echo -e "${YELLOW}Shutting down...${RESET}"
  log "SHUTDOWN initiated"
  for pid in "${PIDS[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
  kill $(jobs -p) 2>/dev/null || true
  local elapsed=$(( $(date +%s) - START_TIME ))
  echo -e "  ${GREEN}Stopped.${RESET} Runtime: ${elapsed}s"
  echo -e "  ${DIM}Docker stack still running (use 'make stop' to stop).${RESET}"
  exit 0
}
trap cleanup SIGINT SIGTERM

# ─── Header ──────────────────────────────────────────────────────────────────

echo -e "${BOLD}${CYAN}"
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  LivestockGuard — Development Mode                          ║"
echo "║  Backend + Frontends (no simulators)                        ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo -e "${RESET}"

log "DEV MODE started | mobile=$([ "$SKIP_MOBILE" = true ] && echo off || echo on) | backend_only=$BACKEND_ONLY"

# ─── 1. Docker Cloud Stack ────────────────────────────────────────────────────

echo -e "${CYAN}[1/4] Starting cloud infrastructure...${RESET}"

if ! docker info > /dev/null 2>&1; then
  echo -e "  ${RED}Docker daemon not running. Start Docker Desktop first.${RESET}"
  exit 1
fi

cd cloud
docker compose up -d --build >> "$LOG_FILE" 2>&1
cd "$ROOT_DIR"

echo -e "  ${GREEN}✅${RESET} Docker stack running"
echo -e "  ${DIM}→ API Gateway:  http://localhost:8000/docs${RESET}"
echo -e "  ${DIM}→ PostgreSQL:   localhost:5432${RESET}"
echo -e "  ${DIM}→ Redis:        localhost:6379${RESET}"
echo -e "  ${DIM}→ MQTT Broker:  localhost:1883${RESET}"
echo -e "  ${DIM}→ EMQX Console: http://localhost:18083 (admin/public)${RESET}"

# ─── 2. Migrations ────────────────────────────────────────────────────────────

echo -e "${CYAN}[2/4] Applying database migrations...${RESET}"

cd cloud
for f in migrations/versions/*.sql; do
  docker compose exec -T postgres psql -U livestockguard -d livestockguard < "$f" >> "$LOG_FILE" 2>&1 || true
done
cd "$ROOT_DIR"

echo -e "  ${GREEN}✅${RESET} Migrations applied"

# ─── 3. Wait for API ─────────────────────────────────────────────────────────

echo -e "${CYAN}[3/4] Waiting for API Gateway...${RESET}"

for i in {1..20}; do
  if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
    echo -e "  ${GREEN}✅${RESET} API healthy (http://localhost:8000)"
    break
  fi
  if [ "$i" -eq 20 ]; then
    echo -e "  ${YELLOW}⚠️  API not responding yet — may still be starting${RESET}"
  fi
  sleep 1
done

if [ "$BACKEND_ONLY" = true ]; then
  echo ""
  echo -e "${GREEN}Backend running. Connect real devices or start simulators manually:${RESET}"
  echo -e "  ${DIM}make simulate        # GPS simulator (Boschhoek)${RESET}"
  echo -e "  ${DIM}make simulate-gateway # BLE gateway (Loch Vaal)${RESET}"
  echo ""
  echo -e "${DIM}Ctrl+C to stop. Log: $LOG_FILE${RESET}"
  wait
  exit 0
fi

# ─── 4. Frontends ─────────────────────────────────────────────────────────────

echo -e "${CYAN}[4/4] Starting frontends...${RESET}"

# Dashboard
if lsof -ti :5173 > /dev/null 2>&1; then
  lsof -ti :5173 | xargs kill -9 2>/dev/null || true
  sleep 1
fi

cd dashboard
npm install --silent >> "$LOG_FILE" 2>&1
npx vite --port 5173 --host >> "$LOG_FILE" 2>&1 &
PIDS+=($!)
cd "$ROOT_DIR"

sleep 3
if lsof -i :5173 > /dev/null 2>&1; then
  echo -e "  ${GREEN}✅${RESET} Dashboard: http://localhost:5173"
else
  echo -e "  ${YELLOW}⚠️${RESET}  Dashboard starting... (check logs/dev.log)"
fi

# Mobile (web mode)
if [ "$SKIP_MOBILE" = false ]; then
  if lsof -ti :8082 > /dev/null 2>&1; then
    lsof -ti :8082 | xargs kill -9 2>/dev/null || true
    sleep 1
  fi

  cd mobile
  npm install --silent >> "$LOG_FILE" 2>&1
  CI=1 npx expo start --web --port 8082 >> "$LOG_FILE" 2>&1 &
  PIDS+=($!)
  cd "$ROOT_DIR"

  sleep 8
  if lsof -i :8082 > /dev/null 2>&1; then
    echo -e "  ${GREEN}✅${RESET} Mobile app: http://localhost:8082"
  else
    echo -e "  ${YELLOW}⚠️${RESET}  Mobile starting... (check logs/dev.log)"
  fi
fi

# ─── Summary ──────────────────────────────────────────────────────────────────

ELAPSED=$(( $(date +%s) - START_TIME ))

echo ""
echo -e "${BOLD}${GREEN}╔══════════════════════════════════════════════════════════════╗${RESET}"
echo -e "${BOLD}${GREEN}║  ✅ Development environment ready (${ELAPSED}s)                      ║${RESET}"
echo -e "${BOLD}${GREEN}╠══════════════════════════════════════════════════════════════╣${RESET}"
echo -e "${GREEN}║                                                              ║${RESET}"
echo -e "${GREEN}║  Dashboard:   http://localhost:5173                           ║${RESET}"
if [ "$SKIP_MOBILE" = false ]; then
echo -e "${GREEN}║  Mobile App:  http://localhost:8082                           ║${RESET}"
fi
echo -e "${GREEN}║  API Docs:    http://localhost:8000/docs                      ║${RESET}"
echo -e "${GREEN}║  EMQX:        http://localhost:18083                          ║${RESET}"
echo -e "${GREEN}║                                                              ║${RESET}"
echo -e "${GREEN}║  No simulators running. To add them:                         ║${RESET}"
echo -e "${GREEN}║    make simulate          # GPS (Boschhoek, 5 cows)          ║${RESET}"
echo -e "${GREEN}║    make simulate-gateway  # BLE (Loch Vaal, 10 cows)         ║${RESET}"
echo -e "${GREEN}║    make demo              # Or run full demo with sims        ║${RESET}"
echo -e "${GREEN}║                                                              ║${RESET}"
echo -e "${GREEN}║  Login: africa.mydrive@gmail.com / demo123                   ║${RESET}"
echo -e "${GREEN}║  Stop: Ctrl+C | Log: logs/dev.log                            ║${RESET}"
echo -e "${GREEN}║                                                              ║${RESET}"
echo -e "${BOLD}${GREEN}╚══════════════════════════════════════════════════════════════╝${RESET}"
echo ""

wait
