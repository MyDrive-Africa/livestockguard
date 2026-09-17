# Changelog# Changelog

## 2026-09-16 — Simulation Preflight Status + Dashboard "Simulation Mode" Banner

### Problem

The dashboard live view counts only *today's* BLE sightings and the current
herdsman session. When a farm's simulator wasn't running (e.g. a demo left
overnight), the farm showed zero detections and looked broken — even though the
gateway, ear tags, seed data, and ingestion pipeline were all healthy. There was
no at-a-glance way to tell "no data because nothing is running" from an actual
scanning fault.

### 1. Backend preflight endpoint (`api_gateway/app/routers/system.py`)

Added `GET /api/v1/system/simulation-status` (public, mirrors the existing
`/status`). In one query it reports, per farm that owns a BLE gateway:
`registered_tags`, `sightings_today`, `animals_today`, `session_active`,
`gateway_last_seen`, and a `stale` flag (has tags but zero sightings today). It
also returns an `overall` verdict (`healthy` / `partial` / `idle` /
`no_gateways`) plus active/stale farm counts for a banner headline.

### 2. Dashboard "simulation mode" banner (`dashboard/`)

- `src/hooks/useSimulationHealth.ts` — TanStack Query hook polling the preflight
  endpoint every 10s.
- `src/components/SimulationBanner.tsx` — a slim global banner that detects
  "simulation mode" by probing the dev-only `GET /dev/simulator/status` control
  plane (renders nothing in production). Shows a per-farm status chip (green =
  reporting, amber = idle/stale) and a **Restart everything** button.
- Mounted in `src/components/layout/AppLayout.tsx` as a strip above the routed
  content (main is now a flex column).

### 3. One-click "Restart everything" (`dashboard/vite-simulator-plugin.ts`)

Extended the dev-server simulator control plugin with `POST /dev/simulator/restart`
(refactored shared `spawnLoopSimulators` / `stopSimulators` helpers). It stops any
running sims and re-spawns both farm loop simulators on the host. This lives in
the Vite dev server (host, localhost-only, dev-only, hardcoded commands) because
the API gateway runs in a container and cannot orchestrate the host stack.

### 4. Robust interpreter selection + no more silent failures (`dashboard/vite-simulator-plugin.ts`)

Originally the sims were spawned with bare `python3` and `stdio: 'ignore'`, so a
host Python missing `click`/`requests` would crash instantly with no trace and
the banner would still claim "data should resume". Fixed:

- **Prefer the simulator venv**: `resolvePythonBin()` uses
  `tools/simulator/.venv/bin/python3` (or `Scripts/python.exe` on Windows) when
  present — the env `make setup` builds with the sim deps — and only falls back
  to host `python3` otherwise.
- **Capture stderr + detect early exit**: a sim that exits non-zero within
  `CRASH_WINDOW_MS` (3s) is treated as a launch failure; the stderr tail (e.g. an
  `ImportError`) is recorded in `lastError`.
- **Report the truth**: start/restart wait just past the crash window before
  responding, so a launch failure returns `{status:"failed", error, using_venv}`
  (HTTP 500) instead of a false success; `GET /dev/simulator/status` now also
  exposes `using_venv` and `error`. The banner surfaces the real reason and
  suggests `make setup` rather than the misleading "data should resume" toast.

### Verification

Live: the endpoint returns `healthy` with both farms; the restart action
re-spawns `gateway_daily_sim.py` + `sibanyoni_daily_sim.py` under the venv
interpreter (`status: restarted, using_venv: true`) and the DB receives fresh
sightings from both gateways within seconds; stop cleans up. The early-exit
detection was verified against a forced `ModuleNotFoundError` (exit 1 in ~2.4s,
correctly flagged as a failure with the traceback captured). Dashboard
`tsc --noEmit` and `npm run build` both pass. The banner is hidden entirely when
the dev control plane is unreachable (production).

