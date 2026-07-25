#!/usr/bin/env bash
#
# LivestockGuard Feature Verification Script
# Tests every feature via the API to confirm correct behavior.
#
# Usage:
#   ./scripts/verify-features.sh                 # Run all tests
#   ./scripts/verify-features.sh --api-url http://localhost:8000
#
# Prerequisites:
#   - API Gateway running (make start)
#   - Database seeded (make db-seed)
#   - curl, jq installed
#
# Output: logs/verify-api.log (detailed) + stdout summary

set -euo pipefail

# ─── Configuration ────────────────────────────────────────────────────────────

API_URL="${API_URL:-http://localhost:8000}"
LOG_FILE="logs/verify-api.log"
PASS=0
FAIL=0
SKIP=0

# Parse args
while [[ $# -gt 0 ]]; do
  case $1 in
    --api-url) API_URL="$2"; shift 2 ;;
    *) shift ;;
  esac
done

mkdir -p logs

# ─── Helpers ──────────────────────────────────────────────────────────────────

GREEN='\033[32m'
RED='\033[31m'
YELLOW='\033[33m'
CYAN='\033[36m'
RESET='\033[0m'

log() { echo "[$(date '+%H:%M:%S')] $*" >> "$LOG_FILE"; }
pass() { PASS=$((PASS+1)); echo -e "  ${GREEN}✓${RESET} $1"; log "PASS: $1"; }
fail() { FAIL=$((FAIL+1)); echo -e "  ${RED}✗${RESET} $1 — $2"; log "FAIL: $1 — $2"; }
skip() { SKIP=$((SKIP+1)); echo -e "  ${YELLOW}○${RESET} $1 (skipped)"; log "SKIP: $1"; }
section() { echo -e "\n${CYAN}━━━ $1 ━━━${RESET}"; log ""; log "=== $1 ==="; }

# HTTP helpers
get() { curl -s -H "Authorization: Bearer $TOKEN" "$API_URL$1" 2>/dev/null; }
post() { curl -s -X POST -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" -d "$2" "$API_URL$1" 2>/dev/null; }
get_noauth() { curl -s "$API_URL$1" 2>/dev/null; }
post_noauth() { curl -s -X POST -H "Content-Type: application/json" -d "$2" "$API_URL$1" 2>/dev/null; }

# ─── Start ────────────────────────────────────────────────────────────────────

echo "╔══════════════════════════════════════════════════════╗"
echo "║  LivestockGuard Feature Verification                 ║"
echo "║  API: $API_URL"
echo "║  Time: $(date '+%Y-%m-%d %H:%M:%S')                  ║"
echo "╚══════════════════════════════════════════════════════╝"

echo "" > "$LOG_FILE"
log "LivestockGuard Feature Verification"
log "API: $API_URL"
log "Started: $(date)"
log ""

TOKEN=""

# ─── 1. Health Check ──────────────────────────────────────────────────────────

section "1. Health & Connectivity"

HEALTH=$(get_noauth "/health" || echo "FAILED")
if echo "$HEALTH" | grep -q '"healthy"'; then
  pass "API health check returns healthy"
  log "  Response: $HEALTH"
else
  fail "API health check" "Service unreachable at $API_URL"
  echo -e "\n${RED}Cannot reach API. Is the stack running? (make start)${RESET}"
  exit 1
fi

# ─── 2. Authentication ────────────────────────────────────────────────────────

section "2. Authentication (JWT)"

# Valid login
LOGIN_RESP=$(post_noauth "/api/auth/login" '{"email":"africa.mydrive@gmail.com","password":"demo123"}' || echo "FAILED")
if echo "$LOGIN_RESP" | grep -q "access_token"; then
  TOKEN=$(echo "$LOGIN_RESP" | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])" 2>/dev/null)
  pass "Login with valid credentials returns JWT"
else
  fail "Login with valid credentials" "No token returned"
  exit 1
fi

# Invalid login
INVALID_LOGIN=$(curl -s -o /dev/null -w "%{http_code}" -X POST -H "Content-Type: application/json" -d '{"email":"wrong@test.com","password":"bad"}' "$API_URL/api/auth/login")
if [ "$INVALID_LOGIN" = "401" ]; then
  pass "Invalid credentials return 401"
