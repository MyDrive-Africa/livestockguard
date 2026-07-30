# LivestockGuard — Complete System Overview

## What Is LivestockGuard?

LivestockGuard is a full-stack GPS livestock tracking and geofencing platform built for South African farmers. It provides real-time animal monitoring, virtual fencing, theft detection, and herd health analytics — delivered through affordable GPS collars, passive BLE ear tags, and a cloud-connected ecosystem of web dashboard, mobile apps, and alert systems.

The platform supports two tracking approaches:
1. **GPS Collars** — individual cellular-connected collars (nRF9160) for high-value animals
2. **BLE Ear Tags + Herdsman Gateway** — R50 passive tags detected by a herdsman's phone, for cost-effective herd-wide tracking

---

## Table of Contents

- [High-Level Architecture](#high-level-architecture)
- [Data Flow](#data-flow)
- [Device Layer (Firmware)](#device-layer-firmware)
- [Connectivity Layer](#connectivity-layer)
- [Cloud Backend Services](#cloud-backend-services)
- [Web Dashboard](#web-dashboard)
- [Mobile App (iOS/Android)](#mobile-app-iosandroid)
- [BLE Herdsman Gateway System](#ble-herdsman-gateway-system)
- [Simulators](#simulators)
- [Database Architecture](#database-architecture)
- [Alert & Notification System](#alert--notification-system)
- [Authentication & Authorisation](#authentication--authorisation)
- [CI/CD Pipeline](#cicd-pipeline)
- [Design Principles](#design-principles)
- [Technology Stack Summary](#technology-stack-summary)

---

## High-Level Architecture

LivestockGuard uses a **4-layer architecture**:

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  LAYER 4: USER INTERFACES                                                        │
│                                                                                   │
│  ┌─────────────────────────┐  ┌────────────────────────────────────────────┐    │
│  │  WEB DASHBOARD           │  │  MOBILE APP (React Native + Expo)          │    │
│  │  React 18 + Vite         │  │  iOS + Android + Web                       │    │
│  │  MapLibre GL JS          │  │  Admin mode: map, alerts, animals          │    │
│  │  TailwindCSS + Zustand   │  │  Herdsman mode: BLE scan, GPS, count      │    │
│  │  Recharts analytics      │  │                                            │    │
│  │  Framer Motion UI        │  │  Background foreground service:            │    │
│  │  Port 5173               │  │  - BLE scan every 5s                       │    │
│  │                           │  │  - GPS every 30s                           │    │
│  └─────────────┬─────────────┘  │  - Batch report every 25-30s             │    │
│                │                  │  - Offline SQLite buffer                  │    │
│                │                  │  Port 8082 (web mode)                     │    │
│                │                  └──────────────┬───────────────────────────┘    │
│                │                                  │                               │
└────────────────┼──────────────────────────────────┼───────────────────────────────┘
                 │ REST + WebSocket                  │ REST (HTTPS)
                 ▼                                   ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  LAYER 3: CLOUD BACKEND                                                          │
│                                                                                   │
│  ┌────────────────────┐  ┌───────────────────┐  ┌──────────────────────────┐   │
│  │  API GATEWAY        │  │  MQTT WRITER      │  │  ALERT ENGINE            │   │
│  │  FastAPI (Python)   │  │  (Python)         │  │  (Python)                │   │
│  │  - REST CRUD        │  │  - Subscribe MQTT │  │  - Rule evaluation       │   │
│  │  - JWT auth         │  │  - Decode binary  │  │  - Email (SES)           │   │
│  │  - WebSocket        │  │  - CRC-16 verify  │  │  - Push (FCM)            │   │
│  │  - Rate limiting    │  │  - Write to DB    │  │  - Webhook               │   │
│  │  - Gateway API      │  │  - Redis pub/sub  │  │  - SMS (Africa's Talking)│   │
│  │  Port 8000          │  │  - Theft detect   │  │  - Redis (dashboard)     │   │
│  └────────────────────┘  │  - Breach detect   │  └──────────────────────────┘   │
│                           └───────────────────┘                                   │
│  ┌────────────────────┐  ┌───────────────────┐                                  │
│  │  INGESTION          │  │  GEOFENCE ENGINE  │  (Rust — compiled, for          │
│  │  (Rust/Tokio)       │  │  (Rust)           │   high-throughput production)    │
│  │  - 5000 msg/sec     │  │  - R-tree index   │                                  │
│  │  - Binary decode    │  │  - Point-in-poly  │                                  │
│  │  - Validation       │  │  - Breach detect  │                                  │
│  └────────────────────┘  └───────────────────┘                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
                 │ SQL / MQTT / Redis
                 ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  LAYER 2: INFRASTRUCTURE & DATA                                                  │
│                                                                                   │
│  ┌──────────────────────────┐  ┌────────────┐  ┌────────────────────────────┐  │
│  │  PostgreSQL 16            │  │  Redis 7   │  │  EMQX 5.5                  │  │
│  │  + TimescaleDB            │  │  (Alpine)  │  │  MQTT 5.0 Broker           │  │
│  │                           │  │            │  │                             │  │
│  │  • positions hypertable   │  │  • Session │  │  • QoS 1 device messaging  │  │
│  │    (time-series, auto-    │  │    cache   │  │  • Topic: lg/dev/{id}/pos  │  │
│  │    partitioned weekly)    │  │  • Pub/sub │  │  • Topic: lg/dev/{id}/alert│  │
│  │  • ble_sightings hyper   │  │    for WS  │  │  • 10k concurrent conns    │  │
│  │  • farms, animals, users  │  │    fan-out │  │  • Dashboard: port 18083   │  │
│  │  • geofences (PostGIS)    │  │  • Real-   │  │  • MQTT: port 1883         │  │
│  │  • alerts, devices        │  │    time    │  │  • MQTTS: port 8883        │  │
│  │  • gateway, ble_ear_tags  │  │    state   │  │                             │  │
│  │  Port 5432                │  │  Port 6379 │  │                             │  │
│  └──────────────────────────┘  └────────────┘  └────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────┘
                 │ MQTT binary / BLE / Cellular
                 ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  LAYER 1: DEVICE LAYER                                                           │
│                                                                                   │
│  ┌─────────────────────────────────┐  ┌────────────────────────────────────┐   │
│  │  GPS COLLAR (nRF9160)            │  │  BLE EAR TAG (nRF52840)            │   │
│  │  - LTE-M / NB-IoT cellular       │  │  - Passive BLE 5.0 beacon          │   │
│  │  - GPS/GNSS positioning          │  │  - Broadcasts MAC every 1-2s       │   │
│  │  - On-device geofencing          │  │  - CR2032 coin cell (3-5 year)     │   │
│  │  - Binary protocol (CRC-16)      │  │  - No GPS, no cellular, no CPU     │   │
│  │  - Store-and-forward offline     │  │  - Cost: ~R50 per tag              │   │
│  │  - 2-5 year battery (adaptive)   │  │  - Detected by gateway phone       │   │
│  │  - Cost: ~R800+ per collar       │  │                                     │   │
│  └─────────────────────────────────┘  └────────────────────────────────────┘   │
│                                                                                   │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │  HERDSMAN GATEWAY (Phone or Dedicated ESP32 Device)                     │    │
│  │  - Scans BLE advertisements → records MAC + RSSI                        │    │
│  │  - Records own GPS position                                             │    │
│  │  - Batches sightings → POST /api/gateway/batch every 30s               │    │
│  │  - One cellular connection serves entire herd (50-200 animals)          │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Data Flow

### GPS Collar Flow (Boschhoek Farm)

```
GPS Collar (nRF9160)
    │
    │ Binary MQTT message (CRC-16 verified)
    │ Topic: lg/dev/{device_id}/pos
    ▼
EMQX Broker (port 1883)
    │
    │ Subscription: lg/dev/+/pos, lg/dev/+/alert
    ▼
MQTT Writer (Python)
    │
    ├── Decode binary header (version, msg_type, priority, device_id, timestamp, seq)
    ├── Verify CRC-16 CCITT checksum
    ├── Decode position payload (lat, lon, speed, heading, hdop, flags)
    ├── Check speed → THEFT ALERT if > 30 km/h
    ├── Check geofence → BREACH ALERT if outside polygon
    ├── Write to TimescaleDB positions hypertable
    ├── Publish to Redis pub/sub (real-time channel)
    │
    ▼
API Gateway → WebSocket → Dashboard (live marker update)
```

### BLE Gateway Flow (Loch Vaal Farm)

```
BLE Ear Tags (passive, broadcasting MAC every 1-2s)
    │
    │ BLE advertisement (≤100m range)
    ▼
Herdsman's Phone (Gateway App or Simulator)
    │
    ├── Scan BLE every 5s → filter known MACs
    ├── Record: MAC, RSSI, own GPS, timestamp
    ├── Estimate distance from RSSI (log-distance path loss model)
    │
    │ HTTPS POST /api/gateway/batch (every 25-30s)
    │ Payload: {gateway_serial, lat, lon, battery, sightings: [{mac, rssi}...]}
    ▼
API Gateway
    │
    ├── Resolve MAC → animal_id (ble_ear_tags registry)
    ├── Write to ble_sightings hypertable
    ├── Write to positions table (animal appears on map)
    ├── Update gateway_devices.last_seen
    ├── Track herdsman_sessions (patrol coverage)
    │
    ▼
Dashboard (cattle visible on map using gateway GPS as position)
```

### Alert Flow

```
Detection (MQTT Writer or Geofence Engine)
    │
    ├── Theft: speed > threshold (vehicle movement)
    ├── Breach: position outside geofence polygon
    ├── Missing: no BLE ping from tag in 24h
    │
    │ Write alert to DB + publish to Redis
    ▼
Alert Engine (subscribes to Redis alert channel)
    │
    ├── Email via AWS SES
    ├── Push notification via Firebase Cloud Messaging (FCM)
    ├── Webhook POST to configured URLs
    ├── SMS via Africa's Talking
    └── Redis pub/sub → Dashboard real-time alert badge
```

---

## Device Layer (Firmware)

The firmware is written in **C11** targeting Nordic Semiconductor chips, built with CMake and the nRF Connect SDK (Zephyr RTOS).

### Hardware Targets

| Device | Chip | Role | Connectivity | Battery |
|--------|------|------|-------------|---------|
| GPS Collar | nRF9160 | Full-featured tracker | LTE-M / NB-IoT cellular | 2-5 years (adaptive duty cycling) |
| BLE Ear Tag | nRF52840 | Passive beacon | BLE 5.0 advertisement | 3-5 years (CR2032 coin cell) |

### Firmware Architecture

```
firmware/
├── hal/include/            # Hardware Abstraction Layer
│   ├── hal_gnss.h          # GPS/GNSS module control
│   ├── hal_radio.h         # Radio interface (LTE, LoRa, BLE, Satellite)
│   ├── hal_accel.h         # Accelerometer (activity classification)
│   ├── hal_power.h         # Battery, sleep, charging
│   └── hal_types.h         # Common type definitions
│
├── src/
│   ├── main.c              # Application entry point
│   ├── app/                # State machine (sleep→fix→transmit→sleep)
│   └── services/
│       ├── gnss_service     # Acquire GPS fix, manage duty cycle
│       ├── comms_service    # Multi-protocol radio management
│       ├── power_service    # Battery monitoring, adaptive sleep
│       ├── sensor_service   # Accelerometer, temperature
│       └── config_service   # Remote configuration, OTA triggers
│
├── lib/
│   ├── geofence/           # On-device point-in-polygon (winding number)
│   ├── protocol/           # Binary wire protocol encoder (matches MQTT Writer decoder)
│   └── collections/        # Ring buffer (store-and-forward), linked list
│
└── platforms/
    ├── nrf9160_collar/     # Cellular GPS collar board config
    └── nrf52840_eartag/    # BLE beacon ear tag board config
```

### Key Firmware Features

- **On-device geofencing**: Point-in-polygon evaluation on the collar itself — can trigger local deterrents (audio/vibration) before cloud even knows
- **Store-and-forward**: Ring buffer stores positions when cellular connectivity drops; flushes when signal returns
- **Adaptive duty cycling**: Adjusts GPS fix interval based on movement (accelerometer) and battery level — achieves 2-5 year battery life
- **Binary protocol**: Compact encoding with CRC-16 CCITT integrity check, fits in single MQTT message
- **Multi-protocol HAL**: Abstract radio interface supports LTE-M, NB-IoT, LoRaWAN, BLE, and Globalstar satellite

### Connectivity Options (Architecture)

| Protocol | Use Case | Range | Power | Status |
|----------|----------|-------|-------|--------|
| LTE-M / NB-IoT | Primary cellular | National | Medium | HAL defined |
| LoRaWAN | Rural fallback | 10-15 km | Low | HAL defined |
| BLE 5.0 | Ear tag → gateway | 100m | Very low | Working (simulator) |
| Globalstar Satellite | Remote no-cell areas | Global | High | HAL defined |

---

## Cloud Backend Services

All services run in Docker Compose locally. In production, they deploy to AWS af-south-1 (Cape Town).

### API Gateway (`cloud/services/api_gateway/`)

The central REST + WebSocket server. All client applications (dashboard, mobile app, simulators) talk to this.

| Aspect | Detail |
|--------|--------|
| Framework | FastAPI (Python 3.12) |
| ORM | SQLAlchemy 2.0 (async) |
| DB Driver | asyncpg (PostgreSQL) |
| Auth | JWT (access + refresh tokens), bcrypt password hashing |
| Port | 8000 |
| Docs | Swagger UI at `/docs`, ReDoc at `/redoc` |

**Router modules:**
- `auth.py` — login, register, refresh token, password reset
- `animals.py` — CRUD, search, filter by farm/species/status, pagination
- `devices.py` — list, detail, command queuing, status updates
- `alerts.py` — list, acknowledge, resolve, filter by severity/type
- `geofences.py` — CRUD, GeoJSON geometry, active/inactive toggle
- `farms.py` — farm management, location details
- `analytics.py` — aggregated stats, time-series queries
- `gateway.py` — BLE gateway batch ingestion, tag registration, session management

**Key endpoints:**
```
POST   /api/auth/login              # JWT login
POST   /api/auth/register           # New user
GET    /api/animals                  # List animals (paginated)
GET    /api/animals/{id}            # Animal detail + device info
GET    /api/animals/{id}/history    # Position history (trail)
GET    /api/devices                  # List devices
POST   /api/devices/{id}/command    # Queue command to device
GET    /api/alerts                   # List alerts
PUT    /api/alerts/{id}/acknowledge # Acknowledge alert
GET    /api/geofences               # List geofences
POST   /api/geofences               # Create geofence (GeoJSON polygon)
GET    /api/analytics/summary       # Dashboard stats
POST   /api/gateway/batch           # BLE gateway sighting batch
POST   /api/gateway/register        # Register gateway device
POST   /api/gateway/tags            # Register BLE ear tag
POST   /api/gateway/sessions/start  # Start patrol session
POST   /api/gateway/sessions/{id}/end  # End patrol session
GET    /ws                           # WebSocket real-time feed
GET    /health                       # Health check
```

### MQTT Writer (`cloud/services/mqtt_writer/`)

Bridges the gap between MQTT device messages and the database. Runs as a long-lived Python process.

| Aspect | Detail |
|--------|--------|
| Language | Python 3.12 |
| MQTT Client | paho-mqtt |
| DB | asyncpg (direct SQL, no ORM overhead) |
| Real-time | Redis pub/sub for WebSocket fan-out |

**Responsibilities:**
1. Subscribe to `lg/dev/+/pos` and `lg/dev/+/alert` on EMQX
2. Decode binary protocol header (11 bytes) + payload
3. Verify CRC-16 CCITT integrity
4. Parse position records (lat, lon, speed, heading, HDOP, flags)
5. **Theft detection**: speed > 30 km/h → generate theft alert
6. **Geofence check**: point-in-polygon against active geofences → breach alert
7. Write positions to TimescaleDB `positions` hypertable
8. Write alerts to `alerts` table
9. Publish real-time updates to Redis channel → WebSocket consumers

### Alert Engine (`cloud/services/alert_engine/`)

Multi-channel notification dispatch system. Subscribes to Redis for new alerts and fans out to configured channels.

| Aspect | Detail |
|--------|--------|
| Language | Python 3.12 |
| Architecture | Dispatcher plugin pattern |

**Dispatchers (pluggable):**
- `email_ses.py` — AWS Simple Email Service (af-south-1 region)
- `push_fcm.py` — Firebase Cloud Messaging (iOS/Android push)
- `sms_africastalking.py` — Africa's Talking SMS API (South African numbers)
- `webhook.py` — HTTP POST to configured webhook URLs
- `dashboard_redis.py` — Redis pub/sub for real-time dashboard badge

### Ingestion Service (`cloud/services/ingestion/`)

High-throughput binary message decoder written in Rust for production scale.

| Aspect | Detail |
|--------|--------|
| Language | Rust (Tokio async runtime) |
| Throughput | 5,000 messages/sec target |
| Role | Decode, validate, route MQTT messages to TimescaleDB |

### Geofence Engine (`cloud/services/geofence_engine/`)

Spatial breach detection service using R-tree spatial indexing.

| Aspect | Detail |
|--------|--------|
| Language | Rust |
| Algorithm | Point-in-polygon with R-tree index for O(log n) lookup |
| Role | Evaluate every incoming position against all active geofences |

---

## Web Dashboard

The web dashboard is a single-page application providing real-time livestock monitoring, geofence management, analytics, and alert handling.

### Technology

| Component | Library |
|-----------|---------|
| Framework | React 18 |
| Build | Vite 5 |
| Language | TypeScript |
| Styling | TailwindCSS 3.4 |
| Maps | MapLibre GL JS 4 (OpenStreetMap + Satellite tiles) |
| State | Zustand 4.5 |
| Data Fetching | TanStack React Query 5 |
| Charts | Recharts 2.10 |
| Animations | Framer Motion 11 |
| HTTP | Axios |
| Routing | React Router 6 |

### Pages & Features

| Page | Path | Features |
|------|------|----------|
| **Map** | `/map` | Live animal markers, movement trails (24h), geofence polygon overlays, tile switching (Street/Satellite/Terrain), click-to-draw geofence, 📍 farm coordinate pin marker (shows exact farm centre, name label, coordinate readout — pin moves when switching farms, stays visible on satellite view for geofence orientation) |
| **Animals** | `/animals` | Sortable/searchable list, filter by species/status/farm, detail view with history trail |
| **Alerts** | `/alerts` | Real-time alert feed, severity badges, acknowledge/resolve workflow, filter by type |
| **Analytics** | `/analytics` | Area/line/bar/donut charts, sparklines in summary cards, date range picker, dark-mode tooltips |
| **Devices** | `/devices` | Device status grid, battery levels, last-seen, firmware version, command queue |
| **Geofences** | `/geofences` | List, create, edit, toggle active/inactive, GeoJSON geometry |
| **Gateway** | `/gateway` | Gateway device status, BLE tag registry, herdsman patrol sessions, animals per gateway |
| **Auth** | `/login` | JWT login form, session persistence |

### State Management (Zustand Stores)

- **authStore** — JWT tokens, user info, login/logout, refresh
- **mapStore** — map position, zoom, selected animal, tile layer
- **realtimeStore** — WebSocket connection, live position updates, alert badges
- **themeStore** — dark/light/system preference, persists to localStorage

### Real-Time Updates

```
MQTT Writer → Redis pub/sub → API Gateway WebSocket → Dashboard
```

The dashboard connects via WebSocket to `/ws` and receives:
- Position updates (animal moved)
- New alerts (theft, breach, missing)
- Device status changes (battery, offline)

### UI/UX

- **Theme**: Dark / Light / System toggle — stored in localStorage, applied via Tailwind `darkMode: 'class'`
- **Animations**: Framer Motion page transitions, staggered card animations, animated progress bars, count-up numbers, pulse alert badges
- **Responsive**: Works on desktop, tablet, mobile browsers
- **Accessibility**: Semantic HTML, ARIA labels, keyboard navigation

---

## Mobile App (iOS/Android)

A single React Native app with **two modes** based on user role:

### Technology

| Component | Library |
|-----------|---------|
| Framework | React Native 0.74 |
| Platform | Expo 51 (managed + bare workflows) |
| Maps | react-native-maps (Google Maps provider) |
| Storage | @react-native-async-storage/async-storage |
| HTTP | Axios |
| Language | TypeScript |

### App Modes

#### Admin/Farmer Mode
Full monitoring capabilities — a mobile-optimized version of the web dashboard:
- Map with cattle markers (react-native-maps)
- Animal list with search/filter
- Geofence view (read-only on mobile)
- Alert feed with push notifications (FCM)
- Cattle count summary
- Schedule viewer
- User management (owner only)

#### Herdsman Mode
Turns the phone into a BLE gateway device — runs as a background foreground service:
- **BLE scanning**: Every 5-10 seconds, scans for known BLE ear tags
- **GPS tracking**: Fused location updates every 30 seconds
- **Batch reporting**: POST `/api/gateway/batch` every 25-30s
- **Offline buffer**: SQLite stores sightings when no internet (up to 24h, ~100KB)
- **Lock screen notification**: "📶 LivestockGuard: 10/10 cattle in range"
- **Missing animal alert**: "⚠️ LV-003 out of range for 10 min"
- **Auto-start on boot**: Foreground service resumes after phone restart
- **Battery usage**: ~5-8% per hour (BLE + GPS combined)

### Screens

| Screen | File | Admin | Herdsman |
|--------|------|:-----:|:--------:|
| Login | `LoginScreen.tsx` | ✅ | ✅ |
| Admin Dashboard | `AdminDashboard.tsx` | ✅ | ❌ |
| Map | `MapScreen.tsx` | ✅ | ❌ |
| Animals | `AnimalsScreen.tsx` | ✅ | ❌ |
| Herdsman BLE | `HerdsmanScreen.tsx` | ❌ | ✅ |

### Running the Mobile App

```bash
make mobile-web       # Browser at http://localhost:8082
make mobile-ios       # iOS simulator (requires Xcode)
make mobile-android   # Android emulator (requires Android SDK + JDK 17)
```

---

## BLE Herdsman Gateway System

The cost-effective alternative to individual GPS collars. Uses passive BLE ear tags (~R50 each) detected by a herdsman's phone.

### Cost Comparison (50 cattle)

| Item | GPS Collar Approach | BLE Gateway Approach |
|------|--------------------|--------------------|
| Tags/Collars (50x) | 50 × R800 = R40,000 | 50 × R50 = R2,500 |
| Cellular SIMs (50x) | 50 × R99/mo = R4,950/mo | 0 |
| Gateway device | N/A | 1 × R0 (phone) or R1,200 (dedicated) |
| Gateway SIM | N/A | 1 × R99/mo |
| **Year 1 Total** | **~R100,000+** | **~R4,000** |
| **Annual ongoing** | **~R60,000** | **~R1,200** |

### How It Works

1. **BLE Ear Tags** broadcast their MAC address via BLE advertisement every 1-2 seconds
2. **Gateway** (herdsman's phone) scans every 5 seconds, filters by known MACs
3. **RSSI → Distance**: Log-distance path loss model estimates distance from signal strength
4. **Batch POST**: Every 30 seconds, gateway sends `{serial, gps, battery, sightings[{mac, rssi}...]}` to API
5. **Cloud resolves**: MAC → animal_id lookup, stores sighting, writes position (gateway GPS = animal position ±100m)
6. **Dashboard**: Animal appears on map at gateway's GPS coordinates

### RSSI Distance Estimation

```
distance = 10 ^ ((TxPower - RSSI) / (10 * n))
```

| RSSI (dBm) | Estimated Distance | Signal Quality |
|------------|-------------------|----------------|
| -50 to -60 | 1–3m | Excellent |
| -60 to -75 | 3–15m | Good |
| -75 to -90 | 15–50m | Fair |
| -90 to -100 | 50–100m | Weak |

### Database Tables (Gateway-Specific)

- **gateway_devices** — registered gateways (phone or hardware), config, last position
- **ble_ear_tags** — MAC → animal mapping, battery estimates, install date
- **ble_sightings** — TimescaleDB hypertable of every BLE detection (high-volume, 1-year retention)
- **herdsman_sessions** — patrol shifts: start/end, animals seen, distance walked

### Limitations & Mitigations

| Limitation | Mitigation |
|-----------|-----------|
| Position accuracy ±100m | Acceptable for theft/breach detection at farm scale |
| Only tracked during patrols | Fixed BLE gateways at watering points (future) |
| Single point of failure (phone) | Multiple gateways per farm, alert if offline |
| BLE range ~100m | Herdsman walks among herd; sufficient for counting |

---

## Simulators

Three Python simulators replicate device behaviour without requiring real hardware.

### 1. GPS Collar Simulator (`tools/simulator/simulator.py`)

Simulates nRF9160 GPS collars sending binary MQTT messages.

| Aspect | Detail |
|--------|--------|
| Protocol | Binary MQTT with CRC-16 CCITT (matches firmware exactly) |
| Encoding | struct.pack: version, msg_type, priority, device_id, timestamp, seq, payload |
| Broker | EMQX on localhost:1883 |
| Topics | `lg/dev/{device_id}/pos` |

**Scenarios:**
- **Normal**: Animals graze within paddock, random walk within geofence
- **Theft**: One animal accelerates to vehicle speed (60+ km/h), moves away rapidly
- **Breach**: One animal drifts outside geofence polygon boundary

**Commands:**
```bash
make simulate             # Boschhoek, 5 animals, 10s interval
make simulate-lochvaal    # Loch Vaal, 10 animals, 10s interval
make simulate-theft       # Theft scenario
make simulate-breach      # Breach scenario
make simulate-many        # 50 animals stress test
```

### 2. BLE Gateway Simulator (`tools/simulator/gateway_simulator.py`)

Simulates a herdsman carrying a phone that scans BLE ear tags.

| Aspect | Detail |
|--------|--------|
| Protocol | REST API (POST /api/gateway/batch) |
| BLE Simulation | Virtual MAC addresses, RSSI calculated from distance |
| GPS | Simulated rectangular patrol route |

**Commands:**
```bash
make simulate-gateway          # Real-time with API
make simulate-gateway-offline  # Print only
```

### 3. Herdsman Daily Routine Simulator (`tools/simulator/gateway_daily_sim.py`)

The most realistic simulator — follows actual Loch Vaal Plot 30 farm layout and daily schedule.

| Aspect | Detail |
|--------|--------|
| Farm Layout | Real coordinates: kraal, feeding area, gate, road waypoints, grazing fields |
| Schedule | Configurable kraal-open/return times, mimics actual farm routine |
| Movement | Cattle follow roads/paths (not through fences), realistic herd behaviour |
| Speed Control | `--speed 20` = 20x real-time, `--speed 360` = 12h in 2 min |

**Daily Schedule (simulated):**
```
Night:     Cattle sleeping in kraal (15m radius cluster)
08:30:     Gate opens → cattle move to feeding troughs (20m radius)
09:20:     Walk to Entrance/Exit gate (single file on path)
09:50:     Exit yard → herdsman leads via roads to grazing area
12:00:     Midday rest (cattle clustered, low movement)
13:00:     Afternoon grazing (wider spread, individual wandering)
16:30:     Return via road back to gate
17:00:     Enter gate, water stop at troughs
17:45:     Walk to kraal, settle for night
```

**Scenarios:**
- `--scenario normal` — uneventful day, all cattle return safely
- `--scenario theft` — at sim 10:00, one cow is "loaded onto a bakkie" and driven 5km away
- `--scenario breach` — one cow exits the 100m BLE detection range

**Commands:**
```bash
make simulate-day              # Normal day, speed 120x (~6 min)
make simulate-day-offline      # Same without API
make simulate-day-theft        # Theft at 10:00, speed 360x
make simulate-day-breach       # Breach scenario, speed 360x
```

---

## Database Architecture

PostgreSQL 16 with TimescaleDB extension for time-series data.

### Schema Overview (9 migrations)

| Migration | What It Creates |
|-----------|----------------|
| 001_initial_schema | Core tables: organisations, farms, users, animals, devices, positions (hypertable), geofences, alerts |
| 002_geofence_geometry_nullable | Make geofence geometry nullable for draft geofences |
| 003_animal_inventory_fields | Add gender, colour, description, weight, date_of_birth, acquired_date to animals |
| 004_farm_location_details | Add province, district, latitude, longitude, area_hectares to farms |
| 005_notification_preferences | User notification preferences (channels, quiet hours) |
| 006_activity_classification | Activity states (grazing, walking, resting, running) for health analytics |
| 007_herdsman_gateway | gateway_devices, ble_ear_tags, ble_sightings (hypertable), herdsman_sessions |
| 008_geofence_breach_severity | Severity levels on alerts (low, medium, high, critical) |
| 009_farm_schedule_config | Farm schedule configuration (kraal open/close times, feed times) |

### Key Tables

```sql
-- Time-series: GPS positions (auto-partitioned weekly)
CREATE TABLE positions (
    time        TIMESTAMPTZ NOT NULL,
    device_id   UUID,
    animal_id   UUID,
    latitude    DOUBLE PRECISION,
    longitude   DOUBLE PRECISION,
    altitude    REAL,
    speed       REAL,
    heading     REAL,
    hdop        REAL,
    battery_pct INTEGER
);
SELECT create_hypertable('positions', 'time');

-- Time-series: BLE sightings (high-volume, 1-year retention)
CREATE TABLE ble_sightings (
    time                TIMESTAMPTZ NOT NULL,
    gateway_id          UUID,
    ble_tag_id          UUID,
    mac_address         VARCHAR(17),
    animal_id           UUID,
    rssi                INTEGER,
    estimated_distance_m REAL,
    gateway_latitude    DOUBLE PRECISION,
    gateway_longitude   DOUBLE PRECISION,
    gateway_speed       REAL,
    gateway_battery_pct INTEGER
);
SELECT create_hypertable('ble_sightings', 'time');

-- Geofences with GeoJSON geometry
CREATE TABLE geofences (
    id          UUID PRIMARY KEY,
    farm_id     UUID REFERENCES farms(id),
    name        VARCHAR(255),
    geometry    JSONB,        -- GeoJSON Polygon
    fence_type  VARCHAR(50),  -- inclusion, exclusion
    is_active   BOOLEAN DEFAULT true
);
```

### Data Stores Summary

| Store | Role | Technology |
|-------|------|-----------|
| PostgreSQL 16 | Entity storage (farms, animals, users, geofences, alerts) | Relational, ACID |
| TimescaleDB | Time-series hypertables (positions, ble_sightings) | Auto-partitioned, compression |
| Redis 7 | Session cache, real-time pub/sub, WebSocket fan-out | In-memory, AOF persistence |
| EMQX 5.5 | Device MQTT messaging (QoS 1, topic routing) | Clusterable, 10k connections |

---

## Alert & Notification System

### Alert Types

| Type | Trigger | Severity | Detection |
|------|---------|----------|-----------|
| Theft | Animal speed > 30 km/h (vehicle movement) | Critical | MQTT Writer |
| Geofence Breach | Position outside inclusion polygon or inside exclusion zone | High | MQTT Writer / Geofence Engine |
| Animal Missing | No BLE ping from tag in configurable threshold (default 24h) | Medium | Scheduled check |
| Gateway Offline | Gateway device not reporting for > 1 hour | Medium | Scheduled check |
| Low Battery | Device or gateway battery below 20% | Low | Position/batch report |

### Dispatch Channels

| Channel | Provider | Configuration |
|---------|----------|---------------|
| Email | AWS SES (af-south-1) | `SES_SENDER_EMAIL`, `ALERT_EMAIL_RECIPIENTS` |
| Push Notification | Firebase Cloud Messaging | `FIREBASE_CREDENTIALS_FILE` |
| SMS | Africa's Talking | API key in config |
| Webhook | HTTP POST | `WEBHOOK_URLS` (comma-separated) |
| Dashboard | Redis pub/sub | Always active |

### Alert Lifecycle

```
ACTIVE → ACKNOWLEDGED → RESOLVED
```

- **Active**: New alert, appears as badge on dashboard, triggers notifications
- **Acknowledged**: User has seen it, stops repeated notifications
- **Resolved**: Issue handled, archived for reporting

---

## Authentication & Authorisation

### JWT Flow

```
POST /api/auth/login {email, password}
    → Verify bcrypt hash
    → Issue access_token (short-lived) + refresh_token (long-lived)
    → Client stores in localStorage (web) or SecureStore (mobile)

Protected request: Authorization: Bearer <access_token>
    → Validate JWT signature + expiry
    → Extract user_id, organisation_id, role

Token refresh: POST /api/auth/refresh {refresh_token}
    → Issue new access_token
```

### Roles (RBAC)

| Role | Permissions |
|------|-------------|
| Owner | Full access: all CRUD, user management, billing |
| Admin | Manage animals, devices, geofences, view analytics |
| Farmer | View dashboard, acknowledge alerts, view animals |
| Herdsman | BLE gateway mode only, patrol sessions, cattle count |

### Multi-Tenancy

- Organisation-scoped: every query filtered by `organisation_id`
- Farm-level isolation within organisation
- Users belong to one organisation, can access all farms in that org

---

## CI/CD Pipeline

GitHub Actions workflow (`.github/workflows/ci.yml`) runs on every push/PR to `main`.

### Jobs

| Job | What It Tests | Language |
|-----|---------------|----------|
| `api-gateway-tests` | 47+ pytest cases (auth, CRUD, WebSocket) | Python 3.12 |
| `alert-engine-tests` | Dispatcher unit tests | Python 3.12 |
| `mqtt-writer-tests` | Protocol decode, DB write tests | Python 3.12 |
| `rust-tests` | Ingestion + Geofence Engine unit tests | Rust stable |
| `dashboard-build` | TypeScript type check + Vite production build | Node 20 |
| `ci-pass` | Gate job — all above must pass | — |

### Local Testing

```bash
make test           # Run all tests (firmware, cloud, dashboard)
make test-cloud     # Python backend only
make test-dashboard # Dashboard TypeScript check
make verify-api     # API feature verification (needs stack running)
make verify-e2e     # Playwright E2E (needs dashboard + stack)
make verify-all     # All verification
```

### E2E Testing (Playwright)

Located in `e2e/` — tests the full stack including:
- Login flow
- Map rendering
- Animal CRUD
- Alert acknowledge
- Geofence visibility

```bash
cd e2e && npx playwright test tests/features.spec.ts --reporter=list
```

---

## Design Principles

| Principle | Implementation |
|-----------|---------------|
| **Offline-first** | Firmware store-and-forward ring buffer; mobile SQLite offline buffer; gateway batch flush on reconnect |
| **Power-aware** | Adaptive GPS duty cycling based on accelerometer + battery; BLE ear tags last 3-5 years on coin cell |
| **Multi-tenant** | Organisation-scoped RBAC; farm-level data isolation; shared infrastructure |
| **South Africa-first** | AWS af-south-1 (Cape Town); POPIA compliant; ICASA spectrum rules; ZAR pricing; local SMS provider |
| **Resilient** | Graceful degradation: GPS → BLE → LoRa → Satellite fallback chain; retry queues; circuit breakers |
| **Cost-effective** | BLE ear tags at R50 vs GPS collars at R800; one SIM per herd not per animal; open-source stack |
| **Real-time** | MQTT → Redis pub/sub → WebSocket pipeline; sub-second dashboard updates |
| **Testable** | In-memory SQLite for unit tests; simulators replace hardware; Docker Compose for integration |

---

## Technology Stack Summary

### Languages

| Language | Where Used | Why |
|----------|-----------|-----|
| **Python 3.12** | API Gateway, MQTT Writer, Alert Engine, Simulators | Fast iteration, async (FastAPI), rich ecosystem |
| **Rust** | Ingestion Service, Geofence Engine | Performance-critical paths (5000 msg/sec), memory safety |
| **TypeScript** | Dashboard, Mobile App | Type safety across frontend codebases |
| **C11** | Firmware | Bare-metal embedded (Zephyr RTOS, nRF SDK) |
| **SQL** | Migrations, seed data | Schema definition, complex queries |

### Frameworks & Libraries

| Category | Technology | Purpose |
|----------|-----------|---------|
| Backend API | FastAPI | Async REST + WebSocket, auto-generated Swagger docs |
| ORM | SQLAlchemy 2.0 (async) | Database models, async queries with asyncpg |
| MQTT | paho-mqtt (Python), EMQX (broker) | Device-to-cloud messaging |
| Async Runtime | Tokio (Rust) | High-concurrency MQTT ingestion |
| Web Framework | React 18 | Component-based dashboard UI |
| Build Tool | Vite 5 | Fast HMR, optimised production builds |
| CSS | TailwindCSS 3.4 | Utility-first, dark mode support |
| Maps | MapLibre GL JS 4 | Open-source vector map rendering |
| State | Zustand 4.5 | Lightweight React state management |
| Data Fetching | TanStack React Query 5 | Cache, refetch, optimistic updates |
| Charts | Recharts 2.10 | Composable SVG charts |
| Animations | Framer Motion 11 | Page transitions, micro-interactions |
| Mobile | React Native 0.74 + Expo 51 | Cross-platform iOS/Android |
| Mobile Maps | react-native-maps | Google Maps on mobile |
| Testing | pytest, cargo test, Playwright | Unit + integration + E2E |

### Infrastructure

| Component | Technology | Port |
|-----------|-----------|------|
| Database | PostgreSQL 16 + TimescaleDB | 5432 |
| Cache/PubSub | Redis 7 Alpine | 6379 |
| MQTT Broker | EMQX 5.5 | 1883, 8883, 18083 |
| Containers | Docker Compose | — |
| CI/CD | GitHub Actions | — |
| Cloud (prod) | AWS af-south-1 (Cape Town) | — |
| IaC | Terraform | — |

### Hardware (Production)

| Device | Chip | Role |
|--------|------|------|
| GPS Collar | Nordic nRF9160 | Cellular + GPS tracker |
| BLE Ear Tag | Nordic nRF52840 | Passive BLE beacon |
| Gateway (option) | ESP32-S3 | Dedicated BLE scanner + LTE |

---

## Demo Farms

The dashboard map shows a **📍 pin marker** at each farm's exact centre coordinates. The pin displays:
- Farm name label below the pin
- Coordinate readout (lat, lon)
- Pin stays visible on satellite view to help orient geofence drawing
- Switches position when you change the selected farm

### Boschhoek Farm (Free State)

| Detail | Value |
|--------|-------|
| Location | **-29.12, 26.21** (Free State, Lejweleputswa) |
| Pin Marker | 📍 -29.12000, 26.21000 |
| Size | 450 hectares |
| Animals | 5 (Bella, Storm, Thunder, Daisy, Rosie) |
| Breeds | Nguni, Brahman, Bonsmara, Jersey |
| Tracking | GPS collars (binary MQTT protocol) |
| Geofences | 3 (Paddock North, Paddock South, Dam exclusion zone) |

### Loch Vaal Plot 30 (Gauteng)

| Detail | Value |
|--------|-------|
| Location | **-26.719088, 27.709759** (Vanderbijlpark, Gauteng) |
| Pin Marker | 📍 -26.71909, 27.70976 |
| Size | 2 hectares (yard) + surrounding grazing |
| Animals | 10 BLE-tagged cattle |
| Tracking | BLE ear tags + herdsman gateway |
| Infrastructure | Kraal, feeding troughs, entrance/exit gate |
| Herdsman | Sipho Molefe (GW-LV-001) |
| Daily Schedule | 08:30 open → graze → 17:45 return |

### Sibanyoni Farm (North West)

| Detail | Value |
|--------|-------|
| Location | **-25.35806, 25.36128** (North West Province) |
| Pin Marker | 📍 -25.35806, 25.36128 |
| Tracking | GPS collars (device base 0x3000) |
| Simulator | `python simulator.py --farm sibanyoni` |

---

## GPS Coordinates & Map Markers

All coordinates used in the system (simulators, seed data, geofences). Use these to verify markers on the dashboard map or to configure new farms.

### Farm Centres

| Farm | Latitude | Longitude | Province | Simulator Flag |
|------|----------|-----------|----------|----------------|
| Boschhoek Farm | -29.120000 | 26.210000 | Free State (Lejweleputswa) | `--farm boschhoek` |
| Loch Vaal Plot 30 | -26.719088 | 27.709759 | Gauteng (Vanderbijlpark) | `--farm lochvaal` |
| Sibanyoni Farm | -25.358056 | 25.361275 | North West | `--farm sibanyoni` |

### Boschhoek Geofences (Polygons)

| Geofence | Type | NW Corner | SE Corner | Area |
|----------|------|-----------|-----------|------|
| Paddock North | Inclusion | -29.110, 26.200 | -29.125, 26.220 | ~2.2 km × 1.7 km |
| Paddock South | Inclusion | -29.125, 26.200 | -29.140, 26.220 | ~2.2 km × 1.7 km |
| Dam (Exclusion) | Exclusion | -29.118, 26.208 | -29.122, 26.212 | ~440m × 440m |

**Paddock North polygon (WKT):**
```
POLYGON((26.200 -29.110, 26.220 -29.110, 26.220 -29.125, 26.200 -29.125, 26.200 -29.110))
```

**Paddock South polygon (WKT):**
```
POLYGON((26.200 -29.125, 26.220 -29.125, 26.220 -29.140, 26.200 -29.140, 26.200 -29.125))
```

**Dam exclusion polygon (WKT):**
```
POLYGON((26.208 -29.118, 26.212 -29.118, 26.212 -29.122, 26.208 -29.122, 26.208 -29.118))
```

### Loch Vaal Geofences (Layered Zones)

Escalating breach severity — inner zones are more critical.

| Zone | Name | Severity | NW Corner | SE Corner | Size |
|------|------|----------|-----------|-----------|------|
| 1 | Kraal (Night Enclosure) | Critical | -26.71879, 27.70926 | -26.71939, 27.71026 | ~50m × 65m |
| 2 | Yard Boundary (2ha) | High | -26.71809, 27.70876 | -26.72009, 27.71076 | ~200m × 220m |
| 3 | Loch Vaal Area (100km) | Medium | -25.819, 26.610 | -27.619, 28.810 | ~200km × 200km |
| — | Dam (Exclusion Zone) | High | -26.71940, 27.70940 | -26.71980, 27.70990 | ~45m × 55m |

### Loch Vaal Key Landmarks (BLE Simulator)

These are the physical infrastructure points that cattle and the herdsman move between during the daily simulation.

| Landmark | Latitude | Longitude | Radius | Purpose |
|----------|----------|-----------|--------|---------|
| Kraal Centre | -26.719000 | 27.708830 | 15m | Night enclosure (cattle sleep here) |
| Feeding Troughs | -26.719000 | 27.709300 | 20m | Morning feed + evening water |
| Entrance/Exit Gate | -26.718910 | 27.709940 | — | Only way in/out of the yard |

### Loch Vaal Road Waypoints (Herdsman Route)

The BLE gateway simulator moves the herdsman along these waypoints — cattle follow roads, not straight lines through fences.

| # | Latitude | Longitude | Description |
|---|----------|-----------|-------------|
| 1 | -26.718800 | 27.710200 | Just outside gate, on road |
| 2 | -26.718500 | 27.710600 | Road heading north-east |
| 3 | -26.718000 | 27.711000 | Road intersection (grazing areas branch from here) |

### Loch Vaal Grazing Areas

| Area | Centre Lat | Centre Lon | Waypoints To Reach |
|------|-----------|-----------|-------------------|
| North field (along Barrage Rd) | -26.715500 | 27.709500 | via intersection → NW track |
| East riverside | -26.719000 | 27.713500 | via intersection → E road |
| South pasture | -26.722000 | 27.709500 | via gate → south track |
| West clearing | -26.718500 | 27.706000 | via gate → W dirt track |

### Boschhoek Animal Start Positions

All 5 GPS-collared animals begin near the farm centre (-29.12, 26.21) with small random offsets. Device IDs are hex-based:

| Animal | Device ID | Start Lat | Start Lon | Breed |
|--------|-----------|-----------|-----------|-------|
| Bella | 0x1000 | -29.120 + offset | 26.210 + offset | Nguni |
| Storm | 0x1001 | -29.120 + offset | 26.210 + offset | Brahman |
| Thunder | 0x1002 | -29.120 + offset | 26.210 + offset | Bonsmara |
| Daisy | 0x1003 | -29.120 + offset | 26.210 + offset | Nguni |
| Rosie | 0x1004 | -29.120 + offset | 26.210 + offset | Jersey |

*(offset = random ±0.001° ≈ ±111m at start)*

### Loch Vaal BLE Animals

All 10 BLE-tagged cattle start in the kraal (-26.719, 27.70883) and follow the daily routine.

| Animal | BLE MAC | Device ID | Breed | Colour |
|--------|---------|-----------|-------|--------|
| LV-001 | A1:B2:C3:D4:E5:01 | 0x2000 | Nguni | Brown speckled |
| LV-002 | A1:B2:C3:D4:E5:02 | 0x2001 | Nguni | Black and white |
| LV-003 | A1:B2:C3:D4:E5:03 | 0x2002 | Bonsmara | Red-brown |
| LV-004 | A1:B2:C3:D4:E5:04 | 0x2003 | Brahman | White-grey |
| LV-005 | A1:B2:C3:D4:E5:05 | 0x2004 | Nguni | Dun with black points |
| LV-006 | A1:B2:C3:D4:E5:06 | 0x2005 | Bonsmara | Light red |
| LV-007 | A1:B2:C3:D4:E5:07 | 0x2006 | Nguni | Tricolour |
| LV-008 | A1:B2:C3:D4:E5:08 | 0x2007 | Brahman | Light grey |
| LV-009 | A1:B2:C3:D4:E5:09 | 0x2008 | Nguni | Red with white spots |
| LV-010 | A1:B2:C3:D4:E5:10 | 0x2009 | Bonsmara | Dark red |

### Gateway Device

| Field | Value |
|-------|-------|
| Serial | GW-LV-001 |
| Herdsman | Sipho Molefe |
| Type | Phone |
| Start Position | Kraal (-26.719, 27.70883) |
| Scan Interval | 5000ms |
| Report Interval | 30s |
| Max BLE Range | 100m |

### Coordinate Reference (How to Verify on Map)

To see these locations on a real map:
1. Open Google Maps
2. Paste coordinates (e.g. `-26.719088, 27.709759`)
3. Or open the dashboard at http://localhost:5173 and zoom to the marker cluster

The dashboard uses MapLibre GL with OpenStreetMap tiles. All coordinates are WGS84 (EPSG:4326) — standard GPS datum.

---

## Related Documents

| Document | Focus |
|----------|-------|
| [README.md](../README.md) | Quick start, make targets, run guide |
| [FIRMWARE_SPEC.md](FIRMWARE_SPEC.md) | Embedded C architecture, state machine, power management |
| [CLOUD_BACKEND_SPEC.md](CLOUD_BACKEND_SPEC.md) | Microservice contracts, DB schema detail, API reference |
| [DASHBOARD_SPEC.md](DASHBOARD_SPEC.md) | React pages, component architecture, store design |
| [MOBILE_APP_SPEC.md](MOBILE_APP_SPEC.md) | React Native app, BLE scanning, offline buffer, roles |
| [HERDSMAN_GATEWAY_SPEC.md](HERDSMAN_GATEWAY_SPEC.md) | BLE ear tag system, RSSI math, cost analysis |
| [CONNECTIVITY_SPEC.md](CONNECTIVITY_SPEC.md) | Multi-protocol fallback, compression, duty cycling |
| [DEPLOYMENT_SPEC.md](DEPLOYMENT_SPEC.md) | AWS deployment, POPIA compliance, pricing model |
