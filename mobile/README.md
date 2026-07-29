# LivestockGuard Mobile App

React Native (Expo) app for livestock monitoring — dual-role (Admin + Herdsman).

## Setup

```bash
cd mobile
npm install
npx expo start
```

## Development

```bash
# Run on iOS simulator
npx expo run:ios

# Run on Android emulator
npx expo run:android

# Run on physical device (Expo Go)
npx expo start --tunnel
```

## Architecture

```
mobile/
├── App.tsx                    # Entry point, role-based routing
├── src/
│   ├── screens/
│   │   ├── LoginScreen.tsx    # Authentication
│   │   ├── HerdsmanScreen.tsx # Cattle count (herdsman view)
│   │   └── AdminScreen.tsx    # Full dashboard (TODO)
│   ├── services/
│   │   ├── api.ts             # REST API client (same as web)
│   │   ├── bleScanner.ts      # BLE ear tag detection
│   │   └── offlineBuffer.ts   # Local storage for offline mode
│   ├── stores/                # Zustand state management
│   ├── components/            # Shared UI components
│   └── navigation/            # React Navigation config
├── app.json                   # Expo config (permissions, etc.)
└── package.json
```

## Permissions Required

**Android:**
- ACCESS_FINE_LOCATION (GPS)
- ACCESS_BACKGROUND_LOCATION (background GPS)
- BLUETOOTH_SCAN (BLE scanning)
- BLUETOOTH_CONNECT (BLE connection)
- FOREGROUND_SERVICE (keep scanning when app in background)

**iOS:**
- NSBluetoothAlwaysUsageDescription
- NSLocationAlwaysAndWhenInUseUsageDescription
- UIBackgroundModes: bluetooth-central, location, fetch

## API Endpoints Used

Same as web dashboard:
- POST /api/auth/login
- POST /api/gateway/batch (BLE sightings)
- GET /api/gateway/tags (registered MACs)
- GET /api/animals (cattle list)
- GET /api/gateway/herd-count/{farm_id}
