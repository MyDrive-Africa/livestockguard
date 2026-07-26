#!/usr/bin/env python3
"""
LivestockGuard — Herdsman Daily Routine Simulator

Simulates a realistic day for a herdsman at Loch Vaal Plot 30:
- 05:00 Wake up, cattle in kraal (night enclosure)
- 06:00 Open kraal, herd moves to grazing area
- 06:00–11:00 Morning grazing (herdsman walks with herd)
- 11:00–13:00 Midday rest near water
- 13:00–17:00 Afternoon grazing (different area)
- 17:00–18:00 Return to kraal
- 18:00+ Cattle in kraal, herdsman at house

The simulator sends BLE batch sightings to the API every 30s,
mimicking the herdsman's phone scanning ear tags as he walks.

Usage:
    python gateway_daily_sim.py                     # Full day (compressed to ~5 min)
    python gateway_daily_sim.py --realtime          # Real pace (12 hours)
    python gateway_daily_sim.py --speed 60          # 60x speed (12 min)
    python gateway_daily_sim.py --offline           # No API, print only
"""

import time
import math
import random
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime, timezone

import click
import requests


# ─── Loch Vaal Plot 30 Coordinates ───────────────────────────────────────────

FARM_CENTER = (-26.719088, 27.709759)

# Key locations on the plot
LOCATIONS = {
    'kraal':        (-26.71909, 27.70976),   # Night enclosure (centre of plot)
    'house':        (-26.71880, 27.70950),   # Farmhouse (near kraal)
    'water_point':  (-26.71850, 27.71020),   # Dam/trough
    'gate':         (-26.71810, 27.70880),   # Plot entrance gate
    'grazing_north': (-26.71650, 27.71050),  # North grazing area
    'grazing_east':  (-26.71900, 27.71200),  # East grazing area
    'grazing_south': (-26.72100, 27.70950),  # South grazing area
}

# BLE simulation
BLE_TX_POWER = -59
BLE_PATH_LOSS_N = 2.2
BLE_MAX_RANGE_M = 100
BLE_NOISE_DB = 4


# ─── Simulated Entities ──────────────────────────────────────────────────────

@dataclass
class Cow:
    """A cow with a BLE ear tag."""
    name: str
    mac: str
    lat: float
    lon: float

    def move_towards(self, target_lat: float, target_lon: float, speed_mps: float, dt: float):
        """Move towards target at given speed."""
        dy = (target_lat - self.lat) * 111320.0
        dx = (target_lon - self.lon) * 111320.0 * math.cos(math.radians(self.lat))
        dist = math.sqrt(dx * dx + dy * dy)
        if dist < 2:
            return
        move_dist = min(speed_mps * dt, dist)
        ratio = move_dist / dist
        self.lat += (target_lat - self.lat) * ratio
        self.lon += (target_lon - self.lon) * ratio
        # Add wander
        self.lat += random.gauss(0, 0.00001)
        self.lon += random.gauss(0, 0.00001)

    def graze(self, dt: float):
        """Random slow grazing movement."""
        speed = random.uniform(0.1, 0.5)  # m/s
        heading = random.uniform(0, 360)
        dist = speed * dt
        dlat = (dist * math.cos(math.radians(heading))) / 111320.0
        dlon = (dist * math.sin(math.radians(heading))) / (111320.0 * math.cos(math.radians(self.lat)))
        self.lat += dlat
        self.lon += dlon


@dataclass
class Herdsman:
    """The herdsman carrying the gateway phone."""
    lat: float
    lon: float
    battery: float = 100.0
    speed_kmh: float = 0.0

    def move_towards(self, target_lat: float, target_lon: float, speed_mps: float, dt: float):
        """Walk towards a target."""
        dy = (target_lat - self.lat) * 111320.0
        dx = (target_lon - self.lon) * 111320.0 * math.cos(math.radians(self.lat))
        dist = math.sqrt(dx * dx + dy * dy)
        if dist < 3:
            self.speed_kmh = 0
            return True  # Arrived
        move_dist = min(speed_mps * dt, dist)
        ratio = move_dist / dist
        self.lat += (target_lat - self.lat) * ratio
        self.lon += (target_lon - self.lon) * ratio
        self.speed_kmh = speed_mps * 3.6
        self.battery -= random.uniform(0.001, 0.005)
        return False  # Still moving


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


def generate_mac():
    return ':'.join(f'{random.randint(0, 255):02X}' for _ in range(6))


