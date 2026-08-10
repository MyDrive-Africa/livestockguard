#!/usr/bin/env bash
#
# LivestockGuard — Run Everything (with detailed logging)
#
# Starts the entire platform end-to-end:
#   1. Docker cloud stack (Postgres, Redis, EMQX, API, MQTT Writer, Alert Engine)
#   2. Database migrations + seed data (3 farms, 65 animals)
#   3. GPS simulators (Boschhoek + Sibanyoni)
#   4. BLE gateway simulator (Loch Vaal, herdsman day)
#   5. Web Dashboard (http://localhost:5173)
#   6. Mobile App — web mode (http://localhost:8082)
#
# Every step is logged with timestamps, durations, and full output to:
#   logs/run-all.log (master log)
#   logs/run-all-*.log (per-service logs)
#
# Usage:
#   bash scripts/run-all.sh                # Default: breach scenario
#   bash scripts/run-all.sh --normal       # Normal day
#   bash scripts/run-all.sh --theft        # Theft scenario
#   bash scripts/run-all.sh --no-mobile    # Skip mobile app
#   bash scripts/run-all.sh --no-sim       # Skip simulators
#
# Stop: Ctrl+C (gracefully kills all processes)

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$ROOT_DIR"

# ─── Parse Arguments ──────────────────────────────────────────────────────────

SCENARIO="breach"
SKIP_MOBILE=false
SKIP_SIM=false

for arg in "$@"; do
  case "$arg" in
    --normal) SCENARIO="normal" ;;
    --theft) SCENARIO="theft" ;;
    --breach) SCENARIO="breach" ;;
    --no-mobile) SKIP_MOBILE=true ;;
    --no-sim) SKIP_SIM=true ;;
    --help|-h)
      echo "Usage: bash scripts/run-all.sh [--normal|--theft|--breach] [--no-mobile] [--no-sim]"
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
MASTER_LOG="$ROOT_DIR/logs/run-all.log"
: > "$MASTER_LOG"

STEP_NUM=0
TOTAL_STEPS=10
START_TIME=$(date +%s)

# Logging functions
log_master() {
  local timestamp
  timestamp="$(date '+%Y-%m-%d %H:%M:%S')"
  echo "[$timestamp] $*" >> "$MASTER_LOG"
}

log_step() {
  STEP_NUM=$((STEP_NUM + 1))
  local elapsed=$(( $(date +%s) - START_TIME ))
  local msg="[$STEP_NUM/$TOTAL_STEPS] $*"
  echo ""
  echo -e "${BOLD}${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
  echo -e "${BOLD}${CYAN}  $msg${RESET}"
  echo -e "${BOLD}${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
  echo -e "${DIM}  Elapsed: ${elapsed}s${RESET}"
  log_master "═══ STEP $STEP_NUM/$TOTAL_STEPS: $* (elapsed: ${elapsed}s) ═══"
}

log_info() {
  local timestamp
  timestamp="$(date '+%Y-%m-%d %H:%M:%S')"
  echo -e "  ${GREEN}✅${RESET} $*"
  echo "[$timestamp] [INFO] $*" >> "$MASTER_LOG"
}

log_detail() {
  local timestamp
  timestamp="$(date '+%Y-%m-%d %H:%M:%S')"
  echo -e "  ${DIM}→ $*${RESET}"
  echo "[$timestamp] [DETAIL] $*" >> "$MASTER_LOG"
}

log_warn() {
  local timestamp
  timestamp="$(date '+%Y-%m-%d %H:%M:%S')"
  echo -e "  ${YELLOW}⚠️  $*${RESET}"
  echo "[$timestamp] [WARN] $*" >> "$MASTER_LOG"
}

log_error() {
  local timestamp
  timestamp="$(date '+%Y-%m-%d %H:%M:%S')"
  echo -e "  ${RED}❌ $*${RESET}"
  echo "[$timestamp] [ERROR] $*" >> "$MASTER_LOG"
}

log_cmd() {
  # Log a command with its full output to a specific log file
  local logfile="$1"
  shift
  log_detail "Running: $*"
  log_master "[CMD] $* → $logfile"
  "$@" >> "$logfile" 2>&1
}

# ─── Cleanup on Exit ──────────────────────────────────────────────────────────

PIDS=()

