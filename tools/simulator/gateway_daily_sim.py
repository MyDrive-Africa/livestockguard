#!/usr/bin/env python3
"""
LivestockGuard — Herdsman Daily Routine Simulator (Loch Vaal Plot 30)

Realistic cattle movement simulation based on actual geofence locations:

DRY NIGHT: Cattle in TheKraal (enclosed overnight)
WET NIGHT: Cattle scattered in Yard Boundary (kraal too muddy)

MORNING ROUTINE:
  1. Cattle start in kraal (dry) or yard (wet)
  2. Kraal gate opens → cattle move within yard
  3. Cattle navigate to Entrance/Exit gate
  4. Exit through gate → outside yard boundary

DAY (Herdsman leads):
  5. Herdsman leads cattle to grazing areas (random directions)
  6. Cattle graze, walk, rest throughout the day

EVENING:
  7. Herdsman leads cattle back through Entrance/Exit gate
  8. Cattle return to kraal (dry) or yard (wet)

Usage:
    python gateway_daily_sim.py                          # Normal day (dry)
    python gateway_daily_sim.py --weather wet            # Wet day
    python gateway_daily_sim.py --scenario theft         # Theft at 8am
    python gateway_daily_sim.py --scenario breach        # Cow wanders off
    python gateway_daily_sim.py --offline                # No API
"""

import time
import math
import random
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime, timezone

import click
import requests


# ─── Actual Geofence Coordinates (from seed_data.sql) ─────────────────────────

# TheKraal (user-drawn, ~705 m²)
KRAAL_CENTER = (-26.71900, 27.70883)
KRAAL_RADIUS_M = 15  # ~30m across

# Yard Boundary (2ha, ~140m x 200m)
YARD_CENTER = (-26.71909, 27.70976)
YARD_BOUNDS = {
    'min_lat': -26.72009, 'max_lat': -26.71809,
    'min_lon': 27.70876, 'max_lon': 27.71076,
}

# Entrance/Exit Gate (tiny zone at property boundary)
GATE_POSITION = (-26.71891, 27.70994)

# Grazing areas outside the yard (various directions)
GRAZING_AREAS = [
    {'name': 'North field', 'lat': -26.71600, 'lon': 27.70950},
    {'name': 'East riverbank', 'lat': -26.71900, 'lon': 27.71300},
    {'name': 'South pasture', 'lat': -26.72200, 'lon': 27.70900},
    {'name': 'West clearing', 'lat': -26.71850, 'lon': 27.70600},
]

# BLE simulation parameters
BLE_TX_POWER = -59
BLE_PATH_LOSS_N = 2.2
BLE_MAX_RANGE_M = 100
BLE_NOISE_DB = 4

# Registered BLE MACs (must match seed_data.sql)
REGISTERED_MACS = [
    'A1:B2:C3:D4:E5:01', 'A1:B2:C3:D4:E5:02', 'A1:B2:C3:D4:E5:03',
    'A1:B2:C3:D4:E5:04', 'A1:B2:C3:D4:E5:05', 'A1:B2:C3:D4:E5:06',
    'A1:B2:C3:D4:E5:07', 'A1:B2:C3:D4:E5:08', 'A1:B2:C3:D4:E5:09',
    'A1:B2:C3:D4:E5:10',
]


# ─── Simulated Entities ──────────────────────────────────────────────────────

@dataclass
class Cow:
    name: str
    mac: str
    lat: float
    lon: float

    def move_towards(self, target_lat: float, target_lon: float, speed_mps: float, dt: float):
        dy = (target_lat - self.lat) * 111320.0
        dx = (target_lon - self.lon) * 111320.0 * math.cos(math.radians(self.lat))
        dist = math.sqrt(dx * dx + dy * dy)
        if dist < 2:
            return True  # Arrived
        move_dist = min(speed_mps * dt, dist)
        ratio = move_dist / dist
        self.lat += (target_lat - self.lat) * ratio
        self.lon += (target_lon - self.lon) * ratio
        # Natural wander
        self.lat += random.gauss(0, 0.000008)
        self.lon += random.gauss(0, 0.000008)
        return False

    def graze(self, dt: float):
        speed = random.uniform(0.1, 0.4)
        heading = random.uniform(0, 360)
        dist = speed * dt
        dlat = (dist * math.cos(math.radians(heading))) / 111320.0
        dlon = (dist * math.sin(math.radians(heading))) / (111320.0 * math.cos(math.radians(self.lat)))
        self.lat += dlat
        self.lon += dlon

    def random_in_yard(self):
        """Place cow randomly within yard boundary."""
        self.lat = random.uniform(YARD_BOUNDS['min_lat'], YARD_BOUNDS['max_lat'])
        self.lon = random.uniform(YARD_BOUNDS['min_lon'], YARD_BOUNDS['max_lon'])

    def random_in_kraal(self):
        """Place cow randomly within the kraal."""
        angle = random.uniform(0, 2 * math.pi)
        r = random.uniform(0, KRAAL_RADIUS_M)
        self.lat = KRAAL_CENTER[0] + (r * math.cos(angle)) / 111320.0
        self.lon = KRAAL_CENTER[1] + (r * math.sin(angle)) / (111320.0 * math.cos(math.radians(KRAAL_CENTER[0])))


