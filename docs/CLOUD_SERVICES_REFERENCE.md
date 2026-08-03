# LivestockGuard — Cloud Services Reference

Complete reference for all cloud infrastructure services, their configuration, ports, credentials, and interconnections.

---

## Quick Reference (Development)

| Service | Port | URL / Connection String | Credentials |
|---------|------|------------------------|-------------|
| API Gateway | 8000 | http://localhost:8000/docs | JWT auth (see below) |
| MQTT Broker (EMQX) | 1883 | `mqtt://localhost:1883` | No auth (dev) |
| EMQX Dashboard | 18083 | http://localhost:18083 | `admin` / `public` |
| MQTTS (TLS) | 8883 | `mqtts://localhost:8883` | (production only) |
| PostgreSQL | 5432 | `postgresql://livestockguard:livestockguard_dev@localhost:5432/livestockguard` | `livestockguard` / `livestockguard_dev` |
| Redis | 6379 | `redis://localhost:6379/0` | No auth (dev) |
| Web Dashboard | 5173 | http://localhost:5173 | Use API login below |
| Mobile App (web) | 8082 | http://localhost:8082 | Use API login below |

---

## All Login Credentials (Development)

Everything you need to log into any part of the system:

### EMQX Broker Dashboard

| URL | Username | Password |
|-----|----------|----------|
| http://localhost:18083 | `admin` | `public` |

This gives full admin access to the MQTT broker — view connected clients, subscriptions, message stats, rules engine, etc.

### PostgreSQL Database

| Host | Port | Database | Username | Password |
|------|------|----------|----------|----------|
| `localhost` | `5432` | `livestockguard` | `livestockguard` | `livestockguard_dev` |

Connect with any SQL client or via CLI:
```bash
psql -h localhost -p 5432 -U livestockguard -d livestockguard
# Password: livestockguard_dev
```

Or use the project shortcut:
```bash
make db-shell
```

### Redis

| Host | Port | Auth |
|------|------|------|
| `localhost` | `6379` | None (no password in dev) |

```bash
redis-cli -h localhost -p 6379
```

### API / Dashboard / Mobile App (User Accounts)

All demo accounts use password **`demo123`**. Load them with `make db-seed`.

| Email | Password | Role | Farm Access |
|-------|----------|------|-------------|
| `africa.mydrive@gmail.com` | `demo123` | owner | All 3 farms (Boschhoek, Loch Vaal, Sibanyoni) |
| `lochvaal@livestockguard.co.za` | `demo123` | owner | Loch Vaal Plot 30 only |
| `sibanyoni@livestockguard.co.za` | `demo123` | owner | Sibanyoni Farm only |

Use these credentials to log into:
- **Web Dashboard** at http://localhost:5173
- **Mobile App** at http://localhost:8082
- **API Swagger UI** at http://localhost:8000/docs (click "Authorize", use login endpoint first)

### MQTT Broker (Device Connections)

| Host | Port | Auth |
|------|------|------|
| `localhost` | `1883` | None (anonymous allowed in dev) |

Devices and simulators connect without credentials in development. Production uses client certificates.

---

## 1. API Gateway

**Purpose:** Central REST + WebSocket server. All clients (dashboard, mobile, simulators) communicate with the platform through this service.

### Connection Details

| Aspect | Value |
|--------|-------|
| Image | Custom build (`services/api_gateway/Dockerfile`) |
| Framework | FastAPI (Python 3.12) |
| Port | `8000` |
| Swagger UI | http://localhost:8000/docs |
| ReDoc | http://localhost:8000/redoc |
| Health Check | `GET /health` |
| Metrics | `GET /metrics` (Prometheus format) |
| API Version | `v1` (prefix: `/api/v1/`) |

### Authentication

- **Method:** JWT Bearer tokens (HS256)
- **Access token expiry:** 60 minutes
- **Refresh token expiry:** 7 days
- **Password hashing:** bcrypt
- **Rate limiting:** 200/minute, 50/second (backed by Redis)

### Demo Login Credentials

All demo accounts use the same password. Load them with `make db-seed`.

| Email | Password | Role | Farm Access |
|-------|----------|------|-------------|
| `africa.mydrive@gmail.com` | `demo123` | owner | All 3 farms (Boschhoek, Loch Vaal, Sibanyoni) |
| `lochvaal@livestockguard.co.za` | `demo123` | owner | Loch Vaal Plot 30 |
| `sibanyoni@livestockguard.co.za` | `demo123` | owner | Sibanyoni Farm |

