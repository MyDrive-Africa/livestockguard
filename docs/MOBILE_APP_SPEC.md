# LivestockGuard Mobile App Specification

## Overview

One app, three modes based on user role:
- **Admin mode**: Full system access across all farms — monitor cattle, manage users, create farms
- **Farm Owner mode**: Full control within assigned farm(s) — map, geofences, alerts, herdsman management
- **Herdsman mode**: Background BLE scanning, GPS tracking, cattle count display (locked to assigned farm)

## Role Model

| Role | Scope | Farm Access | Mobile Mode |
|------|-------|-------------|-------------|
| **admin** | Entire organisation | All farms (picker) | Admin view |
| **farm_owner** | Assigned farm(s) | Assigned farms only (picker if multiple) | Farm Owner view |
| **herdsman** | Single assigned farm | Locked to assigned farm | Herdsman view |
| **viewer** | Assigned farm(s) | Read-only on assigned farms | Read-only Farm Owner view |

### Permission Matrix

| Action | Admin | Farm Owner | Herdsman | Viewer |
|--------|:---:|:---:|:---:|:---:|
| View map with cattle | ✅ | ✅ (own farms) | ❌ | ✅ (own farms) |
| Manage geofences | ✅ | ✅ (own farms) | ❌ | ❌ |
| View alerts | ✅ | ✅ (own farms) | ✅ (own farm) | ✅ (own farms) |
| Configure schedules | ✅ | ✅ (own farms) | ❌ | ❌ |
| Manage animals | ✅ | ✅ (own farms) | ❌ | ❌ |
| Create farms | ✅ | ❌ | ❌ | ❌ |
| Create users | ✅ | ✅ (herdsman/viewer) | ❌ | ❌ |
| Assign herdsmen to farm | ✅ | ✅ (own farms) | ❌ | ❌ |
| Assign farm_owner | ✅ | ❌ | ❌ | ❌ |
| BLE scanning / patrol | ❌ | ❌ | ✅ | ❌ |
| Start/end patrol session | ❌ | ❌ | ✅ | ❌ |
| Switch farms | ✅ (all) | ✅ (assigned) | ❌ | ✅ (assigned) |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  React Native App (iOS + Android)                                │
│                                                                   │
│  ┌──────────────────────┐  ┌──────────────────────┐            │
│  │  ADMIN VIEW           │  │  FARM OWNER VIEW     │            │
│  │  - Farm picker (all)  │  │  - Farm picker       │            │
│  │  - Map with cattle    │  │    (assigned only)    │            │
│  │  - All farm data      │  │  - Map with cattle    │            │
│  │  - User management    │  │  - Geofences          │            │
│  │  - Farm creation      │  │  - Alerts/breach      │            │
│  │  - Assign farm_owners │  │  - Cattle inventory   │            │
│  │  - System overview    │  │  - Schedule config    │            │
│  └──────────────────────┘  │  - Herdsman mgmt      │            │
│                             └──────────────────────┘            │
│  ┌──────────────────────┐  ┌──────────────────────┐            │
│  │  HERDSMAN VIEW        │  │  VIEWER (read-only)  │            │
│  │  - BLE scanner (bg)   │  │  - Farm picker       │            │
│  │  - GPS tracker (bg)   │  │    (assigned only)    │            │
│  │  - Cattle count badge │  │  - Map (read-only)    │            │
│  │  - Missing alert      │  │  - Alerts (read-only) │            │
│  │  - Patrol session     │  │  - Animal list        │            │
│  │  - Offline buffer     │  │  - No edit controls   │            │
│  │  - NO farm picker     │  └──────────────────────┘            │
│  └──────────────────────┘                                       │
│                                                                   │
│  ┌──────────────────────────────────────────────────┐           │
│  │  SHARED SERVICES                                  │           │
│  │  - Auth (JWT with role + org_id)                  │           │
│  │  - API client (axios)                             │           │
│  │  - Farm context provider (selected farm state)    │           │
│  │  - Offline storage (SQLite/AsyncStorage)          │           │
│  │  - Push notifications (FCM)                       │           │
│  │  - Background task manager                        │           │
│  └──────────────────────────────────────────────────┘           │
└─────────────────────────────────────────────────────────────────┘
         │
         │ HTTPS / REST API
         ▼