## 2026-09-16 — Unseen-Cow Recovery Sim, Honest Herd Count & Backend Hot-Reload

### 1. "Unseen cow" recovery simulator (`tools/simulator/lostcow_sim.py`)

Loch Vaal has 10 BLE-tagged cattle, but a cow that strays beyond the herdsman's
normal sweep is never scanned and shows as "not seen today". Added a standalone,
separately-runnable simulator that models the herdsman making a dedicated trip to
find and BLE-track one such cow (default `LV-010`), flipping it from missing to
seen. It reuses the existing gateway API flow (`sessions/start` → repeated
`/api/gateway/batch` → `sessions/end`), matches the seeded ear-tag MACs, and
follows the project's `click` + `--seed` + `--offline` conventions.

New Makefile targets (and a `pkill` line in `stop-all`):

- `make simulate-lostcow` — find & track LV-010 for one trip
- `make simulate-lostcow-strays` — herdsman searches but never gets it in range
- `make simulate-lostcow-offline` — no API, print only

### 2. Herd-count reconciliation made consistent (`api_gateway/app/routers/gateway.py`)

`GET /api/v1/gateway/herd-count/{farm_id}` promised a daily "are all my cattle
accounted for today?" check, but `missing` used a rolling 24h window while
`seen_today` used the calendar day. That let the endpoint report `seen_today: 1/10`
with `missing_count: 0` — internally inconsistent for a stock check.

- **Default is now today-based**: `missing` is the exact complement of
  `seen_today`, so `seen_today + missing_count == total_registered` always holds.
- **Backward compatible**: pass `?missing_threshold_hours=N` to use the old
  rolling-window behaviour; `hours_missing` still reports true elapsed time.
- **Hardened**: `last_row.time` is now coerced to a timezone-aware `datetime`
  before `.isoformat()` / delta math, so a string timestamp (e.g. from SQLite in
  tests) can no longer raise `AttributeError`.

Added a `TestHerdCount` suite in `tests/test_gateway.py` (never-seen, seen-today,
and rolling-window cases); all 18 gateway tests pass.

### 3. Backend hot-reload for local development (`cloud/docker-compose.yml`)

All four Python services now hot-reload on file save — no rebuild, no restart.
`api_gateway` uses `uvicorn --reload`; the plain workers (`mqtt_writer`,
`alert_engine`, `analytics_engine`) are wrapped with the `watchfiles` CLI. Source
is bind-mounted over the baked-in copies, and `WATCHFILES_FORCE_POLLING=true` is
set because macOS bind mounts don't forward inotify events into the Docker Linux
VM. Dockerfiles are unchanged for production (mounts/commands live only in
compose). `watchfiles` was added to the three workers' `requirements.txt`.
Full guide: `docs/LOCAL_HOT_RELOAD.md`.

### 4. pip build resilience (all Python Dockerfiles)

Backend image builds now use `pip install --timeout 120 --retries 10` so slow
mirrors or large wheels (numpy, shapely, boto3, firebase-admin) don't abort the
build on a transient network hiccup.

### Verification

- 18/18 `api_gateway` gateway tests pass on in-memory SQLite.
- Live: recovering a cow moves `seen_today` up and drops it from `missing`, with
  the `seen_today + missing_count == total` invariant holding.
- Live: edited a source file in `api_gateway` and `mqtt_writer` and observed
  `WatchFiles detected changes … Reloading` / `changes detected` in the logs,
  then reverted — no rebuild needed.

## 2026-09-14 — Migration Ordering Fix (fresh-DB reliability)

### Problem

On a fresh database, `cloud/docker-compose.yml` mounts `migrations/versions/` into
Postgres `/docker-entrypoint-initdb.d`, which runs every `*.sql` at init in filename
order. Migration `009_farm_schedule_config.sql` seeded a `farm_schedule` row for the
Loch Vaal farm (`bbbb…`) that does not exist until `scripts/seed_data.sql` runs later.
The resulting foreign-key error aborted the init chain, so migrations `010`–`013` never
applied — leaving `beam_sensors`, `herding_robots`, and `ble_estimated_position` missing
and the `herding_orchestrator` service crash-looping on `relation "herding_robots" does not exist`.

