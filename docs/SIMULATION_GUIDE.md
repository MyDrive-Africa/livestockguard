# LivestockGuard Simulation Guide

This guide covers running the BLE livestock simulation for all farms, with focus on the Sibanyoni Farm (North West) daily routine simulation.

---

## Quick Start (Sibanyoni Farm — 50 Cattle)

```bash
# 1. Start cloud stack (PostgreSQL, Redis, EMQX, API, MQTT writer)
make start

# 2. Run DB migration (adds per-cow estimated positions — only needed once)
cd cloud && docker compose exec -T postgres psql -U livestockguard -d livestockguard \
  < migrations/versions/011_ble_estimated_position.sql

# 3. Start the web dashboard
make dashboard
# Opens at http://localhost:5173 (or next available port)

# 4. Start Sibanyoni BLE daily simulation (50 cattle, 12h in ~6 min)
make simulate-day-sibanyoni
```

### Dashboard Login

| Email | Password | Farm Access |
|-------|----------|-------------|
| `africa.mydrive@gmail.com` | `demo123` | All farms |
| `sibanyoni@livestockguard.co.za` | `demo123` | Sibanyoni only |
| `lochvaal@livestockguard.co.za` | `demo123` | Loch Vaal only |

After logging in, select **Sibanyoni Farm** from the farm dropdown on the Live Map page.

---

## How the BLE Simulation Works

### Architecture

```
┌─────────────────────┐     HTTP POST       ┌──────────────┐     Redis Pub/Sub     ┌───────────┐
│  sibanyoni_daily_sim │ ──────────────────> │  API Gateway │ ──────────────────>  │ Dashboard │
│  (Python CLI)       │  /api/gateway/batch  │  (FastAPI)   │  position.update      │ (React)   │
└─────────────────────┘                      └──────────────┘                       └───────────┘
        │                                           │
        │ Simulates:                                │ Stores:
        │  • 50 cows with individual positions      │  • BLE sightings (per-cow lat/lon)
        │  • Herdsman walking a patrol route        │  • Gateway position updates
        │  • BLE scanning (RSSI from distance)      │  • Geofence breach detection
        │  • Sub-group herd dynamics                │
        └───────────────────────────────────────────┘
```

### Data Flow

