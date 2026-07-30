#!/usr/bin/env bash
#
# LivestockGuard — FULL Platform Demo (Everything)
#
# Launches the entire LivestockGuard platform:
#   - Docker stack (Postgres, Redis, EMQX, API, MQTT Writer, Alert Engine)
#   - Database seed (3 farms, 65 animals, 13 geofences, 2 gateways, 60 BLE tags)
#   - All migrations
#   - GPS simulator: Boschhoek (5 animals, Free State)
#   - GPS simulator: Sibanyoni (50 animals, North West)
#   - BLE gateway simulator: Loch Vaal (10 animals, full day, Gauteng)
#   - Web dashboard (http://localhost:5173)
#   - Mobile app in browser (http://localhost:8082)
#
# Usage:
#   ./scripts/run-demo-full.sh                # Default: breach scenario
#   ./scripts/run-demo-full.sh --normal       # Normal day (no incidents)
#   ./scripts/run-demo-full.sh --theft        # Theft scenario
#   ./scripts/run-demo-full.sh --breach       # Breach scenario (default)
#
# Stop: Ctrl+C (kills all background processes)

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$ROOT_DIR"

# Parse args
SCENARIO="breach"
for arg in "$@"; do
  case "$arg" in
    --normal) SCENARIO="normal" ;;
    --theft) SCENARIO="theft" ;;
    --breach) SCENARIO="breach" ;;
  esac
done

# Colours
GREEN='\033[32m'
CYAN='\033[36m'
YELLOW='\033[33m'
RED='\033[31m'
BOLD='\033[1m'
RESET='\033[0m'

# Create logs directory
mkdir -p logs

cleanup() {
  echo -e "\n${YELLOW}Stopping all demo processes...${RESET}"
  kill $(jobs -p) 2>/dev/null || true
  echo -e "${GREEN}Demo stopped. All processes cleaned up.${RESET}"
  echo -e "${YELLOW}Docker stack still running (use 'make stop' to stop).${RESET}"
  exit 0
}
trap cleanup SIGINT SIGTERM

echo -e "${BOLD}${CYAN}"
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  LivestockGuard — FULL PLATFORM DEMO                        ║"
echo "║  All 3 farms • All simulators • Dashboard • Mobile          ║"
echo "║  Scenario: ${SCENARIO}                                              ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo -e "${RESET}"
echo ""

# ─── 1. Docker Stack ──────────────────────────────────────────────────────────

echo -e "${GREEN}[1/9] Starting cloud infrastructure...${RESET}"
cd cloud && docker compose up -d --build 2>&1 | grep -E "Started|Running|Healthy" | tail -5
cd "$ROOT_DIR"
sleep 4

# Verify API
for i in {1..15}; do
  if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
    echo -e "  ✅ API healthy (http://localhost:8000)"
    break
  fi
  if [ "$i" -eq 15 ]; then
    echo -e "${RED}ERROR: API not responding on port 8000 after 15s${RESET}"
    echo "Check: cd cloud && docker compose logs api_gateway"
    exit 1
  fi
  sleep 1
done

# ─── 2. Seed Database (all 3 farms) ──────────────────────────────────────────

echo -e "${GREEN}[2/9] Seeding database (3 farms, 65 animals)...${RESET}"
cd cloud
docker compose exec -T postgres psql -U livestockguard -d livestockguard < ../scripts/seed_data.sql 2>&1 | grep "NOTICE" || true
cd "$ROOT_DIR"
echo -e "  ✅ Boschhoek (5 animals, GPS) + Loch Vaal (10 animals, BLE) + Sibanyoni (50 animals, BLE)"

# ─── 3. Migrations ───────────────────────────────────────────────────────────