def send_batch(api_url, gateway_serial, herdsman, sightings, session_id=None):
    payload = {
        "gateway_serial": gateway_serial,
        "latitude": herdsman.lat,
        "longitude": herdsman.lon,
        "speed": herdsman.speed_kmh,
        "battery_pct": int(herdsman.battery),
        "session_id": session_id,
        "sightings": sightings,
    }
    try:
        resp = requests.post(f"{api_url}/api/gateway/batch", json=payload, timeout=10)
        return resp.json() if resp.status_code == 200 else None
    except Exception:
        return None


# ─── Daily Routine Phases ─────────────────────────────────────────────────────

def phase_in_kraal(herdsman, cows, duration_sim_sec, dt, **kw):
    """Cattle in kraal, herdsman nearby. All animals detectable."""
    kraal = LOCATIONS['kraal']
    for cow in cows:
        cow.lat = kraal[0] + random.uniform(-0.0002, 0.0002)
        cow.lon = kraal[1] + random.uniform(-0.0002, 0.0002)
    herdsman.lat = LOCATIONS['house'][0]
    herdsman.lon = LOCATIONS['house'][1]
    herdsman.speed_kmh = 0


def phase_move_to_grazing(herdsman, cows, target_key, dt, **kw):
    """Herdsman and cows walk to grazing area."""
    target = LOCATIONS[target_key]
    herdsman.move_towards(target[0], target[1], 1.2, dt)  # ~4.3 km/h
    for cow in cows:
        # Cows follow herdsman loosely
        cow.move_towards(
            herdsman.lat + random.uniform(-0.0003, 0.0003),
            herdsman.lon + random.uniform(-0.0003, 0.0003),
            random.uniform(0.8, 1.5), dt
        )


def phase_grazing(herdsman, cows, center_key, dt, **kw):
    """Cows graze, herdsman walks slowly among them."""
    center = LOCATIONS[center_key]
    # Herdsman wanders slowly
    herdsman.lat += random.gauss(0, 0.00002)
    herdsman.lon += random.gauss(0, 0.00002)
    herdsman.speed_kmh = random.uniform(1.0, 3.0)
    # Cows graze
    for cow in cows:
        cow.graze(dt)


# ─── Main Simulation ─────────────────────────────────────────────────────────

