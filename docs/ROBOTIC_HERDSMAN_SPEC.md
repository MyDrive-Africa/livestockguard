# Robotic Herdsman Architecture

> Status: **Design proposal** — not yet implemented.
> Scope: Four cooperative humanoid herding robots that keep every animal inside its
> boundary (square, rectangle, or circle), for control and security.
> This document leads with **Layer 3 (Cloud Backend brain)** because that is what
> coordinates the robots. Layers 1 (device) and 2 (connectivity) follow.

---

## 1. Goal

Deploy **4 autonomous humanoid robots per farm** that cooperatively ensure **all cattle
remain inside their assigned boundary at all times**. When an animal approaches or
crosses the boundary, the nearest available robot is dispatched to intercept and gently
push it back toward the herd centre. The robots replace the human herdsman's *judgment
and physical presence*, not just the phone-based sensing that the current gateway
provides.

Two outcomes:

- **Control** — the herd is actively kept together and inside the paddock, on schedule
  (kraal at night, grazing zones by day) without a person present.
- **Security** — a moving physical presence deters theft and predators; a robot arriving
  at a breach point is a stronger response than an alert on a phone.

### Where this fits the existing system

The current system is a **passive observer**: collars and BLE tags report positions; the
cloud detects breaches and *notifies a human*. A robotic herdsman closes the loop — it
adds **actuation**. The same breach event that today sends an SMS instead (or also)
dispatches a robot.

```
TODAY:   sense  →  detect breach  →  notify human   →  human acts (maybe)
GOAL:    sense  →  detect breach  →  decide + dispatch robot  →  robot acts (always)
```

---

## 2. Honest feasibility summary

| Layer of ambition | What it is | Feasibility | Effort |
|-------------------|-----------|-------------|--------|
| **L1 — Software autopilot** | Cloud brain that decides herding actions and issues commands | High — pure software on existing stack | Weeks |
| **L2 — Robot fleet coordination** | The brain commands N robots, tracks their state, assigns jobs | High (software); robot integration via a device contract | Weeks (sim) → months (real telemetry) |
| **L3 — Humanoid robot hardware** | 4 legged/wheeled humanoids that navigate a paddock and move cattle | Hard — a full robotics program (locomotion, terrain, animal-safe behaviour, power, safety liability) | 1+ years, hardware team |

**Recommendation:** build the brain and the robot *contract* first, prove it end-to-end
with a **robot simulator** (same philosophy as your existing GPS/BLE simulators), and
treat the physical humanoid as a hardware track that plugs into the already-proven
software. Every part of L1 and L2 is real work you can ship and demo now; L3 is where the
long pole and the real cost live. The humanoid form factor specifically is the most
expensive and least necessary choice — a rugged wheeled/legged rover herds cattle just as
well. Keep "humanoid" as the product vision but design the contract so any robot body
satisfies it.

---

## 3. Layer 3 — Cloud Backend (the brain)

Layer 3 is where the coordination lives. It introduces **one new service** and reuses
everything else you already have (positions, geofences, MQTT, Redis, WebSocket, alerts).

### 3.1 New service: Herding Orchestrator

A new Python service alongside `alert_engine` and `analytics_engine`, following the same
conventions (Python 3.12, async, dispatcher/plugin patterns, pytest with in-memory
SQLite).

```
cloud/services/herding_orchestrator/
├── Dockerfile
├── requirements.txt
├── requirements-test.txt
├── app/
│   ├── __init__.py
│   ├── main.py                 # APScheduler-style control loop (like analytics_engine)
│   ├── containment.py          # Boundary math: is animal inside square/rect/circle?
│   ├── planner.py              # Decide which animals need herding, compute intercepts
│   ├── assigner.py             # Assign the 4 robots to jobs (cost-based, load-balanced)
│   ├── commands.py             # Emit robot commands over MQTT (via command bridge)
│   └── models.py               # SQLAlchemy models for robots, jobs, telemetry
└── tests/
    ├── conftest.py
    ├── test_containment.py
    ├── test_planner.py
    └── test_assigner.py
```