### Fixes

- `009_farm_schedule_config.sql`: the Loch Vaal seed `INSERT` is now guarded with
  `DO $$ IF EXISTS (SELECT 1 FROM farms WHERE id = …) $$`, so it is a no-op on a fresh
  DB instead of aborting the migration chain.
- `scripts/seed_data.sql`: the Loch Vaal default schedule seed moved here (guarded with
  `WHERE EXISTS (… farms …)` + `ON CONFLICT (farm_id) DO NOTHING`), so it runs after farms exist.
- Renamed `010_user_farm_assignments.sql` → `010b_user_farm_assignments.sql` to remove a
  duplicate `010_` prefix and make init order deterministic
  (`010_analytics_intelligence` → `010b_user_farm_assignments` → `011` → `012` → `013`).

### Verification

`docker compose down -v && docker compose up -d` on fresh volumes applied all migrations
`001`–`013` in order with no errors; seeding produced 3 farms, 65 animals, 23 geofences,
9 beam sensors, 8 robots, and 1 farm schedule; `herding_orchestrator` runs its control
loop cleanly. No manual migration steps are needed anymore.

## 2026-08-11 — Mobile BLE Scanner Fix & API Path Migration

### BLE Scanner — Zero Animals Fix (`mobile/src/services/bleScanner.ts`)

**Fixed**: Scanner showed "0 in range now" and "0% Seen Today" despite being active. Three root causes:

1. **No fallback when position-based path yields 0 animals**: The scanner's poll would successfully find a gateway with coordinates (from prior simulator runs), call the `/status` endpoint, get 0 recent animals (sightings expired from the 1-hour DB window), and then do nothing — never falling through to the herd-count simulation fallback.
2. **Shift not auto-starting**: The `addToSeenToday()` method gates on `shiftState !== null`. Previously required a manual button tap to start a shift before any tracking occurred. Now auto-starts when scanning begins.
3. **Percentage mismatch across devices**: Each device built its own "seen today" set from independent random local picks. Now syncs from the server's `herd-count` endpoint — uses the `missing` list to determine which animals are seen vs not seen, so all devices converge to the same percentage.

### "In Range" Count Variability

**Fixed**: "In range" count was stuck at exactly 8 for Sibanyoni (50 cattle) due to a fixed `0.15 * totalRegistered` formula. Now uses a variable percentage with random jitter each poll tick to simulate realistic BLE detection fluctuation.

### API Path Migration (Mobile App)

**Migrated** all mobile app API calls from deprecated `/api/...` to versioned `/api/v1/...`:

| File | Endpoints Updated |
|------|------------------|
| `mobile/src/services/bleScanner.ts` | `/api/v1/gateway/tags`, `/api/v1/gateway`, `/api/v1/gateway/status/{serial}`, `/api/v1/gateway/herd-count/{farm_id}`, `/api/v1/animals` |
| `mobile/src/services/offlineBuffer.ts` | `/api/v1/gateway/batch` |
| `mobile/src/screens/MapScreen.tsx` | `/api/v1/animals`, `/api/v1/geofences`, `/api/v1/gateway`, `/api/v1/animals/{id}/history` |
| `mobile/src/screens/AdminDashboard.tsx` | `/api/v1/system/status`, `/api/v1/alerts` |
| `mobile/src/screens/AnimalsScreen.tsx` | `/api/v1/animals` |

### Documentation

- Updated `docs/HERDSMAN_GATEWAY_SPEC.md` architecture diagram to reference `/api/v1/gateway/batch`

---

## 2026-08-10 — Simulator Lifecycle & Map Marker Stability

### Gateway Simulator v2 — Daily Lifecycle (`tools/simulator/gateway_simulator.py`)

