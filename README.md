# LivestockGuard

**GPS livestock tracking & geofencing platform for South African farmers.**

Real-time animal monitoring, virtual fencing, theft detection, and herd health — delivered through affordable GPS tags and a cloud dashboard.

---

## Run Locally (Mac)

### Prerequisites

| Requirement | Install |
|-------------|---------|
| Docker (Colima or Desktop) | `brew install colima docker docker-compose` then `colima start` |
| Node.js 18+ | `brew install node` |
| Python 3.10+ | `brew install python3` |
| Git | `brew install git` |

> **Colima users:** After installing, link the Compose plugin so `docker compose` works:
> ```bash
> mkdir -p ~/.docker/cli-plugins
> ln -sfn /opt/homebrew/opt/docker-compose/bin/docker-compose ~/.docker/cli-plugins/docker-compose
> ```

### Clone & Setup (One Time)

```bash
git clone https://github.com/MyDrive-Africa/livestockguard.git
cd livestockguard
make setup
```

This will:
- Check all prerequisites
- Install Python dependencies (simulator)
- Install Node dependencies (dashboard)
- Start Docker containers (PostgreSQL, Redis, EMQX)
- Run database migrations
- Create `.env` with dev defaults

### Start Development (4 Terminals)

```bash
# Terminal 1: Start cloud infrastructure
make start
make db-seed          # Load demo farm (5 animals, 3 geofences)

# Terminal 2: MQTT → Database bridge
make mqtt-writer

# Terminal 3: Simulate GPS devices
make simulate         # 5 animals sending positions every 10s

# Terminal 4: Web dashboard
make dashboard        # Opens at http://localhost:5173
```

### Verify It's Working

```bash
# Check services are running
make status

# Query API directly
curl http://localhost:8000/api/animals
curl http://localhost:8000/api/devices
curl http://localhost:8000/health

# Open dashboard
open http://localhost:5173
```

### All Available Commands

```bash
make help             # Show all commands

# Infrastructure
make start            # Start Docker stack
make stop             # Stop Docker stack
make restart          # Restart
make status           # Show container status
make logs             # Tail all logs

# Database
make db-seed          # Load demo data
make db-shell         # PostgreSQL CLI
make db-reset         # Destroy and recreate (WARNING: data loss)

# Development
make dashboard        # Start React dev server (port 5173)
make mqtt-writer      # Start MQTT→DB bridge
make simulate         # Normal grazing (5 animals)
make simulate-theft   # Theft scenario
make simulate-breach  # Geofence breach scenario
make simulate-many    # 50 animals (stress test)

# Cleanup
make clean            # Stop everything, remove volumes
```

---

## System Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│  DASHBOARD (React + MapLibre GL)          http://localhost:5173       │
│  - Live map with animal markers                                      │
│  - Geofence polygon overlays                                         │
│  - Movement trail lines (24h)                                        │
│  - Alerts, Analytics, Device management                              │
└───────────────────────────────────┬──────────────────────────────────┘
                                    │ REST API
                                    ▼
┌──────────────────────────────────────────────────────────────────────┐
│  CLOUD BACKEND (Python FastAPI + Rust)    http://localhost:8000       │
│  - API Gateway (FastAPI): animals, devices, geofences, alerts        │
│  - Ingestion Service (Rust): binary decode, MQTT subscribe           │
│  - Geofence Engine (Rust): spatial evaluation                        │
│  - Alert Engine (Python): multi-channel dispatch                     │
│  - MQTT Writer (Python): bridge MQTT → PostgreSQL                    │
└───────────────────────────────────┬──────────────────────────────────┘
                                    │ SQL / MQTT
                                    ▼
┌──────────────────────────────────────────────────────────────────────┐
│  INFRASTRUCTURE (Docker)                                             │
│  - PostgreSQL + TimescaleDB (port 5432)                              │
│  - Redis (port 6379)                                                 │
│  - EMQX MQTT Broker (port 1883, dashboard: 18083)                   │
└───────────────────────────────────┬──────────────────────────────────┘
                                    │ MQTT binary protocol
                                    ▼
┌──────────────────────────────────────────────────────────────────────┐
│  DEVICE SIMULATOR (Python)        make simulate                      │
│  - Simulates N GPS-tagged animals                                    │
│  - Binary protocol encoding (CRC-16 verified)                        │
│  - Scenarios: normal, theft, breach, night                           │
│  (In production: real firmware on nRF9160/nRF52840 hardware)         │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Project Structure

