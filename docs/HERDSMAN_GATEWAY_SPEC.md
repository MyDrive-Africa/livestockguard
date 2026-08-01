# Herdsman Gateway Architecture

## Overview

The Herdsman Gateway system enables affordable livestock tracking using **passive BLE ear tags** on cattle, with position data collected by a **gateway device** (smartphone or dedicated hardware) carried by a herdsman during patrols.

This is the cost-effective alternative to individual GPS collars:

| Approach | Cost per Head | Battery Life | Cellular Required per Animal |
|----------|--------------|--------------|------------------------------|
| GPS Collar | ~R800+ | 3-6 months | Yes (each collar has SIM) |
| **BLE Ear Tag + Gateway** | **~R50** | **2-5 years** | **No (gateway only)** |

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│  CATTLE (Passive BLE Ear Tags)                                       │
│  - Broadcast BLE advertisement every 1-2 seconds                     │
│  - Contains: MAC address (unique ID)                                 │
│  - No GPS, no cellular, no processing                                │
│  - Battery: CR2032 coin cell (2-5 year lifespan)                     │
│  - Cost: ~R50 per tag                                                │
└──────────────────────────────────┬──────────────────────────────────┘
                                   │ BLE advertisements (≤100m range)
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│  HERDSMAN GATEWAY (Phone or Dedicated Device)                        │
│  - Scans for BLE advertisements (every 5s default)                   │
│  - Records own GPS position                                          │
│  - Batches sightings: {mac, rssi, gateway_gps, timestamp}           │
│  - Sends batch to cloud API every 30s (configurable)                 │
│  - Tracks patrol sessions (start/end shift)                          │
│  - One cellular connection serves entire herd                        │
└──────────────────────────────────┬──────────────────────────────────┘
                                   │ HTTPS POST /api/gateway/batch
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│  CLOUD BACKEND                                                       │
│  - Resolves MAC → animal_id via ble_ear_tags registry                │
│  - Stores sightings in TimescaleDB (ble_sightings hypertable)        │
│  - Writes positions to main positions table (animal shows on map)    │
│  - Calculates estimated distance from RSSI                           │
│  - Updates gateway_devices.last_seen/position                        │
│  - Tracks herdsman patrol sessions                                   │
└──────────────────────────────────┬──────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│  DASHBOARD                                                           │
│  - Gateway status panel (online/offline, battery, last ping)         │
│  - Animals per gateway (which cows were seen, when, signal quality)  │
│  - Herdsman patrol tracking (shift times, coverage, distance)        │
│  - Animals appear on main map using gateway GPS as position          │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Position Resolution

The animal's position is approximated using the **gateway's GPS coordinates** at the time of detection. This is acceptable because:

1. The herdsman is walking among the herd (typically within 50m of any animal)
2. BLE range is ~100m, so detected animals are within 100m of the gateway
3. For theft detection and geofence breach, 100m accuracy is sufficient
4. RSSI-based distance estimation provides additional granularity

### RSSI to Distance Calculation

Uses the **log-distance path loss model**:

```
distance = 10 ^ ((TxPower - RSSI) / (10 * n))
```

Where:
- `TxPower` = -59 dBm (calibrated signal strength at 1 metre)
- `RSSI` = measured signal strength (e.g., -72 dBm)
- `n` = 2.0–2.5 (path loss exponent, outdoor environment)

| RSSI (dBm) | Estimated Distance | Signal Quality |
|------------|-------------------|----------------|
| -50 to -60 | 1–3m | Excellent |
| -60 to -75 | 3–15m | Good |
| -75 to -90 | 15–50m | Fair |
| -90 to -100 | 50–100m | Weak |

---

## Database Schema