**Login via API (curl):**

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "africa.mydrive@gmail.com", "password": "demo123"}'
```

**Response:**
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 3600,
  "user": {
    "id": "33333333-3333-3333-3333-333333333333",
    "email": "africa.mydrive@gmail.com",
    "role": "owner",
    "full_name": "Johan van der Merwe"
  }
}
```

**Using the token in subsequent requests:**
```bash
curl http://localhost:8000/api/v1/animals \
  -H "Authorization: Bearer <access_token>"
```

**Login via Dashboard:**
Open http://localhost:5173 and enter any of the email/password combinations above.

**Login via Mobile App:**
Open http://localhost:8082 (web mode) and use the same credentials.

### Role-Based Access Control

| Role | Level | Permissions |
|------|-------|-------------|
| `admin` | 4 | Org-level superuser, sees all farms |
| `farm_owner` | 3 | Full control of assigned farm(s) |
| `herdsman` | 2 | Assigned farm only, BLE scanning |
| `viewer` | 1 | Read-only access to assigned farms |

### API Endpoints (v1)

```
Authentication:
  POST   /api/v1/auth/login            → JWT tokens
  POST   /api/v1/auth/register         → Create user + JWT
  POST   /api/v1/auth/refresh          → Refresh access token

Farms:
  GET    /api/v1/farms                  → List user's farms
  POST   /api/v1/farms                  → Create farm (admin/owner)
  GET    /api/v1/farms/{id}            → Farm detail

Animals:
  GET    /api/v1/animals                → List animals (paginated)
  GET    /api/v1/animals/{id}          → Animal detail + device info
  GET    /api/v1/animals/{id}/history  → Position history (trail)

Devices:
  GET    /api/v1/devices                → List devices
  POST   /api/v1/devices/{id}/command  → Queue command to device

Alerts:
  GET    /api/v1/alerts                 → List alerts (filterable)
  PUT    /api/v1/alerts/{id}/acknowledge → Acknowledge alert

Geofences:
  GET    /api/v1/geofences             → List geofences
  POST   /api/v1/geofences             → Create (GeoJSON polygon)

Analytics:
  GET    /api/v1/analytics/summary     → Dashboard stats

BLE Gateway:
  POST   /api/v1/gateway/batch          → Submit BLE sighting batch
  POST   /api/v1/gateway/register       → Register gateway device
  POST   /api/v1/gateway/tags           → Register BLE ear tag
  POST   /api/v1/gateway/sessions/start → Start patrol session
  POST   /api/v1/gateway/sessions/{id}/end → End patrol

Insights:
  GET    /api/v1/insights               → AI-generated farm insights

Notifications:
  GET    /api/v1/notifications          → User notification preferences

Users & Assignments:
  GET    /api/v1/users                  → List users (admin)
  POST   /api/v1/assignments            → Assign user to farm

WebSocket (real-time):
  WS     /ws                            → Real-time position + alert feed

System:
  GET    /api/v1/system/status          → System health overview
```

### CORS Allowed Origins

```
http://localhost:3000
http://localhost:5173  (dashboard dev)
http://localhost:5174
http://localhost:5175
http://localhost:8082  (mobile web)
https://app.livestockguard.co.za (production)
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://livestockguard:livestockguard_dev@postgres:5432/livestockguard` | Async SQLAlchemy connection |
| `REDIS_URL` | `redis://redis:6379/0` | Redis for rate limiting + pub/sub |
| `JWT_SECRET` | `dev_secret_change_in_production` | HMAC signing key |
| `MQTT_HOST` | `emqx` | MQTT broker hostname |
| `MQTT_PORT` | `1883` | MQTT broker port |

### Dependencies

Waits for:
- PostgreSQL (healthy)
- Redis (healthy)

---

## 2. MQTT Broker (EMQX)

**Purpose:** High-performance MQTT 5.0 message broker. Handles all device-to-cloud communication for GPS collars sending position telemetry and alert messages.

### Connection Details

| Aspect | Value |
|--------|-------|
| Image | `emqx/emqx:5.5` |
| MQTT Port | `1883` (plaintext) |
| MQTTS Port | `8883` (TLS, production) |
| Dashboard | `18083` (web admin) |
| Protocol | MQTT 5.0 |
| Max Connections | 10,000 concurrent |
| QoS | 1 (telemetry), 2 (alerts) |