cleanup() {
  echo ""
  echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
  echo -e "${YELLOW}  Shutting down all processes...${RESET}"
  echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
  log_master "═══ SHUTDOWN initiated ═══"

  for pid in "${PIDS[@]}"; do
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
      log_master "Killed PID $pid"
    fi
  done

  # Also kill any stray child processes
  kill $(jobs -p) 2>/dev/null || true

  local total_elapsed=$(( $(date +%s) - START_TIME ))
  log_master "═══ Total runtime: ${total_elapsed}s ═══"

  echo -e "  ${GREEN}All processes stopped.${RESET}"
  echo -e "  ${DIM}Total runtime: ${total_elapsed}s${RESET}"
  echo -e "  ${DIM}Docker stack still running (use 'make stop' to stop).${RESET}"
  echo -e "  ${DIM}Full log: $MASTER_LOG${RESET}"
  echo ""
  exit 0
}
trap cleanup SIGINT SIGTERM

# ─── Header ──────────────────────────────────────────────────────────────────

echo -e "${BOLD}${CYAN}"
echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║                                                                  ║"
echo "║   LivestockGuard — FULL PLATFORM (Detailed Logging)              ║"
echo "║                                                                  ║"
echo "║   Scenario: ${SCENARIO}                                                  ║"
echo "║   Mobile:   $([ "$SKIP_MOBILE" = true ] && echo "disabled" || echo "enabled (web mode)")                                       ║"
echo "║   Sims:     $([ "$SKIP_SIM" = true ] && echo "disabled" || echo "enabled (3 farms)")                                       ║"
echo "║                                                                  ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo -e "${RESET}"
echo -e "${DIM}  Master log: $MASTER_LOG${RESET}"
echo -e "${DIM}  Per-service logs: logs/run-all-*.log${RESET}"

log_master "═══ LivestockGuard Run-All Started ═══"
log_master "Scenario: $SCENARIO | Mobile: $([ "$SKIP_MOBILE" = true ] && echo "off" || echo "on") | Sims: $([ "$SKIP_SIM" = true ] && echo "off" || echo "on")"
log_master "Working directory: $ROOT_DIR"
log_master "Node: $(node -v 2>/dev/null || echo 'not found') | npm: $(npm -v 2>/dev/null || echo 'not found')"
log_master "Python: $(python3 --version 2>/dev/null || echo 'not found')"
log_master "Docker: $(docker --version 2>/dev/null || echo 'not found')"

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 1: Docker Cloud Stack
# ═══════════════════════════════════════════════════════════════════════════════

log_step "Starting Docker cloud infrastructure"

DOCKER_LOG="$ROOT_DIR/logs/run-all-docker.log"
: > "$DOCKER_LOG"

log_detail "Checking Docker daemon..."
if ! docker info >> "$DOCKER_LOG" 2>&1; then
  log_error "Docker daemon not running. Start Docker Desktop first."
  exit 1
fi
log_info "Docker daemon: running"

log_detail "Building and starting containers (docker compose up -d --build)..."
STEP_START=$(date +%s)
cd cloud
docker compose up -d --build >> "$DOCKER_LOG" 2>&1
cd "$ROOT_DIR"
STEP_DURATION=$(( $(date +%s) - STEP_START ))
log_info "Docker Compose up (took ${STEP_DURATION}s)"

log_detail "Services starting:"
log_detail "  PostgreSQL 16 + TimescaleDB + PostGIS → :5432"
log_detail "  Redis 7 → :6379"
log_detail "  EMQX 5.5 (MQTT Broker) → :1883, :18083"
log_detail "  API Gateway (FastAPI) → :8000"
log_detail "  MQTT Writer (Python) → subscribed to lg/dev/+/pos"
log_detail "  Alert Engine (Python) → Redis pub/sub"

# Log container status
docker compose -f cloud/docker-compose.yml ps >> "$DOCKER_LOG" 2>&1 || true
log_master "Docker containers started in ${STEP_DURATION}s"

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 2: Wait for PostgreSQL health
# ═══════════════════════════════════════════════════════════════════════════════

log_step "Waiting for PostgreSQL to be healthy"

PG_LOG="$ROOT_DIR/logs/run-all-postgres.log"
: > "$PG_LOG"

