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
