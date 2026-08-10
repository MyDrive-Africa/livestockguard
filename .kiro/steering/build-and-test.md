# Build, Test & Run Commands

## Quick Reference

All commands use the Makefile. Run `make help` to see everything.

## Fresh Machine Setup

```bash
make setup              # Backend: Docker, Python venv, migrations, seeds DB
make setup-frontend     # Frontend: dashboard + mobile deps, native prerequisites, env files
```

### `make setup` (Backend — scripts/setup.sh)
1. Checks prerequisites (docker, node, npm, python3, pip3, git)
2. Creates Python venv for simulator (`tools/simulator/.venv`)
3. Installs dashboard npm deps
4. Starts Docker stack
5. Waits for PostgreSQL health check
6. Runs migrations (001_initial_schema.sql)
7. Creates `.env` with dev defaults

### `make setup-frontend` (Frontend — scripts/setup-frontend.sh)
1. Checks Node.js version (20+ required for mobile, 18+ for dashboard)
2. Installs dashboard deps (`npm install`) + TypeScript type check
3. Installs mobile deps (`npm install`) + verifies @react-native resolution
4. iOS prerequisites: Xcode + CocoaPods + `pod install`
5. Android prerequisites: SDK + JDK 17 + AVD + `local.properties`
6. Creates `.env` files for dashboard and mobile (API URLs)

Flags: `--web` (skip native), `--ios`, `--android`
Log: `logs/setup-frontend.log`

## Running the Platform

### Development Mode (No Simulators)

```bash
make dev                # Backend + Dashboard (:5173) + Mobile (:8082)
make dev-no-mobile      # Backend + Dashboard only
make dev-backend        # Backend infrastructure only (no frontends)
```

Use for coding or with real hardware. Add simulators manually:
```bash
make simulate           # GPS (Boschhoek)
make simulate-gateway   # BLE (Loch Vaal)
```

### Demo Mode (With Simulators + Detailed Logging)

```bash
make demo               # 3 farms, 65 animals, dashboard + mobile (breach scenario)
make demo-normal        # Normal day — cattle graze peacefully, no alerts
make demo-theft         # Theft scenario — LV-001 stolen at ~sim 10:00
make demo-no-mobile     # Full demo without mobile app
make demo-no-sim        # Backend + frontends, no simulators
```

`make demo` runs `scripts/run-all.sh` which:
1. Docker stack (Postgres, Redis, EMQX, API, MQTT Writer, Alert Engine)
2. Waits for PostgreSQL + Redis health
3. Applies all 12 migrations
4. Seeds 3 farms, 65 animals, geofences, gateways
5. Verifies API health
6. GPS simulator: Boschhoek (5 animals, binary MQTT)
7. BLE gateway: Sibanyoni (50 animals, herdsman day)
8. BLE gateway: Loch Vaal (10 animals, herdsman day + scenario)
9. Dashboard → http://localhost:5173
10. Mobile app → http://localhost:8082

Logs: `logs/run-all.log` (master) + `logs/run-all-*.log` (per service)
Stop: Ctrl+C (graceful cleanup)

### Manual Multi-Terminal

```bash
# Terminal 1: make start && make db-seed
# Terminal 2: make mqtt-writer
# Terminal 3: make simulate (or simulate-day, simulate-gateway, etc.)
# Terminal 4: make dashboard
```

## Starting Services

```bash
make start          # Docker stack (Postgres, Redis, EMQX, API, MQTT Writer, Alert Engine)
make stop           # Stop Docker stack
make restart        # Stop + start
make status         # Show container status
make logs           # Tail all Docker logs
make logs-api       # Tail API gateway only
make stop-all       # Kill sims, dashboard, mobile (Docker stays up)
```

## Database

```bash
make db-migrate     # Run SQL migrations
make db-seed        # Load 3 farms, 65 animals, geofences, gateways
make db-shell       # Interactive psql
make db-reset       # DESTROYS DATA — recreates everything from scratch
```

## Simulators

