# LivestockGuard System Overview

## Architecture

LivestockGuard uses a 4-layer architecture:

1. **Device Layer** — GPS-enabled collars/ear-tags with on-device geofencing
2. **Connectivity Layer** — Multi-protocol (LTE-M, NB-IoT, LoRaWAN, Satellite, BLE)
3. **Cloud Layer** — Microservices for ingestion, processing, alerting, and management
4. **User Layer** — Web dashboard + mobile app for real-time monitoring

## Key Services

| Service | Role | Tech |
|---------|------|------|
| Ingestion | MQTT message decode, validation, routing | Rust (5000 msg/sec) |
| Geofence Engine | Spatial breach detection with R-tree index | Rust |
| Alert Engine | Rule evaluation, notification dispatch | Python |
| Device Management | Provisioning, OTA, health monitoring | Python FastAPI |
| Health Analytics | Activity classification, herd insights | Python |
| API Gateway | REST + WebSocket, auth, rate limiting | Python FastAPI |

## Data Stores

- **TimescaleDB** — Telemetry positions hypertable (time-series, auto-partitioned)
- **PostgreSQL + PostGIS** — Entity storage (farms, animals, geofences, users)
- **Redis** — Session cache, real-time state, pub/sub for WebSocket fan-out
- **EMQX** — MQTT broker cluster for device connectivity (QoS 1)

## Technology Stack Summary

| Layer | Technologies |
|-------|-------------|
| Firmware | C11, Zephyr RTOS / FreeRTOS, nRF Connect SDK |
| Cloud | Rust, Python 3.11+, FastAPI, SQLAlchemy, Tokio |
| Frontend | React 18, TypeScript, MapLibre GL, TailwindCSS |
| Mobile | React Native, Expo |
| Infra | AWS (af-south-1), Docker, Terraform, GitHub Actions |
| Messaging | EMQX (MQTT 5.0), Redis Streams |

## Project Structure

```
livestockguard/
├── firmware/          # Embedded C code, HAL, platform configs
│   ├── hal/           # Hardware abstraction layer
│   ├── lib/           # Shared libraries (geofence, protocol, collections)
│   ├── platforms/     # Board-specific (nRF9160, nRF52840, STM32, ESP32)
│   └── src/           # Application logic, services, state machine
├── cloud/
│   ├── services/      # Microservices (ingestion, geofence, alert, API)
│   ├── shared/        # Common models, schemas, utilities
│   └── migrations/    # Database schema versions
├── dashboard/         # React web application
│   └── src/           # Components, pages, stores, hooks, API layer
└── docs/              # Specifications and documentation
```

## Design Principles

- **Offline-first**: Devices store-and-forward when connectivity drops
- **Power-aware**: Adaptive duty cycling for 2-5 year battery life
- **Multi-tenant**: Organisation-scoped RBAC with farm-level isolation
- **South Africa-first**: AWS af-south-1, local compliance (POPIA, ICASA)
- **Resilient**: Graceful degradation across all connectivity protocols