### gateway_devices
Represents the physical gateway device (phone or dedicated hardware).

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| farm_id | UUID | FK → farms |
| serial_number | VARCHAR(100) | Unique device identifier |
| name | VARCHAR(255) | Human label (e.g., "Sipho's Phone") |
| device_type | VARCHAR(50) | 'phone' or 'dedicated_hardware' |
| herdsman_name | VARCHAR(255) | Who carries this device |
| herdsman_phone | VARCHAR(50) | Contact number |
| status | VARCHAR(50) | active/inactive/maintenance/lost |
| last_seen | TIMESTAMPTZ | Last successful API report |
| last_latitude | FLOAT | Gateway's last GPS position |
| last_longitude | FLOAT | Gateway's last GPS position |
| last_battery_pct | INT | Gateway battery level |
| ble_scan_interval_ms | INT | How often to scan (default 5000ms) |
| report_interval_sec | INT | How often to send batch (default 30s) |
| max_ble_range_m | INT | Expected BLE range (default 100m) |

### ble_ear_tags
Registry mapping BLE MAC addresses to animals.

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| farm_id | UUID | FK → farms |
| animal_id | UUID | FK → animals (nullable until assigned) |
| mac_address | VARCHAR(17) | BLE MAC (e.g., "AA:BB:CC:DD:EE:FF") |
| tag_name | VARCHAR(100) | Human label |
| manufacturer | VARCHAR(100) | Tag hardware maker |
| battery_type | VARCHAR(50) | Coin cell type (default CR2032) |
| estimated_battery_months | INT | Expected lifespan (default 36) |
| installed_date | DATE | When attached to animal |
| status | VARCHAR(50) | active/inactive/lost/replaced |

### ble_sightings (TimescaleDB hypertable)
Time-series of every BLE detection. High-volume, 1-year retention.

| Column | Type | Description |
|--------|------|-------------|
| time | TIMESTAMPTZ | When the ping was received |
| gateway_id | UUID | Which gateway detected it |
| ble_tag_id | UUID | FK → ble_ear_tags |
| mac_address | VARCHAR(17) | Raw MAC from scan |
| animal_id | UUID | Resolved animal (nullable if unknown MAC) |
| rssi | INT | Signal strength (dBm) |
| estimated_distance_m | REAL | Calculated from RSSI |
| gateway_latitude | FLOAT | Gateway GPS at time of scan |
| gateway_longitude | FLOAT | Gateway GPS at time of scan |
| gateway_speed | REAL | Herdsman walking speed |
| gateway_battery_pct | INT | Gateway battery at scan time |

### herdsman_sessions
Tracks patrol shifts for attendance and coverage reporting.

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| gateway_id | UUID | Which gateway |
| farm_id | UUID | Which farm |
| herdsman_name | VARCHAR(255) | Who was on patrol |
| started_at | TIMESTAMPTZ | Shift start |
| ended_at | TIMESTAMPTZ | Shift end |
| animals_seen | INT | Unique animals detected |
| total_sightings | INT | Total BLE pings |
| distance_walked_m | REAL | GPS track distance |
| status | VARCHAR(20) | active/completed/abandoned |

---

## API Endpoints

### POST /api/gateway/register
Register a new gateway device.

```json
{
  "farm_id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
  "serial_number": "GW-LV-001",
  "name": "Sipho's Phone",
  "device_type": "phone",
  "herdsman_name": "Sipho Molefe",
  "herdsman_phone": "+27 82 123 4567",
  "ble_scan_interval_ms": 5000,
  "report_interval_sec": 30
}
```

### POST /api/gateway/batch
Submit a batch of BLE sightings from a gateway.

```json
{
  "gateway_serial": "GW-LV-001",
  "latitude": -26.719088,
  "longitude": 27.709759,
  "altitude": 1450.0,
  "speed": 4.2,
  "battery_pct": 72,
  "session_id": "uuid-of-active-session",
  "sightings": [
    { "mac_address": "AA:BB:CC:DD:EE:01", "rssi": -65 },
    { "mac_address": "AA:BB:CC:DD:EE:02", "rssi": -78 },
    { "mac_address": "AA:BB:CC:DD:EE:03", "rssi": -92 },
    { "mac_address": "FF:00:11:22:33:44", "rssi": -55 }
  ]
}
```

