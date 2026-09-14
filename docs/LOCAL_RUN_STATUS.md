# LivestockGuard — Local Run Status Report

> Captured live from a full setup + run of the platform on a fresh macOS machine.
> This document records exactly what was installed, what is running, how it was
> verified, the issues encountered and how they were fixed, and what remains.
>
> **Date:** 2026-09-14
> **Machine:** macOS (Apple Silicon / aarch64), zsh
> **Outcome:** ✅ Backend + Web Dashboard + Mobile (web) running and verified. iOS native build chain ready. Android native not provisioned.

---

## 1. Executive Summary

| Tier | Component | Status | Endpoint |
|------|-----------|--------|----------|
| Backend | 8 Docker services (Postgres, Redis, EMQX, API, MQTT Writer, Alert Engine, Analytics, Herding Orchestrator) | ✅ Running & healthy | http://localhost:8000 |
| Web | React dashboard (Vite) | ✅ Running (HTTP 200) | http://localhost:5173 |
| Mobile | Expo web (React Native web) | ✅ Running (HTTP 200, bundle compiles) | http://localhost:8082 |
| Mobile | iOS native build chain | ✅ Ready (needs Simulator runtime to launch) | `mobile/ios/LivestockGuard.xcworkspace` |
| Mobile | Android native | ⚠️ Not provisioned (SDK + JDK 17 missing) | — |

The full request/response chain was verified end to end: login returns a JWT, and an
authenticated call to `/api/animals` returns all **65** seeded animals.

---

## 2. Environment / Toolchain Installed

This machine started with **no Homebrew, Docker, Node, or package manager** — only
Apple system Python 3.9, Git, and Xcode 26.6. The following were installed to run the platform.

| Tool | Version | How | Notes |
|------|---------|-----|-------|
| Homebrew | 7.0.1 | installed by user (needs sudo) | at `/opt/homebrew` |
| colima | 0.10.3 | `brew install` | Docker runtime VM (aarch64, macOS Virtualization.Framework) |
| docker | 29.8.0 | `brew install` | client |
| docker-compose | 5.5.1 | `brew install` + CLI-plugin symlink | linked `~/.docker/cli-plugins/docker-compose` so `docker compose` v2 works |
| node | 26.8.2 (system), **20.20.2 (fnm, default)** | `brew install node` + `fnm install 20` | mobile requires Node 20; Node 22+ crashes Metro |
| npm | 11.19.1 / 10.8.2 (Node 20) | bundled | — |
| python@3.12 | 3.12.14 | `brew install` | backend / analytics use 3.12 in Docker |
| fnm | 1.39.0 | `brew install` | Fast Node Manager; added to `~/.zprofile` |
| CocoaPods | 1.17.0 | `brew install cocoapods` | pulled ruby 4.0.6 + libyaml; needed for iOS native |
| Xcode | 26.6 | pre-existing | iOS toolchain |

### Shell configuration changes (`~/.zprofile`)
```sh
eval "$(/opt/homebrew/bin/brew shellenv)"          # Homebrew on PATH
eval "$(fnm env --use-on-cd)"                        # fnm auto-switch (Node 20 in mobile/)
export NODE_EXTRA_CA_CERTS="$HOME/.certs/corp-ca-bundle.pem"   # corp TLS fix (see §6)
```

---

## 3. Backend (Docker stack)

Started with `make setup` (`scripts/setup.sh`) which builds and launches `cloud/docker-compose.yml`.

### Running services (verified up ~49 min at capture)

| Service | Status | Published ports |
|---------|--------|-----------------|
| postgres (TimescaleDB pg16) | Up (healthy) | 5432 |
| redis (7-alpine) | Up (healthy) | 6379 |
| emqx (5.5) | Up | 1883 (MQTT), 8883 (MQTTS), 18083 (dashboard) |
| api_gateway (FastAPI) | Up | 8000 |
| mqtt_writer | Up | (internal) |
| alert_engine | Up | (internal) |
| analytics_engine | Up | (internal) |
| herding_orchestrator | Up | (internal) |

### Seeded data (verified via SQL count)

