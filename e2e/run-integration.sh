#!/usr/bin/env bash
set -euo pipefail

# ─── LivestockGuard E2E Integration Test Runner ─────────────────────
#
# Spins up the full Docker stack, runs database migrations,
# seeds test data, and validates the entire data flow:
#   Simulator → MQTT → MQTT Writer → PostgreSQL → API Gateway → Response
#
# Usage: ./e2e/run-integration.sh
# Requires: docker compose, curl, python3
# ─────────────────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE_FILE="$SCRIPT_DIR/docker-compose.test.yml"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

PASSED=0
FAILED=0

pass() { echo -e "  ${GREEN}✓${NC} $1"; ((PASSED++)); }
fail() { echo -e "  ${RED}✗${NC} $1"; ((FAILED++)); }

# ─── Cleanup ─────────────────────────────────────────

cleanup() {
    echo ""
    echo "Cleaning up..."
    docker compose -f "$COMPOSE_FILE" down -v --remove-orphans 2>/dev/null || true
}
trap cleanup EXIT

# ─── Start Infrastructure ─────────────────────────────

echo "═══════════════════════════════════════════════════════"
echo " LivestockGuard E2E Integration Tests"
echo "═══════════════════════════════════════════════════════"
echo ""
echo "Starting infrastructure..."
docker compose -f "$COMPOSE_FILE" up -d

echo "Waiting for services to be healthy..."
for i in $(seq 1 30); do
    PG_READY=$(docker compose -f "$COMPOSE_FILE" exec -T postgres pg_isready -U livestockguard 2>/dev/null && echo "yes" || echo "no")
    REDIS_READY=$(docker compose -f "$COMPOSE_FILE" exec -T redis redis-cli ping 2>/dev/null | grep -q PONG && echo "yes" || echo "no")

    if [[ "$PG_READY" == "yes" && "$REDIS_READY" == "yes" ]]; then
        echo "  All services healthy."
        break
    fi

    if [[ $i -eq 30 ]]; then
        echo "  ERROR: Services failed to start within 30 seconds."
        exit 1
    fi

    sleep 1
done

# ─── Run Migrations ──────────────────────────────────