**Control loop (runs every ~2–5s):**

```
1. READ herd state
   - Latest position per animal (positions hypertable + Redis live cache)
   - Boundary geometry per farm (geofences — polygon, or a circle/rect definition)
   - Current robot fleet state (robots table + live telemetry)

2. EVALUATE containment (containment.py)
   - For each animal: inside boundary? distance to nearest edge? heading toward edge?
   - Classify: SAFE | APPROACHING (within buffer of edge) | BREACHED (outside)
   - Priority = f(severity, distance outside, animal value, herd drift)

3. PLAN (planner.py)
   - For each APPROACHING/BREACHED animal, compute an interception point:
     a target standoff position from which a robot can push it back toward herd centre
   - Merge nearby targets (one robot can shepherd a small cluster)

4. ASSIGN (assigner.py)
   - Match the 4 robots to the prioritised jobs
   - Cost = travel distance + robot battery + current job priority
   - Keep at least 1 robot free/patrolling if fleet not fully committed
   - Never leave a BREACHED animal unassigned if any robot is available

5. COMMAND (commands.py)
   - Emit MOVE_TO / SHEPHERD / RETURN_TO_PATROL commands per robot over MQTT
   - Publish fleet + job state to Redis → WebSocket → dashboard
```

### 3.2 Boundary containment (square, rectangle, circle)

You asked specifically for square/rectangle/circle boundaries. Your `geofences` table
already stores arbitrary PostGIS polygons, and a square/rectangle is just a 4-vertex
polygon. A circle is best stored as **centre + radius** (cheap containment: compare
distance-to-centre against radius) rather than an approximated polygon.

Proposed boundary model (extends the geofence concept, additive migration):

| Field | Purpose |
|-------|---------|
| `shape` | `'polygon'` \| `'rectangle'` \| `'circle'` |
| `center_lat`, `center_lon`, `radius_m` | For `circle` shape |
| `geometry` (existing PostGIS) | For `polygon`/`rectangle` |
| `buffer_m` | Inner warning band; animal within this of the edge = APPROACHING |

Containment math (all in `containment.py`, unit-tested with no DB):

- **Circle:** `haversine(animal, center) <= radius_m` (inside); `radius_m - dist <= buffer_m` (approaching).
- **Rectangle / polygon:** point-in-polygon (winding number — you already have this in
  firmware `lib/geofence/` and the Rust geofence engine; reuse the same algorithm for
  consistency), plus distance-to-nearest-edge for the buffer band.

This keeps the boundary definition in one place and lets the same geometry drive both the
existing breach alerts and the new robot dispatch.

### 3.3 New data model (Migration 013 — follows your 012 pattern)

Mirrors exactly how `012_beam_sensors.sql` introduced a fixed non-animal device: add the
device type to the shared constraint, add a definition table, add a telemetry hypertable.

```sql
-- Allow 'herding_robot' as a device_type (same ALTER pattern as 007 and 012)
ALTER TABLE devices DROP CONSTRAINT IF EXISTS devices_device_type_check;
ALTER TABLE devices ADD CONSTRAINT devices_device_type_check
    CHECK (device_type IN ('collar','eartag','herdsman_gateway','beam_sensor','herding_robot'));
```

