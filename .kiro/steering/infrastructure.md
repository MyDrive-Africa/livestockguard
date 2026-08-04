# Infrastructure & Services

## Docker Compose Topology

All backend services run in Docker Compose (defined in `cloud/docker-compose.yml`).

### Services

| Service | Image/Build | Port | Depends On |
|---------|-------------|------|------------|
| postgres | timescale/timescaledb-ha:pg16 | 5432 | — |
| redis | redis:7-alpine | 6379 | — |
| emqx | emqx/emqx:5.5 | 1883, 18083 | — |
| api_gateway | Build: services/api_gateway/Dockerfile | 8000 | postgres, redis |
| mqtt_writer | Build: services/mqtt_writer/Dockerfile | — | postgres, redis, emqx |
| alert_engine | Build: services/alert_engine/Dockerfile | — | redis |
| analytics_engine | Build: services/analytics_engine/Dockerfile | — | postgres |

### Health Checks
- **postgres**: `pg_isready -U livestockguard` (5s interval)
- **redis**: `redis-cli ping` (5s interval)
- Services with `condition: service_healthy` wait for deps before starting

### Volumes
- `pgdata` — PostgreSQL data (persistent)
- `redisdata` — Redis data
- `emqxdata` — EMQX broker data

## Database

### PostgreSQL 16 + TimescaleDB + PostGIS

- **User**: `livestockguard`
- **Password**: `livestockguard_dev` (dev) — set via `POSTGRES_PASSWORD` env var
- **Database**: `livestockguard`
- **Extensions**: TimescaleDB (hypertables), PostGIS (geometry/geography)

### Migrations

Located in `cloud/migrations/versions/`. Applied in order:

| # | File | Purpose |
|---|------|---------|
| 001 | initial_schema.sql | Core tables: orgs, farms, users, animals, devices, positions (hypertable), geofences, alerts |
| 002 | geofence_geometry_nullable.sql | Allow draft geofences without geometry |
| 003 | animal_inventory_fields.sql | Gender, colour, weight, DOB, acquired_date |
| 004 | farm_location_details.sql | Province, district, lat/lon, area_hectares |
| 005 | notification_preferences.sql | User notification channel preferences |
| 006 | activity_classification.sql | Grazing/walking/resting/running states |
| 007 | herdsman_gateway.sql | gateway_devices, ble_ear_tags, ble_sightings, herdsman_sessions |
| 008 | geofence_breach_severity.sql | Severity levels on alerts |
| 009 | farm_schedule_config.sql | Kraal open/close, feed times |
| 010 | analytics_intelligence.sql | Analytics tables |
| 010 | user_farm_assignments.sql | RBAC farm assignments |
| 011 | ble_estimated_position.sql | BLE position estimation |

### Key Tables

- **positions** — TimescaleDB hypertable (time-series GPS, weekly partitions)
- **ble_sightings** — TimescaleDB hypertable (BLE detections, 1-year retention)
- **geofences** — PostGIS geometry column for polygon storage
- **user_farm_assignments** — RBAC: who can access which farm

## MQTT Broker (EMQX)

- **Protocol**: MQTT 5.0
- **Port**: 1883 (unencrypted), 8883 (TLS), 18083 (web dashboard)
- **Topics**:
  - `lg/dev/{device_id}/pos` — GPS position reports
  - `lg/dev/{device_id}/alert` — Device-generated alerts
  - `lg/up/{device_id}/telemetry` — Simulator telemetry
- **QoS**: 1 for positions, 2 for alerts
- **Dashboard creds**: admin / public

## Redis

- **Port**: 6379
- **Uses**:
  - Real-time pub/sub for WebSocket fan-out (API → Dashboard)
  - Alert channel: `alerts:incoming` (Alert Engine subscribes)
  - Session cache
  - Rate limiter storage (slowapi)

## Environment Variables

Defined in `cloud/.env.example`:

| Variable | Purpose | Default |
|----------|---------|---------|
| POSTGRES_PASSWORD | DB password | livestockguard_dev |
| JWT_SECRET | JWT signing key | dev_secret_change_in_production |
| AWS_ACCESS_KEY_ID | SES email sending | (empty) |
| AWS_SECRET_ACCESS_KEY | SES credentials | (empty) |
| AWS_REGION | AWS region | af-south-1 |
| SES_SENDER_EMAIL | Alert sender address | alerts@livestockguard.co.za |
| ALERT_EMAIL_RECIPIENTS | Comma-separated emails | (empty) |
| FIREBASE_CREDENTIALS_FILE | FCM service account JSON | ./config/firebase-credentials.json |
| WEBHOOK_URLS | Comma-separated webhook URLs | (empty) |
| ALERT_SMS_RECIPIENTS | Comma-separated phone numbers (E.164) | (empty) |

## Production Target

- **Region**: AWS af-south-1 (Cape Town)
- **Deployment**: ECS Fargate or EKS
- **Database**: RDS PostgreSQL with TimescaleDB extension
- **MQTT**: EMQX Cloud or AWS IoT Core
- **CDN**: CloudFront for dashboard static assets
- **SMS**: Africa's Talking API (South African numbers)
