#!/usr/bin/env bash
#
# LivestockGuard — Full Live Demo
#
# Starts the entire platform with all simulators and dashboards.
#
# Usage:
#   ./scripts/run-demo.sh              # Full demo (breach scenario)
#   ./scripts/run-demo.sh --normal     # Normal day (no incidents)
#   ./scripts/run-demo.sh --theft      # Theft scenario
#   ./scripts/run-demo.sh --mobile     # Include mobile app (web mode)
#   ./scripts/run-demo.sh --ios        # Include iOS simulator build
#   ./scripts/run-demo.sh --android    # Include Android emulator build
#
# What it starts:
#   1. Docker stack (Postgres, Redis, EMQX, API, MQTT Writer)
#   2. Database seed (2 farms, 15 animals, 7 geofences, gateway, BLE tags)
#   3. Migrations (breach severity, schedule config)
#   4. GPS simulator (Boschhoek, 5 animals, live)
#   5. BLE simulator (Loch Vaal, 10 animals, full day with scenario)
#   6. Web dashboard (http://localhost:5173)
#   7. Mobile app web (http://localhost:8082) [optional]
#   8. iOS/Android build [optional]
#
# Stop: Ctrl+C (kills all background processes)

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$ROOT_DIR"

# Parse args
SCENARIO="breach"
MOBILE=false
IOS_BUILD=false
ANDROID_BUILD=false

for arg in "$@"; do
  case "$arg" in
    --normal) SCENARIO="normal" ;;
    --theft) SCENARIO="theft" ;;
    --breach) SCENARIO="breach" ;;
    --mobile) MOBILE=true ;;
    --ios) IOS_BUILD=true ;;
    --android) ANDROID_BUILD=true ;;
  esac
done

# Colours
GREEN='\033[32m'
CYAN='\033[36m'
YELLOW='\033[33m'
RED='\033[31m'
RESET='\033[0m'

cleanup() {
  echo -e "\n${YELLOW}Stopping all demo processes...${RESET}"
  kill $(jobs -p) 2>/dev/null
  echo -e "${GREEN}Demo stopped. All processes cleaned up.${RESET}"
  exit 0
}
trap cleanup SIGINT SIGTERM

echo -e "${CYAN}╔══════════════════════════════════════════════════════════╗${RESET}"
echo -e "${CYAN}║  LivestockGuard — Full Platform Demo                     ║${RESET}"
echo -e "${CYAN}║  Scenario: ${SCENARIO}                                           ║${RESET}"
echo -e "${CYAN}╚══════════════════════════════════════════════════════════╝${RESET}"
echo ""

# ─── 1. Docker Stack ──────────────────────────────────────────────────────────

echo -e "${GREEN}[1/8] Starting cloud infrastructure...${RESET}"
cd cloud && docker compose up -d --build 2>&1 | grep -E "Started|Running|Healthy" | tail -5
cd "$ROOT_DIR"
sleep 4

# Verify
if ! curl -sf http://localhost:8000/health > /dev/null 2>&1; then
  echo -e "${RED}ERROR: API not responding on port 8000${RESET}"
  echo "Check: cd cloud && docker compose logs api_gateway"
  exit 1
fi
echo -e "  ✅ API healthy"

# ─── 2. Seed Database ────────────────────────────────────────────────────────

echo -e "${GREEN}[2/8] Seeding database...${RESET}"
cd cloud
docker compose exec -T postgres psql -U livestockguard -d livestockguard < ../scripts/seed_data.sql 2>&1 | grep "NOTICE" || true
cd "$ROOT_DIR"
echo -e "  ✅ 2 farms, 15 animals, 7 geofences, gateway, BLE tags"

# ─── 3. Migrations ───────────────────────────────────────────────────────────

echo -e "${GREEN}[3/8] Applying migrations...${RESET}"
cd cloud
for f in ../cloud/migrations/versions/008_*.sql ../cloud/migrations/versions/009_*.sql; do
  docker compose exec -T postgres psql -U livestockguard -d livestockguard < "$f" 2>/dev/null || true
done
cd "$ROOT_DIR"
echo -e "  ✅ Breach severity + schedule config"

# ─── 4. GPS Simulator (Boschhoek) ────────────────────────────────────────────

echo -e "${GREEN}[4/8] Starting GPS simulator (Boschhoek, 5 animals)...${RESET}"
cd tools/simulator
python3 simulator.py --farm boschhoek --animals 5 --interval 10 --duration 3600 > ../../logs/gps-sim.log 2>&1 &
cd "$ROOT_DIR"
echo -e "  ✅ 5 cows moving live (Free State)"

# ─── 5. BLE Simulator (Loch Vaal) ────────────────────────────────────────────

