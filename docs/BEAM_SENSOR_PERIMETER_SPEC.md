# Beam Sensor Perimeter Layer

## Overview

The Beam Sensor Perimeter layer adds **physical break-beam sensors** (infrared, microwave, or laser) mounted at chokepoints along a farm border. When something crosses the invisible line between a beam's transmitter and receiver posts, the beam breaks and an edge controller reports a **crossing event** to the cloud, which fires an alert through the existing notification pipeline.

This is a **complementary layer** to the existing virtual geofence, not a replacement:

| Layer | What it watches | Strength | Weakness |
|-------|-----------------|----------|----------|
| Virtual geofence (GPS/BLE polygon) | The whole area — "is the herd inside?" | Full-area coverage | Interval-based; depends on a working collar / nearby gateway |
| **Beam sensor (physical line)** | **A specific crossing line — a gate or fence gap** | **Instant, collar-independent** | **Only covers the guarded line, not the whole perimeter** |

A beam crossing near a GPS/BLE breach at the same spot is a high-confidence theft signal.

---

## Why beams, and where they fit

A beam only covers the line between two posts (practical outdoor range ~10–100m per span). Beaming an entire perimeter is expensive and false-trigger prone, so beams are deployed at **chokepoints**: the main gate, loading ramp, kraal entrance, drainage lines, and known theft paths.

### Phased rollout toward a physical fence

For a large border such as the **50ha Sibanyoni farm** (~707m/side, ~2.8km perimeter), the intended progression is:

1. **Now** — Virtual geofence covers the full 50ha. Beam sensors act as interim **border sentinels** at the gaps that matter.
2. **Building** — As a physical fence or wall is constructed section by section, the risky open spans are closed. Beams stay at the permanent gates.
3. **Later** — The perimeter is a real fence; beams remain the electronic watch at every gate and loading point.

A beam may optionally be linked to the geofence whose border it guards (`beam_sensors.geofence_id`), and stores the line segment it protects (`span`), so the dashboard can draw the guarded spans on top of the geofence polygon and visualise fence coverage as it grows.

---

## System Architecture

```
Beam sensor (IR / microwave / laser) at a gate or fence gap
   │  crossing detected (beam broken)
   ▼
Edge controller (ESP32 / RPi / nRF) at the farm
   │  POST /api/v1/beam/event
   ▼
API Gateway  (cloud/services/api_gateway/app/routers/beam.py)
   ├─ store crossing → beam_crossings (TimescaleDB hypertable)
   └─ if alert_on_crossing → INSERT alerts row  +  publish to Redis
        ├─ farm:{farm_id}     → dashboard WebSocket (live map / alert feed)
        └─ alerts:incoming    → Alert Engine → push / SMS / email
   ▼
Dashboard alert + Mobile push notification
```

Everything downstream of ingestion — the `alerts` table, Redis fan-out, the Alert Engine dispatchers, and the cooldown logic — is reused unchanged. The beam layer only adds a device type and an ingestion entry point.

---

## Data Model (Migration 012)

### `beam_sensors`

Fixed-location device representing one guarded crossing line. Like a herdsman gateway, it is **not attached to an animal**.

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID | PK |
| `farm_id` | UUID | FK → farms |
| `geofence_id` | UUID (nullable) | FK → geofences — the border this beam guards |
| `serial_number` | VARCHAR unique | e.g. `BEAM-SB-001` |
| `name` | VARCHAR | e.g. "Main Gate Beam" |
| `beam_type` | VARCHAR | `infrared` \| `microwave` \| `laser` |
| `latitude` / `longitude` | DOUBLE | Mount (transmitter post) location |
| `span_start_*` / `span_end_*` | DOUBLE | The two posts of the guarded line |
| `span` | GEOGRAPHY(LINESTRING,4326) | PostGIS line for map rendering / spatial queries |
| `orientation_deg` | REAL | Compass bearing the beam faces |
| `span_length_m` | REAL | Distance between posts |
| `breach_severity` | VARCHAR | `critical`..`info`, default `high` |
| `alert_on_crossing` | BOOLEAN | default `true` |
| `status` | VARCHAR | `active` \| `inactive` \| `maintenance` \| `fault` |
| `last_seen`, `last_battery_pct`, `config` | | Device housekeeping |

`devices.device_type` also gains `beam_sensor` (mirrors how migration 007 added `herdsman_gateway`).

### `beam_crossings` (TimescaleDB hypertable)

Each row is one crossing event. The beam usually cannot identify **which** animal crossed, so `animal_id` is nullable and only set if a crossing is later attributed to a nearby GPS/BLE position. Retained 1 year (matches `ble_sightings`).