**Response:**
```json
{
  "accepted": 4,
  "resolved": 3,
  "unresolved_macs": ["FF:00:11:22:33:44"],
  "gateway_id": "uuid",
  "timestamp": "2025-07-25T10:30:00Z"
}
```

### GET /api/gateway/status/{serial}
Get gateway status with recent animal sightings.

### POST /api/gateway/tags
Register a BLE ear tag and link to an animal.

### GET /api/gateway/tags?farm_id=...
List all registered BLE tags for a farm.

### POST /api/gateway/sessions/start
Start a patrol session.

### POST /api/gateway/sessions/{id}/end
End a patrol session.

---

## Herdsman Unique Marker

Each herdsman is uniquely identified in the system through their **gateway device serial number** (e.g. `GW-LV-001`). This serial serves as the herdsman's marker — every BLE scan batch references it, creating a clear audit trail: who scanned, where, when, and which animals were detected.

### Identity Chain

```
Herdsman (gateway_serial) → detects → Cattle (ear tag MAC) → at → GPS position
```

Every batch submission to `POST /api/gateway/batch` includes `gateway_serial` as the identifying marker. The cloud resolves this to the registered herdsman via the `gateway_devices` table (`herdsman_name`, `herdsman_phone`).

### How the Marker Works

| Layer | Identifier | Purpose |
|-------|-----------|---------|
| Physical device | Phone IMEI / Android ID | Hardware-level uniqueness (not transmitted) |
| **System marker** | **`gateway_serial`** (e.g. `GW-LV-001`) | **Primary reference for all scans** |
| Session | `session_id` (UUID) | Groups scans within a patrol shift |
| User account | `user_id` (JWT) | Auth-level identity, links to `herdsman` role |

### Marker Assignment Flow

1. Admin/Farm Owner registers gateway: `POST /api/gateway/register` with `serial_number` + `herdsman_name`
2. Herdsman logs into mobile app → app reads assigned gateway serial from user profile
3. Every BLE batch includes `gateway_serial` — this is the scan reference
4. Dashboard displays herdsman name + gateway serial on patrol tracking views
5. Historical queries can filter all sightings by `gateway_id` (resolved from serial)

### Why gateway_serial (Not Phone MAC or IMEI)

- **Portable:** If the herdsman's phone breaks, assign the same serial to a new phone — history preserved
- **Human-readable:** `GW-LV-001` is meaningful; `A4:C1:38:7B:2D:E9` is not
- **Already implemented:** The batch API, simulator, and database all reference `gateway_serial`
- **Multi-device safe:** A herdsman could switch between phone and dedicated hardware without losing identity

### Map Marker Visual Distinction

The herdsman marker on the dashboard/mobile map must be visually distinct from cattle markers:

| Marker Type | Icon | Colour | Label | Data Source |
|-------------|------|--------|-------|-------------|
| **Cattle** | Cow/circle dot | Green (normal), Orange (warning), Red (breach/theft) | Animal name (e.g. `LV-003`) | `positions` table (from BLE sighting, uses gateway GPS) |
| **Herdsman** | Person/phone icon | **Blue** | Herdsman name + serial (e.g. `Sipho · GW-LV-001`) | `gateway_devices.last_latitude/longitude` |

**Rendering rules:**
- Herdsman marker updates every 30s (each batch updates `gateway_devices.last_latitude/longitude`)
- Cattle markers cluster around the herdsman marker (detected within 100m of the phone)
- Herdsman marker has a subtle **100m radius ring** (optional, togglable) showing BLE detection range
- When herdsman is offline (no batch for > 5 min), marker turns grey with "Last seen: X min ago" tooltip
- Multiple herdsmen on same farm render as separate blue markers (future multi-gateway support)

