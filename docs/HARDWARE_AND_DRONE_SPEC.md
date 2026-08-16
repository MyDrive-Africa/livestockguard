# LivestockGuard — Hardware, Drone & Camera Surveillance Spec

> Last updated: 2026-08-16

---

## 1. Hardware: GPS Collars & BLE Ear Tags

### 1.1 BLE Ear Tags (Passive — Cheapest Entry Point)

BLE ear tags are passive beacons that broadcast their MAC address. The herdsman's phone (gateway) detects them and reports sightings to the API. No firmware development required — the LivestockGuard gateway batch API, herd-count, and missing-animal logic already work with any BLE beacon.

| Product | Price (ZAR) | Battery Life | Range | Notes |
|---------|-------------|--------------|-------|-------|
| Minew C6 Livestock Beacon | R50–R100 | 3–5 years (CR2477) | 80m | IP67, -30°C to 85°C, configurable interval |
| RF-Star RF-B-AR1 | R60–R120 | 2–4 years | 60m | Small form factor, ear tag mount |
| April Brother ABTemp | R80–R150 | 3 years | 50m | Temperature sensor built-in |
| Laird Sentrius BT710 | R200–R350 | 5+ years | 100m | Industrial grade, long range |

**Recommendation**: Start with Minew C6 (best value for South African farms). Buy 10–20 for Loch Vaal pilot.

**Integration**: Zero code changes needed. Register each tag's MAC via `POST /api/v1/gateway/tags` and link to an animal. The herdsman's phone gateway picks them up immediately.

### 1.2 GPS Collars (Active — Position Reporting)

GPS collars use the nRF9160 SiP (System-in-Package) with integrated LTE-M/NB-IoT modem and GPS receiver. They send binary position data over MQTT using the LivestockGuard binary protocol (CRC-16, compact 16-byte records).

| Option | Price (ZAR) | Purpose | Connectivity |
|--------|-------------|---------|--------------|
| Nordic nRF9160-DK | R3,500 | Dev kit — prototype firmware | LTE-M / NB-IoT |
| Thingy:91 | R2,000 | Quick eval (pre-built hardware) | LTE-M / NB-IoT |
| Digital Matter Oyster3 | R1,500–R2,500 | Commercial tracker (HTTP/MQTT) | LTE-M Cat-M1 |
| Digital Matter Yabby Edge | R2,000–R3,000 | Rugged, long battery | LTE-M Cat-M1 |
| Custom PCB (nRF9160 + solar) | R800–R1,200 per unit at 100+ | Production collar | LTE-M / NB-IoT |

**Recommendation**: Buy 1x nRF9160-DK to prototype the Zephyr firmware against the live MQTT broker. The existing `firmware/` codebase targets this exact chip.

**Integration**: The MQTT writer already decodes the binary protocol. Flash firmware → collar connects to EMQX → positions appear on the dashboard map in real-time.

### 1.3 BLE Gateway Hardware (Dedicated — Optional)

For farms where the herdsman doesn't carry a phone, a dedicated BLE gateway can be installed at water points, gates, or kraals.

| Option | Price (ZAR) | Notes |
|--------|-------------|-------|
| Raspberry Pi 4 + BLE dongle + solar | R2,500 | DIY, runs gateway batch script |
| Minew G1 Gateway | R3,000–R5,000 | Commercial, WiFi/4G backhaul |
| RAKwireless RAK7289 | R8,000 | LoRaWAN + BLE, solar option |

### 1.4 Procurement Plan

| Phase | Items | Qty | Est. Cost | Timeline |
|-------|-------|-----|-----------|----------|
| Pilot (Loch Vaal) | Minew C6 BLE tags | 10 | R1,000 | Week 1 |
| Pilot (Boschhoek) | nRF9160-DK + SIM | 1 | R3,800 | Week 1 |
| Scale (Loch Vaal) | BLE tags for all cattle | 10 | R1,000 | Week 3 |
| Scale (Sibanyoni) | BLE tags | 50 | R5,000 | Week 4 |
| Production | Custom collar PCBs | 5 | R6,000 | Month 2 |

**Total pilot budget**: ~R5,000 (10 BLE tags + 1 GPS dev kit)

---

## 2. Drone Surveillance Integration

### 2.1 Use Cases

| Use Case | Trigger | Value |
|----------|---------|-------|
| Perimeter patrol | Scheduled (daily) or on-demand | Verify fence integrity, detect gaps |
| Aerial headcount | Scheduled (morning/evening) | Automated stock count via computer vision |
| Breach response | Geofence alert fires | Fly to breach location, capture footage |
| Predator/intruder detection | Thermal anomaly at night | Early warning, evidence capture |
| Missing animal search | Animal not seen >24h | Fly to last known BLE position, expand search |
| Pasture assessment | Weekly schedule | Grass coverage, water level, overgrazing |