**Rewritten** to guarantee 100% cattle detection at morning and evening:

- **3-phase daily lifecycle**: Morning kraal (100% detection) → Daytime patrol (progressive scatter to grazing clusters) → Evening return (cattle herded back, 100% again)
- **Grazing clusters**: Animals scatter to 3-6 clusters 150-300m from kraal centre during patrol phase
- **Realistic convergence**: Gateway returns to kraal first, cattle are herded back at 6 km/h — full headcount restored within 30s of evening phase start
- Tested and verified for both **Loch Vaal** (10 cattle) and **Sibanyoni** (50 cattle)

### Reproducible Simulations (`--seed` option)

Added `--seed` CLI option to all three simulators for deterministic, repeatable runs:

- `gateway_simulator.py` (BLE gateway lifecycle)
- `gateway_daily_sim.py` (full herdsman day routine)
- `simulator.py` (GPS collar MQTT)

Two runs with the same seed produce byte-for-byte identical output.

### BLE Scanning Fix (`gateway_simulator.py`)

**Fixed**: BLE scanning was detecting 0 animals because the scatter radius (500m) far exceeded BLE range (100m). Animals are now placed within 67m of patrol waypoints.

### Dashboard Map — Marker Stability (`dashboard/src/pages/map/MapPage.tsx`)

**Fixed** cow and herdsman markers disappearing/moving on hover, click, or refresh:

1. **Deterministic scatter**: Replaced order-dependent index-based scatter with stable ID hash — same animal always gets the same offset regardless of API response order
2. **Inner wrapper pattern**: All hover transforms (scale) moved to an inner DOM element. Outer element has zero CSS transforms so it never conflicts with MapLibre's positioning
3. **Removed popups from markers**: MapLibre Popup DOM manipulation was causing markers to visually disappear on click. Click now directly triggers trail instead
4. **Prevented spurious marker clearing**: `useEffect` deps no longer trigger full clear on every `farms`/`loading` state change — only on actual farm ID change
5. **WebSocket scatter**: Realtime position updates now apply the same deterministic scatter as initial fetch (previously they bypassed scatter, collapsing markers)
6. **Removed demo trail fallback**: Failed trail fetch no longer renders a hardcoded trail at wrong coordinates — shows toast instead

### Trail Drawing Fix

**Fixed**: Trail line now connects to the cow's actual visual marker position (accounting for scatter offset), not the raw API coordinates. The "Now" time label also appears at the marker.

### Find Herdsman Feature (`dashboard/src/pages/map/MapPage.tsx`)

**New** map control button "Find Herdsman":

- Flies map to herdsman's current position (zoom 17)
- Displays herdsman coordinates as a blue label
- Labels all cow markers >100m from herdsman with their coordinates and distance
- Shows toast with herdsman GPS coordinates

### Mobile App — Marker Scatter (`mobile/src/screens/MapScreen.tsx`)

- Added same deterministic ID-based scatter for overlapping BLE animal markers
- Added `tracksViewChanges={false}` for performance
- Mobile web version (iframe) inherits all dashboard fixes automatically

---

### Files Modified

| File | Change |
|------|--------|
| `tools/simulator/gateway_simulator.py` | Full rewrite: daily lifecycle, --seed, scatter fix |
| `tools/simulator/gateway_daily_sim.py` | Added --seed option |
| `tools/simulator/simulator.py` | Added --seed option |
| `dashboard/src/pages/map/MapPage.tsx` | Marker stability, trail fix, find herdsman, scatter |
| `mobile/src/screens/MapScreen.tsx` | Deterministic scatter, tracksViewChanges |
| `docs/SIMULATION_GUIDE.md` | Gateway v2 docs, --seed docs, scatter docs |
| `docs/DASHBOARD_SPEC.md` | Updated Live Map feature list |
| `docs/MOBILE_APP_SPEC.md` | Added scatter and performance notes |
| `docs/CHANGELOG.md` | This file |