**Click/tap interaction:**
- Cattle marker → shows animal detail (name, breed, last seen, signal strength)
- Herdsman marker → shows patrol info (name, shift duration, animals detected, battery %, walking speed)

---

## Hardware Requirements

### Recommended BLE Ear Tags (Cattle)

The system requires passive BLE beacons in cattle ear tag form factor. These are the validated options:

#### Option 1: Skylab VDB06 (Budget — Best for Large Herds)

| Spec | Value |
|------|-------|
| Protocol | BLE 5.0 (iBeacon / Eddystone) |
| Range | ~70m advertise range |
| Battery | CR2477 button lithium cell |
| Battery Life | 2–4 years (at 1s advertising interval) |
| Features | Step counting, position tracking |
| Form Factor | Cattle ear tag |
| Applications | Cattle, sheep, horses |
| IP Rating | IP65 |
| Cost | ~R50–R90 per unit at volume |

Best fit for: Sibanyoni (50 cattle), budget-constrained deployments. The 70m range works because the herdsman walks among the herd, and the XCover 7's BLE 5.3 receiver extends effective detection to ~80m.

#### Option 2: GAORFID SKU#127555 (Premium — Best for Small Herds with Health Monitoring)

| Spec | Value |
|------|-------|
| Protocol | BLE (Bluetooth Low Energy) |
| Range | 100m stable, up to 200m max to gateway |
| Battery | Built-in replaceable button cell |
| Battery Life | 2–3 years |
| Features | Body temperature (±0.1°C), 3-axis accelerometer (steps, running, head shaking) |
| Data Upload | Every 20 min (adjustable) |
| Weight | 14g |
| Dimensions | 55 × 30 × 12 mm |
| IP Rating | IP67 |
| Operating Temp | -30°C to +60°C |
| Cost | ~R140–R180 per unit |

Best fit for: Loch Vaal (10 cattle), where per-head investment is affordable and temperature/activity data enables early disease detection.

#### General Ear Tag Requirements

- **Type:** Bluetooth Low Energy 5.0 beacon
- **Form factor:** Cattle ear tag (weather/UV resistant)
- **Advertising interval:** 1000ms (configurable)
- **TX Power:** -4 dBm to 0 dBm
- **Battery:** CR2032 or CR2477 (estimated 2-5 year life at 1s interval)
- **IP Rating:** IP67 minimum (dust/water resistant)
- **Temperature:** -20°C to +60°C operating
- **Cost:** R50–R180 per unit depending on features

### Recommended Gateway Phone: Samsung Galaxy XCover 7

The primary gateway device is the herdsman's phone. The Samsung Galaxy XCover 7 is the recommended model for South African deployments:

| Spec | Value |
|------|-------|
| **Bluetooth** | **5.3** (coded PHY long-range support) |
| IP Rating | IP68 + MIL-STD-810H (drops, dust, rain, temperature extremes) |
| Battery | 4,050 mAh (**removable** — carry a spare for full-day patrols) |
| GPS | Dual-band (L1+L5) — excellent outdoor accuracy (±2m) |
| OS | Android 14 (full BLE scanning API support) |
| Processor | MediaTek Dimensity 6100+ |
| Storage | 128GB + microSD up to 1TB |
| Connectivity | 5G / 4G LTE (for batch uploads over cellular) |
| NFC | Yes (tap-to-register ear tags in future) |
| Display | 6.6" PLS LCD (1080×2408) — readable in direct sunlight |
| Price (ZA) | ~R5,000–R6,500 (Samsung ZA, Vodacom, MTN, Takealot) |

