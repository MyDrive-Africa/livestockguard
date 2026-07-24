# LivestockGuard

GPS livestock tracking & geofencing platform for South African farmers.

## System Components

| Component | Location | Technology |
|-----------|----------|-----------|
| Firmware | `/firmware/` | C (embedded), CMake, Zephyr/FreeRTOS |
| Cloud Backend | `/cloud/` | Rust (ingestion, geofence), Python (FastAPI), PostgreSQL, TimescaleDB, Redis, EMQX |
| Web Dashboard | `/dashboard/` | React 18, TypeScript, MapLibre GL, TailwindCSS |
| Specifications | `/docs/` | Markdown design documents |

## Quick Start (Cloud Backend)

```bash
cd cloud
docker-compose up -d
# API available at http://localhost:8000
# MQTT broker at localhost:1883
# API docs at http://localhost:8000/docs
```

## Documentation

- [System Overview](docs/SYSTEM_OVERVIEW.md)
- [Firmware Spec](docs/FIRMWARE_SPEC.md)
- [Cloud Backend Spec](docs/CLOUD_BACKEND_SPEC.md)
- [Dashboard Spec](docs/DASHBOARD_SPEC.md)
- [Connectivity Spec](docs/CONNECTIVITY_SPEC.md)
- [Deployment Spec](docs/DEPLOYMENT_SPEC.md)

## Key Features

- Real-time GPS tracking (multi-constellation GNSS)
- On-device geofencing with breach state machine
- Multi-protocol connectivity (NB-IoT, LoRaWAN, Satellite, BLE)
- Theft detection & recovery (transport speed, tamper, panic mode)
- Herd health monitoring (activity classification, anomaly detection)
- Virtual fencing with audio/vibration deterrents
- Multi-channel alerts (Push, SMS, WhatsApp)
- Designed for South African conditions (load-shedding resilient, POPIA compliant)

## License

Proprietary - All rights reserved.