```
livestockguard/
├── README.md              # This file
├── Makefile               # All development commands
├── scripts/
│   ├── setup.sh           # First-time environment setup
│   └── seed_data.sql      # Demo farm data
├── docs/                  # Specification documents
│   ├── SYSTEM_OVERVIEW.md
│   ├── FIRMWARE_SPEC.md
│   ├── CLOUD_BACKEND_SPEC.md
│   ├── DASHBOARD_SPEC.md
│   ├── CONNECTIVITY_SPEC.md
│   └── DEPLOYMENT_SPEC.md
├── firmware/              # Embedded C firmware
│   ├── CMakeLists.txt
│   ├── hal/include/       # Hardware Abstraction Layer
│   ├── src/               # Application + services
│   ├── lib/               # Geofence, protocol, collections
│   └── platforms/         # nRF9160, nRF52840 configs
├── cloud/                 # Cloud backend services
│   ├── docker-compose.yml
│   ├── services/
│   │   ├── api_gateway/   # FastAPI (Python)
│   │   ├── ingestion/     # Binary decoder (Rust)
│   │   ├── geofence_engine/ # Spatial evaluation (Rust)
│   │   ├── alert_engine/  # Notification dispatch (Python)
│   │   └── mqtt_writer/   # MQTT → DB bridge (Python)
│   ├── shared/            # Common models, DB connection
│   └── migrations/        # SQL schema
├── dashboard/             # Web application
│   ├── src/
│   │   ├── pages/         # Map, Animals, Geofences, Alerts, etc.
│   │   ├── stores/        # Zustand state management
│   │   ├── hooks/         # WebSocket, API hooks
│   │   └── components/    # Shared UI components
│   └── package.json
└── tools/
    └── simulator/         # Device simulator (Python)
```

---

## Key Features

| Feature | Status |
|---------|--------|
| Real-time GPS tracking | ✅ Working |
| On-device geofencing (point-in-polygon) | ✅ Firmware complete |
| Multi-protocol (NB-IoT, LoRaWAN, Satellite, BLE) | ✅ Architecture + HAL |
| Theft detection (transport speed + night movement) | ✅ Firmware + alerts |
| Herd health monitoring (activity classification) | ✅ Firmware |
| Web dashboard with live map | ✅ MapLibre GL |
| Geofence polygon overlays | ✅ Dashboard |
| Movement trail visualisation | ✅ Dashboard |
| Satellite/terrain tile switching | ✅ Dashboard |
| Geofence drawing tools | ✅ Dashboard |
| Multi-channel alerts (SMS, WhatsApp, Push) | 🔧 Framework ready |
| Virtual fencing deterrents | 🔧 Firmware hooks ready |
| OTA firmware updates | 🔧 Module structure ready |

---

## Documentation

| Document | Description |
|----------|-------------|
| [System Overview](docs/SYSTEM_OVERVIEW.md) | Architecture, data flow, tech stack |
| [Firmware Spec](docs/FIRMWARE_SPEC.md) | Embedded C design, HAL, state machine |
| [Cloud Backend Spec](docs/CLOUD_BACKEND_SPEC.md) | Microservices, DB schema, API |
| [Dashboard Spec](docs/DASHBOARD_SPEC.md) | React app, pages, state management |
| [Connectivity Spec](docs/CONNECTIVITY_SPEC.md) | Protocols, fallback, compression |
| [Deployment Spec](docs/DEPLOYMENT_SPEC.md) | SA compliance, pricing, go-to-market |

---

## Demo Credentials

After running `make db-seed`, log into the dashboard at **http://localhost:5173**:

| Field | Value |
|-------|-------|
| Email | `africa.mydrive@gmail.com` |
| Password | `demo123` |
| Farm | Boschhoek Farm (Free State) |
| Animals | Bella, Storm, Thunder, Daisy, Rosie |

EMQX MQTT broker dashboard at **http://localhost:18083**:

| Field | Value |
|-------|-------|
| Username | `admin` |
| Password | `public` |

---

## Tech Stack

| Layer | Technologies |
|-------|-------------|
| Firmware | C11, Zephyr RTOS, nRF Connect SDK, CMake |
| Cloud | Python (FastAPI), Rust (Tokio, Axum), PostgreSQL, TimescaleDB, Redis, EMQX |
| Frontend | React 18, TypeScript, MapLibre GL JS, TailwindCSS, Zustand |
| Infra | Docker, AWS (af-south-1 for production), Terraform |
| Protocols | MQTT 5.0, LoRaWAN, NB-IoT, BLE 5.0, Globalstar satellite |

---

## License

Proprietary - All rights reserved.
MyDrive-Africa / LivestockGuard