**Why this phone:**
1. **BLE 5.3 with coded PHY** — maximum scanning range (~120m receive sensitivity in open field)
2. **IP68 + MIL-STD-810H** — survives being dropped in mud, rained on, left in 60°C sun
3. **Removable battery** — herdsman swaps battery mid-shift without losing GPS track
4. **Enterprise-grade** — Samsung Knox security, reliable BLE stack, no bloatware
5. **Available in South Africa** — official Samsung channels, Vodacom, MTN contract options
6. **NFC** — future tap-to-register workflow for new ear tags

**Alternative (budget):** Samsung Galaxy A15 (~R3,500) — BLE 5.3 but no ruggedization or removable battery.

### BLE Range Compatibility Matrix

The effective detection range is the minimum of phone receive range and tag transmit range:

| Phone BLE Version | Tag Model | Tag TX Range | Effective Detection Range |
|-------------------|-----------|-------------|--------------------------|
| BLE 5.3 (XCover 7) | Skylab VDB06 | 70m | **~70–80m** |
| BLE 5.3 (XCover 7) | GAORFID SKU#127555 | 100–200m | **~100–120m** |
| BLE 5.0 (budget phone) | Skylab VDB06 | 70m | ~50–60m |
| BLE 5.0 (budget phone) | GAORFID SKU#127555 | 100–200m | ~80–100m |

For the system's 100m design assumption: XCover 7 + GAORFID tags meets it fully. XCover 7 + Skylab VDB06 is slightly under but acceptable since the herdsman walks within the herd.

### Gateway Device Option B: Dedicated Hardware

For farms wanting a no-touch solution (no phone interaction required):

- **MCU:** ESP32-S3 or nRF52840 (BLE + WiFi/LTE)
- **GPS:** u-blox M8N or similar
- **Cellular:** SIM7600 (4G LTE) or SIM800L (2G fallback)
- **Battery:** 5000mAh LiPo (12+ hours active scanning)
- **Enclosure:** IP67 rugged plastic, belt-clip mount
- **Cost:** R800–R1500 per unit
- **Pros:** Dedicated, waterproof, longer battery, no user interaction needed
- **Cons:** Extra hardware cost, no display feedback for herdsman

### Cost Summary (Loch Vaal — 10 Cattle)

| Item | Model | Unit Cost | Qty | Total |
|------|-------|-----------|-----|-------|
| Gateway phone | Samsung Galaxy XCover 7 | R5,500 | 1 | R5,500 |
| BLE ear tags | GAORFID SKU#127555 | R160 | 10 | R1,600 |
| Data SIM | Vodacom 1GB/mo | R99/mo | 1 | R1,188/yr |
| **Year 1 Total** | | | | **R8,288** |

### Cost Summary (Sibanyoni — 50 Cattle)

| Item | Model | Unit Cost | Qty | Total |
|------|-------|-----------|-----|-------|
| Gateway phone | Samsung Galaxy XCover 7 | R5,500 | 1 | R5,500 |
| BLE ear tags | Skylab VDB06 | R70 | 50 | R3,500 |
| Data SIM | Vodacom 1GB/mo | R99/mo | 1 | R1,188/yr |
| **Year 1 Total** | | | | **R10,188** |

---

## BLE Advertising Format

The ear tag broadcasts a standard BLE advertisement packet:

```
┌─────────────┬──────────────┬────────────────────┐
│ Preamble    │ Access Addr  │ PDU                 │
│ (1 byte)    │ (4 bytes)    │ (up to 37 bytes)    │
└─────────────┴──────────────┴────────────────────┘

PDU contains:
- MAC Address (6 bytes) — unique identifier per tag
- Flags (1 byte) — BLE general discoverable
- TX Power Level (1 byte) — for RSSI calibration
- Manufacturer Data (optional):
  - Company ID: 0xFFFF (development)
  - Tag firmware version (1 byte)
  - Battery voltage (1 byte, scaled)
  - Sequence counter (1 byte, for packet loss detection)
```

The gateway scans for **all BLE advertisements**, filters by known MACs (from the `ble_ear_tags` registry), and forwards them in batches.

---