### Dashboard Credentials (Dev)

| Username | Password |
|----------|----------|
| `admin` | `public` |

### Topic Structure

```
lg/up/{device_id}/telemetry    — GPS position batches (QoS 1)
lg/up/{device_id}/alert        — Device-originated alerts (QoS 2)
lg/down/{device_id}/command    — Commands TO device (future)
```

### Message Format

All messages use a **compact binary protocol** with CRC-16 CCITT integrity checking:

```
┌─────────────────── Header (11 bytes) ───────────────────┐
│ version (1B) │ msg_type (1B) │ priority (1B) │          │
│ device_id (2B, LE) │ timestamp (4B, LE, Unix) │         │
│ sequence (1B) │ payload_len (1B, signed) │              │
├─────────────────── Payload (variable) ──────────────────┤
│ Position record(s): 16 bytes each                       │
│   lat_offset(4B) │ lon_offset(4B) │ speed(1B) │        │
│   heading(1B) │ hdop_x10(1B) │ flags(1B) │ ts(4B)     │
├─────────────────── CRC (2 bytes) ───────────────────────┤
│ CRC-16/CCITT Big Endian                                 │
└─────────────────────────────────────────────────────────┘
```

### Message Types

| Code | Type | Description |
|------|------|-------------|
| `0x01` | Position Batch | One or more position records |
| `0x02` | Geofence Alert | Device-detected breach |
| `0x03` | Theft Alert | Vehicle-speed movement detected |
| `0x04` | Heartbeat | Keep-alive (updates `last_seen`) |

### Data Volume

| Volume | Persistent Storage |
|--------|-------------------|
| Named volume: `emqxdata` | `/opt/emqx/data` |

---

## 3. PostgreSQL (TimescaleDB)

**Purpose:** Primary data store for all platform data. Runs TimescaleDB (time-series extension) on top of PostgreSQL 16 with PostGIS for geospatial queries.

### Connection Details

| Aspect | Value |
|--------|-------|
| Image | `timescale/timescaledb-ha:pg16` |
| Port | `5432` |
| Database | `livestockguard` |
| Username | `livestockguard` |
| Password | `livestockguard_dev` (dev) |
| Extensions | `uuid-ossp`, `postgis`, `timescaledb` |

### Connection Strings

```bash
# psql CLI
psql -U livestockguard -d livestockguard -h localhost -p 5432

# SQLAlchemy (async, used by API Gateway & Analytics)
postgresql+asyncpg://livestockguard:livestockguard_dev@localhost:5432/livestockguard

# asyncpg (direct, used by MQTT Writer)
postgresql://livestockguard:livestockguard_dev@localhost:5432/livestockguard
```

### Database Schema

**Core Tables:**

| Table | Purpose | Key Features |
|-------|---------|--------------|
| `organisations` | Multi-tenancy | Plan limits, max_devices |
| `farms` | Farm profiles | PostGIS location, timezone |
| `users` | Authentication | bcrypt hash, role, org link |
| `devices` | GPS collars & ear tags | Serial, type, firmware, status |
| `animals` | Livestock registry | Species, breed, tag_id, farm link |
| `geofences` | Virtual fencing | PostGIS polygon, inclusion/exclusion |
| `positions` | **Hypertable** — GPS positions | Time-series, 2-year retention |
| `ble_sightings` | **Hypertable** — BLE detections | RSSI, estimated distance |
| `alerts` | Alert history | Type, severity, status lifecycle |
| `gateway_devices` | Herdsman gateways | Serial, phone model, last_seen |
| `ble_ear_tags` | BLE tag registry | MAC address → animal mapping |
| `herdsman_sessions` | Patrol sessions | Start/end time, coverage |
| `user_farm_assignments` | RBAC farm access | Role per farm, revocable |
| `notification_preferences` | Per-user settings | Channel enable/disable |
| `activity_classifications` | ML activity labels | Grazing, resting, walking |
| `animal_baselines` | Learned behaviour | Daily distance, active hours |
| `anomaly_events` | Detected anomalies | Type, z-score, resolved? |
| `farm_suggestions` | AI suggestions | Priority, actionable advice |
| `intelligence_reports` | Daily/weekly reports | JSON content, farm scope |