| Column | Type | Notes |
|--------|------|-------|
| `time` | TIMESTAMPTZ | Hypertable time dimension |
| `beam_sensor_id` | UUID | FK → beam_sensors |
| `farm_id` | UUID | FK → farms |
| `direction` | VARCHAR | `in` \| `out` \| `unknown` |
| `confidence` | REAL | 0.0–1.0 detection confidence |
| `animal_id` | UUID (nullable) | Set only if attributed downstream |
| `beam_battery_pct` | INT | |
| `metadata` | JSONB | |

---

## API

Base path `/api/v1/beam` (deprecated unversioned alias `/api/beam`).

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/register` | Register a beam sensor (idempotent-friendly; 409 if serial exists) |
| GET | `/` | List beam sensors (filter by `farm_id`, `status`) |
| GET | `/{serial}` | Get one beam sensor |
| POST | `/event` | Ingest a crossing event — stores it and fires an alert |

### `POST /api/v1/beam/event`

Request:
```json
{
  "beam_serial": "BEAM-SB-001",
  "direction": "out",
  "confidence": 0.92,
  "battery_pct": 88,
  "timestamp": "2026-08-30T10:15:00Z"
}
```

Response:
```json
{
  "accepted": true,
  "beam_sensor_id": "…",
  "alert_created": true,
  "alert_id": "…",
  "timestamp": "2026-08-30T10:15:00Z"
}
```

Behaviour: stores the crossing in `beam_crossings` (always, no cooldown — every crossing is logged), and when the beam is `active` with `alert_on_crossing`, inserts a `beam_crossing` alert at the beam's `breach_severity` and publishes it to Redis on `farm:{farm_id}` (dashboard) and `alerts:incoming` (Alert Engine). Redis publish is best-effort and happens outside the DB transaction so notification fan-out never blocks ingestion.

---

## Alert Pipeline

`beam_crossing` is registered as an `AlertType` in the Alert Engine (without it, events would be dropped). Severity → channel routing is unchanged:

| Severity | Channels |
|----------|----------|
| critical | push + SMS + email + dashboard |
| high (beam default) | push + email + dashboard |
| medium | push + dashboard |
| low / info | dashboard |

Display names for `beam_crossing` ("Perimeter Crossing") were added to the push, SMS, and email dispatchers.

### Cooldown note

The Alert Engine cooldown key is `{alert_type}:{device_id}` over 300s. Because `device_id` is the **beam serial**, repeated crossings at one beam (e.g. a whole herd passing) collapse into a single alert for 5 minutes. This is the desired behaviour for theft alerting. Every individual crossing is still recorded in `beam_crossings` (which has no cooldown), so per-crossing counts and analytics remain accurate.

---

## Simulator

`tools/simulator/beam_simulator.py` lays out beams around a farm's perimeter square and fires crossing events.

```bash
make simulate-beam            # Sibanyoni 50ha perimeter, 5 beams, occasional crossings
make simulate-beam-theft      # crossing burst at the main gate (theft scenario)
make simulate-beam-offline    # lay out beams / print only, no live API needed
```

Options mirror the other simulators: `--farm`, `--beams`, `--severity`, `--interval`, `--duration`, `--scenario {normal,theft}`, `--seed`, `--offline`. For a 50ha farm it computes a ~707m/side square and distributes beams around that boundary — the line a physical fence would follow.

---

## Cost Context (planning ballpark, ZAR)

Figures are order-of-magnitude for planning, not supplier quotes; confirm locally. Do **not** beam a full perimeter — cover chokepoints.

| Approach (50ha) | Once-off | Monthly |
|-----------------|----------|---------|
| Chokepoint beams (4–6) + virtual fence | ~R35k – R90k | ~R200 – R900 data |
| Full beam perimeter (~30–55 pairs) — not recommended | ~R180k – R500k+ | higher + high maintenance |
| Software integration | build effort only | R0 |

Per farm-grade installed beam runs roughly R4,400 – R14,500 (sensor + solar + edge controller + mounting), with a realistic mid-range gate install around R6k–R10k.

---

## Files

- `cloud/migrations/versions/012_beam_sensors.sql` — schema
- `cloud/shared/livestockguard_common/db_models.py` — `BeamSensor`, `BeamCrossing`
- `cloud/services/api_gateway/app/routers/beam.py` — API + ingestion + Redis publish
- `cloud/services/api_gateway/app/main.py` — router registration
- `cloud/services/alert_engine/app/main.py` — `AlertType.BEAM_CROSSING`
- `cloud/services/alert_engine/app/dispatchers/{push_fcm,sms_africastalking,email_ses}.py` — display templates
- `tools/simulator/beam_simulator.py` — simulator
- `Makefile` — `simulate-beam*` targets
