# Changelog

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