┌─────────────────────────────────────────────────────────────────┐
│  LivestockGuard Cloud API                                        │
│  GET /api/v1/assignments/me/farms  — get user's farms            │
│  POST /api/v1/gateway/batch        — herdsman BLE data           │
│  GET /api/v1/animals, alerts, etc. — farm-scoped data            │
└─────────────────────────────────────────────────────────────────┘
```

---

## Farm Selection Flow (Login → Mode)

```
┌─────────────┐
│   LOGIN     │
│  (email +   │
│  password)  │
└──────┬──────┘
       │ JWT returned with: user_id, email, role, organisation_id
       ▼
┌─────────────────┐
│ GET /me/farms   │  ← Fetch accessible farms
└──────┬──────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────┐
│                    ROLE CHECK                              │
├───────────────┬──────────────────┬───────────────────────┤
│ role = admin  │ role = farm_owner│ role = herdsman       │
│               │ or viewer        │                       │
│ All farms     │ Assigned farms   │ Assigned farm (1)     │
│ in org        │ only             │ only                  │
│               │                  │                       │
│ Show farm     │ If 1 farm:       │ Auto-select farm      │
│ picker        │   auto-select    │ No picker shown       │
│ (dropdown)    │ If multiple:     │ → Herdsman mode       │
│               │   show picker    │                       │
│ → Admin mode  │ → Farm Owner mode│                       │
└───────────────┴──────────────────┴───────────────────────┘
```

### Farm Picker UI

- **Location:** Top of screen, persistent header bar
- **Admin:** Dropdown shows all farms in org with search
- **Farm Owner:** Dropdown shows only assigned farms (no search if ≤ 3 farms)
- **Herdsman:** No picker — farm name displayed as static text
- **Persistence:** Last selected farm stored in AsyncStorage, auto-selected on next launch
- **Switching:** Changing farm reloads all data (animals, map, alerts) for new farm context

### Farm Picker Implementation (Native App)

**Status:** Implemented

The farm picker is fully wired into the React Native app with the following files:

| File | Purpose |
|------|---------|
| `mobile/src/services/api.ts` | `getMyFarms()` calls `GET /api/v1/assignments/me/farms`; `getSelectedFarmId()` / `setSelectedFarmId()` persist selection in AsyncStorage |
| `mobile/src/context/FarmContext.tsx` | React context (`FarmProvider` + `useFarm` hook) — holds farm list, selected farm, and `switchFarm()` function |
| `mobile/src/components/FarmPicker.tsx` | Header bar component — shows current farm name; tapping opens a bottom-sheet modal with all available farms |
| `mobile/App.tsx` | Wraps authenticated app in `FarmProvider`; renders `FarmPicker` in a `SafeAreaView` header above all screens |

**Behaviour:**
1. After login, `FarmProvider` fetches accessible farms from the API
2. Restores last selected farm from AsyncStorage (or auto-selects if single farm)
3. Header bar displays current farm name with ▼ chevron (non-interactive for locked herdsmen)
4. Tapping opens a modal listing farms — selecting one calls `switchFarm(id)` which updates context and persists
5. All screens (`AdminDashboard`, `MapScreen`, `AnimalsScreen`) pass `selectedFarm.id` as `farm_id` query param and re-fetch when farm changes

---

## Cumulative Daily Scan (Seen Today)

### Concept

The BLE scanner tracks two counts simultaneously:
1. **In Range (now):** Cattle within BLE range this instant (~100m) — fluctuates as herdsman moves
2. **Seen Today (cumulative):** Unique tags detected at any point since shift start — only goes UP

On a large farm like Sibanyoni (50 cattle across 50ha), the herdsman can't see all cattle at once.
But as they patrol through different areas, the cumulative count climbs toward 100%.

### Daily Cycle

```
NIGHT (kraal)      → 50/50 confirmed (all cattle penned)
~06:00             → Shift auto-resets "seen today" set
~08:30 kraal opens → DEPARTURE COUNT: scan before cattle scatter (baseline = 100%)
09:00–17:00        → PATROL: cumulative unique tags accumulate
                     Alert if < 90% seen by midday