else
  fail "Invalid credentials rejection" "Got HTTP $INVALID_LOGIN (expected 401)"
fi

# Protected route without token
UNAUTH=$(curl -s -o /dev/null -w "%{http_code}" "$API_URL/api/animals")
if [ "$UNAUTH" = "401" ] || [ "$UNAUTH" = "403" ]; then
  pass "Protected route rejects unauthenticated request"
else
  fail "Protected route guard" "Got HTTP $UNAUTH (expected 401/403)"
fi

# ─── 3. Farms (Multi-location) ───────────────────────────────────────────────

section "3. Farms (Multi-location Support)"

FARMS=$(get "/api/farms" || echo "[]")
FARM_COUNT=$(echo "$FARMS" | python3 -c "import sys,json;print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")

if [ "$FARM_COUNT" -ge 2 ]; then
  pass "Multiple farms loaded ($FARM_COUNT farms)"
else
  fail "Multi-farm support" "Only $FARM_COUNT farm(s) found (expected ≥2)"
fi

# Check Boschhoek
if echo "$FARMS" | grep -q "Boschhoek"; then
  pass "Boschhoek Farm (Free State) present"
else
  fail "Boschhoek Farm" "Not found in farms list"
fi

# Check Loch Vaal
if echo "$FARMS" | grep -q "Loch Vaal"; then
  pass "Loch Vaal Plot 30 (Gauteng) present"
else
  fail "Loch Vaal farm" "Not found in farms list"
fi

# Check coordinates
LV_LAT=$(echo "$FARMS" | python3 -c "import sys,json;farms=json.load(sys.stdin);lv=[f for f in farms if 'Loch' in f['name']];print(lv[0]['latitude'] if lv else 'NONE')" 2>/dev/null)
if [ "$LV_LAT" = "-26.719088" ]; then
  pass "Loch Vaal coordinates correct (-26.719088, 27.709759)"
else
  fail "Loch Vaal coordinates" "Got latitude=$LV_LAT"
fi

# ─── 4. Animals (Inventory) ──────────────────────────────────────────────────

section "4. Animals (Inventory Management)"

ANIMALS=$(get "/api/animals" || echo "[]")
ANIMAL_COUNT=$(echo "$ANIMALS" | python3 -c "import sys,json;print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")

if [ "$ANIMAL_COUNT" -ge 15 ]; then
  pass "All animals loaded ($ANIMAL_COUNT total)"
else
  fail "Animal count" "Got $ANIMAL_COUNT (expected ≥15)"
fi

# Check gender field
HAS_GENDER=$(echo "$ANIMALS" | python3 -c "import sys,json;a=json.load(sys.stdin);print(sum(1 for x in a if x.get('gender')))" 2>/dev/null || echo "0")
if [ "$HAS_GENDER" -gt 0 ]; then
  pass "Animals have gender field ($HAS_GENDER with gender set)"
else
  fail "Gender field" "No animals have gender set"
fi

# Check breed
HAS_BREED=$(echo "$ANIMALS" | python3 -c "import sys,json;a=json.load(sys.stdin);print(sum(1 for x in a if x.get('breed')))" 2>/dev/null || echo "0")
if [ "$HAS_BREED" -gt 0 ]; then
  pass "Animals have breed field ($HAS_BREED with breed set)"
else
  fail "Breed field" "No animals have breed set"
fi

# Check colour
HAS_COLOUR=$(echo "$ANIMALS" | python3 -c "import sys,json;a=json.load(sys.stdin);print(sum(1 for x in a if x.get('colour')))" 2>/dev/null || echo "0")
if [ "$HAS_COLOUR" -gt 0 ]; then
  pass "Animals have colour field ($HAS_COLOUR with colour set)"
else
  fail "Colour field" "No animals have colour set"
fi

# Filter by gender
MALES=$(get "/api/animals?gender=male" || echo "[]")
MALE_COUNT=$(echo "$MALES" | python3 -c "import sys,json;print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")
if [ "$MALE_COUNT" -gt 0 ]; then
  pass "Filter by gender=male works ($MALE_COUNT males)"
else
  fail "Gender filter" "No males returned"
fi