```bash
# GPS collar sims (binary MQTT protocol)
make simulate                    # Boschhoek, 5 animals, normal
make simulate-theft              # Theft scenario
make simulate-breach             # Geofence breach scenario

# BLE gateway sims (REST API batches)
make simulate-gateway            # Loch Vaal, 10 animals, real-time
make simulate-gateway-sibanyoni  # Sibanyoni, 50 animals, real-time
make simulate-day                # Full herdsman day, 12h in ~6min (Loch Vaal)
make simulate-day-sibanyoni      # Sibanyoni, 50 cattle, full day

# Scenarios
make simulate-day-theft          # Theft at sim 10:00 (Loch Vaal)
make simulate-day-breach         # Geofence breach (Loch Vaal)
make simulate-day-sibanyoni-theft    # Theft at Sibanyoni
make simulate-day-sibanyoni-breach   # Breach at Sibanyoni
make simulate-loop               # Continuous both farms (never stops)
```

## Dashboard

```bash
make dashboard          # Dev server at http://localhost:5173
make dashboard-install  # npm install
make dashboard-build    # Production build (tsc + vite build)
```

## Mobile App

```bash
make mobile-web       # Browser at http://localhost:8082
make mobile-ios       # iOS simulator (needs Xcode)
make mobile-android   # Android emulator (needs SDK + JDK 17)
```

## Testing

### Backend (Python)
```bash
# API Gateway (47+ tests, in-memory SQLite)
cd cloud/services/api_gateway
pip install -r requirements.txt -r requirements-test.txt
pytest -v

# Alert Engine
cd cloud/services/alert_engine
pip install -r requirements.txt -r requirements-test.txt
pytest -v

# MQTT Writer
cd cloud/services/mqtt_writer
pip install -r requirements.txt -r requirements-test.txt
pytest -v
```

### Rust
```bash
cd cloud/services/ingestion && cargo test --verbose
cd cloud/services/geofence_engine && cargo test --verbose
```

### Dashboard
```bash
cd dashboard && npx tsc --noEmit   # Type check
cd dashboard && npm run build       # Full build
```

### E2E (Playwright)
```bash
make verify-e2e    # Requires dashboard + stack running
```

### All at Once
```bash
make test           # Runs test-firmware + test-cloud + test-dashboard
make verify-all     # API verification + E2E tests
```

## Verification

```bash
make verify-api     # Hits API endpoints, checks responses
make verify-e2e     # Playwright browser tests
curl http://localhost:8000/health    # API health check
curl http://localhost:8000/docs      # Swagger UI
```

## URLs (Dev)

| Service | URL |
|---------|-----|
| API Gateway (Swagger) | http://localhost:8000/docs |
| Web Dashboard | http://localhost:5173 |
| Mobile App (web) | http://localhost:8082 |
| EMQX Dashboard | http://localhost:18083 (admin/public) |
| PostgreSQL | localhost:5432 (livestockguard/livestockguard_dev) |
| Redis | localhost:6379 |
| MQTT Broker | localhost:1883 |

## Demo Credentials

| Email | Password | Role | Farms |
|-------|----------|------|-------|
| africa.mydrive@gmail.com | demo123 | owner | All 3 |
| lochvaal@livestockguard.co.za | demo123 | owner | Loch Vaal only |
| sibanyoni@livestockguard.co.za | demo123 | owner | Sibanyoni only |

## CI Pipeline

GitHub Actions runs on push/PR to `main`:
1. **api-gateway-tests** — Python 3.12, pytest (in-memory SQLite)
2. **alert-engine-tests** — Python 3.12, pytest
3. **mqtt-writer-tests** — Python 3.12, pytest
4. **rust-tests** — cargo test (ingestion + geofence_engine)
5. **dashboard-build** — Node 20, tsc --noEmit + npm run build

All must pass for merge (ci-pass gate job).

## Prerequisites

| Tool | Version | macOS Install |
|------|---------|---------------|
| Docker + Compose | 24+ | `brew install colima docker docker-compose` then `colima start` |
| Node.js | 20 LTS (mobile requires 20, dashboard 18+) | `brew install node@20` or `fnm install 20` |
| Python | 3.10+ | `brew install python3` |
| Rust | stable | `curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs \| sh` |
| Git | any | `brew install git` |

### Optional (Native Mobile)

| Tool | Purpose | Install |
|------|---------|---------|
| Xcode 15+ | iOS simulator builds | Mac App Store |
| CocoaPods | iOS dependency manager | `sudo gem install cocoapods` |
| Android Studio + SDK 34 | Android emulator | [developer.android.com](https://developer.android.com/studio) |
| OpenJDK 17 | Android Gradle builds | `brew install openjdk@17` |
