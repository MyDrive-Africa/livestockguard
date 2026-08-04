# LivestockGuard — Project Overview

## What This Is

LivestockGuard is a full-stack GPS livestock tracking and geofencing platform for South African farmers. It provides real-time animal monitoring, virtual fencing, theft detection, and herd health analytics through GPS collars, BLE ear tags, and a cloud-connected ecosystem.

## Architecture (4 Layers)

```
Layer 4: User Interfaces
  - Web Dashboard (React 18 + Vite + MapLibre GL) — port 5173
  - Mobile App (React Native + Expo 52) — port 8082

Layer 3: Cloud Backend (Docker Compose)
  - API Gateway (FastAPI, Python 3.12) — port 8000
  - MQTT Writer (Python) — binary decode, MQTT → Postgres
  - Alert Engine (Python) — SES, FCM, Webhook, SMS, Redis
  - Analytics Engine (Python) — APScheduler, anomaly detection
  - Ingestion (Rust/Tokio) — 5000 msg/sec binary decoder
  - Geofence Engine (Rust) — R-tree spatial breach detection

Layer 2: Infrastructure
  - PostgreSQL 16 + TimescaleDB — port 5432
  - Redis 7 — port 6379
  - EMQX 5.5 (MQTT Broker) — ports 1883, 18083

Layer 1: Devices / Simulators
  - GPS Collar Simulator (binary MQTT, CRC-16)
  - BLE Gateway Simulator (REST API batch)
  - Herdsman Daily Routine Simulator (realistic farm schedules)
  - Real Hardware: nRF9160 (GPS collar) + nRF52840 (BLE ear tag)
```

## Tech Stack Summary

| Layer | Technology |
|-------|-----------|
| Frontend (Web) | React 18, TypeScript 5.3, Vite 5, TailwindCSS 3.4, MapLibre GL 4, Zustand 4.5, TanStack Query 5, Recharts, Framer Motion |
| Frontend (Mobile) | React Native 0.76, Expo 52, react-native-maps, AsyncStorage |
| Backend (Python) | Python 3.12, FastAPI, SQLAlchemy 2.0 (async), asyncpg, pydantic, redis, paho-mqtt |
| Backend (Rust) | Rust stable, Tokio, geo crate, rstar (R-tree) |
| Firmware | C11, Zephyr RTOS, nRF Connect SDK, CMake |
| Database | PostgreSQL 16 + TimescaleDB + PostGIS |
| Infrastructure | Docker Compose, EMQX 5.5, Redis 7 |
| CI | GitHub Actions (Python pytest, Rust cargo test, TS tsc + Vite build) |
| Notifications | AWS SES (email), Firebase FCM (push), Africa's Talking (SMS), Webhooks |

## Key Conventions

- **API versioning**: All routes use `/api/v1/...` prefix. Unversioned `/api/...` routes are deprecated.
- **Auth**: JWT (access + refresh tokens), bcrypt password hashing, role-based (admin, farm_owner, herdsman, viewer).
- **Multi-farm RBAC**: Users are assigned to farms via `user_farm_assignments` table. Admin sees all, others see assigned only.
- **Time-series**: Positions and BLE sightings use TimescaleDB hypertables (auto-partitioned weekly).
- **Binary protocol**: GPS collars use compact binary encoding with CRC-16 CCITT integrity.
- **BLE gateway**: Herdsman phone scans BLE ear tags, batches to `POST /api/v1/gateway/batch` every 30s.
- **Alert severity**: critical > high > medium > low > info. Channels escalate with severity.

## Project Structure

```
livestockguard/
├── Makefile              # All dev commands (make help)
├── cloud/                # Docker Compose backend
│   ├── docker-compose.yml
│   ├── migrations/versions/  # SQL migrations (001–011)
│   └── services/
│       ├── api_gateway/      # FastAPI REST + WebSocket
│       ├── mqtt_writer/      # MQTT → TimescaleDB bridge
│       ├── alert_engine/     # Multi-channel notifications
│       ├── analytics_engine/ # Scheduled analytics jobs
│       ├── ingestion/        # Rust binary decoder
│       └── geofence_engine/  # Rust spatial engine
├── dashboard/            # React web app (Vite)
├── mobile/               # React Native app (Expo)
├── firmware/             # Embedded C (nRF chips)
├── tools/simulator/      # Python device simulators
├── e2e/                  # Playwright E2E tests
├── scripts/              # Setup, seed, demo, verify scripts
├── docs/                 # Architecture & spec documents
└── .github/workflows/    # CI pipeline
```

## Demo Farms

| Farm | Location | Animals | Tracking |
|------|----------|---------|----------|
| Boschhoek | Free State (-29.12, 26.21) | 5 cattle | GPS collars |
| Loch Vaal Plot 30 | Gauteng (-26.719, 27.710) | 10 cattle | BLE ear tags + gateway |
| Sibanyoni | North West (-25.358, 25.361) | 50 cattle | BLE ear tags + gateway |

## Key Documentation

#[[file:docs/SYSTEM_OVERVIEW.md]]
#[[file:docs/CLOUD_BACKEND_SPEC.md]]
#[[file:docs/DASHBOARD_SPEC.md]]
#[[file:docs/MOBILE_APP_SPEC.md]]
#[[file:docs/HERDSMAN_GATEWAY_SPEC.md]]
#[[file:docs/FIRMWARE_SPEC.md]]
#[[file:docs/CONNECTIVITY_SPEC.md]]
#[[file:docs/DEPLOYMENT_SPEC.md]]
#[[file:docs/ANALYTICS_INTELLIGENCE_SPEC.md]]
#[[file:docs/SIMULATION_GUIDE.md]]