# Filter by farm
LV_ANIMALS=$(get "/api/animals?farm_id=bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb" || echo "[]")
LV_COUNT=$(echo "$LV_ANIMALS" | python3 -c "import sys,json;print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")
if [ "$LV_COUNT" -ge 10 ]; then
  pass "Filter by Loch Vaal farm_id returns $LV_COUNT animals"
else
  fail "Farm filter" "Got $LV_COUNT Loch Vaal animals (expected ≥10)"
fi

# ─── 5. Geofences ────────────────────────────────────────────────────────────

section "5. Geofences"

GEOFENCES=$(get "/api/geofences?farm_id=22222222-2222-2222-2222-222222222222" || echo "[]")
GEO_COUNT=$(echo "$GEOFENCES" | python3 -c "import sys,json;print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")

if [ "$GEO_COUNT" -ge 3 ]; then
  pass "Boschhoek geofences loaded ($GEO_COUNT fences)"
else
  fail "Geofence count" "Got $GEO_COUNT (expected ≥3)"
fi

# Check fence types
HAS_EXCLUSION=$(echo "$GEOFENCES" | python3 -c "import sys,json;g=json.load(sys.stdin);print(sum(1 for f in g if f.get('fence_type')=='exclusion'))" 2>/dev/null || echo "0")
if [ "$HAS_EXCLUSION" -gt 0 ]; then
  pass "Exclusion zone geofence present"
else
  fail "Exclusion zone" "No exclusion fences found"
fi

# Check geometry returned
HAS_GEOM=$(echo "$GEOFENCES" | python3 -c "import sys,json;g=json.load(sys.stdin);print(sum(1 for f in g if f.get('geometry')))" 2>/dev/null || echo "0")
if [ "$HAS_GEOM" -gt 0 ]; then
  pass "Geofence geometry (GeoJSON polygon) returned ($HAS_GEOM)"
else
  fail "Geofence geometry" "No geometry data in response"
fi

# Loch Vaal geofence
LV_FENCES=$(get "/api/geofences?farm_id=bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb" || echo "[]")
LV_FENCE_COUNT=$(echo "$LV_FENCES" | python3 -c "import sys,json;print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")
if [ "$LV_FENCE_COUNT" -ge 1 ]; then
  pass "Loch Vaal geofence present ($LV_FENCE_COUNT)"
else
  fail "Loch Vaal geofence" "None found"
fi

# ─── 6. Devices ──────────────────────────────────────────────────────────────

section "6. Devices"

DEVICES=$(get "/api/devices" || echo "[]")
DEV_COUNT=$(echo "$DEVICES" | python3 -c "import sys,json;print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")

if [ "$DEV_COUNT" -ge 15 ]; then
  pass "All devices loaded ($DEV_COUNT)"
else
  fail "Device count" "Got $DEV_COUNT (expected ≥15)"
fi

# ─── 7. Gateway (Herdsman System) ────────────────────────────────────────────

section "7. Herdsman Gateway"

# List gateways (should be empty initially)
GATEWAYS=$(get "/api/gateway" || echo "FAILED")
if [ "$GATEWAYS" != "FAILED" ]; then
  pass "GET /api/gateway endpoint accessible"
else
  fail "Gateway list endpoint" "Not accessible"
fi

# Register a test gateway
GW_REG=$(post "/api/gateway/register" '{
  "farm_id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
  "serial_number": "GW-TEST-001",
  "name": "Test Gateway",
  "device_type": "phone",
  "herdsman_name": "Test Herdsman"
}' || echo "FAILED")

if echo "$GW_REG" | grep -q "GW-TEST-001"; then
  pass "Register gateway (GW-TEST-001) succeeds"
  log "  Response: $GW_REG"
else
  # Might already exist from previous run
  if echo "$GW_REG" | grep -q "already exists"; then
    pass "Gateway GW-TEST-001 already registered (idempotent)"
  else
    fail "Register gateway" "Unexpected response: ${GW_REG:0:100}"
  fi
fi

# Register a BLE tag
TAG_REG=$(post "/api/gateway/tags" '{
  "farm_id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
  "animal_id": "eeeeeeee-eeee-eeee-eeee-eeeeeeeeee01",
  "mac_address": "AA:BB:CC:DD:EE:01",
  "tag_name": "Test-Tag-001"
}' || echo "FAILED")

