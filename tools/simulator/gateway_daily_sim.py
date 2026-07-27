#!/usr/bin/env python3
"""
LivestockGuard — Herdsman Daily Routine Simulator (Loch Vaal Plot 30)

Realistic cattle movement based on actual farm layout and schedule.
Cattle follow paths (roads) around fenced properties, not through them.

Schedule (configurable):
  Night:  Cattle in kraal (dry) or yard (wet kraal)
  08:30:  Kraal gate opens → cattle move to feeding lots/dishes
  08:30-09:20: Feeding at troughs (just outside kraal)
  09:20-09:50: Walk to Entrance/Exit gate, exit yard
  09:50+: Herdsman leads outside via roads to grazing area
  12:00-13:00: Midday rest
  13:00-16:30: Afternoon grazing
  16:30: Return via road back to Entrance/Exit gate
  17:00-17:20: Enter gate, water stop at troughs (same area as feeding)
  17:20-17:45: Walk to kraal, settle for night
  18:00: All in kraal/yard

Usage:
    python gateway_daily_sim.py                     # Normal dry day
    python gateway_daily_sim.py --weather wet       # Wet kraal
    python gateway_daily_sim.py --scenario theft    # Theft at 10am
    python gateway_daily_sim.py --scenario breach   # Cow exits range
    python gateway_daily_sim.py --kraal-open 8.5    # Open at 08:30 (default)
    python gateway_daily_sim.py --return-time 16.5  # Return at 16:30 (default)
    python gateway_daily_sim.py --offline           # No API calls
"""

import time
import math
import random
from dataclasses import dataclass
from typing import List, Optional

import click
import requests


# ─── Farm Layout (Loch Vaal Plot 30) ─────────────────────────────────────────

# TheKraal (~705 m², cattle sleep here at night)
KRAAL_CENTER = (-26.71900, 27.70883)
KRAAL_RADIUS_M = 15

# Feeding lots & water troughs (just east of kraal, within yard)
FEEDING_AREA = (-26.71900, 27.70930)
FEEDING_RADIUS_M = 20

# Yard Boundary (2ha property)
YARD_CENTER = (-26.71909, 27.70976)
YARD_BOUNDS = {
    'min_lat': -26.72009, 'max_lat': -26.71809,
    'min_lon': 27.70876, 'max_lon': 27.71076,
}

# Entrance/Exit Gate (only way in/out of yard)
GATE_POSITION = (-26.71891, 27.70994)

# Road waypoints outside the gate (cattle follow roads, not cut through fences)
# These represent the road/path network around Plot 30
ROAD_FROM_GATE = [
    (-26.71880, 27.71020),   # Just outside gate, on road
    (-26.71850, 27.71060),   # Road heading north-east
    (-26.71800, 27.71100),   # Road intersection
]

# Grazing areas (reached via road waypoints, not straight lines)
GRAZING_AREAS = [
    {
        'name': 'North field (along Barrage Road)',
        'waypoints': [(-26.71800, 27.71100), (-26.71700, 27.71050), (-26.71600, 27.70950)],
        'center': (-26.71550, 27.70950),
    },
    {
        'name': 'East riverside',
        'waypoints': [(-26.71800, 27.71100), (-26.71850, 27.71200), (-26.71900, 27.71300)],
        'center': (-26.71900, 27.71350),
    },
    {
        'name': 'South pasture (past boundary road)',
        'waypoints': [(-26.71880, 27.71020), (-26.71950, 27.71050), (-26.72100, 27.71000)],
        'center': (-26.72200, 27.70950),
    },
    {
        'name': 'West clearing (along dirt track)',
        'waypoints': [(-26.71880, 27.71020), (-26.71870, 27.70900), (-26.71860, 27.70750)],
        'center': (-26.71850, 27.70600),
    },
]

# BLE parameters
BLE_TX_POWER = -59
BLE_PATH_LOSS_N = 2.2
BLE_MAX_RANGE_M = 100
BLE_NOISE_DB = 4

