# LivestockGuard Mobile App Specification

## Overview

One app, two modes based on user role:
- **Admin/Farmer mode**: Monitor cattle, view map, manage geofences, receive alerts
- **Herdsman mode**: Background BLE scanning, GPS tracking, cattle count display

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  React Native App (iOS + Android)                                │
│                                                                   │
│  ┌──────────────────────┐  ┌──────────────────────┐            │
│  │  ADMIN/FARMER VIEW   │  │  HERDSMAN VIEW        │            │
│  │  - Map with cattle    │  │  - BLE scanner (bg)   │            │
│  │  - Geofences          │  │  - GPS tracker (bg)   │            │
│  │  - Alerts/breach      │  │  - Cattle count badge │            │
│  │  - Cattle inventory   │  │  - Missing alert      │            │
│  │  - Schedule config    │  │  - Patrol session     │            │
│  │  - User management    │  │  - Offline buffer     │            │
│  └──────────────────────┘  └──────────────────────┘            │
│                                                                   │
│  ┌──────────────────────────────────────────────────┐           │
│  │  SHARED SERVICES                                  │           │
│  │  - Auth (JWT)                                     │           │
│  │  - API client (axios)                             │           │
│  │  - Offline storage (SQLite/AsyncStorage)          │           │
│  │  - Push notifications (FCM)                       │           │
│  │  - Background task manager                        │           │
│  └──────────────────────────────────────────────────┘           │
└─────────────────────────────────────────────────────────────────┘
         │
         │ HTTPS / REST API
         ▼
┌─────────────────────────────────────────────────────────────────┐
│  LivestockGuard Cloud API (existing)                             │
│  POST /api/gateway/batch, GET /api/animals, etc.                 │
└─────────────────────────────────────────────────────────────────┘
```

## Herdsman Background Service

The herdsman's phone runs a **foreground service** that:

### Requirements
- Phone charged and ON (screen can be off/locked)
- App does NOT need to be open/visible
- Auto-starts on phone boot
- Works offline (buffers data, syncs when signal available)

### BLE Scanning
- Scans every 5-10 seconds for BLE advertisements
- Filters by known MAC addresses (registered ear tags)
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
  POST /api/gateway/batch
  {
    "gateway_serial": "GW-LV-001",
    "latitude": -26.719,
    "longitude": 27.710,
    "battery_pct": 72,
    "sightings": [{"mac_address": "AA:BB:CC:DD:EE:01", "rssi": -65}, ...]
  }
  ```

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

## Admin/Farmer View

Same functionality as web dashboard but mobile-optimized:
- Map (react-native-maps)
- Animal list with search/filter
- Geofence view (read-only on mobile)
- Alert feed with push notifications
- Cattle count summary
- Schedule viewer

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

## Roles & Screens

| Screen | Admin/Farmer | Herdsman |
|--------|:---:|:---:|
| Login | ✅ | ✅ |
| Map with cattle | ✅ | ❌ |
| Animal list | ✅ | ❌ |
| Alerts feed | ✅ | ✅ (own farm) |
| Cattle count | ✅ | ✅ |
| Missing animals | ✅ | ✅ |
| Geofence view | ✅ | ❌ |
| Schedule config | ✅ | ❌ |
| User management | ✅ (owner) | ❌ |
| BLE scanner status | ❌ | ✅ |
| Patrol session | ❌ | ✅ |

## Development Phases

### Phase 1: Herdsman MVP
- Foreground service with BLE scan + GPS
- Batch sending to API
- Offline buffer
- Lock screen notification with cattle count
- Auto-start on boot

### Phase 2: Admin View
- Login + role detection
- Map with cattle markers
- Alert feed with push
- Animal list

### Phase 3: Full Feature
- Geofence view
- Schedule config
- User management
- Trail history viewer
- Export reports

## Simulator Preservation

The Python simulator (`tools/simulator/gateway_daily_sim.py`) remains for:
- Development & testing without physical devices
- CI/CD integration tests
- Demo purposes
- Load testing (simulate 100+ cattle)
- New feature development (test BLE logic without phones)

The mobile app and simulator both call the same API endpoints — they're interchangeable from the server's perspective.