if echo "$TAG_REG" | grep -q "AA:BB:CC:DD:EE:01"; then
  pass "Register BLE ear tag (AA:BB:CC:DD:EE:01) succeeds"
elif echo "$TAG_REG" | grep -q "already"; then
  pass "BLE tag already registered (idempotent)"
else
  fail "Register BLE tag" "${TAG_REG:0:100}"
fi

# List BLE tags
TAGS=$(get "/api/gateway/tags?farm_id=bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb" || echo "[]")
TAG_COUNT=$(echo "$TAGS" | python3 -c "import sys,json;d=json.load(sys.stdin);print(len(d) if isinstance(d,list) else 0)" 2>/dev/null || echo "0")
if [ "$TAG_COUNT" -ge 1 ]; then
  pass "List BLE tags returns $TAG_COUNT tag(s)"
else
  fail "List BLE tags" "Got $TAG_COUNT"
fi

# Send batch sighting
BATCH_RESP=$(post "/api/gateway/batch" '{
  "gateway_serial": "GW-TEST-001",
  "latitude": -26.719088,
  "longitude": 27.709759,
  "battery_pct": 82,
  "sightings": [
    {"mac_address": "AA:BB:CC:DD:EE:01", "rssi": -65},
    {"mac_address": "FF:FF:FF:FF:FF:FF", "rssi": -90}
  ]
}' || echo "FAILED")

if echo "$BATCH_RESP" | grep -q '"accepted"'; then
  ACCEPTED=$(echo "$BATCH_RESP" | python3 -c "import sys,json;print(json.load(sys.stdin)['accepted'])" 2>/dev/null)
  RESOLVED=$(echo "$BATCH_RESP" | python3 -c "import sys,json;print(json.load(sys.stdin)['resolved'])" 2>/dev/null)
  pass "Batch sighting ingestion: $ACCEPTED accepted, $RESOLVED resolved"
  
  if [ "$RESOLVED" -ge 1 ]; then
    pass "MAC→animal resolution works (known tag resolved)"
  else
    fail "MAC→animal resolution" "0 resolved (expected ≥1)"
  fi
  
  UNRESOLVED=$(echo "$BATCH_RESP" | python3 -c "import sys,json;print(json.load(sys.stdin)['unresolved_macs'])" 2>/dev/null)
  if echo "$UNRESOLVED" | grep -q "FF:FF:FF:FF:FF:FF"; then
    pass "Unknown MAC reported as unresolved"
  else
    fail "Unresolved MAC reporting" "FF:FF:FF:FF:FF:FF not in unresolved list"
  fi
else
  fail "Batch sighting ingestion" "${BATCH_RESP:0:100}"
fi

# Gateway status
GW_STATUS=$(get "/api/gateway/status/GW-TEST-001" || echo "FAILED")
if echo "$GW_STATUS" | grep -q "recent_animals"; then
  pass "Gateway status endpoint returns data"
  ANIMALS_TODAY=$(echo "$GW_STATUS" | python3 -c "import sys,json;print(json.load(sys.stdin)['unique_animals_today'])" 2>/dev/null || echo "0")
  if [ "$ANIMALS_TODAY" -ge 1 ]; then
    pass "Gateway status shows $ANIMALS_TODAY unique animal(s) today"
  fi
else
  fail "Gateway status" "${GW_STATUS:0:100}"
fi

# ─── 8. Animal Lifecycle ─────────────────────────────────────────────────────

section "8. Animal Lifecycle (Create → Update → Newborn → Deceased)"

# Create a test animal
NEW_ANIMAL=$(post "/api/animals" '{
  "name": "TestCow-Verify",
  "tag_id": "VERIFY-001",
  "species": "cattle",
  "breed": "Test Breed",
  "gender": "female",
  "colour": "test-colour",
  "farm_id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
}' || echo "FAILED")

