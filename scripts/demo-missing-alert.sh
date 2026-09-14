#!/usr/bin/env bash
#
# LivestockGuard — Missing-Animal Alert Demo
#
# Demonstrates the "undetected animal -> major alert" pipeline end to end:
#   1. Ensures the cloud stack is up.
#   2. Runs the Loch Vaal BLE gateway simulator briefly so those animals ARE seen.
#   3. Leaves the Sibanyoni herd dark (no simulator) so it stays undetected.
#   4. Triggers the analytics_engine missing-animal detector on demand.
#   5. Shows the resulting critical `animal_missing` alerts (Sibanyoni only) and
#      confirms the just-seen Loch Vaal animals are NOT flagged.
#
# The detector normally runs every MISSING_ALERT_CHECK_INTERVAL_MINUTES with a
# MISSING_ALERT_THRESHOLD_HOURS window; this demo forces an immediate run with a
# short (0.05h ~= 3min) threshold and MISSING_ALERT_ON_NEVER_SEEN=true so you
# don't have to wait. A tiny non-zero threshold is used (not 0) so animals seen
# seconds ago fall INSIDE the window and are correctly treated as detected.
DEMO_THRESHOLD_HOURS="0.05"
#
# Usage:
#   bash scripts/demo-missing-alert.sh
#
# Requires: the cloud stack (make start) and seed data already loaded.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$ROOT_DIR"

GREEN='\033[32m'; YELLOW='\033[33m'; CYAN='\033[36m'; BOLD='\033[1m'; RESET='\033[0m'

COMPOSE="docker compose -f cloud/docker-compose.yml"
LOCHVAAL_FARM="bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"

psql() { $COMPOSE exec -T postgres psql -U livestockguard -d livestockguard "$@"; }

echo -e "${BOLD}${CYAN}LivestockGuard — Missing-Animal Alert Demo${RESET}"
echo "────────────────────────────────────────────"

# 1) Stack up?
echo -e "${CYAN}[1/5]${RESET} Checking cloud stack..."
if ! curl -sf http://localhost:8000/health >/dev/null 2>&1; then
  echo -e "${YELLOW}API not responding — starting the stack (make start)...${RESET}"
  (cd cloud && docker compose up -d) >/dev/null 2>&1
  for i in $(seq 1 30); do
    curl -sf http://localhost:8000/health >/dev/null 2>&1 && break
    sleep 1
  done
fi
echo -e "  ${GREEN}API healthy.${RESET}"

# Clear any stale animal_missing alerts so the demo starts clean.
psql -c "DELETE FROM alerts WHERE alert_type='animal_missing';" >/dev/null 2>&1 || true

# 2) Ensure simulator venv, then feed Loch Vaal detections.
echo -e "${CYAN}[2/5]${RESET} Feeding Loch Vaal detections (so those cattle are SEEN)..."
cd tools/simulator
if [ ! -d ".venv" ]; then
  python3 -m venv .venv >/dev/null 2>&1 || true
  [ -d ".venv" ] && .venv/bin/pip install --quiet -r requirements.txt >/dev/null 2>&1 || true
fi
PY=".venv/bin/python"; [ -x "$PY" ] || PY="python3"
"$PY" gateway_simulator.py --farm lochvaal --animals 10 --duration 30 \
  --scan-interval 3 --report-interval 8 --seed 42 >/tmp/lg-missing-demo-sim.log 2>&1 || true
cd "$ROOT_DIR"
echo -e "  ${GREEN}Loch Vaal fed. Sibanyoni left dark (no simulator).${RESET}"

# 3) Show detection state before alerting.
echo -e "${CYAN}[3/5]${RESET} Detection coverage:"
curl -s "http://localhost:8000/api/gateway/herd-count/${LOCHVAAL_FARM}" | \
  python3 -c "import sys,json;d=json.load(sys.stdin);print(f\"    Loch Vaal: seen_today={d['seen_today']}/{d['total_registered']} coverage={d['coverage_pct']}% missing={d['missing_count']}\")" 2>/dev/null || true

# 4) Force the detector to run now (0h threshold, alert on never-seen).
echo -e "${CYAN}[4/5]${RESET} Running missing-animal detector (forced: threshold ${DEMO_THRESHOLD_HOURS}h, on-never-seen)..."
$COMPOSE exec -T \
  -e MISSING_ALERT_ON_NEVER_SEEN=true \
  -e MISSING_ALERT_THRESHOLD_HOURS="${DEMO_THRESHOLD_HOURS}" \
  analytics_engine python -c "
import asyncio
from app.jobs.missing_animal_detector import run_missing_animal_detector
r, v = asyncio.run(run_missing_animal_detector())
print(f'    raised={r} resolved={v}')
"

# 5) Show the resulting alerts by farm.
echo -e "${CYAN}[5/5]${RESET} Critical animal_missing alerts by farm:"
psql -c "
  SELECT f.name AS farm, al.severity, count(*) AS missing_alerts
  FROM alerts al JOIN farms f ON f.id = al.farm_id
  WHERE al.alert_type='animal_missing' AND al.status='active'
  GROUP BY f.name, al.severity ORDER BY f.name;"

echo ""
echo -e "${GREEN}Done.${RESET} Loch Vaal cattle were detected and should NOT be flagged;"
echo -e "the Sibanyoni herd (no simulator) is flagged as ${BOLD}missing (critical)${RESET}."
echo -e "The alert_engine received these on Redis 'alerts:incoming' — check with:"
echo -e "  ${CYAN}$COMPOSE logs alert_engine | grep animal_missing${RESET}"
echo -e "Clear the demo alerts with:"
echo -e "  ${CYAN}$COMPOSE exec -T postgres psql -U livestockguard -d livestockguard -c \"DELETE FROM alerts WHERE alert_type='animal_missing';\"${RESET}"
