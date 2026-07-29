#!/usr/bin/env bash
#
# LivestockGuard — Full Live Demo
#
# Starts the entire stack with live simulations:
# - Docker infrastructure (Postgres, Redis, EMQX, API, MQTT Writer)
# - Database seeded with both farms
# - GPS simulator (Boschhoek, 5 animals moving)
# - BLE simulator (Loch Vaal, 10 animals + breach scenario)
# - Web dashboard (localhost:5173)
#
# Usage:
#   ./scripts/run-demo.sh              # Normal (breach scenario)
#   ./scripts/run-demo.sh --normal     # No breach
#   ./scripts/run-demo.sh --theft      # Theft scenario instead
#
# Stop: Ctrl+C (kills all background processes)

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$ROOT_DIR"

SCENARIO="${1:-breach}"
case "$1" in
  --normal) SCENARIO="normal" ;;
  --theft) SCENARIO="theft" ;;
  --breach) SCENARIO="breach" ;;
esac

# Colours
GREEN='\033[32m'
CYAN='\033[36m'
YELLOW='\033[33m'
RESET='\033[0m'

cleanup() {
  echo -e "\n${YELLOW}Stopping demo processes...${RESET}"
  kill $(jobs -p) 2>/dev/null
  echo -e "${GREEN}Demo stopped.${RESET}"
  exit 0
}
trap cleanup SIGINT SIGTERM

echo -e "${CYAN}╔══════════════════════════════════════════════════════╗${RESET}"
echo -e "${CYAN}║  LivestockGuard — Full Live Demo                     ║${RESET}"
echo -e "${CYAN}║  Scenario: ${SCENARIO}                                       ║${RESET}"
echo -e "${CYAN}╚══════════════════════════════════════════════════════╝${RESET}"
echo ""

# 1. Start Docker stack
echo -e "${GREEN}1. Starting cloud infrastructure...${RESET}"
cd cloud && docker compose up -d --build 2>&1 | tail -3
cd "$ROOT_DIR"
sleep 4

# 2. Seed database
echo -e "${GREEN}2. Seeding database...${RESET}"
cd cloud && docker compose exec -T postgres psql -U livestockguard -d livestockguard < ../scripts/seed_data.sql 2>&1 | grep "NOTICE" || true
cd "$ROOT_DIR"

# 3. Run migrations
echo -e "${GREEN}3. Applying migrations...${RESET}"
cd cloud
docker compose exec -T postgres psql -U livestockguard -d livestockguard < ../cloud/migrations/versions/008_geofence_breach_severity.sql 2>/dev/null || true
docker compose exec -T postgres psql -U livestockguard -d livestockguard < ../cloud/migrations/versions/009_farm_schedule_config.sql 2>/dev/null || true
cd "$ROOT_DIR"

# 4. Start GPS simulator (Boschhoek)
echo -e "${GREEN}4. Starting GPS simulator (Boschhoek, 5 animals)...${RESET}"
cd tools/simulator && python3 simulator.py --farm boschhoek --animals 5 --interval 10 --duration 3600 > ../../logs/gps-sim.log 2>&1 &
cd "$ROOT_DIR"

# 5. Start BLE simulator (Loch Vaal) with scenario
echo -e "${GREEN}5. Starting BLE simulator (Loch Vaal, ${SCENARIO}, ~36 min)...${RESET}"
cd tools/simulator && python3 gateway_daily_sim.py --speed 20 --scan-interval 8 --report-interval 20 --scenario "$SCENARIO" > ../../logs/ble-sim.log 2>&1 &
cd "$ROOT_DIR"
sleep 2

# 6. Start dashboard
echo -e "${GREEN}6. Starting dashboard on port 5173...${RESET}"
cd dashboard && npx vite --port 5173 > ../logs/dashboard-demo.log 2>&1 &
cd "$ROOT_DIR"
sleep 3

# 7. Verify
echo ""
API_STATUS=$(curl -s http://localhost:8000/health 2>/dev/null | python3 -c "import sys,json;print(json.load(sys.stdin)['status'])" 2>/dev/null || echo "unreachable")
DASH_OK=$(lsof -i :5173 2>/dev/null | grep -c LISTEN || echo "0")

echo -e "${CYAN}╔══════════════════════════════════════════════════════╗${RESET}"
echo -e "${CYAN}║  ✅ DEMO RUNNING                                     ║${RESET}"
echo -e "${CYAN}║                                                      ║${RESET}"
echo -e "${CYAN}║  Dashboard:  http://localhost:5173                    ║${RESET}"
echo -e "${CYAN}║  Login:      africa.mydrive@gmail.com / demo123      ║${RESET}"
echo -e "${CYAN}║  API:        http://localhost:8000 (${API_STATUS})       ║${RESET}"
echo -e "${CYAN}║                                                      ║${RESET}"
echo -e "${CYAN}║  LIVE SIMULATION (${SCENARIO}):                          ║${RESET}"
echo -e "${CYAN}║  • Boschhoek: 5 GPS cows moving (Free State)        ║${RESET}"
echo -e "${CYAN}║  • Loch Vaal: 10 BLE cows (Gauteng)                 ║${RESET}"
echo -e "${CYAN}║    Schedule: Kraal→Feed→Gate→Graze→Return→Kraal     ║${RESET}"
echo -e "${CYAN}║    Full day in ~36 real minutes (speed 20x)          ║${RESET}"
echo -e "${CYAN}║                                                      ║${RESET}"
echo -e "${CYAN}║  Logs: logs/gps-sim.log, logs/ble-sim.log           ║${RESET}"
echo -e "${CYAN}║  Press Ctrl+C to stop                                ║${RESET}"
echo -e "${CYAN}╚══════════════════════════════════════════════════════╝${RESET}"
echo ""

# Wait for all background processes
wait
