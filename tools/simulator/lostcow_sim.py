"""LivestockGuard — "Unseen Cow" Recovery Simulator (Loch Vaal Plot 30).

Background
----------
Loch Vaal has 10 registered, BLE-tagged cattle (LV-001..LV-010). On a normal
herdsman day (``gateway_daily_sim.py``) all ten are within range of Teboho's
gateway phone, so the herd-count reconciliation
(``GET /api/v1/gateway/herd-count/{farm_id}``) reports full coverage.

In practice one animal — here **LV-010** by default — often wanders off to a
far corner of the property and is *not* picked up during the regular sweep, so
it shows as "missing / not seen today" in the dashboard stock check.

This script is the deliberate, separately-runnable counterpart: it simulates
the herdsman making a dedicated trip to find that specific cow and successfully
BLE-tracking it for a while. Running it flips the target cow from "missing" to
"seen today" in the herd count, and drops a trail of ``ble_sightings`` for it.

Run it on the days you want to demonstrate the unseen cow being recovered:

    python3 lostcow_sim.py                    # find & track LV-010 once
    python3 lostcow_sim.py --cow LV-003       # a different animal
    python3 lostcow_sim.py --outcome strays   # herdsman looks but never finds it
    python3 lostcow_sim.py --offline          # no API, print only
    python3 lostcow_sim.py --seed 42          # reproducible run

It talks to the same endpoints as the other gateway simulators:
``POST /api/gateway/sessions/start`` → repeated ``POST /api/gateway/batch``
→ ``POST /api/gateway/sessions/{id}/end``. MACs match ``scripts/seed_data.sql``.
"""

import math
import random
import time
from dataclasses import dataclass, field
from typing import Optional

import click
import requests


# ─── Farm layout (Loch Vaal Plot 30 — matches gateway_daily_sim.py) ───────────

KRAAL_CENTER = (-26.71900, 27.70883)
YARD_CENTER = (-26.71909, 27.70976)
GATE_POSITION = (-26.71891, 27.70994)

# Registered ear-tag MACs, LV-001..LV-010 (must match seed_data.sql)
REGISTERED_MACS = {
    f"LV-{i + 1:03d}": f"A1:B2:C3:D4:E5:{i + 1:02d}" for i in range(10)
}

# Remote spots where a stray cow is typically found — well outside the yard,
# so the regular kraal/patrol sweep never reaches them.
HIDING_SPOTS = [
    {"name": "Far north field edge (Barrage Road fence line)", "pos": (-26.71400, 27.70900)},
    {"name": "East riverside thicket", "pos": (-26.71950, 27.71450)},
    {"name": "South pasture dip (past boundary road)", "pos": (-26.72350, 27.70930)},
    {"name": "West clearing dirt track", "pos": (-26.71850, 27.70500)},
]

# BLE parameters (match the other Loch Vaal sims)
BLE_TX_POWER = -59
BLE_PATH_LOSS_N = 2.2
BLE_MAX_RANGE_M = 100
BLE_NOISE_DB = 4


# ─── Entities ─────────────────────────────────────────────────────────────────


@dataclass
class Cow:
    name: str
    mac: str
    lat: float
    lon: float

    def graze(self, dt):
        """Slow random drift while grazing in place."""
        speed = random.uniform(0.05, 0.3)
        heading = random.uniform(0, 360)
        dist = speed * dt
        self.lat += (dist * math.cos(math.radians(heading))) / 111320.0
        self.lon += (dist * math.sin(math.radians(heading))) / (
            111320.0 * math.cos(math.radians(self.lat))
        )

    def wander_away(self, dt, speed_mps=0.8):
        """Keep drifting further off — used when the cow is never found."""
        self.lat += (speed_mps * dt) * random.uniform(0.3, 1.0) / 111320.0
        self.lon += (speed_mps * dt) * random.uniform(-0.5, 0.5) / (
            111320.0 * math.cos(math.radians(self.lat))
        )


@dataclass
class Herdsman:
    lat: float
    lon: float
    battery: float = 100.0
    speed_kmh: float = 0.0

    def move_towards(self, target_lat, target_lon, speed_mps, dt):
        dy = (target_lat - self.lat) * 111320.0
        dx = (target_lon - self.lon) * 111320.0 * math.cos(math.radians(self.lat))
        dist = math.sqrt(dx * dx + dy * dy)
        if dist < 3:
            self.speed_kmh = 0
            return True
        move_dist = min(speed_mps * dt, dist)
        ratio = move_dist / dist
        self.lat += (target_lat - self.lat) * ratio
        self.lon += (target_lon - self.lon) * ratio
        self.speed_kmh = speed_mps * 3.6
        self.battery -= random.uniform(0.0005, 0.002)
        return False