~17:30 kraal close → RETURN COUNT (Kraal Check): all must be present
                     Missing from kraal at night = CRITICAL alert
```

### Shift Management

| Action | What Happens |
|--------|-------------|
| **Start Shift** | Resets "seen today" set, records departure count from current scan |
| **Patrol Mode** | Each BLE scan adds new unique MACs to the cumulative set |
| **End Patrol (Kraal Check)** | Switches to kraal mode — compares current hard count to departure |
| **New Shift** | Resets everything for a new day |

### Herdsman Screen UI

```
┌─── PATROL MODE ─────────────────────┐
│                                       │
│   📶 Scanner Active · On Patrol       │
│                                       │
│            38                         │
│       / 50 in range now               │
│                                       │
│   ┌─────────────────────────────┐    │
│   │ 📋 Seen Today (Cumulative)   │    │
│   │ ████████████░░░░  86%        │    │
│   │ 43 / 50 unique tags detected │    │
│   │ Last new tag: 11:34          │    │
│   └─────────────────────────────┘    │
│                                       │
│   ┌─────────────────────────────┐    │
│   │ ⚠️ Not Seen Today (7)        │    │
│   │ Never detected since shift   │    │
│   │ • SB-023                     │    │
│   │ • SB-041                     │    │
│   │ • SB-009  ...                │    │
│   └─────────────────────────────┘    │
│                                       │
│   [🏠 Kraal Check (End Patrol)]      │
└───────────────────────────────────────┘
```

### Implementation Files

| File | Purpose |
|------|---------|
| `mobile/src/services/bleScanner.ts` | Core logic: `seenToday` Map, `startShift()`, `endShift()`, `addToSeenToday()`, AsyncStorage persistence |
| `mobile/src/screens/HerdsmanScreen.tsx` | UI: patrol mode, kraal mode, progress bar, not-seen-today list, shift buttons |

### Key Behaviours

- **Persistence:** `seenToday` is saved to AsyncStorage every poll cycle — survives app restart mid-shift
- **Farm-aware:** Switching farms in the picker resets and re-initializes for the new farm's registered tags
- **Large farm simulation:** Sibanyoni (50 cattle, 50ha) detects 40–80% per scan cycle; cumulative climbs over hours
- **Small farm:** Loch Vaal (10 cattle, small plot) detects 70–95% per cycle; reaches 100% quickly
- **Kraal verification:** Evening mode does a hard count — all cattle must be within BLE range at the kraal
- **Threshold alert (future):** If < 90% seen by midday → push notification to farm owner

---

## Herdsman Device Identity (Unique Marker)

The herdsman's phone serves as their **unique marker** in the system. Every BLE scan batch is stamped with the `gateway_serial` (e.g. `GW-LV-001`), which is the primary reference linking scans to a specific herdsman.

### Identity Resolution

```
Phone (gateway_serial: GW-LV-001)
  → assigned to: Sipho Molefe (herdsman_name)
  → registered to: Loch Vaal (farm_id)
  → every batch includes: gateway_serial + GPS + sightings
  → cloud resolves: gateway_serial → gateway_id → herdsman identity