# Registered MACs (match seed_data.sql)
REGISTERED_MACS = [
    'A1:B2:C3:D4:E5:01', 'A1:B2:C3:D4:E5:02', 'A1:B2:C3:D4:E5:03',
    'A1:B2:C3:D4:E5:04', 'A1:B2:C3:D4:E5:05', 'A1:B2:C3:D4:E5:06',
    'A1:B2:C3:D4:E5:07', 'A1:B2:C3:D4:E5:08', 'A1:B2:C3:D4:E5:09',
    'A1:B2:C3:D4:E5:10',
]


# ─── Entities ─────────────────────────────────────────────────────────────────

@dataclass
class Cow:
    name: str
    mac: str
    lat: float
    lon: float

    def move_towards(self, target_lat, target_lon, speed_mps, dt):
        dy = (target_lat - self.lat) * 111320.0
        dx = (target_lon - self.lon) * 111320.0 * math.cos(math.radians(self.lat))
        dist = math.sqrt(dx * dx + dy * dy)
        if dist < 2:
            return True
        move_dist = min(speed_mps * dt, dist)
        ratio = move_dist / dist
        self.lat += (target_lat - self.lat) * ratio
        self.lon += (target_lon - self.lon) * ratio
        self.lat += random.gauss(0, 0.000006)
        self.lon += random.gauss(0, 0.000006)
        return False

    def graze(self, dt):
        speed = random.uniform(0.05, 0.3)
        heading = random.uniform(0, 360)
        dist = speed * dt
        self.lat += (dist * math.cos(math.radians(heading))) / 111320.0
        self.lon += (dist * math.sin(math.radians(heading))) / (111320.0 * math.cos(math.radians(self.lat)))

    def random_in_kraal(self):
        angle = random.uniform(0, 2 * math.pi)
        r = random.uniform(0, KRAAL_RADIUS_M)
        self.lat = KRAAL_CENTER[0] + (r * math.cos(angle)) / 111320.0
        self.lon = KRAAL_CENTER[1] + (r * math.sin(angle)) / (111320.0 * math.cos(math.radians(KRAAL_CENTER[0])))

    def random_near(self, center, radius_m):
        angle = random.uniform(0, 2 * math.pi)
        r = random.uniform(0, radius_m)
        self.lat = center[0] + (r * math.cos(angle)) / 111320.0
        self.lon = center[1] + (r * math.sin(angle)) / (111320.0 * math.cos(math.radians(center[0])))


@dataclass
class Herdsman:
    lat: float
    lon: float
    battery: float = 100.0
    speed_kmh: float = 0.0
    waypoint_idx: int = 0

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

    def follow_waypoints(self, waypoints, speed_mps, dt):
        """Move along waypoints in sequence. Returns True when all reached."""
        if self.waypoint_idx >= len(waypoints):
            return True
        target = waypoints[self.waypoint_idx]
        if self.move_towards(target[0], target[1], speed_mps, dt):
            self.waypoint_idx += 1
        return self.waypoint_idx >= len(waypoints)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def distance_m(lat1, lon1, lat2, lon2):
    dy = (lat2 - lat1) * 111320.0
    dx = (lon2 - lon1) * 111320.0 * math.cos(math.radians(lat1))
    return math.sqrt(dx * dx + dy * dy)


def rssi_from_distance(dist):
    if dist < 0.5: dist = 0.5
    rssi = BLE_TX_POWER - 10 * BLE_PATH_LOSS_N * math.log10(dist)
    rssi += random.gauss(0, BLE_NOISE_DB)
    return max(-120, min(-30, int(rssi)))