# ─── Helpers ──────────────────────────────────────────────────────────────────


def distance_m(lat1, lon1, lat2, lon2):
    dy = (lat2 - lat1) * 111320.0
    dx = (lon2 - lon1) * 111320.0 * math.cos(math.radians(lat1))
    return math.sqrt(dx * dx + dy * dy)


def rssi_from_distance(dist):
    if dist < 0.5:
        dist = 0.5
    rssi = BLE_TX_POWER - 10 * BLE_PATH_LOSS_N * math.log10(dist)
    rssi += random.gauss(0, BLE_NOISE_DB)
    return max(-120, min(-30, int(rssi)))


def start_session(api_url, gateway_serial, herdsman):
    try:
        resp = requests.post(
            f"{api_url}/api/gateway/sessions/start",
            json={
                "gateway_serial": gateway_serial,
                "latitude": herdsman.lat,
                "longitude": herdsman.lon,
                "herdsman_name": "Teboho Mpeki",
            },
            timeout=5,
        )
        if resp.status_code == 201:
            return resp.json().get("session_id")
    except Exception as e:
        print(f"  [API] Session start failed: {e}")
    return None


def end_session(api_url, session_id, herdsman):
    try:
        requests.post(
            f"{api_url}/api/gateway/sessions/{session_id}/end",
            json={"latitude": herdsman.lat, "longitude": herdsman.lon},
            timeout=5,
        )
    except Exception:
        pass