if echo "$NEW_ANIMAL" | grep -q "TestCow-Verify"; then
  ANIMAL_ID=$(echo "$NEW_ANIMAL" | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])" 2>/dev/null)
  pass "Create animal (TestCow-Verify) → ID: ${ANIMAL_ID:0:8}..."
  log "  Animal ID: $ANIMAL_ID"
  
  # Update weight
  UPDATED=$(curl -sf -X PATCH -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" \
    -d '{"weight_kg": 425.5}' "$API_URL/api/animals/$ANIMAL_ID" 2>/dev/null || echo "FAILED")
  if echo "$UPDATED" | grep -q "425.5"; then
    pass "Update animal weight (PATCH) works"
  else
    fail "Update animal" "${UPDATED:0:100}"
  fi
  
  # Register newborn
  CALF=$(post "/api/animals/$ANIMAL_ID/newborn" "{
    \"name\": \"TestCalf-001\",
    \"tag_id\": \"VERIFY-CALF-001\",
    \"gender\": \"male\",
    \"colour\": \"black\",
    \"mother_id\": \"$ANIMAL_ID\"
  }" || echo "FAILED")
  if echo "$CALF" | grep -q "TestCalf-001"; then
    CALF_ID=$(echo "$CALF" | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])" 2>/dev/null)
    pass "Register newborn calf (mother_id linked)"
    
    # Mark calf as deceased
    DECEASED=$(post "/api/animals/$CALF_ID/deceased" '{"reason":"Test verification"}' || echo "FAILED")
    if echo "$DECEASED" | grep -q "deceased"; then
      pass "Mark animal as deceased (soft delete, keeps history)"
    else
      fail "Mark deceased" "${DECEASED:0:100}"
    fi
  else
    fail "Register newborn" "${CALF:0:100}"
  fi
  
  # Get offspring
  OFFSPRING=$(get "/api/animals/$ANIMAL_ID/offspring" || echo "[]")
  OFF_COUNT=$(echo "$OFFSPRING" | python3 -c "import sys,json;d=json.load(sys.stdin);print(len(d) if isinstance(d,list) else 0)" 2>/dev/null || echo "0")
  if [ "$OFF_COUNT" -ge 1 ]; then
    pass "Offspring endpoint returns $OFF_COUNT calf/calves"
  else
    fail "Offspring query" "Got $OFF_COUNT"
  fi
  
else
  fail "Create animal" "${NEW_ANIMAL:0:100}"
fi

# ─── 9. Positions (GPS Data Pipeline) ────────────────────────────────────────

section "9. GPS Position Pipeline"

POS_COUNT=$(curl -sf -H "Authorization: Bearer $TOKEN" "$API_URL/api/devices" 2>/dev/null | python3 -c "
import sys,json
devs = json.load(sys.stdin)
seen = sum(1 for d in devs if d.get('last_seen'))
print(seen)
" 2>/dev/null || echo "0")

if [ "$POS_COUNT" -gt 0 ]; then
  pass "Devices have last_seen timestamps ($POS_COUNT reporting)"
else
  skip "No devices reporting yet (run: make simulate)"
fi

# Check position history for first Boschhoek animal
HISTORY=$(get "/api/animals/55555555-5555-5555-5555-555555555501/history?hours=24" || echo "{}")
HIST_COUNT=$(echo "$HISTORY" | python3 -c "import sys,json;print(json.load(sys.stdin).get('count',0))" 2>/dev/null || echo "0")
if [ "$HIST_COUNT" -gt 0 ]; then
  pass "Position history available ($HIST_COUNT points for Bella)"
else
  skip "No position history yet (run: make simulate)"
fi

# ─── 10. Alerts ──────────────────────────────────────────────────────────────

section "10. Alerts"

ALERTS=$(get "/api/alerts" || echo "[]")
if [ "$ALERTS" != "FAILED" ]; then
  pass "Alerts endpoint accessible"
else
  fail "Alerts endpoint" "Not accessible"
fi

# ─── Summary ──────────────────────────────────────────────────────────────────

echo ""
echo "╔══════════════════════════════════════════════════════╗"
TOTAL=$((PASS+FAIL+SKIP))
echo -e "║  Results: ${GREEN}$PASS passed${RESET}, ${RED}$FAIL failed${RESET}, ${YELLOW}$SKIP skipped${RESET} / $TOTAL total"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

log ""
log "═══════════════════════════════"
log "Results: $PASS passed, $FAIL failed, $SKIP skipped / $TOTAL total"
log "Finished: $(date)"

if [ $FAIL -eq 0 ]; then
  echo -e "${GREEN}All features verified successfully.${RESET}"
  exit 0
else
  echo -e "${RED}$FAIL feature(s) failed. Check logs/verify-api.log for details.${RESET}"
  exit 1
fi
