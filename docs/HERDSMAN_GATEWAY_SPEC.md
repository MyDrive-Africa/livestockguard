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

## Hardware Requirements

### BLE Ear Tags (Cattle)
- **Type:** Bluetooth Low Energy 5.0 beacon
- **Form factor:** Cattle ear tag (weather/UV resistant)
- **Advertising interval:** 1000ms (configurable)
- **TX Power:** -4 dBm to 0 dBm
- **Battery:** CR2032 (estimated 3-5 year life at 1s interval)
- **IP Rating:** IP67 minimum (dust/water resistant)
- **Temperature:** -20°C to +60°C operating
- **Cost:** R40–R80 per unit at volume
- **Examples:** Minew C6, April Beacon N02, custom cattle tag

### Gateway Device Option A: Smartphone
- **OS:** Android 8+ with BLE 5.0 support
- **App:** LivestockGuard Gateway (future mobile app)
- **GPS:** Built-in
- **Cellular:** Built-in (data SIM for API calls)
- **Pros:** Herdsman already has phone, no extra hardware
- **Cons:** Battery drain, may not be waterproof

### Gateway Device Option B: Dedicated Hardware
- **MCU:** ESP32-S3 or nRF52840 (BLE + WiFi/LTE)
- **GPS:** u-blox M8N or similar
- **Cellular:** SIM7600 (4G LTE) or SIM800L (2G fallback)
- **Battery:** 5000mAh LiPo (12+ hours active scanning)
- **Enclosure:** IP67 rugged plastic, belt-clip mount
- **Cost:** R800–R1500 per unit
- **Pros:** Dedicated, waterproof, longer battery, no user interaction needed

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
- Creates N virtual animals with random BLE MACs
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