@dataclass
class Herdsman:
    lat: float
    lon: float
    battery: float = 100.0
    speed_kmh: float = 0.0

    def move_towards(self, target_lat: float, target_lon: float, speed_mps: float, dt: float):
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
        self.battery -= random.uniform(0.001, 0.003)
        return False


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


# ─── Main Simulation ─────────────────────────────────────────────────────────

@click.command()
@click.option('--api-url', default='http://localhost:8000', help='API base URL')
@click.option('--gateway-serial', default='GW-LV-001', help='Gateway serial')
@click.option('--animals', default=10, help='Number of cattle')
@click.option('--speed', default=120, help='Speed multiplier (120 = 12h in 6min)')
@click.option('--weather', default='dry', type=click.Choice(['dry', 'wet']),
              help='Weather: dry (kraal overnight) or wet (yard overnight)')
@click.option('--scenario', default='normal',
              type=click.Choice(['normal', 'theft', 'breach']),
              help='Scenario: normal, theft (cow taken at 8am), breach (cow wanders)')
@click.option('--offline', is_flag=True, help='No API calls')
@click.option('--scan-interval', default=5, help='Real seconds between ticks')
@click.option('--report-interval', default=30, help='Real seconds between API reports')
def main(api_url, gateway_serial, animals, speed, weather, scenario, offline,
         scan_interval, report_interval):
    """
    Simulate a realistic herdsman day at Loch Vaal Plot 30.

    Cattle start in kraal (dry) or yard (wet), exit through the gate,
    graze outside with the herdsman, then return in the evening.
    """
    print(f"LivestockGuard — Realistic Daily Simulator")
    print(f"{'═' * 55}")
    print(f"Farm:      Loch Vaal Plot 30")
    print(f"Gateway:   {gateway_serial}")
    print(f"Herdsman:  Teboho Mpeki")
    print(f"Cattle:    {animals}")
    print(f"Weather:   {weather} ({'kraal overnight' if weather == 'dry' else 'yard overnight — kraal muddy'})")
    print(f"Scenario:  {scenario}")
    print(f"Speed:     {speed}x ({12*3600/speed/60:.0f} min real time)")
    print(f"API:       {'OFFLINE' if offline else api_url}")
    print(f"{'═' * 55}\n")

    # Create cattle
    cows = []
    for i in range(min(animals, len(REGISTERED_MACS))):
        cow = Cow(name=f"LV-{i+1:03d}", mac=REGISTERED_MACS[i], lat=0, lon=0)
        if weather == 'dry':
            cow.random_in_kraal()
        else:
            cow.random_in_yard()
        cows.append(cow)

    # Herdsman starts at the house (near kraal)
    herdsman = Herdsman(lat=KRAAL_CENTER[0] + 0.0002, lon=KRAAL_CENTER[1] - 0.0003)

    # Pick today's grazing area (random)
    todays_grazing = random.choice(GRAZING_AREAS)
    print(f"  Today's grazing: {todays_grazing['name']}")
    print(f"  Cattle start: {'TheKraal' if weather == 'dry' else 'Yard (wet kraal)'}")
    print()

    # Day schedule
    # Phase: (sim_hour, phase_key, description)
    schedule = [
        (5.0,  'night',       f"Cattle in {'kraal' if weather == 'dry' else 'yard'} (night)"),
        (6.0,  'gate_open',   "Kraal gate open → cattle move to yard"),
        (6.5,  'to_gate',     "Cattle walking to Entrance/Exit gate"),
        (7.0,  'exit_gate',   "Exiting through gate"),
        (7.5,  'to_grazing',  f"Walking to {todays_grazing['name']}"),
        (8.5,  'grazing',     f"Grazing at {todays_grazing['name']}"),
        (12.0, 'rest',        "Midday rest (shade)"),
        (13.0, 'grazing2',    "Afternoon grazing"),
        (16.0, 'return_gate', "Returning to gate"),
        (16.5, 'enter_gate',  "Entering through gate"),
        (17.0, 'to_kraal',    f"Walking to {'kraal' if weather == 'dry' else 'yard'}"),
        (17.5, 'night_end',   "Cattle settled for night"),
    ]

    # Simulation loop
    sim_time = 5.0 * 3600
    end_time = 18.0 * 3600
    real_dt = scan_interval
    sim_dt = real_dt * speed

    current_phase_idx = 0
    batch_buffer = []
    last_report = time.time()
    total_sightings = 0
    session_id = None

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

    print(f"  {'Time':<6} {'Phase':<35} {'In range':<10} {'Location'}")
    print(f"  {'─'*6} {'─'*35} {'─'*10} {'─'*25}")

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

            # ── Execute phase logic ──
            if phase_key == 'night' or phase_key == 'night_end':
                # Cattle stationary in kraal or yard
                herdsman.speed_kmh = 0

            elif phase_key == 'gate_open':
                # Cattle move from kraal to yard area
                for cow in cows:
                    cow.move_towards(YARD_CENTER[0], YARD_CENTER[1], 0.5, sim_dt)
                herdsman.move_towards(YARD_CENTER[0], YARD_CENTER[1], 1.0, sim_dt)

            elif phase_key == 'to_gate':
                # Cattle navigate to the Entrance/Exit gate
                for cow in cows:
                    cow.move_towards(GATE_POSITION[0], GATE_POSITION[1], 0.8, sim_dt)
                herdsman.move_towards(GATE_POSITION[0], GATE_POSITION[1], 1.2, sim_dt)

            elif phase_key == 'exit_gate' or phase_key == 'enter_gate':
                # All funnel through the gate
                for cow in cows:
                    cow.move_towards(GATE_POSITION[0], GATE_POSITION[1], 1.0, sim_dt)
                herdsman.move_towards(GATE_POSITION[0], GATE_POSITION[1], 1.2, sim_dt)

            elif phase_key == 'to_grazing':
                # Walk to today's grazing area
                target = (todays_grazing['lat'], todays_grazing['lon'])
                herdsman.move_towards(target[0], target[1], 1.3, sim_dt)
                for cow in cows:
                    cow.move_towards(
                        herdsman.lat + random.uniform(-0.0003, 0.0003),
                        herdsman.lon + random.uniform(-0.0003, 0.0003),
                        random.uniform(0.8, 1.2), sim_dt
                    )

            elif phase_key in ('grazing', 'grazing2'):
                # Cows graze freely, herdsman wanders slowly
                herdsman.lat += random.gauss(0, 0.00002)
                herdsman.lon += random.gauss(0, 0.00002)
                herdsman.speed_kmh = random.uniform(1.0, 2.5)
                for cow in cows:
                    cow.graze(sim_dt)

            elif phase_key == 'rest':
                # Midday rest — minimal movement
                herdsman.speed_kmh = 0
                for cow in cows:
                    cow.lat += random.gauss(0, 0.000005)
                    cow.lon += random.gauss(0, 0.000005)

            elif phase_key == 'return_gate':
                # Walk back to gate
                herdsman.move_towards(GATE_POSITION[0], GATE_POSITION[1], 1.3, sim_dt)
                for cow in cows:
                    cow.move_towards(
                        herdsman.lat + random.uniform(-0.0002, 0.0002),
                        herdsman.lon + random.uniform(-0.0002, 0.0002),
                        random.uniform(0.9, 1.3), sim_dt
                    )

            elif phase_key == 'to_kraal':
                # From gate back to kraal or yard
                target = KRAAL_CENTER if weather == 'dry' else YARD_CENTER
                herdsman.move_towards(target[0], target[1], 1.0, sim_dt)
                for cow in cows:
                    cow.move_towards(target[0], target[1], 0.8, sim_dt)

            # ── Scenario overrides ──
            if scenario == 'theft' and sim_hour >= 8.0:
                stolen = cows[0]
                stolen.lat -= 0.002 * (sim_dt / 60)
                stolen.lon += 0.001 * (sim_dt / 60)
                if 8.0 <= sim_hour < 8.1:
                    print(f"  {'':6} 🚨 THEFT: {stolen.name} taken by vehicle!")

            elif scenario == 'breach' and sim_hour >= 9.0:
                breach_cow = cows[0]
                breach_cow.lat += 0.0005 * (sim_dt / 60)
                breach_cow.lon += 0.0002 * (sim_dt / 60)
                if 9.0 <= sim_hour < 9.1:
                    print(f"  {'':6} ⚠️  BREACH: {breach_cow.name} wandering away!")

            # ── BLE scan ──
            detected = 0
            for cow in cows:
                dist = distance_m(herdsman.lat, herdsman.lon, cow.lat, cow.lon)
                if dist <= BLE_MAX_RANGE_M:
                    rssi = rssi_from_distance(dist)
                    batch_buffer.append({
                        "mac_address": cow.mac,
                        "rssi": rssi,
                        "_lat": cow.lat + random.gauss(0, 0.00003),
                        "_lon": cow.lon + random.gauss(0, 0.00003),
                    })
                    detected += 1
            total_sightings += detected

            # Print
            print(f"  {h:02d}:{m:02d}  {phase_label:<35} {detected:>2}/{animals:<6} "
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

    print(f"\n{'═' * 55}")
    print(f"Day complete:")
    print(f"  Total BLE detections: {total_sightings}")
    print(f"  Battery remaining:    {herdsman.battery:.0f}%")
    print(f"  Cattle end position:  {'Kraal' if weather == 'dry' else 'Yard'}")


if __name__ == '__main__':
    main()