**Hypertables (TimescaleDB):**
- `positions` — Auto-partitioned by time (weekly chunks), 2-year retention policy
- `ble_sightings` — Auto-partitioned by time

**Spatial Indexes (PostGIS):**
- `geofences.geometry` — GIST index for spatial queries
- `positions.location` — GIST index for proximity queries

### Migrations

Located in `cloud/migrations/versions/`. Applied automatically via Docker init scripts:

```
001_initial_schema.sql          — Core tables, hypertables, extensions
002_geofence_geometry_nullable.sql — Allow null geofence geometry
003_animal_inventory_fields.sql — Extended animal attributes
004_farm_location_details.sql   — Farm lat/lon/address fields
005_notification_preferences.sql — Per-user notification settings
006_activity_classification.sql — Activity labels table
007_herdsman_gateway.sql        — Gateway devices, BLE tags, sessions
008_geofence_breach_severity.sql — Severity levels on breaches
009_farm_schedule_config.sql    — Farm daily schedule (kraal open/close)
010_analytics_intelligence.sql  — Baselines, anomalies, suggestions, reports
010_user_farm_assignments.sql   — RBAC farm assignments
011_ble_estimated_position.sql  — Estimated position from BLE sightings
```

### Useful Commands

```bash
# Open psql shell
make db-shell

# Run migrations manually
make db-migrate

# Load demo data (Boschhoek + Loch Vaal farms)
make db-seed

# Reset everything (WARNING: destroys data)
make db-reset
```

### Data Volume

| Volume | Mount Point |
|--------|-------------|
| `pgdata` | `/home/postgres/pgdata/data` |

---

## 4. Redis

**Purpose:** In-memory data store used for three functions: real-time pub/sub (WebSocket fan-out), API rate limiting, and session/state caching.

### Connection Details

| Aspect | Value |
|--------|-------|
| Image | `redis:7-alpine` |
| Port | `6379` |
| Database | `0` (default) |
| Auth | None (dev) |
| Protocol | RESP3 |

### Connection String

```
redis://localhost:6379/0
```

### Usage Patterns

#### 1. Real-Time Pub/Sub (WebSocket Fan-Out)

The MQTT Writer and API Gateway use Redis pub/sub to push live data to connected WebSocket clients:

```
Channel: farm:{farm_id}
  → position.update   (animal moved)
  → alert.created     (new alert fired)

Channel: alerts:incoming
  → Alert events for the Alert Engine to process
```

**Flow:**
```
MQTT Writer → Redis pub/sub → API Gateway WebSocket → Dashboard/Mobile
```

#### 2. API Rate Limiting

The API Gateway uses Redis as the backing store for `slowapi` rate limiting:
- Default: 200 requests/minute, 50 requests/second per IP
- Prevents abuse and ensures fair usage

#### 3. Session Cache

- Temporary state storage for active connections
- Alert cooldown tracking (Alert Engine)
- Device last-seen timestamps

### Data Volume

| Volume | Mount Point |
|--------|-------------|
| `redisdata` | `/data` |

### Health Check

```bash
redis-cli ping
# → PONG
```

---

## 5. MQTT Writer

**Purpose:** Critical bridge between MQTT device messages and the database. Subscribes to device topics on EMQX, decodes the binary protocol, validates CRC integrity, writes positions to TimescaleDB, and publishes real-time events to Redis.

### Connection Details

| Aspect | Value |
|--------|-------|
| Image | Custom build (`services/mqtt_writer/Dockerfile`) |
| Language | Python 3.12 |
| MQTT Client | paho-mqtt |
| DB Client | asyncpg (direct SQL, no ORM) |

### Responsibilities

1. Subscribe to `lg/up/+/telemetry` (QoS 1) and `lg/up/+/alert` (QoS 2)
2. Verify CRC-16/CCITT checksum on every message
3. Decode binary header (11 bytes) and position payload (16 bytes/record)
4. Write positions to `positions` hypertable
5. Detect theft (speed > 30 km/h) → create alert
6. Detect geofence breach → create alert
7. Publish real-time events to Redis pub/sub for WebSocket distribution
8. Publish alerts to `alerts:incoming` channel for Alert Engine processing
9. Auto-register unknown devices on first message

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MQTT_BROKER` | `emqx` | Broker hostname (Docker service name) |
| `MQTT_PORT` | `1883` | Broker port |
| `DATABASE_URL` | `postgresql://livestockguard:livestockguard_dev@postgres:5432/livestockguard` | Direct asyncpg connection |
| `REDIS_URL` | `redis://redis:6379/0` | For real-time pub/sub |