## Operational Flow

### Initial Setup (Once)
1. Register gateway device via API (`POST /api/gateway/register`)
2. Attach BLE ear tags to each cow
3. Register each tag's MAC address and link to animal (`POST /api/gateway/tags`)
4. Configure gateway scan/report intervals

### Daily Operation
1. Herdsman starts patrol → gateway starts session (`POST /sessions/start`)
2. Gateway continuously scans for BLE tags (every 5s)
3. Every 30s, gateway sends batch to cloud API (`POST /gateway/batch`)
4. Cloud resolves MACs to animals, stores positions, updates dashboard
5. Dashboard shows real-time animal locations using gateway GPS
6. Herdsman ends patrol → gateway ends session (`POST /sessions/{id}/end`)

### Alert Scenarios
- **Animal not seen in 24h:** No BLE ping from a tag in any gateway scan
- **Unknown MAC detected:** Possible new/stolen tag, flagged as unresolved
- **Gateway offline:** Herdsman's device not reporting (phone dead, no signal)
- **All animals not seen:** Herdsman didn't patrol today

---

## Simulator

Run the gateway simulator to test without real hardware:

```bash
# With API running
make simulate-gateway

# Without API (print output only)
make simulate-gateway-offline

# Custom options
cd tools/simulator
python3 gateway_simulator.py --farm lochvaal --animals 50 --duration 300 --scan-interval 5
```

The simulator:
- Fetches registered BLE tags from the API (so MACs resolve to real animals on the dashboard)
- Falls back to random MACs in offline mode or if no tags are registered
- Simulates a herdsman walking a rectangular patrol route
- Calculates realistic RSSI based on distance (log-distance path loss model)
- Sends batches to the API at configurable intervals
- Supports patrol sessions (start/end)

---

## Cost Comparison (50 cattle, Loch Vaal)

| Item | GPS Collar Approach | BLE Gateway Approach |
|------|--------------------|--------------------|
| Tags/Collars (50x) | 50 × R800 = R40,000 | 50 × R50 = R2,500 |
| Cellular SIMs (50x) | 50 × R99/mo = R4,950/mo | 0 |
| Gateway device | N/A | 1 × R0 (phone) or R1,200 (dedicated) |
| Gateway SIM | N/A | 1 × R99/mo |
| Battery replacement | Every 6 months (50x) | Every 3-5 years (50x) |
| **Year 1 Total** | **~R100,000+** | **~R4,000** |
| **Annual ongoing** | **~R60,000** | **~R1,200** |

---

## Limitations & Trade-offs

1. **Position accuracy:** Animal position = gateway GPS (±100m), not animal's exact location
2. **Coverage gaps:** Animals only tracked when herdsman is patrolling within BLE range
3. **No real-time 24/7:** Unlike GPS collars, positions only update during patrols
4. **Single point of failure:** If gateway is offline, no tracking occurs
5. **BLE range:** Limited to ~100m in open field (less with obstacles)

### Mitigations
- Multiple gateways per farm (multiple herdsmen or fixed gateway stations)
- Combine with a few GPS collars on high-value animals (herd leaders, bulls)
- Fixed BLE gateways at watering points, feeding stations, gates
- Alert if any animal not seen for configurable threshold (default 24h)

---

## Future Enhancements

1. **Multi-gateway triangulation:** Multiple gateways detect same tag → precise position via RSSI trilateration
2. **Fixed gateway stations:** Solar-powered BLE scanners at watering holes, gates, kraals
3. **Mobile app:** Android/iOS app replacing the simulator for real herdsman use
4. **Offline buffering:** Gateway stores sightings when no cellular, syncs when signal returns
5. **Tag health monitoring:** Detect battery-low from BLE manufacturer data field
6. **Herd counting:** "All 50 animals seen today" report for stock reconciliation
7. **Movement patterns:** Detect sick animals (not moving with herd) from sighting patterns