def send_batch(api_url, gateway_serial, herdsman, sightings, session_id=None):
    if not sightings:
        return None
    total_accepted = 0
    total_resolved = 0
    for s in sightings:
        payload = {
            "gateway_serial": gateway_serial,
            "latitude": s.get("_lat", herdsman.lat),
            "longitude": s.get("_lon", herdsman.lon),
            "speed": herdsman.speed_kmh,
            "battery_pct": int(herdsman.battery),
            "session_id": session_id,
            "sightings": [{"mac_address": s["mac_address"], "rssi": s["rssi"]}],
        }
        try:
            resp = requests.post(f"{api_url}/api/gateway/batch", json=payload, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                total_accepted += data.get("accepted", 0)
                total_resolved += data.get("resolved", 0)
        except Exception:
            pass
    return {"accepted": total_accepted, "resolved": total_resolved}


# ─── CLI ──────────────────────────────────────────────────────────────────────

@click.command()
@click.option('--api-url', default='http://localhost:8000')
@click.option('--gateway-serial', default='GW-LV-001')
@click.option('--animals', default=10)
@click.option('--speed', default=120, help='Time multiplier (120=12h in 6min, 30=12h in 24min)')
@click.option('--weather', default='dry', type=click.Choice(['dry', 'wet']))
@click.option('--scenario', default='normal', type=click.Choice(['normal', 'theft', 'breach']))
@click.option('--offline', is_flag=True)
@click.option('--scan-interval', default=5, help='Real seconds per tick')
@click.option('--report-interval', default=25, help='Real seconds between API batches')
@click.option('--kraal-open', default=8.5, help='Hour kraal gate opens (8.5=08:30)')
@click.option('--exit-time', default=9.33, help='Hour cattle exit yard gate (9.33=09:20)')
@click.option('--return-time', default=16.5, help='Hour cattle start returning (16.5=16:30)')
@click.option('--settle-time', default=17.75, help='Hour cattle settled in kraal (17.75=17:45)')
def main(api_url, gateway_serial, animals, speed, weather, scenario, offline,
         scan_interval, report_interval, kraal_open, exit_time, return_time, settle_time):
    """Simulate a realistic herdsman day at Loch Vaal Plot 30."""

    print(f"LivestockGuard — Realistic Daily Simulator")
    print(f"{'═' * 60}")
    print(f"Farm:        Loch Vaal Plot 30 (-26.719088, 27.709759)")
    print(f"Gateway:     {gateway_serial}")
    print(f"Herdsman:    Teboho Mpeki")
    print(f"Cattle:      {animals}")
    print(f"Weather:     {weather} ({'kraal overnight' if weather == 'dry' else 'yard — kraal muddy'})")
    print(f"Scenario:    {scenario}")
    print(f"Schedule:    Kraal open {kraal_open:.1f}h, Exit {exit_time:.2f}h, Return {return_time:.1f}h, Settle {settle_time:.2f}h")
    print(f"Speed:       {speed}x")
    print(f"API:         {'OFFLINE' if offline else api_url}")
    print(f"{'═' * 60}\n")

    # Create cattle
    cows = []
    for i in range(min(animals, len(REGISTERED_MACS))):
        cow = Cow(name=f"LV-{i+1:03d}", mac=REGISTERED_MACS[i], lat=0, lon=0)
        if weather == 'dry':
            cow.random_in_kraal()
        else:
            cow.random_near(YARD_CENTER, 50)
        cows.append(cow)

    # Herdsman at house
    herdsman = Herdsman(lat=KRAAL_CENTER[0] + 0.0002, lon=KRAAL_CENTER[1] - 0.0003)

    # Pick today's grazing area
    todays_grazing = random.choice(GRAZING_AREAS)
    grazing_waypoints = todays_grazing['waypoints']
    grazing_center = todays_grazing['center']
    # Return waypoints = reverse
    return_waypoints = list(reversed(grazing_waypoints)) + [GATE_POSITION]

    print(f"  Grazing:   {todays_grazing['name']}")
    print(f"  Route:     {len(grazing_waypoints)} waypoints (following roads)")
    print(f"  Overnight: {'Kraal' if weather == 'dry' else 'Yard'}\n")

    # Dynamic schedule based on CLI params
    schedule = [
        (5.0,          'night',        "Cattle in kraal/yard (night)"),
        (kraal_open,   'feeding',      "Kraal open → feeding at troughs"),
        (exit_time,    'to_gate',      "Walking to Entrance/Exit gate"),
        (exit_time+0.3,'exit_road',    "Following road to grazing area"),
        (exit_time+1.0,'grazing',      f"Grazing: {todays_grazing['name']}"),
        (12.0,         'rest',         "Midday rest (shade)"),
        (13.0,         'grazing2',     "Afternoon grazing"),
        (return_time,  'return_road',  "Returning via road to gate"),
        (return_time+0.5,'enter_gate', "Entering through gate"),
        (return_time+0.7,'water_stop', "Water stop at troughs"),
        (settle_time,  'to_kraal',     f"Walking to {'kraal' if weather == 'dry' else 'yard'}"),
        (settle_time+0.25,'night_end', "Settled for night"),
    ]

    # Simulation loop
    sim_time = 5.0 * 3600
    end_time = (settle_time + 0.5) * 3600
    real_dt = scan_interval
    sim_dt = real_dt * speed

    current_phase_idx = 0
    batch_buffer = []
    last_report = time.time()
    total_sightings = 0
    session_id = None
    herdsman_on_road = False

    # Start session
    if not offline:
        try:
            resp = requests.post(f"{api_url}/api/gateway/sessions/start", json={
                "gateway_serial": gateway_serial,
                "latitude": herdsman.lat, "longitude": herdsman.lon,
                "herdsman_name": "Teboho Mpeki",
            }, timeout=5)
            if resp.status_code == 201:
                session_id = resp.json().get("session_id")
        except Exception:
            pass

    print(f"  {'Time':<6} {'Phase':<40} {'Seen':<8} {'Herdsman position'}")
    print(f"  {'─'*6} {'─'*40} {'─'*8} {'─'*22}")

    try:
        while sim_time < end_time:
            sim_hour = sim_time / 3600.0
            h = int(sim_hour)
            m = int((sim_hour - h) * 60)

            # Determine phase
            for i, (start_h, _, _) in enumerate(schedule):
                if sim_hour >= start_h:
                    current_phase_idx = i
            phase_key = schedule[current_phase_idx][1]
            phase_label = schedule[current_phase_idx][2]

            # ── Phase logic ──
            if phase_key in ('night', 'night_end'):
                herdsman.speed_kmh = 0

            elif phase_key == 'feeding':
                # Cattle at feeding lots/troughs (just outside kraal)
                for cow in cows:
                    cow.move_towards(
                        FEEDING_AREA[0] + random.uniform(-0.00015, 0.00015),
                        FEEDING_AREA[1] + random.uniform(-0.00015, 0.00015),
                        0.4, sim_dt)
                herdsman.move_towards(FEEDING_AREA[0], FEEDING_AREA[1], 0.8, sim_dt)

            elif phase_key == 'to_gate':
                # Cattle walk from feeding area to gate
                for cow in cows:
                    cow.move_towards(GATE_POSITION[0], GATE_POSITION[1], 0.7, sim_dt)
                herdsman.move_towards(GATE_POSITION[0], GATE_POSITION[1], 1.0, sim_dt)

            elif phase_key == 'exit_road':
                # Follow road waypoints to grazing (not straight line through fences)
                if not herdsman_on_road:
                    herdsman.waypoint_idx = 0
                    herdsman_on_road = True
                herdsman.follow_waypoints(grazing_waypoints, 1.3, sim_dt)
                for cow in cows:
                    cow.move_towards(
                        herdsman.lat + random.uniform(-0.0003, 0.0003),
                        herdsman.lon + random.uniform(-0.0003, 0.0003),
                        random.uniform(0.9, 1.3), sim_dt)

            elif phase_key in ('grazing', 'grazing2'):
                # At grazing area — cows scatter and graze
                herdsman.move_towards(grazing_center[0], grazing_center[1], 0.3, sim_dt)
                herdsman.lat += random.gauss(0, 0.00002)
                herdsman.lon += random.gauss(0, 0.00002)
                herdsman.speed_kmh = random.uniform(0.5, 2.0)
                for cow in cows:
                    cow.graze(sim_dt)

            elif phase_key == 'rest':
                herdsman.speed_kmh = 0
                for cow in cows:
                    cow.lat += random.gauss(0, 0.000003)
                    cow.lon += random.gauss(0, 0.000003)

            elif phase_key == 'return_road':
                # Follow road back (reverse waypoints)
                if herdsman_on_road:
                    herdsman.waypoint_idx = 0
                    herdsman_on_road = False
                herdsman.follow_waypoints(return_waypoints, 1.3, sim_dt)
                for cow in cows:
                    cow.move_towards(
                        herdsman.lat + random.uniform(-0.0002, 0.0002),
                        herdsman.lon + random.uniform(-0.0002, 0.0002),
                        random.uniform(0.9, 1.2), sim_dt)

            elif phase_key == 'enter_gate':
                for cow in cows:
                    cow.move_towards(GATE_POSITION[0], GATE_POSITION[1], 0.8, sim_dt)
                herdsman.move_towards(GATE_POSITION[0], GATE_POSITION[1], 1.0, sim_dt)

            elif phase_key == 'water_stop':
                # Water/feed stop at troughs (same area as morning feeding)
                for cow in cows:
                    cow.move_towards(
                        FEEDING_AREA[0] + random.uniform(-0.0001, 0.0001),
                        FEEDING_AREA[1] + random.uniform(-0.0001, 0.0001),
                        0.5, sim_dt)
                herdsman.move_towards(FEEDING_AREA[0], FEEDING_AREA[1], 0.8, sim_dt)

            elif phase_key == 'to_kraal':
                target = KRAAL_CENTER if weather == 'dry' else YARD_CENTER
                for cow in cows:
                    cow.move_towards(target[0], target[1], 0.6, sim_dt)
                herdsman.move_towards(target[0], target[1], 0.8, sim_dt)

            # ── Scenario overrides ──
            if scenario == 'theft' and sim_hour >= 10.0:
                stolen = cows[0]
                stolen.lat -= 0.0015 * (sim_dt / 60)
                stolen.lon += 0.001 * (sim_dt / 60)
                if 10.0 <= sim_hour < 10.05:
                    print(f"  {'':6} 🚨 THEFT: {stolen.name} taken at speed!")

            elif scenario == 'breach' and sim_hour >= 11.0:
                breach_cow = cows[0]
                breach_cow.lat += 0.0004 * (sim_dt / 60)
                if 11.0 <= sim_hour < 11.05:
                    print(f"  {'':6} ⚠️  BREACH: {breach_cow.name} leaving range!")

            # ── BLE scan ──
            detected = 0
            for cow in cows:
                dist = distance_m(herdsman.lat, herdsman.lon, cow.lat, cow.lon)
                if dist <= BLE_MAX_RANGE_M:
                    rssi = rssi_from_distance(dist)
                    batch_buffer.append({
                        "mac_address": cow.mac,
                        "rssi": rssi,
                        "_lat": cow.lat + random.gauss(0, 0.00002),
                        "_lon": cow.lon + random.gauss(0, 0.00002),
                    })
                    detected += 1
            total_sightings += detected

            print(f"  {h:02d}:{m:02d}  {phase_label:<40} {detected:>2}/{animals:<4} "
                  f"({herdsman.lat:.5f}, {herdsman.lon:.5f})")

            # Send batch
            now = time.time()
            if now - last_report >= report_interval and batch_buffer:
                if not offline:
                    result = send_batch(api_url, gateway_serial, herdsman, batch_buffer, session_id)
                    if result:
                        print(f"  {'':6} → API: {result['accepted']} accepted, {result['resolved']} resolved")
                else:
                    print(f"  {'':6} → [OFFLINE] {len(batch_buffer)} sightings")
                batch_buffer = []
                last_report = now

            sim_time += sim_dt
            time.sleep(real_dt)

    except KeyboardInterrupt:
        print("\n\nStopped by user")

    # End session
    if session_id and not offline:
        try:
            requests.post(f"{api_url}/api/gateway/sessions/{session_id}/end", json={
                "latitude": herdsman.lat, "longitude": herdsman.lon,
            }, timeout=5)
        except Exception:
            pass

    print(f"\n{'═' * 60}")
    print(f"Day complete:")
    print(f"  Total BLE detections: {total_sightings}")
    print(f"  Battery remaining:    {herdsman.battery:.0f}%")
    print(f"  Final position:       ({'Kraal' if weather == 'dry' else 'Yard'})")
    print(f"  Route taken:          {todays_grazing['name']}")


if __name__ == '__main__':
    main()
