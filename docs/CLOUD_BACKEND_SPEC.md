# LivestockGuard Cloud Backend Specification

## Architecture

Microservices deployed on AWS af-south-1 (Cape Town), containerised with Docker on ECS Fargate.

### Service Overview

| Service | Language | Purpose |
|---------|----------|---------|
| Ingestion | Rust (Tokio) | MQTT→decode→validate→route (5000 msg/sec target) |
| Geofence Engine | Rust | Spatial breach detection, R-tree index, event emission |
| Alert Engine | Python | Rule evaluation, deduplication, notification dispatch |
| API Gateway | Python FastAPI | REST API + WebSocket, auth, rate limiting |
| Device Manager | Python FastAPI | Provisioning, OTA orchestration, fleet health |
| Analytics | Python | Herd insights, movement patterns, health scoring |

## Database Schema (PostgreSQL + PostGIS + TimescaleDB)

### Core Tables

```sql
organisations (id, name, billing_plan, created_at)
farms (id, org_id, name, boundary GEOMETRY, timezone)
users (id, org_id, email, password_hash, role, language_pref)
devices (id, farm_id, hardware_type, firmware_version, status, last_seen)
animals (id, farm_id, device_id, name, species, breed, samic_id, tag_number)
geofences (id, farm_id, name, polygon GEOMETRY, alert_type, grace_period_s)
alerts (id, farm_id, animal_id, type, severity, status, created_at, resolved_at)
```

### Time-Series (TimescaleDB Hypertable)

```sql
positions (time TIMESTAMPTZ, device_id, lat, lon, altitude, speed, hdop, battery, activity)
-- Partitioned by 1-day chunks, retention policy 90 days raw / 2 years downsampled
```

## API Design

### REST Endpoints (FastAPI)

- `POST /auth/login` — JWT token issuance (access + refresh)
- `GET /farms/{id}/animals` — List with pagination, filtering
- `GET /animals/{id}/track?from=&to=` — Historical positions
- `POST /geofences` — Create/update polygon geofence
- `GET /alerts?status=active` — Active alerts with WebSocket subscription
- `POST /devices/{id}/command` — Send command (locate, update, config)

### WebSocket

- `/ws/farm/{farm_id}` — Real-time positions, alerts, device status
- JSON frames with event types: `position_update`, `alert_new`, `device_status`

## Event Streaming (Redis Streams)

- `stream:positions` — Decoded position messages for processing
- `stream:geofence_events` — Breach/return events for Alert Engine
- `stream:notifications` — Outbound notification queue
- Consumer groups for horizontal scaling and at-least-once delivery

## Multi-Tenancy & RBAC

| Role | Scope | Permissions |
|------|-------|-------------|
| Super Admin | System | All operations |
| Org Admin | Organisation | Manage farms, users, billing |
| Farm Manager | Farm | Full farm operations |
| Farm Worker | Farm | View-only, acknowledge alerts |

- JWT tokens carry org_id + farm_ids + role claims
- Row-level security enforced at query layer

## Notification Channels

- **Push**: Firebase Cloud Messaging (FCM) for mobile app
- **SMS**: Africa's Talking API (SA coverage, bulk pricing)
- **WhatsApp**: WhatsApp Business API via 360dialog
- **Email**: AWS SES for reports and summaries
- **Escalation**: Configurable chains (SMS→WhatsApp→Phone call)

## Compliance

- **POPIA**: Data residency in SA, consent management, right-to-delete
- **Data retention**: Configurable per org (default 90 days raw, 2 years aggregated)
- **Audit log**: All mutations logged with actor, timestamp, before/after
- **Encryption**: TLS 1.3 in-transit, AES-256 at-rest (RDS encryption)

## Performance Targets

- Ingestion: 5000 messages/second sustained, <100ms p99 latency
- API: <200ms p95 for list endpoints, <50ms for cached lookups
- Geofence: <10ms per point-in-polygon check (R-tree pre-filter)
- WebSocket: <500ms end-to-end from device to dashboard