### 2.2 Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  DRONE FLEET                                                 │
│                                                              │
│  DJI Mavic 3E / Matrice 350 RTK                             │
│  + RGB Camera (48MP)                                         │
│  + Thermal Camera (FLIR / Zenmuse H30T)                     │
│  + Optional: DJI Dock 2 (autonomous launch/land/charge)      │
│                                                              │
│  Communication: DJI Cloud API (REST + WebSocket + MQTT)      │
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│  NEW SERVICE: Drone Manager (Python / FastAPI)               │
│                                                              │
│  Responsibilities:                                           │
│  - Mission planning (waypoints from geofence polygons)       │
│  - Telemetry ingestion (position, battery, heading, speed)   │
│  - Live video relay (RTMP/WebRTC → dashboard)                │
│  - CV result processing (detections → animal matching)       │
│  - Auto-dispatch on alert (geofence breach → fly to point)   │
│  - Flight log storage and audit trail                        │
│                                                              │
│  Ports: 8001 (API), MQTT topics: lg/drone/{id}/*            │
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│  EXISTING CLOUD BACKEND (extended)                           │
│                                                              │
│  New Tables:                                                 │
│  - drones (id, name, model, serial, status, farm_id)        │
│  - drone_missions (id, type, status, waypoints, farm_id)    │
│  - drone_telemetry (time-series: position, battery, speed)  │
│  - drone_detections (id, mission_id, type, bbox, image_url) │
│  - camera_feeds (id, name, url, type, farm_id, status)      │
│  - camera_events (id, feed_id, type, thumbnail, timestamp)  │
│                                                              │
│  New API Endpoints:                                          │
│  - /api/v1/drones — CRUD + telemetry                         │
│  - /api/v1/drones/{id}/missions — mission management         │
│  - /api/v1/drones/{id}/command — RTH, pause, resume          │
│  - /api/v1/cameras — feed management                         │
│  - /api/v1/cameras/{id}/events — motion events               │
│                                                              │
│  Alert Engine Extension:                                     │
│  - New dispatch type: "drone_dispatch" (auto-launch)         │
│  - Thermal anomaly → theft/predator alert escalation         │
│                                                              │
│  Dashboard Extension:                                        │
│  - Drone map layer (real-time position + trail)              │
│  - Mission planner UI (draw flight path on map)              │
│  - Live video feed widget (WebRTC/HLS)                       │
│  - Detection gallery (thumbnails + classification)           │
│  - Camera grid view (multi-feed)                             │
└─────────────────────────────────────────────────────────────┘
```

### 2.3 Computer Vision Pipeline

```
Drone Camera Frame (4K/Thermal)
        │
        ▼
┌─────────────────────┐     ┌──────────────────────┐
│  On-Edge Detection  │ OR  │  Cloud CV Service     │
│  (NVIDIA Jetson /   │     │  (AWS Rekognition /   │
│   DJI onboard AI)   │     │   Self-hosted YOLOv8) │
└─────────┬───────────┘     └──────────┬───────────┘
          │                             │
          ▼                             ▼
┌─────────────────────────────────────────────────┐
│  Detection Results                               │
│  - bounding_box: [x, y, w, h]                   │
│  - class: cattle | person | vehicle | predator   │
│  - confidence: 0.0–1.0                           │
│  - GPS position (from drone telemetry)           │
│  - thumbnail_url (cropped image)                 │
└─────────────────────┬───────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────┐
│  Animal Matching (optional)                      │
│  - Match detection to known animal by:           │
│    • Position proximity to BLE last-seen         │
│    • Coat pattern recognition (future)           │
│    • Tag ID OCR from high-res image (future)     │
│  - Update animal last_seen position              │
│  - Count: reconcile with BLE herd count          │
└─────────────────────────────────────────────────┘
```

### 2.4 Mission Types

| Mission Type | Trigger | Flight Pattern | Duration |
|--------------|---------|----------------|----------|
| Perimeter Patrol | Scheduled / manual | Follow geofence polygon at 30m AGL | 15–40 min |
| Area Scan (headcount) | Scheduled | Grid/lawnmower pattern over paddock | 10–25 min |
| Point of Interest | Breach alert | Fly direct to GPS coordinate, orbit | 5–10 min |
| Search Pattern | Missing animal | Expanding spiral from last known position | 15–30 min |
| Thermal Sweep | Nightly schedule | Low-altitude pass over perimeter | 20–30 min |

### 2.5 Development Sprints

| Sprint | Deliverable | Duration |
|--------|-------------|----------|
| D1 | Database schema + migrations: `drones`, `drone_missions`, `drone_telemetry`, `drone_detections`, `camera_feeds`, `camera_events` | 2 days |
| D2 | Drone CRUD API + telemetry MQTT ingestion: `lg/drone/{id}/telemetry` → TimescaleDB hypertable | 2 days |
| D3 | Mission planner service: generate waypoints from geofence polygons, support all mission types | 3 days |
| D4 | DJI Cloud API integration: auth, telemetry stream, mission upload, live video URL | 3 days |
| D5 | CV integration: receive detection results (HTTP webhook or MQTT), store in `drone_detections`, link to animals | 3 days |
| D6 | Dashboard: drone map layer (real-time), mission history, detection gallery, live video widget | 4 days |
| D7 | Alert integration: auto-dispatch on geofence breach, thermal anomaly → escalation | 2 days |
| D8 | Fixed camera support: RTSP feed registration, motion event webhook, camera grid UI | 3 days |
| D9 | Mobile: drone status card, live feed viewer, dispatch button | 2 days |

**Total estimated effort**: 24 days (4–5 weeks with one developer)

---

## 3. Fixed Camera Surveillance

### 3.1 Hardware Options (South African Market)

| Product | Price (ZAR) | Power | Connectivity | AI Built-in |
|---------|-------------|-------|--------------|-------------|
| Hikvision DS-2XS6A87G1-L/C | R12,000–R18,000 | Solar + battery | 4G SIM | Person/vehicle detection |
| Hikvision ColorVu 4G Solar PTZ | R15,000–R25,000 | Solar | 4G | Full-color night, PTZ |
| Dahua TiOC 2.0 | R5,000–R10,000 | PoE / 12V | WiFi/Ethernet | Person/vehicle, siren, light |
| FLIR Elara FR-345 | R30,000+ | 12V/PoE | Ethernet | Thermal + visible, analytics |
| Reolink Go Plus | R3,500–R5,000 | Solar + battery | 4G SIM | Person/vehicle, basic |

**Recommendation for off-grid farms**: Hikvision Solar 4G PTZ for kraal gates and water points. Built-in person/vehicle detection sends webhook to LivestockGuard alert engine.

### 3.2 Integration Architecture

```
Fixed Camera (4G / WiFi)
    │
    ├── RTSP stream → NVR or cloud recording
    │
    ├── Motion/AI event → HTTP webhook
    │       POST /api/v1/cameras/{id}/events
    │       { type: "person", confidence: 0.92, thumbnail_url: "..." }
    │
    └── Scheduled snapshot → S3 bucket (timelapse / evidence)
```

### 3.3 Camera Placement Strategy

| Location | Camera Type | Purpose |
|----------|-------------|---------|
| Kraal gate | PTZ with night vision | Count animals entering/exiting, detect intruders |
| Water point | Fixed wide-angle | Monitor animal health (limping), predator activity |
| Farm perimeter (high-risk) | Thermal + visible | Night intrusion detection, wire-cut alerts |
| Feed area | Fixed | Feeding behaviour, dominance hierarchy |

---

## 4. MQTT Topic Structure (Extended)

```
Existing:
  lg/dev/{device_id}/pos       — GPS collar positions
  lg/dev/{device_id}/alert     — Device-generated alerts
  lg/up/{device_id}/telemetry  — Simulator telemetry
  lg/cmd/{serial_number}       — Commands to devices

New (Drones):
  lg/drone/{drone_id}/telemetry   — Position, battery, speed, heading
  lg/drone/{drone_id}/status      — Armed, flying, landing, charging
  lg/drone/{drone_id}/detection   — CV detection results
  lg/drone/{drone_id}/command     — RTH, pause, resume, abort

New (Cameras):
  lg/camera/{camera_id}/event     — Motion/AI detection events
  lg/camera/{camera_id}/status    — Online, offline, recording
```

---

## 5. Database Schema (New Tables)

```sql
-- Drone fleet management
CREATE TABLE drones (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    farm_id UUID REFERENCES farms(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    model VARCHAR(100),           -- 'mavic_3e', 'matrice_350', etc.
    serial_number VARCHAR(100) UNIQUE,
    status VARCHAR(50) DEFAULT 'idle',  -- idle, flying, charging, offline, maintenance
    home_latitude DOUBLE PRECISION,
    home_longitude DOUBLE PRECISION,
    last_battery_pct INTEGER,
    last_seen TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Drone missions
CREATE TABLE drone_missions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    drone_id UUID REFERENCES drones(id) ON DELETE CASCADE,
    farm_id UUID REFERENCES farms(id) ON DELETE CASCADE,
    mission_type VARCHAR(50) NOT NULL, -- perimeter, area_scan, poi, search, thermal
    status VARCHAR(50) DEFAULT 'planned', -- planned, in_progress, completed, aborted, failed
    trigger_type VARCHAR(50),            -- scheduled, manual, alert_response
    trigger_alert_id UUID REFERENCES alerts(id),
    waypoints JSONB,                     -- GeoJSON LineString or array of {lat, lon, alt}
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    distance_m DOUBLE PRECISION,
    duration_sec INTEGER,
    detections_count INTEGER DEFAULT 0,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Drone telemetry (time-series)
CREATE TABLE drone_telemetry (
    time TIMESTAMPTZ NOT NULL,
    drone_id UUID NOT NULL REFERENCES drones(id) ON DELETE CASCADE,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    altitude_m DOUBLE PRECISION,
    speed_ms DOUBLE PRECISION,
    heading DOUBLE PRECISION,
    battery_pct INTEGER,
    signal_strength INTEGER,
    mission_id UUID REFERENCES drone_missions(id)
);
SELECT create_hypertable('drone_telemetry', 'time');

-- CV detections from drone or camera
CREATE TABLE drone_detections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    mission_id UUID REFERENCES drone_missions(id),
    camera_feed_id UUID,  -- NULL for drone, set for fixed camera
    detection_type VARCHAR(50) NOT NULL, -- cattle, person, vehicle, predator, unknown
    confidence DOUBLE PRECISION,
    bbox JSONB,                  -- {x, y, width, height} normalized 0-1
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    thumbnail_url TEXT,
    full_image_url TEXT,
    matched_animal_id UUID REFERENCES animals(id),
    reviewed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Fixed camera feeds
CREATE TABLE camera_feeds (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    farm_id UUID REFERENCES farms(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    location_description TEXT,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    camera_type VARCHAR(50),     -- ptz, fixed, thermal, dual
    stream_url TEXT,             -- RTSP URL
    status VARCHAR(50) DEFAULT 'active', -- active, offline, maintenance
    ai_enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Camera motion/AI events
CREATE TABLE camera_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    camera_feed_id UUID REFERENCES camera_feeds(id) ON DELETE CASCADE,
    event_type VARCHAR(50) NOT NULL,  -- motion, person, vehicle, animal, predator
    confidence DOUBLE PRECISION,
    thumbnail_url TEXT,
    video_clip_url TEXT,
    metadata JSONB,
    acknowledged BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 6. API Endpoints (New)

### Drones

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/drones?farm_id=X` | List drones for a farm |
| POST | `/api/v1/drones` | Register a new drone |
| GET | `/api/v1/drones/{id}` | Get drone details + last telemetry |
| POST | `/api/v1/drones/{id}/command` | Send command (RTH, pause, resume) |
| GET | `/api/v1/drones/{id}/missions` | List missions for a drone |
| POST | `/api/v1/drones/{id}/missions` | Create/launch a mission |
| GET | `/api/v1/drones/{id}/missions/{mid}` | Mission detail + detections |
| POST | `/api/v1/drones/{id}/missions/{mid}/abort` | Abort active mission |
| GET | `/api/v1/drones/{id}/telemetry?from=&to=` | Historical telemetry |

### Cameras

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/cameras?farm_id=X` | List camera feeds |
| POST | `/api/v1/cameras` | Register a camera feed |
| GET | `/api/v1/cameras/{id}` | Camera details + stream URL |
| GET | `/api/v1/cameras/{id}/events` | List detection events |
| POST | `/api/v1/cameras/{id}/events` | Webhook: camera pushes event |
| PUT | `/api/v1/cameras/{id}/events/{eid}/acknowledge` | Mark event as reviewed |

### Detections (cross-cutting)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/detections?farm_id=X&type=cattle` | All detections (drone + camera) |
| GET | `/api/v1/detections/{id}` | Detection detail with images |
| PUT | `/api/v1/detections/{id}/match` | Manually match to an animal |

---

## 7. Dashboard UI Extensions

### 7.1 Drone Map Layer
- Real-time drone marker with heading indicator
- Flight trail (polyline) during active mission
- Mission waypoints overlay (planned vs actual path)
- Detection markers (click to see thumbnail + classification)

### 7.2 Mission Control Panel
- Active mission status (progress %, battery, ETA)
- Quick actions: Return-to-Home, Pause, Resume
- Mission history table with playback

### 7.3 Live Video Widget
- WebRTC or HLS stream from drone camera
- Picture-in-picture mode while browsing other pages
- Thermal/RGB toggle (for dual-camera drones)

### 7.4 Detection Gallery
- Grid of thumbnails from CV detections
- Filter by type (cattle, person, vehicle, predator)
- Confidence slider filter
- Click to match detection to a known animal

### 7.5 Camera Grid View
- Multi-feed layout (2x2, 3x3)
- Per-camera event timeline
- Motion heatmap overlay

---

## 8. Alert Engine Extension

New alert types and dispatch actions:

| Alert Type | Trigger | Auto-Action |
|------------|---------|-------------|
| `drone_breach_response` | Geofence breach alert fires | Auto-launch drone to breach coordinates |
| `thermal_anomaly` | Thermal camera detects heat signature at night | Escalate to theft/predator, dispatch drone |
| `person_detected` | Camera AI detects person in restricted area | Alert + drone dispatch + recording |
| `vehicle_detected` | Camera AI detects vehicle at night | High-priority theft alert |
| `predator_detected` | CV classifies predator (jackal, caracal) | Alert herdsman + activate deterrents |
| `drone_low_battery` | Drone battery < 20% during mission | Auto-RTH + notify operator |
| `drone_connection_lost` | No telemetry for >60s | Critical alert to operator |

---

## 9. Hardware Budget Summary

### Minimum Viable Deployment (1 farm, proof-of-concept)

| Item | Qty | Unit Cost | Total |
|------|-----|-----------|-------|
| BLE Ear Tags (Minew C6) | 10 | R100 | R1,000 |
| nRF9160-DK (GPS collar prototype) | 1 | R3,500 | R3,500 |
| DJI Mavic 3 Enterprise | 1 | R85,000 | R85,000 |
| Hikvision Solar 4G Camera | 2 | R15,000 | R30,000 |
| 4G SIM cards (data) | 4 | R200/mo | R800/mo |
| **Total (once-off)** | | | **R119,500** |
| **Total (monthly)** | | | **R800** |

### Phased Approach (recommended)

| Phase | Investment | Capability Gained |
|-------|------------|-------------------|
| Phase 1: BLE Tags | R5,000 | Real herd tracking, missing animal detection |
| Phase 2: GPS Collar | R3,500 | Real-time position, geofence breach |
| Phase 3: Fixed Cameras | R30,000 | Kraal security, night surveillance |
| Phase 4: Drone | R85,000 | Aerial patrol, automated headcount, breach response |

---

## 10. Regulatory Considerations (South Africa)

### Drones (SACAA — South African Civil Aviation Authority)

- **RPAS registration** required for all drones > 250g
- **Remote Pilot License (RPL)** required for commercial operations
- **ROC (Remote Operator Certificate)** required for the operating entity
- **Flight altitude**: Max 120m AGL (400ft) unless approved
- **Visual Line of Sight (VLOS)**: Default requirement; BVLOS needs special approval
- **Autonomous operations**: Requires additional SACAA approval (DJI Dock scenario)
- **Night flights**: Permitted with appropriate lighting and approval
- **Farm airspace**: Generally unrestricted (no controlled airspace), but check local NOTAMs

### Cameras (POPIA — Protection of Personal Information Act)

- Cameras on private farm property are permitted
- Signage required if cameras cover areas accessible to visitors/workers
- Footage retention policy needed (recommend 30 days)
- Thermal cameras: no specific restriction on private property

### Connectivity

- 4G coverage: Verify MTN/Vodacom/Telkom coverage at farm locations
- LTE-M/NB-IoT: Check network support (Vodacom has NB-IoT in ZA)
- Starlink: Viable backup for remote farms (R2,000/mo)

---

## 11. Next Steps

1. **Immediate (Week 1)**: Order BLE tags + nRF9160-DK for hardware pilot
2. **Short-term (Week 2–3)**: Build drone DB schema + API endpoints (Sprint D1–D2)
3. **Medium-term (Month 2)**: DJI Cloud API integration + CV pipeline
4. **Longer-term (Month 3)**: Fixed camera installation + full autonomy

---

## Related Documents

- `docs/FIRMWARE_SPEC.md` — GPS collar firmware (nRF9160 / Zephyr)
- `docs/HERDSMAN_GATEWAY_SPEC.md` — BLE gateway protocol
- `docs/CONNECTIVITY_SPEC.md` — Network architecture
- `docs/SYSTEM_OVERVIEW.md` — Full platform architecture