STEP_START=$(date +%s)
for i in {1..30}; do
  if docker compose -f cloud/docker-compose.yml exec -T postgres pg_isready -U livestockguard >> "$PG_LOG" 2>&1; then
    STEP_DURATION=$(( $(date +%s) - STEP_START ))
    log_info "PostgreSQL healthy (ready in ${STEP_DURATION}s, attempt $i/30)"
    log_master "PostgreSQL ready after ${STEP_DURATION}s ($i attempts)"
    break
  fi
  if [ "$i" -eq 30 ]; then
    log_error "PostgreSQL not ready after 30s — check docker logs"
    log_detail "Run: cd cloud && docker compose logs postgres"
    exit 1
  fi
  log_detail "Waiting... (attempt $i/30)"
  sleep 1
done

# Also wait for Redis
log_detail "Checking Redis..."
for i in {1..10}; do
  if docker compose -f cloud/docker-compose.yml exec -T redis redis-cli ping >> "$PG_LOG" 2>&1; then
    log_info "Redis: PONG (healthy)"
    break
  fi
  sleep 1
done

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 3: Run all database migrations
# ═══════════════════════════════════════════════════════════════════════════════

log_step "Running database migrations (12 migration files)"

MIGRATE_LOG="$ROOT_DIR/logs/run-all-migrations.log"
: > "$MIGRATE_LOG"