### Dependencies

Waits for:
- PostgreSQL (healthy)
- Redis (healthy)
- EMQX (started)

---

## 6. Alert Engine

**Purpose:** Processes incoming alert events and dispatches notifications through multiple channels based on severity. Implements cooldown logic to prevent alert fatigue.

### Connection Details

| Aspect | Value |
|--------|-------|
| Image | Custom build (`services/alert_engine/Dockerfile`) |
| Language | Python 3.12 |
| Input | Redis subscription (`alerts:incoming` channel) |

### Notification Channels

| Channel | Provider | When Used |
|---------|----------|-----------|
| Push | Firebase Cloud Messaging (FCM) | Critical, High, Medium |
| SMS | Africa's Talking | Critical only |
| Email | Amazon SES (af-south-1) | Critical, High |
| Webhook | HTTP POST | Configurable |
| Dashboard | Redis pub/sub → WebSocket | All severities |

### Severity Routing

| Severity | Push | SMS | Email | Webhook | Dashboard |
|----------|------|-----|-------|---------|-----------|
| Critical | Yes | Yes | Yes | Yes | Yes |
| High | Yes | — | Yes | — | Yes |
| Medium | Yes | — | — | — | Yes |
| Low | — | — | — | — | Yes |
| Info | — | — | — | — | Yes |

### Cooldown

Same device + alert_type combination won't fire again within **5 minutes** (300 seconds).

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_URL` | `redis://redis:6379/0` | Event subscription |
| `AWS_REGION` | `af-south-1` | SES region (Cape Town) |
| `SES_SENDER_EMAIL` | `alerts@livestockguard.co.za` | From address |
| `ALERT_EMAIL_RECIPIENTS` | (empty) | Comma-separated emails |
| `FIREBASE_CREDENTIALS_PATH` | `/app/config/firebase-credentials.json` | FCM service account |
| `WEBHOOK_URLS` | (empty) | Comma-separated URLs |

### Dependencies

Waits for:
- Redis (healthy)

---

## 7. Analytics Engine

**Purpose:** Self-monitoring intelligence service. Learns normal animal behaviour patterns and detects anomalies, generating actionable insights and daily/weekly reports.

### Connection Details

| Aspect | Value |
|--------|-------|
| Image | Custom build (`services/analytics_engine/Dockerfile`) |
| Language | Python 3.12 |
| Scheduler | APScheduler (AsyncIO) |
| Timezone | `Africa/Johannesburg` (SAST) |
| Restart Policy | `unless-stopped` |

### Scheduled Jobs

| Job | Schedule | Description |
|-----|----------|-------------|
| Baseline Builder | 02:00 SAST daily | Computes 7-day behaviour baselines per animal |
| Anomaly Detector | Every 2 hours | Flags deviations from learned baselines |
| Suggestion Engine | Every 2h + 5min | Converts anomalies into recommendations |
| Daily Report | 18:00 SAST | Compiles daily intelligence summary |
| Weekly Report | Sunday 19:00 SAST | Weekly trend analysis |

### Anomaly Detection Thresholds

| Parameter | Default | Description |
|-----------|---------|-------------|
| `REDUCED_MOVEMENT_Z_THRESHOLD` | `-2.0` | Z-score below which movement is flagged |
| `ISOLATION_HOURS_THRESHOLD` | `4` | Hours alone before isolation alert |
| `PATROL_GAP_DAYS_THRESHOLD` | `3` | Days without patrol before warning |
| `NIGHT_MOVEMENT_START_HOUR` | `22` | Night period start |
| `NIGHT_MOVEMENT_END_HOUR` | `4` | Night period end |

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://...@postgres:5432/livestockguard` | Async DB connection |
| `RUN_ON_STARTUP` | `true` | Run full pipeline immediately at boot |
| `BASELINE_WINDOW_DAYS` | `7` | Days of history for baselines |
| `ANOMALY_CHECK_INTERVAL_HOURS` | `2` | How often to check for anomalies |
| `DAILY_REPORT_HOUR` | `18` | Hour (SAST) for daily report |