**`herding_robots`** — one row per robot (4 per farm), the fleet registry:

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | PK |
| farm_id | UUID | FK → farms |
| serial_number | VARCHAR UNIQUE | e.g. `ROBO-LV-01` (the robot's marker, like `gateway_serial`) |
| name | VARCHAR | "Herder 1" |
| model | VARCHAR | 'humanoid' \| 'wheeled' \| 'quadruped' |
| status | VARCHAR | idle \| patrolling \| enroute \| shepherding \| charging \| fault \| offline |
| last_latitude / last_longitude | FLOAT | Live position |
| heading_deg | REAL | Facing direction |
| battery_pct | INT | Charge level |
| current_job_id | UUID | FK → herding_jobs (nullable) |
| home_latitude / home_longitude | FLOAT | Charging dock |
| max_speed_mps | REAL | For ETA / intercept planning |
| capabilities | JSONB | audio deterrent, light, camera, etc. |
| last_seen | TIMESTAMPTZ | Last telemetry |

**`herding_jobs`** — a unit of herding work the brain created and assigned:

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | PK |
| farm_id | UUID | FK → farms |
| robot_id | UUID | FK → herding_robots (nullable until assigned) |
| job_type | VARCHAR | intercept \| shepherd \| patrol \| return_kraal \| investigate |
| target_animal_id | UUID | FK → animals (nullable for patrol) |
| target_latitude / target_longitude | FLOAT | Where the robot should go |
| priority | INT | Higher = more urgent (breach > approaching) |
| status | VARCHAR | pending \| assigned \| active \| completed \| failed \| cancelled |
| created_at / assigned_at / completed_at | TIMESTAMPTZ | Lifecycle |

**`robot_telemetry`** (TimescaleDB hypertable) — high-frequency robot state, like
`positions` / `ble_sightings`:

| Column | Type | Description |
|--------|------|-------------|
| time | TIMESTAMPTZ | Report time |
| robot_id | UUID | FK → herding_robots |
| farm_id | UUID | FK → farms |
| latitude / longitude | FLOAT | Position |
| heading_deg | REAL | Facing |
| speed_mps | REAL | Ground speed |
| battery_pct | INT | Charge |
| state | VARCHAR | Robot's self-reported state |
| job_id | UUID | Job being executed (nullable) |
| metadata | JSONB | Sensors, obstacle events, animal-proximity |

Add `create_hypertable('robot_telemetry','time')` and a retention policy, exactly like
`beam_crossings` in migration 012.

### 3.4 Command delivery (the hard prerequisite)

The brain must send commands *to* devices. Your roadmap item **#5 ("Device command
delivery not implemented")** is a blocker: `POST /devices/{id}/command` currently accepts
commands but never delivers them. The robotic herdsman needs this path finished.

Proposed command path (reuses EMQX + the MQTT Writer pattern in reverse):

```
Herding Orchestrator
    │  publish JSON command
    ▼
Redis channel  robot:commands            (or direct MQTT publish)
    │
    ▼
MQTT broker (EMQX)  topic: lg/robot/{serial}/cmd     QoS 1
    │
    ▼
Robot (or robot simulator)  subscribes, executes, acks
    │  telemetry + ack
    ▼
MQTT  lg/robot/{serial}/telemetry  →  MQTT Writer  →  robot_telemetry + Redis
```

Command message (JSON, versioned):

```json
{
  "v": 1,
  "cmd": "shepherd",
  "job_id": "uuid",
  "target": { "lat": -26.7191, "lon": 27.7098 },
  "animal_id": "uuid",
  "deterrent": "audio_low",
  "issued_at": "2026-09-02T10:30:00Z",
  "ttl_sec": 60
}
```

`cmd` values: `move_to`, `shepherd`, `patrol`, `return_home`, `stop`, `investigate`.
The robot acks each command and streams telemetry so the brain can re-plan if the animal
keeps moving (closed loop).

### 3.5 API surface (new router `robots.py`)

Follows your `/api/v1/...` convention and JWT + RBAC pattern (only admin/farm_owner can
command robots; herdsman/viewer read-only).

```
GET    /api/v1/robots                     # Fleet list + live status (per farm)
GET    /api/v1/robots/{id}                # One robot detail + current job
GET    /api/v1/robots/{id}/telemetry      # Telemetry history (trail)
POST   /api/v1/robots/register            # Register a robot (serial, home dock)
POST   /api/v1/robots/{id}/command        # Manual override (move_to, return_home, stop)
GET    /api/v1/herding/jobs               # Active/recent jobs
GET    /api/v1/herding/status             # Containment summary: N inside, N approaching, N breached
POST   /api/v1/herding/mode               # auto | manual | paused (per farm)
```

### 3.6 Dashboard & mobile

Reuse the existing MapLibre map. Add a robot marker type (distinct from cattle/herdsman,
per your existing marker convention table):

| Marker | Icon | Colour | Label |
|--------|------|--------|-------|
| Cattle | dot | green/orange/red | animal name |
| Herdsman (phone) | person | blue | name · serial |
| **Robot** | **robot/hexagon** | **purple** | **name · serial · battery** |

Add:
- Boundary overlay showing the square/rectangle/circle with its buffer band.
- Live robot markers with heading arrows and a line to their current target.
- A **Herding** panel: containment summary, fleet status, mode toggle (auto/manual/paused),
  and a manual "send robot here" action.
- Emergency **STOP ALL** control (safety — halts the fleet instantly).

### 3.7 Alerts integration

The brain emits events into your existing alert pipeline (Redis → Alert Engine), e.g.
`robot_dispatched`, `containment_restored`, `robot_fault`, `breach_unhandled`
(no robot available). Severity fits your existing `critical > high > medium > low > info`
scale.

---

## 4. Layer 2 — Connectivity

The robots are far more capable than a collar, so they use a richer link but the same
broker.

| Aspect | Choice | Rationale |
|--------|--------|-----------|
| Command/telemetry transport | MQTT 5.0 over EMQX (existing broker) | Reuse infra; QoS 1 telemetry, QoS 2 for safety-critical stop |
| Robot ↔ cloud link | 4G/5G LTE (primary), farm Wi-Fi/mesh near dock (secondary) | Robots have power budget for cellular, unlike ear tags |
| Local robot-to-robot | Wi-Fi mesh / UWB ranging | Sub-second coordination and collision avoidance without cloud round-trip |
| Positioning | RTK-GPS (±2cm) preferred, dual-band GNSS (±2m) minimum | Herding intercepts need better accuracy than the ±100m BLE approach |
| Time base | NTP-synced | Ordering telemetry and command TTLs |

New MQTT topics (extend the existing `lg/...` namespace):

```
lg/robot/{serial}/telemetry   # robot → cloud, QoS 1, ~1-2 Hz
lg/robot/{serial}/cmd         # cloud → robot, QoS 1 (QoS 2 for stop)
lg/robot/{serial}/ack         # robot → cloud, command acknowledgements
lg/robot/{serial}/event       # robot → cloud, obstacle/fault/animal-contact events
```

Offline behaviour: if a robot loses the cloud link, it falls back to an **autonomous safe
mode** — continue the current job to completion if safe, otherwise hold position, and keep
local robot-to-robot containment via mesh. Never rely on the cloud for immediate collision
or animal-safety decisions; those are on-robot (see Layer 1).

---

## 5. Layer 1 — Device (the robot)

This is the hardware track. The cloud brain treats a robot as a black box that honours the
**robot contract**: subscribe to `cmd`, execute, stream `telemetry`/`ack`/`event`.
Anything satisfying that contract works — humanoid, wheeled, or quadruped.

### 5.1 Reference capability requirements

| Subsystem | Requirement |
|-----------|-------------|
| Locomotion | Traverse uneven paddock/veld, slopes, mud; ≥ herd walking speed (~1.5–2 m/s sustained) |
| Navigation | Autonomous waypoint nav, obstacle avoidance, geofenced operating area |
| Perception | Camera + LiDAR/depth for animal detection, distance keeping, obstacle/person detection |
| Positioning | RTK-GPS + IMU fusion |
| Herding actuation | Non-contact: directional audio, presence/motion, light; **no striking or contact** |
| Power | All-day operation + autonomous return-to-dock charging |
| Safety | On-board e-stop, animal/person proximity slowdown, geofenced hard limits, watchdog |
| Comms | LTE modem + Wi-Fi/mesh radio, MQTT client |
| Ruggedisation | IP66+, dust/rain/sun, -10°C to +50°C |

### 5.2 On-robot autonomy (must NOT depend on cloud)

Safety-critical behaviour lives on the robot, because a cloud round-trip is too slow and
the link is not guaranteed:

- Collision avoidance (animals, people, fences, other robots).
- Animal-safety distance keeping (never crowd or trap an animal against a fence).
- Hard geofence limits (robot's own operating boundary — never leave the farm).
- E-stop and watchdog (halt if no valid command/heartbeat within TTL).

The cloud brain gives *intent* ("shepherd animal X back inside"); the robot decides *how*
to execute it safely.

### 5.3 Humanoid reality check

A humanoid form is the hardest, most expensive path (bipedal balance on rough terrain is a
frontier robotics problem) and offers little herding advantage over a stable wheeled or
quadruped base. Existing cattle-herding robots in the field are wheeled/tracked rovers or
quadrupeds, not humanoids. Recommendation: keep "humanoid" as the brand/vision, but
**design and pilot with a wheeled or quadruped base**, and let the contract stay
body-agnostic so a humanoid can drop in later without cloud changes.

---

## 6. Robot Simulator (build this first)

Mirror your existing simulator philosophy (`tools/simulator/`): prove the whole Layer 3
brain end-to-end with **zero hardware**. This is the single highest-leverage deliverable.

```
tools/simulator/robot_simulator.py
```

- Spawns 4 virtual robots per farm, each an MQTT client on `lg/robot/{serial}/...`.
- Subscribes to `cmd`, simulates movement toward targets at `max_speed_mps`, streams
  `telemetry` at 1–2 Hz, drains battery, returns to dock to charge.
- Simulates cattle drifting toward the boundary (reuse/extend the herd movement in
  `gateway_daily_sim.py`) so the brain has something to react to.
- Scenarios (matching your existing pattern):
  - `--scenario contain` — normal day, robots keep a wandering herd inside a **circle**.
  - `--scenario breach` — one animal crosses a **rectangle** edge; nearest robot intercepts.
  - `--scenario theft` — animal dragged toward border beam; robot + alert both fire.
  - `--scenario night-kraal` — robots herd all animals into the kraal at the scheduled time.
- Deterministic `--seed` for repeatable demos.

Makefile targets to add (matching existing naming):

```
make simulate-robots            # 4 robots, Loch Vaal, contain scenario
make simulate-robots-breach     # breach + intercept
make simulate-robots-theft      # theft response
make demo-robots                # full stack + robot sim + dashboard
```

---

## 7. Phased plan

### Phase 0 — Foundations (prerequisite)
- [ ] Finish device command delivery (roadmap #5): `POST /devices/{id}/command` → MQTT `lg/.../cmd`.
- [ ] Add boundary shape model (circle centre+radius; rectangle/polygon reuse geofences).

### Phase 1 — Layer 3 brain + simulator (weeks)
- [x] Migration 013: `herding_robots`, `herding_jobs`, `robot_telemetry`; add `herding_robot` device type; geofence `shape`/`center`/`radius`/`buffer_m`.
- [x] `herding_orchestrator` service: containment → planner → assigner → commands control loop.
- [x] `robot_simulator.py` + Makefile targets (`simulate-robots`, `-breach`, `-theft`, `-sibanyoni`).
- [x] `herding_orchestrator` wired into `docker-compose.yml`.
- [x] Tests: containment / planner / assigner (pure-logic, no DB) — 15 passing.
- [x] `robots.py` API router (`/api/v1/robots`, `/api/v1/robots/herding/...`) with JWT + RBAC — 13 tests passing.
- [x] ORM models (`HerdingRobot`, `HerdingJob`, `RobotTelemetry`) in `livestockguard_common.db_models`.
- [x] MQTT Writer: consume `lg/robot/+/telemetry` → `robot_telemetry` + live pose + Redis fan-out.
- [x] Dashboard: robot markers (purple, heading arrow), circular boundary + buffer overlay, Herding panel, STOP ALL. *(tsc clean, build passes)*
- [x] Demo seed: `scripts/seed_robots.sql` + `make seed-robots` / `make demo-robots` (4 robots + 200m circular boundary at Loch Vaal).
- [x] Sibanyoni fleet: `seed_robots.sql` also seeds `ROBO-SI-01..04` + a 400m circular boundary at Sibanyoni (matches the `simulate-robots-sibanyoni` sim); `make demo-robots-sibanyoni`.
- [x] Geofence API exposes circle shape fields (`shape`/`center_latitude`/`center_longitude`/`radius_m`/`buffer_m`) so clients can render the true circle + buffer.
- [x] Mobile app (React Native): robot markers (🤖, status-tinted), circular boundary + buffer, Herding fleet panel with STOP ALL, and a per-robot action card (Send here → `move_to`, Return home, Patrol, Stop). *(tsc clean)*

**Phase 1 complete** — end-to-end robotic herdsman across all layers: DB, orchestrator brain, telemetry ingestion, REST API, simulator, and both the web dashboard and mobile app. Ready to run against the stack.

### Phase 2 — Layer 2 real telemetry (weeks → months)
- [ ] Robot contract doc + MQTT topic schemas frozen.
- [ ] Bench robot (one wheeled/quadruped dev unit) speaking the contract over real LTE.
- [ ] RTK-GPS integration; robot-to-robot mesh for local coordination.
- [ ] Offline safe-mode + watchdog validation.

### Phase 3 — Layer 1 hardware pilot (months → 1+ year)
- [ ] Select platform (wheeled/quadruped first). Ruggedise. Herding actuation (audio/presence).
- [ ] On-robot safety autonomy (collision, animal distance, geofence limits, e-stop).
- [ ] Single-robot field trial on one demo farm; then 4-robot cooperative trial.
- [ ] Humanoid form factor evaluated only after cooperative herding is proven.

---

## 8. Risks, safety & ethics

- **Animal welfare** — herding must be non-contact and calm; stressed cattle lose weight
  and can injure themselves. Audio/presence nudging only; strict distance keeping. This is
  also a regulatory/certification concern.
- **Human safety** — a moving robot near people (herdsman, children, thieves) needs
  proximity slowdown, e-stop, and clear liability handling. High-risk; do not skip.
- **Security of the control channel** — a hijacked robot is dangerous. Per-robot auth on
  MQTT, signed commands, TTLs, and an out-of-band STOP ALL.
- **Failure modes** — link loss, robot fault, dead battery mid-job. Always define the safe
  fallback (hold position, return to dock) and alert a human.
- **Regulatory** — L2/L3 field operation may trigger autonomous-machinery and (if any
  aerial component is added later) SACAA rules. Confirm before field trials.
- **Cost honesty** — 4 capable outdoor robots per farm is a large capital cost; the
  humanoid choice multiplies it. The software (L1 brain, L2 coordination) is where you get
  value fastest and cheapest, and it de-risks the hardware bet.

---

## 9. Summary

- **Yes, it's buildable**, and it's a natural extension: it adds *actuation* to your
  existing *sensing* platform.
- **Layer 3 is the core**: a `herding_orchestrator` service (containment → plan → assign →
  command), a migration that follows your 012 beam-sensor pattern, a `robots` API router,
  and MQTT command delivery (which also unblocks roadmap #5).
- **Build the brain + robot simulator first** — full demo, zero hardware — then attach real
  robots via a body-agnostic contract.
- **Humanoid is the vision, not the starting body**: pilot with a wheeled/quadruped base to
  prove cooperative containment, then swap the body in without touching the cloud.
