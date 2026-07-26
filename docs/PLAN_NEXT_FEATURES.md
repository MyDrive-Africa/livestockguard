# LivestockGuard — Next Features Plan

## Priority Order

### 1. ~~Initial Load Race Condition~~ ✅ DONE
Map now loads data only after farm is selected from API.

### 2. Add Animal Form (Dashboard)
**Status:** API exists, dashboard button is placeholder

**What to build:**
- Modal form triggered by "+ Add Animal" button on Animals page
- Fields: name, tag_id, species, breed, gender, colour, description, weight_kg, date_of_birth, photo_url
- Farm auto-selected from current view
- On submit: POST /api/animals → refresh list
- Validation: name and tag_id required, gender dropdown (male/female), breed dropdown with common SA breeds

**Also needed:**
- Edit animal modal (click row → edit fields → PATCH /api/animals/{id})
- Delete/mark deceased button in edit modal

---

### 3. Geofence Edit / Resize / Names (Dashboard)
**Status:** Geofences display on map with names (via text labels), creation via draw tool works

**What to build:**
- **Names visible on map:** Already rendering via `fence-label-{id}` text layer ✅
- **Geofences page:** List all geofences with name, type, active toggle, actions
- **Edit geofence:** Click geofence in list → edit name, type, active status, alert_on_breach
- **Resize geofence radius:** For circular zones (kraal, yard, range), allow editing the radius in km → recalculate polygon
- **Delete geofence:** DELETE /api/geofences/{id} with confirmation
- **Rename on create:** Draw tool already prompts for name ✅

**Loch Vaal geofence naming:**
| Zone | Current Name | Purpose |
|------|-------------|---------|
| Kraal | "Kraal (Night Enclosure)" | ~50m, cattle sleep here |
| Yard | "Yard Boundary (2ha)" | Property boundary |
| Range | "Loch Vaal Area (30km)" | Max roaming distance |
| Dam | "Dam (Exclusion Zone)" | Cattle must not enter |

**API needed:**
- PATCH /api/geofences/{id} (update name, type, active, geometry)
- DELETE /api/geofences/{id}
- Both exist in the codebase but need dashboard UI

---

### 4. Real-time Breach Alerts on Map
**Status:** Alerts stored in DB, no visual pop-up on map

**What to build:**
- When a breach/theft alert is created, show a **red pulse marker** on the map at the alert location
- Toast notification appears (uses existing toast system)
- Alert badge in sidebar shows count
- WebSocket pushes alert events to dashboard in real-time
- Click alert marker → shows animal name, alert type, severity, time
- "Acknowledge" button to dismiss from map

**Integration:**
- MQTT Writer already creates alerts in DB on breach/theft
- WebSocket bridge already publishes to Redis pub/sub
- Dashboard WebSocket hook receives events
- Just need: render alert marker on map + show toast

---

### 5. Add Device / Register Gateway (Dashboard Forms)
**Status:** API exists, buttons are placeholder

**What to build:**
- "+ Register Device" modal: serial_number, device_type (collar/eartag), farm, animal assignment
- "+ Register Gateway" modal: serial_number, name, herdsman_name, phone, device_type (phone/dedicated)
- Both forms call existing POST endpoints

---

## Geofence Zones — Loch Vaal Plot 30

```
┌─────────────────────────────────────────────────────────────────────┐
│  ZONE 3: Loch Vaal Area (30km radius)                                │
│  Breach here = CRITICAL (likely stolen, far from farm)               │
│                                                                      │
│    ┌───────────────────────────────────────────────────────┐        │
│    │  ZONE 2: Yard Boundary (2 hectares / 140m x 140m)     │        │
│    │  Breach here = HIGH (escaped the property)             │        │
│    │                                                        │        │
│    │    ┌──────────────────────────────────────┐           │        │
│    │    │  ZONE 1: Kraal (50m x 40m)            │           │        │
│    │    │  Breach here at night = CRITICAL       │           │        │
│    │    │  (cattle should be enclosed)           │           │        │
│    │    └──────────────────────────────────────┘           │        │
│    │                                                        │        │
│    │    ┌─ ─ ─ ─ ─ ─ ─ ─ ─┐                              │        │
│    │    │  Dam (Exclusion)   │ ← cattle must NOT enter     │        │
│    │    └─ ─ ─ ─ ─ ─ ─ ─ ─┘                              │        │
│    │                                                        │        │
│    └───────────────────────────────────────────────────────┘        │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Simulation Scenarios Available

| Command | Farm | Scenario |
|---------|------|----------|
| `make simulate` | Boschhoek (GPS) | Normal grazing |
| `make simulate-theft` | Boschhoek (GPS) | Theft (vehicle speed) |
| `make simulate-breach` | Boschhoek (GPS) | Geofence breach |
| `make simulate-day` | Loch Vaal (BLE) | Full day routine |
| `make simulate-day-theft` | Loch Vaal (BLE) | Theft at 8am |
| `make simulate-day-breach` | Loch Vaal (BLE) | Cow wanders out |

---

## Implementation Order

1. **Add Animal form** → most useful for managing the 50 Loch Vaal cattle
2. **Geofence list/edit page** → manage zones, rename, resize, delete
3. **Real-time breach alerts** → visual feedback when simulating theft/breach
4. **Device/Gateway registration forms** → complete the CRUD for all entities
5. **Runtime performance monitor** → dashboard health widget showing API latency, WebSocket status, last data timestamps
