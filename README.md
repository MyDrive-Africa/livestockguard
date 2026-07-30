# LivestockGuard

**GPS livestock tracking & geofencing platform for South African farmers.**

Real-time animal monitoring, virtual fencing, theft detection, and herd health — delivered through affordable GPS collars, BLE ear tags, and a cloud-connected dashboard with mobile app.

---

## Table of Contents

- [Quick Start (One Command)](#quick-start-one-command)
- [Prerequisites](#prerequisites)
- [First-Time Setup](#first-time-setup)
- [Running the Platform](#running-the-platform)
- [Demo Modes](#demo-modes)
- [All Make Targets](#all-make-targets)
- [System Architecture](#system-architecture)
- [Project Structure](#project-structure)
- [Key Features](#key-features)
- [Demo Credentials](#demo-credentials)
- [Testing](#testing)
- [Documentation](#documentation)
- [Tech Stack](#tech-stack)

---

## Quick Start (One Command)

```bash
# Clone and run the full platform demo in one shot:
git clone https://github.com/MyDrive-Africa/livestockguard.git
cd livestockguard
make setup        # installs everything, starts Docker, seeds DB
make demo         # launches full platform with breach scenario
```

Open **http://localhost:5173** — log in with `africa.mydrive@gmail.com` / `demo123`.

---

## Prerequisites

| Requirement | Version | Install (macOS) |
|-------------|---------|-----------------|
| Docker + Compose | 24+ | `brew install colima docker docker-compose` then `colima start` |
| Node.js | 18+ | `brew install node` |
| Python | 3.10+ | `brew install python3` |
| Git | any | `brew install git` |

> **Colima users:** Link the Compose plugin so `docker compose` (v2) works:
> ```bash
> mkdir -p ~/.docker/cli-plugins
> ln -sfn /opt/homebrew/opt/docker-compose/bin/docker-compose ~/.docker/cli-plugins/docker-compose
> ```

> **Docker Desktop users:** No extra config needed — just ensure Docker is running.

### Optional (for mobile app)

| Requirement | Purpose | Install |
|-------------|---------|---------|
| Expo CLI | React Native mobile builds | `npm install -g expo-cli` |
| Xcode 15+ | iOS simulator builds | Mac App Store |
| Android Studio + SDK | Android emulator builds | [developer.android.com](https://developer.android.com/studio) |
| OpenJDK 17 | Android Gradle builds | `brew install openjdk@17` |

---

## First-Time Setup

```bash
make setup
```

This single command runs `scripts/setup.sh` which:

1. **Checks prerequisites** — verifies docker, node, npm, python3, pip3, git are installed
2. **Creates Python venv** — installs simulator dependencies (`paho-mqtt`, `click`) in `tools/simulator/.venv`
3. **Installs dashboard deps** — runs `npm install` in `dashboard/`
4. **Starts Docker stack** — pulls and starts PostgreSQL/TimescaleDB, Redis, EMQX
5. **Waits for PostgreSQL** — health-checks until DB is accepting connections
6. **Runs migrations** — applies `001_initial_schema.sql` (tables, hypertables, indexes)
7. **Creates `.env`** — generates a dev `.env` with sensible defaults

After setup completes, you're ready to run everything.

---

## Running the Platform

### Option A: Full Demo (Recommended for first time)

```bash
make demo           # Breach scenario — a cow escapes the geofence
make demo-normal    # Normal day — no incidents
make demo-theft     # Theft scenario — a cow is loaded onto a vehicle
make demo-mobile    # Breach + mobile app in browser (port 8082)
make demo-ios       # Breach + iOS simulator build
make demo-android   # Breach + Android emulator build
```

`make demo` starts **everything** automatically:
1. Docker infrastructure (Postgres, Redis, EMQX, API, MQTT Writer)
2. Seeds database (3 farms, 65 animals, 10+ geofences, gateways, BLE tags)
3. Applies all migrations
4. GPS simulator (Boschhoek Farm, 5 animals, real-time)
5. BLE gateway simulator (Loch Vaal, 10 animals, full herdsman day at 20x speed)
6. Web dashboard on http://localhost:5173
7. (Optional) Mobile app on http://localhost:8082

Stop with **Ctrl+C** — kills all background processes cleanly.

---

### Option B: Manual Multi-Terminal (Full Control)

Best when developing — each process in its own terminal for easy restart/debug.

```bash
# Terminal 1: Cloud infrastructure
make start            # Docker stack (Postgres, Redis, EMQX, API Gateway, MQTT Writer, Alert Engine)
make db-seed          # Load demo farms (Boschhoek + Loch Vaal + Sibanyoni)

# Terminal 2: MQTT → Database bridge (required for simulator data to reach the DB)
make mqtt-writer

# Terminal 3: Device simulator (pick one)
make simulate              # Boschhoek, 5 GPS-collared cows, normal grazing
make simulate-lochvaal     # Loch Vaal, 10 animals, GPS mode
make simulate-sibanyoni    # Sibanyoni, 50 animals, GPS mode

# Terminal 4: Web dashboard
make dashboard        # React dev server at http://localhost:5173
```

### Option C: Full Dev Stack (start + instructions)

```bash
make dev
```

Starts Docker, then prints the terminal commands for you to run manually.

---

## Verifying Everything Works

```bash
# Check all containers are running
make status

# Hit the API health endpoint
curl http://localhost:8000/health

# List animals from API
curl http://localhost:8000/api/animals

# List devices
curl http://localhost:8000/api/devices

# Open dashboard in browser
open http://localhost:5173

# Open EMQX MQTT broker dashboard
open http://localhost:18083    # admin / public

# Open API Swagger docs
open http://localhost:8000/docs
```

---

## Demo Modes

### GPS Simulator Scenarios (Boschhoek Farm — Free State)

Uses binary MQTT protocol (CRC-16 verified) simulating real GPS collar hardware.

| Command | What Happens |
|---------|-------------|
| `make simulate` | 5 cows grazing normally, positions every 10s |
| `make simulate-theft` | One cow loaded onto a vehicle, speed triggers theft alert |
| `make simulate-breach` | One cow exits the geofence polygon, breach alert fires |
| `make simulate-many` | 50 animals stress test (Loch Vaal), 15s interval |

### BLE Gateway Simulator Scenarios (Loch Vaal Plot 30 — Gauteng)

Simulates a herdsman carrying a phone/gateway through a realistic daily routine.

| Command | What Happens |
|---------|-------------|
| `make simulate-gateway` | Real-time BLE gateway scan + API batch posting |
| `make simulate-gateway-offline` | Same but prints output only (no API calls) |
| `make simulate-day` | Full 12-hour herdsman day compressed to ~6 min (speed 120x) |
| `make simulate-day-offline` | Full day without API calls |
| `make simulate-day-theft` | Theft at sim 10:00 — cow taken 5km away (speed 360x) |
| `make simulate-day-breach` | Geofence breach — cow exits 100m BLE range |

### Sibanyoni Farm Simulator (North West — 50 cattle)

Dedicated large-herd simulator with its own daily routine script.

| Command | What Happens |
|---------|-------------|
| `make simulate-sibanyoni` | GPS simulator: 50 animals at Sibanyoni Farm, 10s interval |
| `make simulate-gateway-sibanyoni` | BLE gateway: 50 ear tags, real-time scan + batch |
| `make simulate-day-sibanyoni` | Full herdsman day: 50 cattle, 12h in ~6 min (speed 120x) |
| `make simulate-day-sibanyoni-theft` | Theft scenario at Sibanyoni (speed 360x) |
| `make simulate-day-sibanyoni-breach` | Breach scenario at Sibanyoni (speed 360x) |

### Daily Routine (BLE Simulator)

The `gateway_daily_sim.py` follows a real Loch Vaal schedule:

```
Night:     Cattle in kraal
08:30:     Kraal gate opens → cattle to feeding troughs
09:20:     Walk to Entrance/Exit gate, exit yard
09:50:     Herdsman leads herd via roads to grazing area
12:00:     Midday rest
13:00:     Afternoon grazing
16:30:     Return via road to gate
17:00:     Enter gate, water stop at troughs
17:45:     Walk to kraal, settle for night
```

---

## All Make Targets

Run `make help` to see all available commands. Full reference:

### Setup & Infrastructure

| Target | Description |
|--------|-------------|
| `make setup` | First-time setup — installs everything, starts Docker, runs migrations |
| `make start` | Start cloud stack (PostgreSQL, Redis, EMQX, API Gateway, MQTT Writer, Alert Engine) |
| `make stop` | Stop cloud Docker stack |
| `make restart` | Stop + start |
| `make status` | Show running container status |
| `make logs` | Tail logs from all Docker services |
| `make logs-api` | Tail API gateway logs only |
| `make clean` | Stop everything, remove Docker volumes, delete node_modules |
| `make stop-all` | Kill simulators, dashboard, mobile processes (Docker stays running) |

### Database

| Target | Description |
|--------|-------------|
| `make db-migrate` | Run SQL migrations (initial schema) |
| `make db-seed` | Load demo farm data: Boschhoek (5 animals) + Loch Vaal (10 animals) + Sibanyoni (50 animals) |
| `make db-shell` | Open interactive PostgreSQL CLI |
| `make db-reset` | **DESTROYS all data** — drops volumes, recreates, re-seeds |

### Simulators

| Target | Description |
|--------|-------------|
| `make simulate` | GPS simulator: Boschhoek, 5 animals, 10s interval |
| `make simulate-lochvaal` | GPS simulator: Loch Vaal, 10 animals, 10s interval |
| `make simulate-sibanyoni` | GPS simulator: Sibanyoni Farm, 50 animals, 10s interval |
| `make simulate-theft` | GPS theft scenario (vehicle speed detected) |
| `make simulate-breach` | GPS geofence breach scenario |
| `make simulate-many` | GPS stress test: 50 animals at Loch Vaal |
| `make simulate-gateway` | BLE gateway: Loch Vaal, 10 animals, real-time |
| `make simulate-gateway-sibanyoni` | BLE gateway: Sibanyoni, 50 animals, real-time |
| `make simulate-gateway-offline` | BLE gateway: print only, no API |
| `make simulate-day` | BLE full day: Loch Vaal, 12h in ~6 min (speed 120x) |
| `make simulate-day-sibanyoni` | BLE full day: Sibanyoni, 50 cattle, 12h in ~6 min |
| `make simulate-day-sibanyoni-theft` | Sibanyoni theft scenario (speed 360x) |
| `make simulate-day-sibanyoni-breach` | Sibanyoni breach scenario (speed 360x) |
| `make simulate-day-offline` | BLE full day: offline mode |
| `make simulate-day-theft` | BLE theft scenario at 10:00 (Loch Vaal, speed 360x) |
| `make simulate-day-breach` | BLE geofence breach (Loch Vaal, speed 360x) |

### Dashboard & Mobile

| Target | Description |
|--------|-------------|
| `make dashboard` | Start web dashboard dev server (http://localhost:5173) |
| `make dashboard-install` | Install dashboard npm dependencies |
| `make dashboard-build` | Production build (TypeScript check + Vite build) |
| `make mobile-web` | Start mobile app in browser (http://localhost:8082) |
| `make mobile-ios` | Build + launch on iOS simulator |
| `make mobile-android` | Build + launch on Android emulator |
| `make mqtt-writer` | Start MQTT→DB bridge (standalone, outside Docker) |

### Full Demo

| Target | Description |
|--------|-------------|
| `make dev` | Start Docker stack + print instructions for other terminals |
| `make demo` | Full live demo with breach scenario |
| `make demo-normal` | Full demo, normal day (no incidents) |
| `make demo-theft` | Full demo with theft scenario |
| `make demo-mobile` | Full demo + mobile app in browser |
| `make demo-ios` | Full demo + iOS simulator build |
| `make demo-android` | Full demo + Android emulator build |

### Testing & Verification

| Target | Description |
|--------|-------------|
| `make test` | Run all tests (firmware, cloud, dashboard) |
| `make test-firmware` | Firmware unit tests (requires Unity framework) |
| `make test-cloud` | Python backend tests (pytest) |
| `make test-dashboard` | Dashboard tests |
| `make verify-api` | API feature verification script (requires stack running) |
| `make verify-e2e` | Playwright E2E browser tests (requires dashboard + stack) |
| `make verify-all` | Run all verification (API + E2E) |

---

## System Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  MOBILE APP (React Native + Expo)                                            │
│  iOS + Android + Web (port 8082)                                             │
│  Admin mode: native map (cow emojis, geofence polygons, trails, type switch) │
│  Herdsman mode: BLE scan, GPS track, cattle count, offline buffer            │
└──────────────────────┬───────────────────────────────────────────────────────┘
                       │
┌──────────────────────┼───────────────────────────────────────────────────────┐
│  WEB DASHBOARD       │   (React + MapLibre GL)       http://localhost:5173   │
│  - Live map with animal markers + movement trails (date picker)              │
│  - Geofence polygon overlays + draw tools (live area calculator)             │
│  - Real-time breach alert markers (red pulsing) on map                       │
│  - Analytics (Recharts: area, line, bar, donut, sparklines)                  │
│  - Dark/Light/System theme toggle                                            │
│  - Animated UI (framer-motion transitions)                                   │
│  - Alerts, Devices, Animals, Geofences, Gateway management                  │
└──────────────────────┬───────────────────────────────────────────────────────┘
                       │ REST API + WebSocket
                       ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  CLOUD BACKEND                                    http://localhost:8000       │
│  ┌─────────────────┐  ┌──────────────────┐  ┌─────────────────────────────┐ │
│  │  API Gateway     │  │  MQTT Writer     │  │  Alert Engine               │ │
│  │  (FastAPI)       │  │  (Python)        │  │  (Python)                   │ │
│  │  REST + WS       │  │  Binary decode   │  │  SES, FCM, Webhook, Redis   │ │
│  │  JWT auth        │  │  MQTT → Postgres │  │  SMS (Africa's Talking)     │ │
│  └─────────────────┘  └──────────────────┘  └─────────────────────────────┘ │
│  ┌─────────────────┐  ┌──────────────────┐                                  │
│  │  Ingestion       │  │  Geofence Engine │  (Rust services — compiled but  │
│  │  (Rust/Tokio)    │  │  (Rust)          │   not in Docker dev stack yet)  │
│  │  5000 msg/sec    │  │  R-tree spatial  │                                  │
│  └─────────────────┘  └──────────────────┘                                  │
└──────────────────────┬───────────────────────────────────────────────────────┘
                       │ SQL / MQTT / Redis pub/sub
                       ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  INFRASTRUCTURE (Docker Compose)                                             │
│  ┌───────────────────────┐  ┌────────────┐  ┌───────────────────────────┐   │
│  │  PostgreSQL 16         │  │  Redis 7   │  │  EMQX 5.5 (MQTT Broker)  │   │
│  │  + TimescaleDB         │  │  (Alpine)  │  │  Port 1883 (MQTT)        │   │
│  │  Port 5432             │  │  Port 6379 │  │  Port 18083 (Dashboard)  │   │
│  └───────────────────────┘  └────────────┘  └───────────────────────────┘   │
└──────────────────────┬───────────────────────────────────────────────────────┘
                       │ MQTT binary protocol / HTTPS REST
                       ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  DEVICES / SIMULATORS                                                        │
│  ┌────────────────────────────┐  ┌──────────────────────────────────────┐   │
│  │  GPS Collar Simulator      │  │  BLE Gateway Simulator               │   │
│  │  (simulator.py)            │  │  (gateway_daily_sim.py)              │   │
│  │  Binary MQTT, CRC-16       │  │  REST API batch, RSSI distance      │   │
│  │  Boschhoek Farm            │  │  Loch Vaal Plot 30                   │   │
│  └────────────────────────────┘  └──────────────────────────────────────┘   │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │  Real Hardware (Production)                                            │  │
│  │  nRF9160 (GPS collar) + nRF52840 (BLE ear tag) — C11/Zephyr firmware  │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Project Structure

```
livestockguard/
├── Makefile                    # All development commands (make help)
├── README.md                   # This file
├── .github/workflows/ci.yml    # GitHub Actions CI pipeline
│
├── scripts/
│   ├── setup.sh                # First-time environment setup
│   ├── run-demo.sh             # Full platform demo launcher
│   ├── seed_data.sql           # Demo farm data (3 farms, 65 animals, devices, geofences)
│   ├── register_ble_tags.py    # Register BLE ear tags via API
│   └── verify-features.sh     # API feature verification
│
├── cloud/                      # Cloud backend (Docker Compose)
│   ├── docker-compose.yml      # Infrastructure definition
│   ├── .env.example            # Environment variable template
│   ├── config/                 # Firebase credentials (not committed)
│   ├── migrations/versions/    # SQL schema migrations (001–009)
│   └── services/
│       ├── api_gateway/        # FastAPI REST + WebSocket (Python)
│       ├── mqtt_writer/        # MQTT → TimescaleDB bridge (Python)
│       ├── alert_engine/       # Multi-channel notification dispatch (Python)
│       ├── ingestion/          # Binary protocol decoder (Rust)
│       └── geofence_engine/    # Spatial breach detection (Rust)
│
├── dashboard/                  # Web application (React + Vite)
│   ├── src/
│   │   ├── pages/              # Map, Animals, Alerts, Analytics, Devices, Geofences, Gateway
│   │   ├── stores/             # Zustand (auth, map, realtime, theme)
│   │   ├── hooks/              # WebSocket, API query hooks
│   │   ├── components/         # ThemeToggle, layout, motion animations
│   │   ├── api/                # Axios API client layer
│   │   └── types/              # TypeScript interfaces
│   └── package.json
│
├── mobile/                     # Mobile app (React Native + Expo)
│   ├── App.tsx                 # Entry point
│   ├── src/
│   │   ├── screens/            # Login, AdminDashboard, HerdsmanScreen, Map, Animals
│   │   ├── components/         # Shared UI components
│   │   ├── navigation/         # React Navigation stack
│   │   ├── services/           # API client, BLE scanner, background tasks
│   │   ├── stores/             # State management
│   │   └── utils/              # Helpers
│   └── package.json
│
├── firmware/                   # Embedded C firmware (nRF hardware)
│   ├── CMakeLists.txt          # Build system
│   ├── hal/include/            # Hardware Abstraction Layer (gnss, radio, accel, power)
│   ├── src/
│   │   ├── main.c              # Application entry
│   │   ├── services/           # comms, gnss, power, sensor, config services
│   │   └── app/                # Application state machine
│   ├── lib/                    # Shared libraries
│   │   ├── geofence/           # On-device point-in-polygon
│   │   ├── protocol/           # Binary wire protocol encoder
│   │   └── collections/        # Ring buffer, linked list
│   └── platforms/
│       ├── nrf9160_collar/     # GPS collar (LTE-M/NB-IoT cellular)
│       └── nrf52840_eartag/    # BLE ear tag (passive beacon)
│
├── tools/simulator/            # Device simulators (Python)
│   ├── simulator.py            # GPS collar sim (binary MQTT protocol)
│   ├── gateway_simulator.py    # BLE gateway sim (REST API batches)
│   ├── gateway_daily_sim.py    # Full herdsman day sim — Loch Vaal schedule
│   ├── sibanyoni_daily_sim.py  # Full herdsman day sim — Sibanyoni Farm (50 cattle)
│   └── requirements.txt        # paho-mqtt, click
│
├── e2e/                        # End-to-end tests
│   ├── playwright.config.ts    # Playwright configuration
│   ├── tests/                  # Feature specs
│   └── run-integration.sh      # Integration test runner
│
├── docs/                       # Specifications & design documents
│   ├── SYSTEM_OVERVIEW.md      # Full architecture reference
│   ├── FIRMWARE_SPEC.md        # Embedded design, HAL, state machine
│   ├── CLOUD_BACKEND_SPEC.md   # Microservices, DB schema, API contracts
│   ├── DASHBOARD_SPEC.md       # React app pages, state, components
│   ├── CONNECTIVITY_SPEC.md    # Protocols, fallback, compression
│   ├── DEPLOYMENT_SPEC.md      # SA compliance, pricing, go-to-market
│   ├── MOBILE_APP_SPEC.md      # React Native app, BLE scanning, roles
│   ├── HERDSMAN_GATEWAY_SPEC.md # BLE ear tag gateway architecture
│   └── PLAN_NEXT_FEATURES.md   # Roadmap
│
└── logs/                       # Runtime logs (gitignored)
```

---

## Key Features

| Feature | Status | How to See It |
|---------|--------|---------------|
| Real-time GPS tracking | ✅ Live | `make simulate` → positions on map every 10s |
| Theft detection (vehicle speed) | ✅ Live | `make simulate-theft` → "THEFT ALERT" in logs + DB |
| Geofence breach alerts | ✅ Live | `make simulate-breach` → "GEOFENCE BREACH" in logs + DB |
| BLE ear tag tracking (gateway) | ✅ Live | `make simulate-day` → full herdsman day, cattle on map |
| BLE geofence breach detection | ✅ Live | `make simulate-day-breach` → breach alert from BLE batch |
| Web dashboard with live map | ✅ Live | `make dashboard` → MapLibre GL, animal markers, trails |
| Geofence polygon overlays | ✅ Live | 10+ polygons visible (paddocks, kraals, exclusion zones) |
| Geofence area display (PostGIS) | ✅ Live | Labels show "TheKraal · 705 m²", "Yard · 4.4 ha" on map |
| Redraw geofence from map | ✅ Live | Geofences page → Redraw button → click new polygon |
| Live area calculator (draw tool) | ✅ Live | While drawing, see area in m²/ha with colour-coded feedback |
| Satellite/terrain tile switching | ✅ Live | Street / Satellite / Terrain toggle on map |
| Farm coordinate pin marker | ✅ Live | 📍 pin at exact farm centre with name + coordinate readout, moves when switching farms |
| Daily trail date picker | ✅ Live | Click cow → trail → pick any date to see that day's route |
| Real-time breach alerts on map | ✅ Live | Red pulsing markers at alert locations, click for details |
| JWT authentication | ✅ Live | Login flow with bcrypt + JWT, protected routes |
| REST API (CRUD all entities) | ✅ Live | FastAPI Swagger at http://localhost:8000/docs |
| Add animal form (with BLE link) | ✅ Live | Animals page → Add → auto-registers BLE tag |
| Admin user management | ✅ Live | CRUD users, change passwords, assign roles |
| Farm schedule config | ✅ Live | Admin sets kraal open/close, feed times |
| Edit herdsman credentials | ✅ Live | Gateway page → edit name, phone on each gateway card |
| Mobile app (iOS + Android + Web) | ✅ Live | `make mobile-web` → admin + herdsman modes |
| Mobile native map (Google Maps) | ✅ Live | Cow emoji markers, geofence polygons, trails, map type switcher |
| Mobile interactive geofences | ✅ Live | Tap polygon to select/highlight, layer panel to show/hide |
| Mobile BLE scanner service | ✅ Live | Herdsman screen: simulated BLE scan, cattle count |
| Mobile offline buffer | ✅ Live | Stores sightings in AsyncStorage, syncs on reconnect |
| Movement trail visualisation | ✅ Built | Click marker → 24h trail from history endpoint |
| Geofence drawing tools | ✅ Built | Click-to-draw polygon, undo last point, finish/cancel |
| Dark/Light/System theme | ✅ Built | Zustand store + Tailwind dark mode, persists in localStorage |
| Animated UI (framer-motion) | ✅ Built | Page transitions, stagger cards, pulse badges |
| Analytics (Recharts) | ✅ Built | Area/line/bar/donut charts, sparklines, date range picker |
| Real-time WebSocket feed | ✅ Built | MQTT Writer → Redis pub/sub → API `/ws` → dashboard |
| Alert dispatchers (SES, FCM, Webhook) | ✅ Built | Alert engine with email, push, webhook, Redis, SMS |
| Herdsman patrol tracking | ✅ Built | Sessions API: start/end shift, distance, animals seen |
| BLE RSSI distance estimation | ✅ Built | Log-distance path loss model in gateway sim |
| On-device geofencing (point-in-polygon) | 📄 Firmware | C implementation in firmware/lib/geofence/ |
| Multi-protocol connectivity | 📄 Architecture | HAL interfaces for LTE-M, NB-IoT, LoRaWAN, BLE, Satellite |
| Activity classification (health) | 📄 Firmware | Accelerometer-based algorithm in firmware |
| Virtual fencing deterrents | 🔧 Scaffold | Audio/vibration trigger points defined |
| OTA firmware updates | 🔧 Scaffold | Module skeleton in firmware |

**Legend:** ✅ Live = works in local dev | ✅ Built = code complete, needs conditions | 📄 = code present, needs hardware | 🔧 = scaffold only

---

## Demo Credentials

After `make db-seed`, log into the dashboard at **http://localhost:5173**:

| Field | Value |
|-------|-------|
| Email | `africa.mydrive@gmail.com` |
| Password | `demo123` |
| Farms | Boschhoek (Free State) + Loch Vaal Plot 30 (Gauteng) |
| Animals | Bella, Storm, Thunder, Daisy, Rosie (Boschhoek) + 10 BLE-tagged (Loch Vaal) |

| Field | Value |
|-------|-------|
| Email | `sibanyoni@livestockguard.co.za` |
| Password | `demo123` |
| Farm | Sibanyoni Farm (North West, Lichtenburg) |
| Animals | 50 cattle (SB-001 to SB-050) — Nguni, Bonsmara, Brahman mix |

EMQX MQTT broker dashboard at **http://localhost:18083**:

| Field | Value |
|-------|-------|
| Username | `admin` |
| Password | `public` |

---

## Testing

### Backend (API Gateway — 47+ pytest cases)

```bash
cd cloud/services/api_gateway
pip install -r requirements.txt -r requirements-test.txt
pytest -v
```

Tests use in-memory SQLite — no Docker needed. Covers:
- Auth: login, register, refresh token, password hashing
- Animals: CRUD, filtering, pagination, search
- Alerts: listing, acknowledge, resolve state transitions
- Devices: listing, detail, command queuing
- Geofences: CRUD, geometry validation, active/inactive filtering
- Analytics: endpoint structure validation
- WebSocket: token verification

### Alert Engine

```bash
cd cloud/services/alert_engine
pip install -r requirements.txt -r requirements-test.txt
pytest -v
```

### MQTT Writer

```bash
cd cloud/services/mqtt_writer
pip install -r requirements.txt -r requirements-test.txt
pytest -v
```

### Dashboard (TypeScript)

```bash
cd dashboard
npm install
npx tsc --noEmit      # Type check
npm run build         # Full production build
```

### E2E (Playwright)

```bash
# Requires: stack running + dashboard running
make verify-e2e
```

### CI Pipeline (GitHub Actions)

Runs automatically on push/PR to `main`:
- Python: API Gateway tests, Alert Engine tests, MQTT Writer tests
- Rust: Ingestion service tests, Geofence engine tests
- TypeScript: Dashboard type check + build

---

## Documentation

| Document | Description |
|----------|-------------|
| [System Overview](docs/SYSTEM_OVERVIEW.md) | Complete architecture, data flow, all services, tech stack |
| [Firmware Spec](docs/FIRMWARE_SPEC.md) | Embedded C design, HAL, state machine, power management |
| [Cloud Backend Spec](docs/CLOUD_BACKEND_SPEC.md) | Microservices, DB schema, API contracts |
| [Dashboard Spec](docs/DASHBOARD_SPEC.md) | React app, pages, state management, animations |
| [Mobile App Spec](docs/MOBILE_APP_SPEC.md) | React Native app, admin/herdsman modes, BLE scanning |
| [Herdsman Gateway Spec](docs/HERDSMAN_GATEWAY_SPEC.md) | BLE ear tag architecture, RSSI, cost comparison |
| [Connectivity Spec](docs/CONNECTIVITY_SPEC.md) | Protocols, fallback, compression, duty cycling |
| [Deployment Spec](docs/DEPLOYMENT_SPEC.md) | SA compliance (POPIA, ICASA), pricing, go-to-market |

---

## Tech Stack

| Layer | Technologies |
|-------|-------------|
| Firmware | C11, Zephyr RTOS, nRF Connect SDK, CMake |
| Cloud Backend | Python 3.12 (FastAPI, SQLAlchemy, asyncpg), Rust (Tokio, Axum) |
| Database | PostgreSQL 16 + TimescaleDB (time-series), Redis 7 (cache/pub-sub) |
| Messaging | EMQX 5.5 (MQTT 5.0 broker), Redis Streams |
| Web Dashboard | React 18, TypeScript, Vite, MapLibre GL JS, TailwindCSS, Zustand, Recharts, Framer Motion |
| Mobile App | React Native, Expo 51, React Native Maps, AsyncStorage |
| Protocols | MQTT 5.0 (binary), REST/JSON, WebSocket, BLE 5.0 |
| Infrastructure | Docker Compose, AWS af-south-1 (production), GitHub Actions CI |
| Hardware | nRF9160 (cellular GPS collar), nRF52840 (BLE ear tag), ESP32-S3 (gateway option) |

---

## Environment Variables

Copy `cloud/.env.example` to `cloud/.env` for production config:

| Variable | Default (Dev) | Purpose |
|----------|---------------|---------|
| `POSTGRES_PASSWORD` | `livestockguard_dev` | Database password |
| `JWT_SECRET` | `dev_secret_change_in_production` | JWT signing key |
| `AWS_REGION` | `af-south-1` | AWS region for SES email |
| `SES_SENDER_EMAIL` | `alerts@livestockguard.co.za` | Email sender address |
| `ALERT_EMAIL_RECIPIENTS` | (empty) | Comma-separated alert emails |
| `FIREBASE_CREDENTIALS_FILE` | `./config/firebase-credentials.json` | FCM push notifications |
| `WEBHOOK_URLS` | (empty) | Comma-separated webhook endpoints |

---

## Ports Reference

| Port | Service |
|------|---------|
| 5173 | Web Dashboard (Vite dev server) |
| 8000 | API Gateway (FastAPI) |
| 8082 | Mobile App (Expo Web) |
| 1883 | MQTT Broker (EMQX) |
| 8883 | MQTT over TLS (EMQX) |
| 18083 | EMQX Management Dashboard |
| 5432 | PostgreSQL + TimescaleDB |
| 6379 | Redis |

---

## GPS Coordinates & Map Markers

All coordinates are WGS84 (EPSG:4326). Paste into Google Maps or view on the dashboard.

### Farm Centres

| Farm | Lat, Lon | Simulator |
|------|----------|-----------|
| Boschhoek Farm (Free State) | `-29.120000, 26.210000` | `make simulate` |
| Loch Vaal Plot 30 (Gauteng) | `-26.719088, 27.709759` | `make simulate-day` |
| Sibanyoni Farm (North West) | `-25.358056, 25.361275` | `--farm sibanyoni` |

### Loch Vaal Key Points

| Landmark | Coordinates | What It Is |
|----------|-------------|------------|
| Kraal | `-26.719000, 27.708830` | Night enclosure (15m radius) |
| Feeding Troughs | `-26.719000, 27.709300` | Morning feed / evening water (20m radius) |
| Entrance Gate | `-26.718910, 27.709940` | Only exit from yard |
| Road Intersection | `-26.718000, 27.711000` | Branch to grazing areas |
| North Grazing | `-26.715500, 27.709500` | Along Barrage Road |
| East Riverside | `-26.719000, 27.713500` | Near river |
| South Pasture | `-26.722000, 27.709500` | Past boundary road |
| West Clearing | `-26.718500, 27.706000` | Along dirt track |

### Geofence Zones (Loch Vaal)

| Zone | Breach Severity | Coordinates (NW → SE) |
|------|----------------|----------------------|
| Kraal | Critical | `-26.71879, 27.70926` → `-26.71939, 27.71026` |
| Yard (2ha) | High | `-26.71809, 27.70876` → `-26.72009, 27.71076` |
| 100km Range | Medium | `-25.819, 26.610` → `-27.619, 28.810` |
| Dam (exclusion) | High | `-26.71940, 27.70940` → `-26.71980, 27.70990` |

### Geofence Zones (Boschhoek)

| Zone | Type | Coordinates (NW → SE) |
|------|------|----------------------|
| Paddock North | Inclusion | `-29.110, 26.200` → `-29.125, 26.220` |
| Paddock South | Inclusion | `-29.125, 26.200` → `-29.140, 26.220` |
| Dam | Exclusion | `-29.118, 26.208` → `-29.122, 26.212` |

### BLE Animal MACs (Loch Vaal)

| Animal | MAC Address | Start Position |
|--------|-------------|---------------|
| LV-001 | `A1:B2:C3:D4:E5:01` | Kraal (-26.719, 27.70883) |
| LV-002 | `A1:B2:C3:D4:E5:02` | Kraal |
| LV-003 | `A1:B2:C3:D4:E5:03` | Kraal |
| LV-004 | `A1:B2:C3:D4:E5:04` | Kraal |
| LV-005 | `A1:B2:C3:D4:E5:05` | Kraal |
| LV-006 | `A1:B2:C3:D4:E5:06` | Kraal |
| LV-007 | `A1:B2:C3:D4:E5:07` | Kraal |
| LV-008 | `A1:B2:C3:D4:E5:08` | Kraal |
| LV-009 | `A1:B2:C3:D4:E5:09` | Kraal |
| LV-010 | `A1:B2:C3:D4:E5:10` | Kraal |

Gateway: `GW-LV-001` (Sipho Molefe's phone, starts at Kraal)

---

## License

Proprietary — All rights reserved.
MyDrive-Africa / LivestockGuard