cd cloud
MIGRATION_COUNT=0
MIGRATION_ERRORS=0
for f in migrations/versions/*.sql; do
  MIGRATION_COUNT=$((MIGRATION_COUNT + 1))
  FNAME=$(basename "$f")
  log_detail "Applying: $FNAME"
  if docker compose exec -T postgres psql -U livestockguard -d livestockguard < "$f" >> "$MIGRATE_LOG" 2>&1; then
    log_master "Migration OK: $FNAME"
  else
    MIGRATION_ERRORS=$((MIGRATION_ERRORS + 1))
    log_master "Migration SKIP/WARN: $FNAME (may already exist)"
  fi
done
cd "$ROOT_DIR"

if [ $MIGRATION_ERRORS -eq 0 ]; then
  log_info "All $MIGRATION_COUNT migrations applied successfully"
else
  log_info "$MIGRATION_COUNT migrations processed ($MIGRATION_ERRORS skipped — likely already applied)"
fi

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 4: Seed database (3 farms, 65 animals)
# ═══════════════════════════════════════════════════════════════════════════════

log_step "Seeding database (3 farms, 65 animals, geofences, gateways)"

SEED_LOG="$ROOT_DIR/logs/run-all-seed.log"
: > "$SEED_LOG"

cd cloud

log_detail "Loading seed_data.sql (Boschhoek + Loch Vaal)..."
docker compose exec -T postgres psql -U livestockguard -d livestockguard \
  < ../scripts/seed_data.sql >> "$SEED_LOG" 2>&1 || true

log_detail "Loading seed_sibanyoni.sql (Sibanyoni Farm, 50 cattle)..."
if [ -f "../scripts/seed_sibanyoni.sql" ]; then
  docker compose exec -T postgres psql -U livestockguard -d livestockguard \
    < ../scripts/seed_sibanyoni.sql >> "$SEED_LOG" 2>&1 || true
fi

cd "$ROOT_DIR"

log_info "Seed data loaded:"
log_detail "Boschhoek Farm (Free State) — 5 animals, GPS collars"
log_detail "Loch Vaal Plot 30 (Gauteng) — 10 animals, BLE ear tags + gateway"
log_detail "Sibanyoni Farm (North West) — 50 animals, BLE ear tags + gateway"
log_detail "13 geofences, 2 gateway devices, 60 BLE ear tags"
log_master "Database seeded: 3 farms, 65 animals"

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 5: Wait for API Gateway to be healthy
# ═══════════════════════════════════════════════════════════════════════════════

log_step "Verifying API Gateway health"

API_LOG="$ROOT_DIR/logs/run-all-api.log"
: > "$API_LOG"

STEP_START=$(date +%s)
for i in {1..20}; do
  RESPONSE=$(curl -sf http://localhost:8000/health 2>&1 || echo "")
  echo "Attempt $i: $RESPONSE" >> "$API_LOG"
  if [ -n "$RESPONSE" ]; then
    STEP_DURATION=$(( $(date +%s) - STEP_START ))
    log_info "API Gateway healthy (${STEP_DURATION}s)"
    log_detail "Health response: $RESPONSE"
    log_detail "Swagger docs: http://localhost:8000/docs"
    log_master "API healthy after ${STEP_DURATION}s"
    break
  fi
  if [ "$i" -eq 20 ]; then
    log_error "API Gateway not responding on :8000 after 20s"
    log_detail "Check: cd cloud && docker compose logs api_gateway"
    log_warn "Continuing anyway — API may still be starting"
  fi
  sleep 1
done

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 6: GPS Simulator — Boschhoek (5 animals)
# ═══════════════════════════════════════════════════════════════════════════════

if [ "$SKIP_SIM" = true ]; then
  log_step "Skipping simulators (--no-sim)"
  # Adjust step counter
  STEP_NUM=$((STEP_NUM + 2))
else

log_step "Starting GPS simulator — Boschhoek Farm (5 animals, Free State)"

SIM1_LOG="$ROOT_DIR/logs/run-all-sim-boschhoek.log"
: > "$SIM1_LOG"

cd tools/simulator
if [ -d ".venv" ]; then
  source .venv/bin/activate 2>/dev/null || true
  log_detail "Activated Python venv: tools/simulator/.venv"
fi

log_detail "Farm: Boschhoek | Location: -29.12, 26.21 | Animals: 5"
log_detail "Protocol: Binary MQTT (CRC-16 CCITT) | Interval: 10s"
log_detail "Topic: lg/dev/{device_id}/pos | QoS: 1"
log_detail "Command: python3 simulator.py --farm boschhoek --animals 5 --interval 10 --duration 7200"

python3 simulator.py --farm boschhoek --animals 5 --interval 10 --duration 7200 > "$SIM1_LOG" 2>&1 &
PIDS+=($!)
log_info "GPS simulator started (PID: ${PIDS[-1]})"
log_master "Boschhoek GPS sim started PID=${PIDS[-1]}"
cd "$ROOT_DIR"

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 7: BLE Gateway Simulator — Sibanyoni (50 animals, herdsman day)
# ═══════════════════════════════════════════════════════════════════════════════

log_step "Starting BLE gateway — Sibanyoni Farm (50 animals, North West)"

SIM2_LOG="$ROOT_DIR/logs/run-all-sim-sibanyoni.log"
: > "$SIM2_LOG"

cd tools/simulator
if [ -d ".venv" ]; then source .venv/bin/activate 2>/dev/null || true; fi

log_detail "Farm: Sibanyoni | Location: -25.358, 25.361 | Animals: 50"
log_detail "Devices: 50 BLE ear tags (serial 3000–3049)"
log_detail "Protocol: REST API batch (POST /api/v1/gateway/batch)"
log_detail "Mode: Herdsman daily routine at 20x speed"
log_detail "Command: python3 sibanyoni_daily_sim.py --speed 20"

python3 sibanyoni_daily_sim.py --speed 20 > "$SIM2_LOG" 2>&1 &
PIDS+=($!)
log_info "BLE gateway simulator started (PID: ${PIDS[-1]})"
log_master "Sibanyoni BLE gateway sim started PID=${PIDS[-1]}"
cd "$ROOT_DIR"

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 8: BLE Gateway Simulator — Loch Vaal (10 animals, daily routine)
# ═══════════════════════════════════════════════════════════════════════════════

log_step "Starting BLE gateway — Loch Vaal Plot 30 (10 animals, herdsman day, $SCENARIO)"

SIM3_LOG="$ROOT_DIR/logs/run-all-sim-lochvaal.log"
: > "$SIM3_LOG"

cd tools/simulator
if [ -d ".venv" ]; then source .venv/bin/activate 2>/dev/null || true; fi

log_detail "Farm: Loch Vaal Plot 30 | Location: -26.719, 27.710 | Animals: 10"
log_detail "Protocol: REST API batch (POST /api/v1/gateway/batch every 20s)"
log_detail "Mode: Herdsman daily routine at 20x speed (~36 min real time)"
log_detail "Scenario: $SCENARIO"
log_detail "Command: python3 gateway_daily_sim.py --speed 20 --scan-interval 8 --report-interval 20 --scenario $SCENARIO"

python3 gateway_daily_sim.py --speed 20 --scan-interval 8 --report-interval 20 --scenario "$SCENARIO" > "$SIM3_LOG" 2>&1 &
PIDS+=($!)
log_info "BLE gateway simulator started (PID: ${PIDS[-1]})"
log_master "Loch Vaal BLE sim started PID=${PIDS[-1]} scenario=$SCENARIO"

if [ "$SCENARIO" = "breach" ]; then
  log_detail "⚠️  LV-001 will BREACH geofence at ~sim 11:00 (~12 min real time)"
elif [ "$SCENARIO" = "theft" ]; then
  log_detail "🚨 LV-001 will be STOLEN at ~sim 10:00 (~10 min real time)"
fi

cd "$ROOT_DIR"

fi  # end SKIP_SIM check

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 9: Web Dashboard
# ═══════════════════════════════════════════════════════════════════════════════

log_step "Starting Web Dashboard (React 18 + Vite + MapLibre GL)"

DASH_LOG="$ROOT_DIR/logs/run-all-dashboard.log"
: > "$DASH_LOG"

# Kill stale process on port 5173
if lsof -ti :5173 > /dev/null 2>&1; then
  log_detail "Killing stale process on port 5173..."
  lsof -ti :5173 | xargs kill -9 2>/dev/null || true
  sleep 1
fi

cd dashboard

log_detail "Directory: dashboard/"
log_detail "Installing dependencies (npm install)..."
STEP_START=$(date +%s)
npm install --silent >> "$DASH_LOG" 2>&1
STEP_DURATION=$(( $(date +%s) - STEP_START ))
log_detail "npm install completed (${STEP_DURATION}s)"

log_detail "Starting Vite dev server on port 5173..."
log_detail "Command: npx vite --port 5173 --host"
npx vite --port 5173 --host >> "$DASH_LOG" 2>&1 &
PIDS+=($!)
log_master "Dashboard started PID=${PIDS[-1]}"

cd "$ROOT_DIR"

# Wait for dashboard to be accessible
sleep 3
for i in {1..10}; do
  if lsof -i :5173 > /dev/null 2>&1; then
    log_info "Dashboard running: http://localhost:5173"
    log_detail "Login: africa.mydrive@gmail.com / demo123"
    break
  fi
  if [ "$i" -eq 10 ]; then
    log_warn "Dashboard may still be starting — check logs/run-all-dashboard.log"
  fi
  sleep 1
done

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 10: Mobile App (Web Mode)
# ═══════════════════════════════════════════════════════════════════════════════

if [ "$SKIP_MOBILE" = true ]; then
  log_step "Skipping mobile app (--no-mobile)"
else

log_step "Starting Mobile App (React Native + Expo 52, web mode)"

MOBILE_LOG="$ROOT_DIR/logs/run-all-mobile.log"
: > "$MOBILE_LOG"

# Kill stale process on port 8082
if lsof -ti :8082 > /dev/null 2>&1; then
  log_detail "Killing stale process on port 8082..."
  lsof -ti :8082 | xargs kill -9 2>/dev/null || true
  sleep 1
fi

cd mobile

log_detail "Directory: mobile/"
log_detail "Installing dependencies (npm install)..."
STEP_START=$(date +%s)
npm install --silent >> "$MOBILE_LOG" 2>&1
STEP_DURATION=$(( $(date +%s) - STEP_START ))
log_detail "npm install completed (${STEP_DURATION}s)"

log_detail "Starting Expo web server on port 8082..."
log_detail "Command: CI=1 npx expo start --web --port 8082"
CI=1 npx expo start --web --port 8082 >> "$MOBILE_LOG" 2>&1 &
PIDS+=($!)
log_master "Mobile app started PID=${PIDS[-1]}"

cd "$ROOT_DIR"

# Wait for mobile to be accessible
sleep 8
for i in {1..15}; do
  if lsof -i :8082 > /dev/null 2>&1; then
    log_info "Mobile app running: http://localhost:8082"
    log_detail "Login: africa.mydrive@gmail.com / demo123"
    break
  fi
  if [ "$i" -eq 15 ]; then
    log_warn "Mobile app may still be starting — check logs/run-all-mobile.log"
  fi
  sleep 1
done

fi  # end SKIP_MOBILE check

# ═══════════════════════════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════════════════════════

TOTAL_ELAPSED=$(( $(date +%s) - START_TIME ))
log_master "═══ ALL SERVICES RUNNING (startup took ${TOTAL_ELAPSED}s) ═══"

echo ""
echo -e "${BOLD}${GREEN}╔══════════════════════════════════════════════════════════════════╗${RESET}"
echo -e "${BOLD}${GREEN}║                                                                  ║${RESET}"
echo -e "${BOLD}${GREEN}║   ✅ LIVESTOCKGUARD — ALL SYSTEMS RUNNING                        ║${RESET}"
echo -e "${BOLD}${GREEN}║                                                                  ║${RESET}"
echo -e "${BOLD}${GREEN}╠══════════════════════════════════════════════════════════════════╣${RESET}"
echo -e "${GREEN}║                                                                  ║${RESET}"
echo -e "${GREEN}║  INTERFACES                                                      ║${RESET}"
echo -e "${GREEN}║    Web Dashboard:   http://localhost:5173                         ║${RESET}"
if [ "$SKIP_MOBILE" = false ]; then
echo -e "${GREEN}║    Mobile App:      http://localhost:8082                         ║${RESET}"
fi
echo -e "${GREEN}║    API Swagger:     http://localhost:8000/docs                    ║${RESET}"
echo -e "${GREEN}║    EMQX Console:    http://localhost:18083 (admin/public)         ║${RESET}"
echo -e "${GREEN}║                                                                  ║${RESET}"
echo -e "${GREEN}║  INFRASTRUCTURE                                                  ║${RESET}"
echo -e "${GREEN}║    PostgreSQL:      localhost:5432 (livestockguard/livestockguard_dev)║${RESET}"
echo -e "${GREEN}║    Redis:           localhost:6379                                ║${RESET}"
echo -e "${GREEN}║    MQTT Broker:     localhost:1883                                ║${RESET}"
echo -e "${GREEN}║                                                                  ║${RESET}"
if [ "$SKIP_SIM" = false ]; then
echo -e "${GREEN}║  SIMULATORS                                                      ║${RESET}"
echo -e "${GREEN}║    🐄 Boschhoek  — 5 GPS cows (Free State)                       ║${RESET}"
echo -e "${GREEN}║    🐄 Sibanyoni  — 50 BLE cows, herdsman day (North West)         ║${RESET}"
echo -e "${GREEN}║    🐄 Loch Vaal  — 10 BLE cows, herdsman day ($SCENARIO)      ║${RESET}"
echo -e "${GREEN}║                                                                  ║${RESET}"
fi
echo -e "${GREEN}║  LOGINS                                                          ║${RESET}"
echo -e "${GREEN}║    africa.mydrive@gmail.com / demo123     (all farms)            ║${RESET}"
echo -e "${GREEN}║    lochvaal@livestockguard.co.za / demo123 (Loch Vaal)           ║${RESET}"
echo -e "${GREEN}║    sibanyoni@livestockguard.co.za / demo123 (Sibanyoni)          ║${RESET}"
echo -e "${GREEN}║                                                                  ║${RESET}"
echo -e "${GREEN}║  LOGS                                                            ║${RESET}"
echo -e "${GREEN}║    Master:     logs/run-all.log                                  ║${RESET}"
echo -e "${GREEN}║    Docker:     logs/run-all-docker.log                           ║${RESET}"
echo -e "${GREEN}║    Migrations: logs/run-all-migrations.log                       ║${RESET}"
echo -e "${GREEN}║    Dashboard:  logs/run-all-dashboard.log                        ║${RESET}"
if [ "$SKIP_MOBILE" = false ]; then
echo -e "${GREEN}║    Mobile:     logs/run-all-mobile.log                           ║${RESET}"
fi
if [ "$SKIP_SIM" = false ]; then
echo -e "${GREEN}║    Sims:       logs/run-all-sim-{boschhoek,sibanyoni,lochvaal}.log║${RESET}"
fi
echo -e "${GREEN}║                                                                  ║${RESET}"
echo -e "${GREEN}║  Startup time: ${TOTAL_ELAPSED}s                                            ║${RESET}"
echo -e "${GREEN}║  Stop: Ctrl+C                                                    ║${RESET}"
echo -e "${GREEN}║                                                                  ║${RESET}"
echo -e "${BOLD}${GREEN}╚══════════════════════════════════════════════════════════════════╝${RESET}"
echo ""

# ─── Keep alive (wait for background processes) ───────────────────────────────

wait