| Entity | Count |
|--------|-------|
| Farms | 3 (Boschhoek, Loch Vaal, Sibanyoni) |
| Animals | 65 |
| Users | 3 (all password `demo123`) |
| Geofences | 23 |
| Beam sensors | 9 |
| BLE ear tags | 60 |
| Gateway devices | 2 |
| Herding robots | 8 |

### Verification performed
```
GET  http://localhost:8000/health                      -> 200 {"status":"healthy",...}
POST http://localhost:8000/api/auth/login              -> 200 {access_token: <JWT>}
GET  http://localhost:8000/api/animals (Bearer token)  -> 200, 65 animals
DB   18 base tables + PostGIS/TimescaleDB extensions present
```

### Demo credentials

| Email | Password | Access |
|-------|----------|--------|
| `africa.mydrive@gmail.com` | `demo123` | All 3 farms |
| `lochvaal@livestockguard.co.za` | `demo123` | Loch Vaal only |
| `sibanyoni@livestockguard.co.za` | `demo123` | Sibanyoni only |

EMQX dashboard: http://localhost:18083 (`admin` / `public`).

---

## 4. Web Dashboard

- **Path:** `dashboard/` — React 18.3.1, Vite 5.4.21, MapLibre GL, TanStack Query, Zustand, TailwindCSS.
- **Command:** `make dashboard` (`npm run dev`).
- **Status:** http://localhost:5173 → HTTP 200.
- **Type check:** `tsc --noEmit` passed with **no errors**.
- **Env:** `dashboard/.env` created (`VITE_API_URL=http://localhost:8000`, `VITE_WS_URL=ws://localhost:8000/ws`, MapLibre Carto style).

---

## 5. Mobile App

- **Path:** `mobile/` — Expo **52.0.49**, React Native **0.76.9**, react-native-maps, AsyncStorage. **Managed Expo workflow.**
- **Bundle IDs:** iOS `co.za.livestockguard.app`, Android `co.za.livestockguard.app`.
- **Env:** `mobile/.env` created (`API_URL`/`WS_URL` → localhost:8000).

### Web mode — ✅ running
- **Command (that works on this network):**
  ```sh
  export NODE_EXTRA_CA_CERTS="$HOME/.certs/corp-ca-bundle.pem"
  ./node_modules/.bin/expo start --web --port 8082 --offline   # CI=1
  ```
- **Status:** http://localhost:8082 → HTTP 200 (serves LivestockGuard HTML).
- **Bundle:** `AppEntry.bundle` compiles → HTTP 200, ~2.5 MB, ~60,745 lines, no errors.

### iOS native — ✅ build chain ready
- `expo prebuild --platform ios` generated `mobile/ios/` (`LivestockGuard.xcodeproj`).
- `pod install` succeeded: **75 dependencies, 74 pods**, `LivestockGuard.xcworkspace` created.
- Xcode 26.6 + CocoaPods 1.17.0 present.
- **Remaining to actually launch:** no iOS **Simulator runtime** is installed. Install with:
  ```sh
  xcodebuild -downloadPlatform iOS      # multi-GB download
  ./node_modules/.bin/expo run:ios
  ```

### Android native — ⚠️ not provisioned
Missing: Android SDK (`~/Library/Android/sdk`), JDK 17, emulator/AVD. To enable:
```sh
brew install --cask android-studio
brew install openjdk@17
# then install SDK 34 + create an AVD via Android Studio, and:
./node_modules/.bin/expo run:android
```

---

## 6. Issues Encountered & Fixes (important for reproducibility)

### 6.1 Migrations 010–013 never applied (backend)
`cloud/docker-compose.yml` mounts `migrations/versions` into Postgres
`/docker-entrypoint-initdb.d`, so all `*.sql` run **at container init, in alphabetical order**.
Migration `009_farm_schedule_config.sql` **failed at init** because it seeds a `farm_schedule`
row for the Loch Vaal farm (`bbbb…`) that does not exist until `seed_data.sql` runs later.
That failure **aborted the init script**, so `010`–`013` never ran, leaving `beam_sensors`,
`herding_robots`, and `ble_estimated_position` missing — and `herding_orchestrator`
crash-looping on `relation "herding_robots" does not exist`.