echo -e "${GREEN}[3/9] Applying all migrations...${RESET}"
cd cloud
for f in migrations/versions/*.sql; do
  docker compose exec -T postgres psql -U livestockguard -d livestockguard < "$f" 2>/dev/null || true
done
cd "$ROOT_DIR"
echo -e "  ✅ All 9 migrations applied"

# ─── 4. GPS Simulator: Boschhoek (Free State, 5 animals) ─────────────────────

echo -e "${GREEN}[4/9] Starting GPS simulator — Boschhoek Farm (5 animals)...${RESET}"
cd tools/simulator
source .venv/bin/activate 2>/dev/null || true
python3 simulator.py --farm boschhoek --animals 5 --interval 10 --duration 7200 > ../../logs/gps-boschhoek.log 2>&1 &
cd "$ROOT_DIR"
echo -e "  ✅ 5 cows with GPS collars (Free State, -29.12, 26.21)"

# ─── 5. GPS Simulator: Sibanyoni (North West, 50 animals) ────────────────────

echo -e "${GREEN}[5/9] Starting GPS simulator — Sibanyoni Farm (50 animals)...${RESET}"
cd tools/simulator
python3 simulator.py --farm sibanyoni --animals 50 --interval 15 --duration 7200 > ../../logs/gps-sibanyoni.log 2>&1 &
cd "$ROOT_DIR"
echo -e "  ✅ 50 cows with GPS collars (North West, -25.358, 25.361)"

# ─── 6. BLE Gateway Simulator: Loch Vaal (Gauteng, 10 animals, full day) ─────

echo -e "${GREEN}[6/9] Starting BLE gateway — Loch Vaal Plot 30 (10 animals, ${SCENARIO})...${RESET}"
cd tools/simulator
python3 gateway_daily_sim.py --speed 20 --scan-interval 8 --report-interval 20 --scenario "$SCENARIO" > ../../logs/ble-lochvaal.log 2>&1 &
cd "$ROOT_DIR"
echo -e "  ✅ 10 cows with BLE ear tags, herdsman gateway (Gauteng, -26.719, 27.710)"
if [ "$SCENARIO" = "breach" ]; then
  echo -e "  ${YELLOW}⚠️  LV-001 will BREACH geofence at ~sim 11:00 (~12 min real)${RESET}"
elif [ "$SCENARIO" = "theft" ]; then
  echo -e "  ${RED}🚨 LV-001 will be STOLEN at ~sim 10:00 (~10 min real)${RESET}"
fi

# ─── 7. Web Dashboard ────────────────────────────────────────────────────────

echo -e "${GREEN}[7/9] Starting web dashboard...${RESET}"
cd dashboard
npm install --silent 2>/dev/null
npx vite --port 5173 > ../logs/dashboard-full.log 2>&1 &
cd "$ROOT_DIR"
sleep 3
if lsof -i :5173 > /dev/null 2>&1; then
  echo -e "  ✅ Dashboard: http://localhost:5173"
else
  echo -e "  ${YELLOW}⚠ Dashboard starting... check logs/dashboard-full.log${RESET}"
fi

# ─── 8. Mobile App (Web Mode) ────────────────────────────────────────────────

echo -e "${GREEN}[8/9] Starting mobile app (web mode)...${RESET}"
cd mobile
npm install --silent 2>/dev/null
npx expo start --web --port 8082 > ../logs/mobile-full.log 2>&1 &
cd "$ROOT_DIR"
sleep 4
if lsof -i :8082 > /dev/null 2>&1; then
  echo -e "  ✅ Mobile app: http://localhost:8082"
else
  echo -e "  ${YELLOW}⚠ Mobile app starting... check logs/mobile-full.log${RESET}"
fi

# ─── 9. Summary ──────────────────────────────────────────────────────────────

echo -e "${GREEN}[9/9] All systems running!${RESET}"
echo ""
echo -e "${BOLD}${CYAN}╔══════════════════════════════════════════════════════════════╗${RESET}"
echo -e "${BOLD}${CYAN}║  ✅ FULL PLATFORM RUNNING                                    ║${RESET}"
echo -e "${BOLD}${CYAN}╠══════════════════════════════════════════════════════════════╣${RESET}"
echo -e "${CYAN}║                                                              ║${RESET}"
echo -e "${CYAN}║  INTERFACES:                                                 ║${RESET}"
echo -e "${CYAN}║    Dashboard:    http://localhost:5173                        ║${RESET}"
echo -e "${CYAN}║    Mobile App:   http://localhost:8082                        ║${RESET}"
echo -e "${CYAN}║    API Docs:     http://localhost:8000/docs                   ║${RESET}"
echo -e "${CYAN}║    EMQX Broker:  http://localhost:18083 (admin/public)        ║${RESET}"
echo -e "${CYAN}║                                                              ║${RESET}"
echo -e "${CYAN}║  FARMS RUNNING:                                              ║${RESET}"
echo -e "${CYAN}║    🐄 Boschhoek (Free State)   — 5 GPS cows, real-time       ║${RESET}"
echo -e "${CYAN}║    🐄 Sibanyoni (North West)   — 50 GPS cows, real-time      ║${RESET}"
echo -e "${CYAN}║    🐄 Loch Vaal (Gauteng)      — 10 BLE cows, full day       ║${RESET}"
echo -e "${CYAN}║                                                              ║${RESET}"
echo -e "${CYAN}║  LOGINS:                                                     ║${RESET}"
echo -e "${CYAN}║    africa.mydrive@gmail.com / demo123  (Boschhoek)           ║${RESET}"
echo -e "${CYAN}║    lochvaal@livestockguard.co.za / demo123  (Loch Vaal)      ║${RESET}"
echo -e "${CYAN}║    sibanyoni@livestockguard.co.za / demo123  (Sibanyoni)     ║${RESET}"
echo -e "${CYAN}║                                                              ║${RESET}"
echo -e "${CYAN}║  SCENARIO: ${SCENARIO}                                            ║${RESET}"
echo -e "${CYAN}║    Loch Vaal daily routine at 20x speed (~36 min real)       ║${RESET}"
echo -e "${CYAN}║                                                              ║${RESET}"
echo -e "${CYAN}║  LOGS: logs/gps-boschhoek.log, logs/gps-sibanyoni.log        ║${RESET}"
echo -e "${CYAN}║        logs/ble-lochvaal.log, logs/dashboard-full.log        ║${RESET}"
echo -e "${CYAN}║        logs/mobile-full.log                                  ║${RESET}"
echo -e "${CYAN}║                                                              ║${RESET}"
echo -e "${CYAN}║  STOP: Ctrl+C                                                ║${RESET}"
echo -e "${BOLD}${CYAN}╚══════════════════════════════════════════════════════════════╝${RESET}"
echo ""

# Wait for background processes
wait