### Dependencies

Waits for:
- PostgreSQL (healthy)

---

## Service Interconnection Diagram

```
                    ┌─────────────┐
                    │   Devices   │
                    │ (GPS/BLE)   │
                    └──────┬──────┘
                           │ MQTT binary
                           ▼
                    ┌─────────────┐
                    │    EMQX     │
                    │  :1883      │
                    └──────┬──────┘
                           │ subscribe
                           ▼
                    ┌─────────────┐         ┌─────────────┐
                    │ MQTT Writer │────────▶│   Redis     │
                    │             │  pub/sub │   :6379     │
                    └──────┬──────┘         └──┬───┬──────┘
                           │ SQL                │   │
                           ▼                    │   │ subscribe
                    ┌─────────────┐            │   ▼
                    │ PostgreSQL  │            │ ┌─────────────┐
                    │  :5432      │            │ │Alert Engine │
                    │ TimescaleDB │            │ │(SES/FCM/SMS)│
                    └──────┬──────┘            │ └─────────────┘
                           │                   │
              ┌────────────┼───────────┐       │ pub/sub
              │            │           │       │
              ▼            ▼           ▼       ▼
     ┌─────────────┐ ┌──────────┐ ┌─────────────┐
     │  Analytics  │ │   API    │ │  WebSocket  │
     │  Engine     │ │ Gateway  │◀┤  (via API)  │
     │ (baselines) │ │  :8000   │ │             │
     └─────────────┘ └────┬─────┘ └─────────────┘
                           │ REST / WS
                    ┌──────┴──────────────┐
                    │                      │
                    ▼                      ▼
             ┌───────────┐         ┌────────────┐
             │ Dashboard │         │ Mobile App │
             │  :5173    │         │  :8082     │
             └───────────┘         └────────────┘
```

---

## Environment Configuration

### Development (.env not required — defaults work)

All services have sensible defaults for local development. No `.env` file is needed to run `make start`.

### Production (.env required)

Copy `cloud/.env.example` and fill in real values:

```bash
# Database
POSTGRES_PASSWORD=<strong_password>

# JWT (generate: openssl rand -hex 32)
JWT_SECRET=<random_64_char_hex>

# Amazon SES (email alerts)
AWS_ACCESS_KEY_ID=<iam_key>
AWS_SECRET_ACCESS_KEY=<iam_secret>
AWS_REGION=af-south-1
SES_SENDER_EMAIL=alerts@livestockguard.co.za

# Alert recipients
ALERT_EMAIL_RECIPIENTS=farmer@example.com,manager@example.com

# Firebase (push notifications)
FIREBASE_CREDENTIALS_FILE=./config/firebase-credentials.json

# Webhooks (optional)
WEBHOOK_URLS=https://hooks.slack.com/services/xxx
```

---

## Docker Volumes

| Volume | Service | Purpose |
|--------|---------|---------|
| `pgdata` | PostgreSQL | Database files (persistent) |
| `redisdata` | Redis | AOF/RDB snapshots |
| `emqxdata` | EMQX | Broker state, retained messages |

---

## Common Operations

### Start/Stop

```bash
make start          # Start all cloud services
make stop           # Stop all cloud services
make restart        # Stop + start
make status         # Show running containers
make logs           # Tail all logs
make logs-api       # Tail API Gateway only
```

### Database

```bash
make db-shell       # Open psql
make db-migrate     # Run migrations
make db-seed        # Load demo data
make db-reset       # Nuclear option (destroy + recreate)
```

### Full Stack Development

```bash
make dev            # Start cloud + instructions for other terminals
make demo           # Automated full demo (breach scenario)
make demo-normal    # Demo with normal day
make demo-theft     # Demo with theft scenario
```

---

## Production Deployment Notes

- **Region:** AWS af-south-1 (Cape Town)
- **Database:** Amazon RDS for PostgreSQL with TimescaleDB extension
- **MQTT:** EMQX Cloud or self-hosted on EC2
- **Redis:** Amazon ElastiCache
- **API:** ECS Fargate or EC2 behind ALB
- **Alerts:** SES (verified domain), FCM (service account), Africa's Talking (SMS)
- **TLS:** All ports secured with certificates in production
- **Secrets:** AWS Secrets Manager (not `.env` files)