echo -e "${GREEN}[5/8] Starting BLE simulator (Loch Vaal, ${SCENARIO}, ~36 min)...${RESET}"
cd tools/simulator
python3 gateway_daily_sim.py --speed 20 --scan-interval 8 --report-interval 20 --scenario "$SCENARIO" > ../../logs/ble-sim.log 2>&1 &
cd "$ROOT_DIR"
echo -e "  ✅ 10 cows: Kraal→Feed→Gate→Graze (speed 20x)"
if [ "$SCENARIO" = "breach" ]; then
  echo -e "  ⚠️  LV-001 will BREACH at ~sim 11:00 (~12 min real)"
elif [ "$SCENARIO" = "theft" ]; then
  echo -e "  🚨 LV-001 will be STOLEN at ~sim 10:00 (~10 min real)"
fi

# ─── 6. Web Dashboard ────────────────────────────────────────────────────────

echo -e "${GREEN}[6/8] Starting web dashboard...${RESET}"
lsof -ti :5173 | xargs kill -9 2>/dev/null || true
sleep 1
cd dashboard
npm install --silent 2>/dev/null
npx vite --port 5173 > ../logs/dashboard-demo.log 2>&1 &
cd "$ROOT_DIR"
sleep 3
if lsof -i :5173 > /dev/null 2>&1; then
  echo -e "  ✅ Dashboard: http://localhost:5173"
else
  echo -e "  ${YELLOW}⚠ Dashboard may be on a different port. Check logs.${RESET}"
fi

# ─── 7. Mobile App (Web Mode) ────────────────────────────────────────────────

if [ "$MOBILE" = true ]; then
  echo -e "${GREEN}[7/8] Starting mobile app (web mode)...${RESET}"
  lsof -ti :8082 | xargs kill -9 2>/dev/null || true
  sleep 1
  cd mobile
  npm install --silent 2>/dev/null
  npx expo start --web --port 8082 --non-interactive > ../logs/mobile-demo.log 2>&1 &
  cd "$ROOT_DIR"
  sleep 5
  echo -e "  ✅ Mobile app: http://localhost:8082"
else
  echo -e "${GREEN}[7/8] Mobile app: skipped (use --mobile flag to include)${RESET}"
fi

# ─── 8. Native Builds ────────────────────────────────────────────────────────

if [ "$IOS_BUILD" = true ]; then
  echo -e "${GREEN}[8/8] Building iOS app for simulator...${RESET}"
  cd mobile
  npx expo run:ios --device "iPhone 16 Pro" > ../logs/ios-build.log 2>&1 &
  cd "$ROOT_DIR"
  echo -e "  ⏳ iOS build running in background (check logs/ios-build.log)"
elif [ "$ANDROID_BUILD" = true ]; then
  echo -e "${GREEN}[8/8] Building Android app for emulator...${RESET}"
  cd mobile
  npx expo run:android > ../logs/android-build.log 2>&1 &
  cd "$ROOT_DIR"
  echo -e "  ⏳ Android build running in background (check logs/android-build.log)"
else
  echo -e "${GREEN}[8/8] Native builds: skipped (use --ios or --android)${RESET}"
fi

# ─── Summary ──────────────────────────────────────────────────────────────────

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════════════╗${RESET}"
echo -e "${CYAN}║  ✅ DEMO RUNNING                                         ║${RESET}"
echo -e "${CYAN}║                                                          ║${RESET}"
echo -e "${CYAN}║  Dashboard:    http://localhost:5173                      ║${RESET}"
if [ "$MOBILE" = true ]; then
echo -e "${CYAN}║  Mobile App:   http://localhost:8082                      ║${RESET}"
fi
echo -e "${CYAN}║  API Docs:     http://localhost:8000/docs                 ║${RESET}"
echo -e "${CYAN}║  Login:        africa.mydrive@gmail.com / demo123         ║${RESET}"
echo -e "${CYAN}║                                                          ║${RESET}"
echo -e "${CYAN}║  LIVE SIMULATION (${SCENARIO}):                              ║${RESET}"
echo -e "${CYAN}║  • Boschhoek: 5 GPS cows moving (Free State)             ║${RESET}"
echo -e "${CYAN}║  • Loch Vaal: 10 BLE cows, full day (Gauteng)            ║${RESET}"
echo -e "${CYAN}║    08:30 Kraal open → 09:20 Gate exit → Grazing          ║${RESET}"
echo -e "${CYAN}║    16:30 Return → 17:00 Gate enter → 17:45 Kraal         ║${RESET}"
echo -e "${CYAN}║    Full day in ~36 real minutes                           ║${RESET}"
echo -e "${CYAN}║                                                          ║${RESET}"
echo -e "${CYAN}║  Logs: logs/gps-sim.log, logs/ble-sim.log                ║${RESET}"
echo -e "${CYAN}║  Stop: Ctrl+C                                            ║${RESET}"
echo -e "${CYAN}╚══════════════════════════════════════════════════════════╝${RESET}"
echo ""

# Wait for background processes
wait