def send_sighting(api_url, gateway_serial, herdsman, cow, rssi, session_id):
    """Post a single BLE sighting to the gateway batch endpoint."""
    payload = {
        "gateway_serial": gateway_serial,
        "latitude": cow.lat + random.gauss(0, 0.00002),
        "longitude": cow.lon + random.gauss(0, 0.00002),
        "speed": herdsman.speed_kmh,
        "battery_pct": int(herdsman.battery),
        "session_id": session_id,
        "sightings": [{"mac_address": cow.mac, "rssi": rssi}],
    }
    try:
        resp = requests.post(f"{api_url}/api/gateway/batch", json=payload, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("accepted", 0), data.get("resolved", 0)
    except Exception:
        pass
    return 0, 0


# ─── CLI ──────────────────────────────────────────────────────────────────────


@click.command()
@click.option("--api-url", default="http://localhost:8000", help="API base URL")
@click.option("--gateway-serial", default="GW-LV-001", help="Gateway serial (Teboho's phone)")
@click.option(
    "--cow",
    default="LV-010",
    type=click.Choice(list(REGISTERED_MACS.keys())),
    help="Which registered cow is the normally-unseen one to go and track",
)
@click.option(
    "--outcome",
    default="found",
    type=click.Choice(["found", "strays"]),
    help="'found' = herdsman reaches & tracks the cow; 'strays' = never gets in range",
)
@click.option("--speed", default=120, help="Time multiplier (120 = ~fast trip)")
@click.option("--scan-interval", default=5, help="Real seconds per tick")
@click.option("--track-minutes", default=20, help="Sim-minutes to keep tracking once found")
@click.option("--offline", is_flag=True, help="Run without API (print output only)")
@click.option("--seed", default=None, type=int, help="Random seed for reproducible runs")
def main(api_url, gateway_serial, cow, outcome, speed, scan_interval, track_minutes, offline, seed):
    """Simulate finding and BLE-tracking a normally-unseen Loch Vaal cow.

    The herdsman starts at the kraal, walks out to the remote spot where the
    stray cow is, and once within BLE range reports a run of sightings — so the
    cow flips from "missing" to "seen today" in the herd count. With
    ``--outcome strays`` the herdsman searches but the cow keeps its distance
    and is never picked up (stays missing).
    """
    if seed is not None:
        random.seed(seed)

    mac = REGISTERED_MACS[cow]
    hiding = random.choice(HIDING_SPOTS)
    target_cow = Cow(name=cow, mac=mac, lat=hiding["pos"][0], lon=hiding["pos"][1])
    herdsman = Herdsman(lat=KRAAL_CENTER[0], lon=KRAAL_CENTER[1])

    approach_dist = distance_m(herdsman.lat, herdsman.lon, target_cow.lat, target_cow.lon)

    print(f"{'═' * 64}")
    print("LivestockGuard — Unseen Cow Recovery Simulator")
    print(f"{'═' * 64}")
    print(f"Farm:       Loch Vaal Plot 30 (-26.719088, 27.709759)")
    print(f"Gateway:    {gateway_serial} (Teboho Mpeki)")
    print(f"Target cow: {cow}  (tag {mac})")
    print(f"Last known: {hiding['name']} — {approach_dist:.0f} m from kraal")
    print(f"Outcome:    {outcome}")
    print(f"Speed:      {speed}x   |   API: {'OFFLINE' if offline else api_url}")
    print(f"Seed:       {seed if seed is not None else 'random'}")
    print(f"{'═' * 64}\n")

    session_id = None
    if not offline:
        session_id = start_session(api_url, gateway_serial, herdsman)
        print(f"Session: {session_id or '(not started — gateway may be unregistered)'}\n")

    real_dt = scan_interval
    # Sim time advanced per tick. Uses a 1s base step scaled by speed so the
    # simulation still progresses even when --scan-interval is 0 (no sleep).
    sim_dt = max(1, scan_interval) * speed

    total_sightings = 0
    total_resolved = 0
    found = False
    tracked_seconds = 0
    track_limit_seconds = track_minutes * 60

    # Hard cap on iterations so a search that never succeeds still terminates
    # (covers the 'strays' outcome and any pathological chase geometry).
    tick = 0
    max_ticks = 400

    print(f"  {'Phase':<26} {'Dist(m)':>8}  {'RSSI':>5}  {'Seen'}")
    print(f"  {'─' * 26} {'─' * 8}  {'─' * 5}  {'─' * 4}")

    try:
        while True:
            tick += 1
            dist = distance_m(herdsman.lat, herdsman.lon, target_cow.lat, target_cow.lon)

            if outcome == "strays":
                # Herdsman heads out, cow keeps drifting further away — never in range.
                herdsman.move_towards(target_cow.lat, target_cow.lon, 1.4, sim_dt)
                target_cow.wander_away(sim_dt, speed_mps=1.5)
                phase = "Searching (cow evading)"
            elif not found:
                # Walk out towards the cow's last-known spot.
                arrived = herdsman.move_towards(target_cow.lat, target_cow.lon, 1.4, sim_dt)
                target_cow.graze(sim_dt)
                phase = "Walking to last-known spot"
                if dist <= BLE_MAX_RANGE_M:
                    found = True
                    phase = "*** Cow in BLE range ***"
            else:
                # Found: shadow the cow closely so it stays in BLE range, then
                # let it graze a little. Herdsman keeps pace with the drift.
                herdsman.move_towards(target_cow.lat, target_cow.lon, 5.0, sim_dt)
                target_cow.graze(min(sim_dt, 60))
                tracked_seconds += sim_dt
                phase = "Tracking cow"

            # ── BLE scan ──
            detected = ""
            if found and dist <= BLE_MAX_RANGE_M:
                rssi = rssi_from_distance(dist)
                detected = "yes"
                total_sightings += 1
                if not offline:
                    acc, res = send_sighting(
                        api_url, gateway_serial, herdsman, target_cow, rssi, session_id
                    )
                    total_resolved += res
                rssi_str = f"{rssi:>5}"
            else:
                rssi_str = f"{'—':>5}"

            print(f"  {phase:<26} {dist:>8.0f}  {rssi_str}  {detected}")

            # ── Termination ──
            if found and tracked_seconds >= track_limit_seconds:
                print(f"\n  Tracked {cow} for {track_minutes} sim-minutes — logging complete.")
                break
            if outcome == "strays" and (dist > 600 or tick >= max_ticks):
                print(f"\n  {cow} kept its distance — never came within BLE range.")
                break
            if tick >= max_ticks:
                print(f"\n  Search ended after {max_ticks} scans.")
                break

            time.sleep(real_dt)

    except KeyboardInterrupt:
        print("\n\nStopped by user")

    if session_id and not offline:
        end_session(api_url, session_id, herdsman)

    print(f"\n{'═' * 64}")
    print("Recovery run complete:")
    print(f"  Cow:                 {cow} ({mac})")
    if outcome == "found":
        print(f"  Result:              {'FOUND & TRACKED' if found else 'NOT FOUND (out of range)'}")
    else:
        print(f"  Result:              STRAYED (deliberately not found)")
    print(f"  BLE sightings sent:  {total_sightings}")
    if not offline:
        print(f"  Resolved to animal:  {total_resolved}")
        print(f"\n  Check the herd count — {cow} should now show as 'seen today':")
        print(f"    GET {api_url}/api/v1/gateway/herd-count/"
              f"bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
    print(f"{'═' * 64}")


if __name__ == "__main__":
    main()