```

### Recommended Device: Samsung Galaxy XCover 7

| Spec | Value |
|------|-------|
| Bluetooth | 5.3 (coded PHY — max BLE scanning range ~120m) |
| IP Rating | IP68 + MIL-STD-810H |
| Battery | 4,050 mAh (removable — swap mid-shift) |
| GPS | Dual-band L1+L5 (±2m outdoor accuracy) |
| OS | Android 14 |
| Price (ZA) | ~R5,000–R6,500 |

See [HERDSMAN_GATEWAY_SPEC.md](HERDSMAN_GATEWAY_SPEC.md#recommended-gateway-phone-samsung-galaxy-xcover-7) for full hardware selection rationale and BLE range compatibility matrix.

### How the Marker is Used in the App

1. **On login:** App fetches herdsman's assigned gateway via user profile / farm assignment
2. **On patrol start:** App includes `gateway_serial` in `POST /api/gateway/sessions/start`
3. **Every batch:** `gateway_serial` is sent with every `POST /api/gateway/batch` — this is the scan reference
4. **On dashboard:** Farm owner sees herdsman name + gateway serial on patrol tracking views
5. **If phone replaced:** Admin re-registers the same `gateway_serial` to the new device — all history preserved

### Why the Phone (Not a Separate BLE Beacon)

The herdsman does not need a separate BLE beacon tag on their person. The phone itself is the marker because:
- It actively submits data (not passively detected)
- The `gateway_serial` is a human-readable, portable identifier
- If the phone dies or is replaced, the serial transfers to the new device
- The phone's GPS provides the position reference for all detected cattle

---

## Herdsman Background Service

The herdsman's phone runs a **foreground service** that:

### Requirements
- Phone charged and ON (screen can be off/locked)
- App does NOT need to be open/visible
- Auto-starts on phone boot
- Works offline (buffers data, syncs when signal available)
- Farm is locked — cannot switch or access other farm data

### BLE Scanning
- Scans every 5-10 seconds for BLE advertisements
- Filters by known MAC addresses (registered ear tags for assigned farm only)
- Records: MAC, RSSI, timestamp
- Power usage: ~2-3% battery per hour

### GPS Tracking  
- Fused location provider (Android) / Core Location (iOS)
- Updates every 30 seconds
- Accuracy: best available (GPS + network)
- Power usage: ~3-5% battery per hour

### Batch Reporting
- Every 25-30 seconds, sends batch to API:
  ```json
  POST /api/v1/gateway/batch
  {
    "gateway_serial": "GW-LV-001",
    "latitude": -26.719,
    "longitude": 27.710,
    "battery_pct": 72,
    "sightings": [{"mac_address": "AA:BB:CC:DD:EE:01", "rssi": -65}, ...]
  }
  ```
- API validates herdsman is assigned to the gateway's farm

### Offline Buffer
- SQLite database stores sightings when no internet
- On reconnect, flushes buffered batches (oldest first)
- Maximum buffer: 24 hours (~100KB)
- Dashboard shows "Last sync: X min ago" if data is delayed

### Notifications (Lock Screen)
- Persistent notification: "📶 LivestockGuard: 10/10 cattle in range"
- Updates count as BLE scan detects/loses cattle
- Alert notification: "⚠️ LV-003 out of range for 10 min"
- Critical: "🚨 LV-001 left 100km zone — possible theft"

---

## Herdsman Access Management

### How Herdsmen Are Assigned

1. **Admin or Farm Owner** creates a user with role `herdsman`
2. Admin/Farm Owner assigns herdsman to a farm via:
   ```
   POST /api/v1/assignments/farms/{farm_id}/assignments
   { "user_id": "...", "farm_id": "...", "role_at_farm": "herdsman" }
   ```
3. Herdsman logs into the app → auto-selects assigned farm → enters herdsman mode
4. Gateway device is registered to the same farm (`gateway_devices.farm_id`)

### Revoking Access

- Admin or Farm Owner calls:
  ```
  DELETE /api/v1/assignments/farms/{farm_id}/assignments/{user_id}
  ```
- Sets `revoked_at` timestamp (soft revoke)
- On next app sync / token refresh, herdsman loses access
- Gateway batch submissions for that farm will be rejected

### Multi-Farm Herdsman (Rare)

If a herdsman works at two farms (e.g. Mon-Wed at Lochvaal, Thu-Sat at North West):
- Assign to both farms
- App shows a simple picker (only those 2 farms)
- Herdsman selects which farm they're patrolling today
- Gateway context switches to selected farm

---

## Admin/Farm Owner View

### Admin-Specific Features
- **Farm creation:** Add new farm to the organisation
- **Org-wide dashboard:** Summary across all farms
- **User management:** Create/edit any user, assign farm_owners
- **System health:** Gateway statuses across all farms

### Farm Owner Features (within assigned farm)
- Map (react-native-maps) with cattle positions
  - Deterministic scatter for overlapping BLE animals (stable ID-based hash, same as dashboard)
  - `tracksViewChanges={false}` for performance on large herds
  - Tap cow marker → 24h trail overlay
- Animal list with search/filter
- Geofence management (create/edit/delete)
- Alert feed with push notifications
- Cattle count summary
- Schedule configuration
- Herdsman management (assign/revoke herdsmen)
- Gateway status for their farm

---

## API Endpoints for Farm Access

| Endpoint | Description |
|----------|-------------|
| `GET /api/v1/assignments/me/farms` | List farms current user can access |
| `GET /api/v1/assignments/farms/{id}/assignments` | List users assigned to a farm |
| `POST /api/v1/assignments/farms/{id}/assignments` | Assign user to farm |
| `DELETE /api/v1/assignments/farms/{id}/assignments/{uid}` | Revoke user from farm |

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Framework | React Native (Expo or bare workflow) |
| BLE | react-native-ble-plx |
| GPS | expo-location or react-native-geolocation |
| Maps | react-native-maps (Google Maps provider) |
| Storage | @react-native-async-storage + expo-sqlite |
| Background | react-native-background-fetch + foreground service |
| Push | @react-native-firebase/messaging (FCM) |
| Auth | JWT stored in SecureStore |
| API | axios with offline queue (axios-retry) |
| State | zustand (with farm context) |

---

## Roles & Screens

| Screen | Admin | Farm Owner | Herdsman | Viewer |
|--------|:---:|:---:|:---:|:---:|
| Login | ✅ | ✅ | ✅ | ✅ |
| Farm picker | ✅ (all) | ✅ (assigned) | ❌ | ✅ (assigned) |
| Map with cattle | ✅ | ✅ | ❌ | ✅ |
| Animal list | ✅ | ✅ | ❌ | ✅ |
| Animal edit | ✅ | ✅ | ❌ | ❌ |
| Alerts feed | ✅ | ✅ | ✅ (own farm) | ✅ |
| Cattle count | ✅ | ✅ | ✅ | ✅ |
| Missing animals | ✅ | ✅ | ✅ | ✅ |
| Geofence view | ✅ | ✅ | ❌ | ✅ |
| Geofence edit | ✅ | ✅ | ❌ | ❌ |
| Schedule config | ✅ | ✅ | ❌ | ❌ |
| User management | ✅ (all) | ✅ (herdsman) | ❌ | ❌ |
| Farm creation | ✅ | ❌ | ❌ | ❌ |
| Herdsman assignment | ✅ | ✅ | ❌ | ❌ |
| BLE scanner status | ❌ | ❌ | ✅ | ❌ |
| Patrol session | ❌ | ❌ | ✅ | ❌ |
| Gateway health | ✅ (all) | ✅ (own farm) | ❌ | ✅ |

---

## Development Phases

### Phase 1: Herdsman MVP
- Foreground service with BLE scan + GPS
- Batch sending to API
- Offline buffer
- Lock screen notification with cattle count
- Auto-start on boot
- Farm auto-selection (single assigned farm)

### Phase 2: Farm Owner View
- Login + role detection + farm selection
- Map with cattle markers
- Alert feed with push
- Animal list
- Herdsman assignment management

### Phase 3: Admin & Full Feature
- Admin mode with org-wide access
- Farm picker (all farms)
- Farm creation
- User management (all roles)
- Geofence management
- Schedule config
- Trail history viewer
- Export reports

---

## Simulator Preservation

The Python simulator (`tools/simulator/gateway_daily_sim.py`) remains for:
- Development & testing without physical devices
- CI/CD integration tests
- Demo purposes
- Load testing (simulate 100+ cattle)
- New feature development (test BLE logic without phones)

The mobile app and simulator both call the same API endpoints — they're interchangeable from the server's perspective.