@click.command()
@click.option('--api-url', default='http://localhost:8000', help='API base URL')
@click.option('--gateway-serial', default='GW-LV-001', help='Gateway serial')
@click.option('--animals', default=10, help='Number of cattle')
@click.option('--speed', default=120, help='Simulation speed multiplier (120 = 12h in 6min)')
@click.option('--offline', is_flag=True, help='No API calls, print only')
@click.option('--scan-interval', default=5, help='BLE scan interval (real seconds)')
@click.option('--report-interval', default=30, help='API batch interval (real seconds)')
def main(api_url, gateway_serial, animals, speed, offline, scan_interval, report_interval):
    """
    Simulate a full herdsman day at Loch Vaal Plot 30.

    The day runs at accelerated speed (default 120x = 12 hours in 6 minutes).
    BLE sightings are sent to the API every 30 real seconds.
    """
    print(f"LivestockGuard — Herdsman Daily Routine Simulator")
    print(f"{'─' * 55}")
    print(f"Farm:      Loch Vaal Plot 30 (-26.719088, 27.709759)")
    print(f"Gateway:   {gateway_serial}")
    print(f"Cattle:    {animals}")
    print(f"Speed:     {speed}x (12h day in {12*3600/speed/60:.0f} minutes)")
    print(f"API:       {'OFFLINE' if offline else api_url}")
    print(f"{'─' * 55}")
    print()

    # Create cattle with BLE ear tags
    cows = []
    kraal = LOCATIONS['kraal']
    for i in range(animals):
        mac = generate_mac()
        cows.append(Cow(
            name=f"LV-{i+1:03d}",
            mac=mac,
            lat=kraal[0] + random.uniform(-0.0002, 0.0002),
            lon=kraal[1] + random.uniform(-0.0002, 0.0002),
        ))

    # Herdsman starts at house
    herdsman = Herdsman(lat=LOCATIONS['house'][0], lon=LOCATIONS['house'][1])

    # Day schedule (sim_hour, phase_name, params)
    schedule = [
        (5.0,  'kraal',         'In kraal (night)'),
        (6.0,  'move_north',    'Walking to north grazing'),
        (6.5,  'graze_north',   'Morning grazing (north)'),
        (9.0,  'move_water',    'Walking to water point'),
        (9.5,  'graze_water',   'Resting near water'),
        (11.0, 'move_east',     'Walking to east grazing'),
        (11.5, 'graze_east',    'Afternoon grazing (east)'),
        (15.0, 'move_south',    'Walking to south grazing'),
        (15.5, 'graze_south',   'Late afternoon grazing (south)'),
        (17.0, 'move_kraal',    'Returning to kraal'),
        (17.5, 'kraal_evening', 'Cattle in kraal (evening)'),
    ]

    # Simulation loop
    sim_time = 5.0 * 3600  # Start at 05:00 (in seconds)
    end_time = 18.0 * 3600  # End at 18:00
    real_dt = scan_interval  # Real seconds per tick
    sim_dt = real_dt * speed  # Simulated seconds per tick

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
                "latitude": herdsman.lat,
                "longitude": herdsman.lon,
                "herdsman_name": "Teboho Mpeki",
            }, timeout=5)
            if resp.status_code == 201:
                session_id = resp.json().get("session_id")
                print(f"  Session started: {session_id[:8]}...")
        except Exception:
            pass

    print(f"\n  {'Time':<6} {'Phase':<30} {'Cows in range':<15} {'Herdsman pos'}")
    print(f"  {'─'*6} {'─'*30} {'─'*15} {'─'*25}")

    try:
        while sim_time < end_time:
            sim_hour = sim_time / 3600.0

            # Determine current phase
            for i, (start_hour, _, _) in enumerate(schedule):
                if sim_hour >= start_hour:
                    current_phase_idx = i

            phase_key = schedule[current_phase_idx][1]
            phase_label = schedule[current_phase_idx][2]

            # Execute phase logic
            if phase_key == 'kraal' or phase_key == 'kraal_evening':
                phase_in_kraal(herdsman, cows, sim_dt, sim_dt)
            elif phase_key == 'move_north':
                phase_move_to_grazing(herdsman, cows, 'grazing_north', sim_dt)
            elif phase_key == 'graze_north':
                phase_grazing(herdsman, cows, 'grazing_north', sim_dt)
            elif phase_key == 'move_water':
                phase_move_to_grazing(herdsman, cows, 'water_point', sim_dt)
            elif phase_key == 'graze_water':
                phase_grazing(herdsman, cows, 'water_point', sim_dt)
            elif phase_key == 'move_east':
                phase_move_to_grazing(herdsman, cows, 'grazing_east', sim_dt)
            elif phase_key == 'graze_east':
                phase_grazing(herdsman, cows, 'grazing_east', sim_dt)
            elif phase_key == 'move_south':
                phase_move_to_grazing(herdsman, cows, 'grazing_south', sim_dt)
            elif phase_key == 'graze_south':
                phase_grazing(herdsman, cows, 'grazing_south', sim_dt)
            elif phase_key == 'move_kraal':
                phase_move_to_grazing(herdsman, cows, 'kraal', sim_dt)

            # BLE scan
            detected = 0
            for cow in cows:
                dist = distance_m(herdsman.lat, herdsman.lon, cow.lat, cow.lon)
                if dist <= BLE_MAX_RANGE_M:
                    rssi = rssi_from_distance(dist)
                    batch_buffer.append({
                        "mac_address": cow.mac,
                        "rssi": rssi,
                    })
                    detected += 1

            total_sightings += detected

            # Print status
            h = int(sim_hour)
            m = int((sim_hour - h) * 60)
            print(f"  {h:02d}:{m:02d}  {phase_label:<30} {detected:>2}/{animals:<12} "
                  f"({herdsman.lat:.5f}, {herdsman.lon:.5f})")

            # Send batch to API at intervals
            now = time.time()
            if now - last_report >= report_interval and batch_buffer:
                if not offline:
                    result = send_batch(api_url, gateway_serial, herdsman, batch_buffer, session_id)
                    if result:
                        print(f"        → API: {result['accepted']} accepted, "
                              f"{result['resolved']} resolved")
                else:
                    print(f"        → [OFFLINE] {len(batch_buffer)} sightings buffered")
                batch_buffer = []
                last_report = now

            # Advance time
            sim_time += sim_dt
            time.sleep(real_dt)

    except KeyboardInterrupt:
        print("\n\nSimulation stopped by user")

    # End session
    if session_id and not offline:
        try:
            requests.post(f"{api_url}/api/gateway/sessions/{session_id}/end", json={
                "latitude": herdsman.lat,
                "longitude": herdsman.lon,
            }, timeout=5)
        except Exception:
            pass

    print(f"\n{'─' * 55}")
    print(f"Day complete:")
    print(f"  Total BLE detections: {total_sightings}")
    print(f"  Herdsman battery:     {herdsman.battery:.0f}%")
    print(f"  Final position:       ({herdsman.lat:.5f}, {herdsman.lon:.5f})")


if __name__ == '__main__':
    main()