1. The simulator computes each cow's real position using movement physics (grazing, walking, sub-group dynamics).
2. When a cow is within BLE range (100m) of the herdsman, it's "detected" with a realistic RSSI value.
3. The batch payload sent to `/api/gateway/batch` includes:
   - **Gateway position** (herdsman's GPS)
   - **Per-cow estimated position** (`latitude`/`longitude` on each sighting)
   - **RSSI** (signal strength, used to estimate distance)
4. The API stores both the gateway position and the per-cow estimated position in `ble_sightings`.
5. The dashboard queries `/api/animals` which returns `COALESCE(estimated_latitude, gateway_latitude)` — each cow gets its own unique map position.
6. Real-time updates flow via WebSocket (Redis Pub/Sub) for live map markers.

### Herd Dynamics

The Sibanyoni simulator models realistic cattle behaviour:

- **Sub-groups**: 50 cattle split into 4-6 clusters of varying size
- **Leaders & followers**: Each group has a lead cow others follow loosely
- **Asymmetric spread**: Groups are elongated along their drift direction, not circular
- **Stragglers**: Some cows move slower and lag behind
- **Personality**: Each cow has individual wander factor and speed
- **Property boundary**: Soft-bounce keeps cattle within the 50-hectare farm

### Daily Schedule

| Time | Phase | Description |
|------|-------|-------------|
| 04:00 | Night | Cattle in kraal (night enclosure) |
| 06:00 | Feeding | Kraal gate opens, cattle walk to water/feed troughs |
| 07:00 | To Gate | Herd moves to main gate |
| 07:30 | Exit Road | Following road to communal grazing area |
| 08:00 | Grazing | Morning grazing (random area selected daily) |
| 12:00 | Rest | Midday rest under trees |
| 13:00 | Grazing | Afternoon grazing |
| 16:00 | Return Road | Returning via road to main gate |
| 16:30 | Enter Gate | Entering property through main gate |
| 17:00 | Water Stop | Water stop at troughs |
| 17:30 | To Kraal | Settling in kraal for night |

---

## All Simulation Commands

### Sibanyoni Farm (North West) — BLE Gateway

| Command | Description |
|---------|-------------|
| `make simulate-day-sibanyoni` | Normal day, 50 cattle, 12h in ~6 min |
| `make simulate-day-sibanyoni-theft` | Theft scenario (2 cows stolen at 10am) |
| `make simulate-day-sibanyoni-breach` | Geofence breach (cow wanders out at 11am) |

### Direct CLI with Options

```bash
cd tools/simulator

# Normal day, default speed (12h in 6min)
python3 sibanyoni_daily_sim.py --speed 120 --animals 50

# Faster playback (12h in 2min)
python3 sibanyoni_daily_sim.py --speed 360 --animals 50

# Slower playback (12h in 12min, more BLE readings)
python3 sibanyoni_daily_sim.py --speed 60 --animals 50

# Offline mode (no API calls, print-only debug)
python3 sibanyoni_daily_sim.py --speed 120 --offline

# Custom schedule (early kraal open, late return)
python3 sibanyoni_daily_sim.py --kraal-open 5.5 --return-time 17.0

# Theft scenario
python3 sibanyoni_daily_sim.py --speed 360 --scenario theft

# Geofence breach scenario
python3 sibanyoni_daily_sim.py --speed 360 --scenario breach
```

### Loch Vaal Plot 30 (Gauteng) — BLE Gateway

| Command | Description |
|---------|-------------|
| `make simulate-day` | Normal day, 10 cattle, 12h in 6 min |
| `make simulate-day-theft` | Theft scenario |
| `make simulate-day-breach` | Geofence breach scenario |
| `make simulate-day-offline` | Offline (no API) |

### Boschhoek Farm (Free State) — GPS Collar (MQTT)

| Command | Description |
|---------|-------------|
| `make simulate` | Normal grazing, 5 animals |
| `make simulate-theft` | Theft scenario |
| `make simulate-breach` | Geofence breach scenario |
| `make simulate-many` | 50 animals stress test |

---

## Troubleshooting

### Cows appear in a circle/ring on the map

This was fixed in migration 011. Ensure you've run:
```bash
cd cloud && docker compose exec -T postgres psql -U livestockguard -d livestockguard \
  < migrations/versions/011_ble_estimated_position.sql
```
Then restart the API: `cd cloud && docker compose restart api_gateway`

### Simulator shows "Connection refused"

The API must be running. Start the cloud stack first:
```bash
make start
```

### No animals visible on map

1. Check the simulator is sending data (look for `→ API: X accepted, X resolved`)
2. Ensure you're on the correct farm in the dashboard dropdown
3. The animal layer must be toggled ON (left sidebar icons)

### All animals show "no position"

The simulation hasn't sent any BLE scans yet. Wait for the herdsman to be within 100m of cattle (typically after 06:00 in the simulated schedule).

### WebSocket not connecting

The dashboard expects the API at `localhost:8000`. Check `docker compose ps` to confirm the API container is healthy.

---

## Farm Coordinates

| Farm | Centre | Area | Province |
|------|--------|------|----------|
| Sibanyoni | -25.3581, 25.3613 | 50 ha | North West |
| Loch Vaal | -26.7191, 27.7098 | 25 ha | Gauteng |
| Boschhoek | -29.12, 26.21 | 450 ha | Free State |

---

## Full Demo (All Farms + Dashboard)

```bash
# Start everything
make start
make dashboard

# In separate terminals:
make simulate              # Boschhoek (GPS collars)
make simulate-day          # Loch Vaal (BLE)
make simulate-day-sibanyoni  # Sibanyoni (BLE, 50 cattle)
```

Or use the scripted demo:
```bash
make demo-full             # All farms, breach scenario
make demo-full-normal      # All farms, normal day
make demo-full-theft       # All farms, theft scenario
```