**Fix applied:** manually ran `010_analytics_intelligence.sql`, `010_user_farm_assignments.sql`,
`011`, `012`, `013`, then `seed_data.sql` + `seed_robots.sql`, then restarted `herding_orchestrator`.

> **Follow-ups worth doing in the repo:**
> - Two migrations share the `010_` prefix (`010_analytics_intelligence.sql` and
>   `010_user_farm_assignments.sql`) — a numbering collision; renumber one.
> - Migration `009` should not seed data that depends on `seed_data.sql`, or seeds should
>   move out of migrations. Otherwise a fresh volume silently skips later migrations.

### 6.2 Node/npm TLS failure on corporate network — `UNABLE_TO_GET_ISSUER_CERT_LOCALLY`
`curl` worked but `npm`/Expo failed TLS. Root cause: the corporate root CA lives in the
**macOS System keychain**, which Node does **not** use (Node ships its own CA list).

**Fix applied:** exported the system + root CAs to a PEM bundle and pointed Node at it:
```sh
security find-certificate -a -p /Library/Keychains/System.keychain            >  ~/.certs/corp-ca-bundle.pem
security find-certificate -a -p /System/Library/Keychains/SystemRootCertificates.keychain >> ~/.certs/corp-ca-bundle.pem
export NODE_EXTRA_CA_CERTS="$HOME/.certs/corp-ca-bundle.pem"   # + added to ~/.zprofile
```
`npm ping` → PONG afterward. (184 certs in bundle.)

### 6.3 `npx expo` fails; mobile `expo` install was left incomplete
`npx expo …` tries to resolve `expo` from the registry first and fails on the same
TLS/DNS issues. The first mobile install also left `node_modules/expo` without a
`package.json`.

**Fix applied:** `rm -rf node_modules/expo && npm install` (with the CA cert set), then run
the **local** CLI directly: `./node_modules/.bin/expo start … --offline` (never `npx`).

### 6.4 Transient OpenDNS/Umbrella DNS hijack
One install failed with `ENOTFOUND registry.npmjs.org.x.<hash>.id.opendns.com` (DNS
interception on a single tarball). Re-running `npm install` (with retries) succeeded.

---

## 7. How to Start / Stop Everything (this machine)

> Every terminal must first load Homebrew; the mobile app also needs fnm Node 20 and the CA cert.

**Start backend** (Docker):
```sh
eval "$(/opt/homebrew/bin/brew shellenv)"
colima start                    # if the VM is not already running
cd cloud && docker compose up -d
```

**Start dashboard** (:5173):
```sh
eval "$(/opt/homebrew/bin/brew shellenv)"
cd dashboard && npm run dev
```

**Start mobile web** (:8082):
```sh
eval "$(/opt/homebrew/bin/brew shellenv)"
export PATH="$HOME/.fnm:$PATH"; eval "$(fnm env)"; fnm use 20
export NODE_EXTRA_CA_CERTS="$HOME/.certs/corp-ca-bundle.pem"; export CI=1
cd mobile && ./node_modules/.bin/expo start --web --port 8082 --offline
```

**Stop:**
```sh
cd cloud && docker compose down     # backend
# Ctrl+C the dashboard and mobile dev servers
```

---

## 8. Ports Reference

| Port | Service |
|------|---------|
| 5173 | Web dashboard (Vite) |
| 8000 | API Gateway (FastAPI) — `/docs` for Swagger |
| 8082 | Mobile app (Expo web) |
| 1883 / 8883 | EMQX MQTT / MQTTS |
| 18083 | EMQX dashboard (`admin`/`public`) |
| 5432 | PostgreSQL + TimescaleDB |
| 6379 | Redis |

---

## 9. Outstanding / Optional Next Steps

- **iOS launch:** install a Simulator runtime (`xcodebuild -downloadPlatform iOS`) then `expo run:ios`.
- **Android:** install Android Studio + JDK 17 + SDK 34 + an AVD to enable `expo run:android`.
- **Repo hygiene:** fix the duplicate `010_` migration prefix and remove the data-seed from migration `009` (see §6.1) so fresh installs apply every migration.
- **AWS / IAM migration:** planned for a separate session — see `docs/AWS_CLOUD9_DEPLOYMENT_PLAN.md` and the summary in this repo's follow-up notes.