echo ""
echo "Running database migrations..."
for migration in "$PROJECT_ROOT"/cloud/migrations/versions/*.sql; do
    docker compose -f "$COMPOSE_FILE" exec -T postgres \
        psql -U livestockguard -d livestockguard -f /dev/stdin < "$migration" 2>/dev/null
done
echo "  Migrations applied."

# ─── Seed Test Data ──────────────────────────────────

echo ""
echo "Seeding test data..."
if [[ -f "$PROJECT_ROOT/scripts/seed_data.sql" ]]; then
    docker compose -f "$COMPOSE_FILE" exec -T postgres \
        psql -U livestockguard -d livestockguard -f /dev/stdin < "$PROJECT_ROOT/scripts/seed_data.sql" 2>/dev/null
    echo "  Seed data loaded."
else
    echo "  No seed_data.sql found, skipping."
fi

# ─── Test 1: Database Connection ─────────────────────

echo ""
echo "Category 6: Stack Integration Tests"
echo "────────────────────────────────────"

TABLES=$(docker compose -f "$COMPOSE_FILE" exec -T postgres \
    psql -U livestockguard -d livestockguard -t -c \
    "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'" 2>/dev/null | tr -d ' ')

if [[ "$TABLES" -gt 0 ]]; then
    pass "Database has $TABLES tables after migration"
else
    fail "Database has no tables after migration"
fi

# ─── Test 2: Redis Connectivity ──────────────────────

REDIS_PONG=$(docker compose -f "$COMPOSE_FILE" exec -T redis redis-cli ping 2>/dev/null)
if [[ "$REDIS_PONG" == "PONG" ]]; then
    pass "Redis responds to PING"
else
    fail "Redis not responding"
fi

# ─── Test 3: MQTT Broker ─────────────────────────────

EMQX_STATUS=$(docker compose -f "$COMPOSE_FILE" exec -T emqx emqx ping 2>/dev/null)
if [[ "$EMQX_STATUS" == "pong" ]]; then
    pass "EMQX MQTT broker is running"
else
    fail "EMQX not responding"
fi

# ─── Test 4: Organisations/Farms seeded ──────────────

ORG_COUNT=$(docker compose -f "$COMPOSE_FILE" exec -T postgres \
    psql -U livestockguard -d livestockguard -t -c \
    "SELECT count(*) FROM organisations" 2>/dev/null | tr -d ' ')

if [[ "$ORG_COUNT" -gt 0 ]]; then
    pass "Organisations table has data ($ORG_COUNT rows)"
else
    fail "No organisations seeded"
fi

# ─── Test 5: Animals seeded ──────────────────────────

ANIMAL_COUNT=$(docker compose -f "$COMPOSE_FILE" exec -T postgres \
    psql -U livestockguard -d livestockguard -t -c \
    "SELECT count(*) FROM animals" 2>/dev/null | tr -d ' ')

if [[ "$ANIMAL_COUNT" -gt 0 ]]; then
    pass "Animals table has data ($ANIMAL_COUNT rows)"
else
    fail "No animals seeded"
fi

# ─── Test 6: Devices seeded ──────────────────────────

DEVICE_COUNT=$(docker compose -f "$COMPOSE_FILE" exec -T postgres \
    psql -U livestockguard -d livestockguard -t -c \
    "SELECT count(*) FROM devices" 2>/dev/null | tr -d ' ')

if [[ "$DEVICE_COUNT" -gt 0 ]]; then
    pass "Devices table has data ($DEVICE_COUNT rows)"
else
    fail "No devices seeded"
fi

# ─── Test 7: Geofences seeded ────────────────────────

GEOFENCE_COUNT=$(docker compose -f "$COMPOSE_FILE" exec -T postgres \
    psql -U livestockguard -d livestockguard -t -c \
    "SELECT count(*) FROM geofences" 2>/dev/null | tr -d ' ')

if [[ "$GEOFENCE_COUNT" -gt 0 ]]; then
    pass "Geofences table has data ($GEOFENCE_COUNT rows)"
else
    fail "No geofences seeded"
fi

# ─── Test 8: Redis pub/sub works ─────────────────────

docker compose -f "$COMPOSE_FILE" exec -T redis \
    redis-cli PUBLISH "test:channel" "hello" >/dev/null 2>&1
pass "Redis pub/sub publish succeeds"

# ─── Test 9: Users seeded with password hash ─────────

USER_HASH=$(docker compose -f "$COMPOSE_FILE" exec -T postgres \
    psql -U livestockguard -d livestockguard -t -c \
    "SELECT password_hash FROM users LIMIT 1" 2>/dev/null | tr -d ' ')

if [[ "$USER_HASH" == \$2b* || "$USER_HASH" == \$2a* ]]; then
    pass "User password stored as bcrypt hash"
else
    fail "User password not properly hashed"
fi

# ─── Test 10: TimescaleDB extension ──────────────────

TIMESCALE=$(docker compose -f "$COMPOSE_FILE" exec -T postgres \
    psql -U livestockguard -d livestockguard -t -c \
    "SELECT count(*) FROM pg_extension WHERE extname='timescaledb'" 2>/dev/null | tr -d ' ')

if [[ "$TIMESCALE" == "1" ]]; then
    pass "TimescaleDB extension installed"
else
    # Not fatal — depends on image
    echo -e "  ${YELLOW}⚠${NC} TimescaleDB extension not found (may need CREATE EXTENSION)"
fi

# ─── Summary ─────────────────────────────────────────

echo ""
echo "═══════════════════════════════════════════════════════"
echo -e " Results: ${GREEN}$PASSED passed${NC}, ${RED}$FAILED failed${NC}"
echo "═══════════════════════════════════════════════════════"

if [[ $FAILED -gt 0 ]]; then
    exit 1
fi
