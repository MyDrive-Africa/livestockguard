"""
LivestockGuard Beam Sensor Simulator

Simulates fixed perimeter break-beam sensors mounted at chokepoints along a
farm border (gates, fence gaps, drainage lines). Each beam guards a crossing
line; when something passes through, the beam breaks and posts a crossing
event to the API, which stores it and fires an alert through the existing
Redis / Alert Engine pipeline (dashboard live update + push/SMS/email).

This is the interim "border sentinel" layer over the virtual geofence while a
physical fence/wall is built. For the 50ha Sibanyoni border, the simulator lays
out beams around the perimeter square so you can see the guarded-span concept.

Usage:
    python beam_simulator.py --farm sibanyoni --beams 5
    python beam_simulator.py --farm sibanyoni --beams 5 --scenario theft
    python beam_simulator.py --farm lochvaal --beams 3 --seed 42 --offline

Behaviour:
    1. Registers N beam sensors around the farm border (idempotent — 409s are OK).
    2. Every --interval seconds, fires occasional random crossings (livestock,
       wildlife, false triggers).
    3. --scenario theft: at ~1/3 through the run, a burst of crossings fires at
       one gate beam (someone moving stock out) — a high/critical alert cluster.
"""

import math
import random
import time
from datetime import datetime, timezone
from typing import List, Optional

import click
import requests


# ─── Configuration ────────────────────────────────────────────────────────────

FARM_PRESETS = {
    'boschhoek': {
        'lat': -29.12, 'lon': 26.21,
        'name': 'Boschhoek Farm (Free State)',
        'beam_prefix': 'BEAM-BH',
        'farm_id': 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
        'area_hectares': 20,
    },
    'lochvaal': {
        'lat': -26.719088, 'lon': 27.709759,
        'name': 'Loch Vaal Plot 30 (Gauteng)',
        'beam_prefix': 'BEAM-LV',
        'farm_id': 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
        'area_hectares': 8,
    },
    'sibanyoni': {
        'lat': -25.3580560, 'lon': 25.3612750,
        'name': 'Sibanyoni Farm (North West)',
        'beam_prefix': 'BEAM-SB',
        'farm_id': 'dddddddd-1111-2222-3333-555555555555',
        'area_hectares': 50,
    },
}

# Descriptive names for the first few beams (chokepoints), then generic.
CHOKEPOINT_NAMES = [
    "Main Gate Beam",
    "Loading Ramp Beam",
    "Kraal Entrance Beam",
    "North Fence Gap",
    "Drainage Line Beam",
    "East Fence Gap",
    "South Fence Gap",
    "West Fence Gap",
]

BEAM_SPAN_M = 6.0  # Typical gate/gap width the beam spans


# ─── Geometry helpers ──────────────────────────────────────────────────────────

def offset_point(lat: float, lon: float, dnorth_m: float, deast_m: float):
    """Offset a lat/lon by metres north/east."""
    dlat = dnorth_m / 111320.0
    dlon = deast_m / (111320.0 * math.cos(math.radians(lat)))
    return lat + dlat, lon + dlon


def perimeter_positions(center_lat: float, center_lon: float,
                        area_hectares: float, count: int) -> List[dict]:
    """Place `count` beams evenly around a square perimeter sized for the farm.

    A `area_hectares` square has side = sqrt(area_m2). Beams are distributed
    around that square boundary — the points a physical fence would follow.
    """
    side_m = math.sqrt(area_hectares * 10_000.0)
    half = side_m / 2.0
    positions = []
    for i in range(count):
        # Fraction around the square perimeter (0..1).
        f = (i / count) * 4.0  # 4 sides
        side = int(f)
        t = f - side  # 0..1 along the current side
        if side == 0:      # bottom edge, west→east
            n, e = -half, -half + t * side_m
            orient = 0.0
        elif side == 1:    # right edge, south→north
            n, e = -half + t * side_m, half
            orient = 90.0
        elif side == 2:    # top edge, east→west
            n, e = half, half - t * side_m
            orient = 180.0
        else:              # left edge, north→south
            n, e = half - t * side_m, -half
            orient = 270.0

        mount_lat, mount_lon = offset_point(center_lat, center_lon, n, e)
        # Span perpendicular-ish across the gap.
        span_start_lat, span_start_lon = offset_point(mount_lat, mount_lon, -BEAM_SPAN_M / 2, 0)
        span_end_lat, span_end_lon = offset_point(mount_lat, mount_lon, BEAM_SPAN_M / 2, 0)
        positions.append({
            'latitude': mount_lat,
            'longitude': mount_lon,
            'span_start_latitude': span_start_lat,
            'span_start_longitude': span_start_lon,
            'span_end_latitude': span_end_lat,
            'span_end_longitude': span_end_lon,
            'orientation_deg': orient,
            'span_length_m': BEAM_SPAN_M,
        })
    return positions


# ─── API client ────────────────────────────────────────────────────────────────

def register_beam(api_url: str, farm_id: str, serial: str, name: str,
                  pos: dict, severity: str) -> bool:
    """Register a beam sensor. Returns True if created or already exists."""
    payload = {
        'farm_id': farm_id,
        'serial_number': serial,
        'name': name,
        'beam_type': 'infrared',
        'breach_severity': severity,
        **pos,
    }
    try:
        resp = requests.post(f"{api_url}/api/v1/beam/register", json=payload, timeout=10)
        if resp.status_code in (201, 409):
            return True
        print(f"  ! register {serial} failed: {resp.status_code} {resp.text[:120]}")
        return False
    except Exception as e:
        print(f"  ! register {serial} error: {e}")
        return False


def send_crossing(api_url: str, serial: str, direction: str,
                  confidence: float, battery_pct: int) -> Optional[dict]:
    """Post a crossing event to the API."""
    payload = {
        'beam_serial': serial,
        'direction': direction,
        'confidence': round(confidence, 2),
        'battery_pct': battery_pct,
        'timestamp': datetime.now(timezone.utc).isoformat(),
    }
    try:
        resp = requests.post(f"{api_url}/api/v1/beam/event", json=payload, timeout=10)
        if resp.status_code == 200:
            return resp.json()
        print(f"  ! event {serial} failed: {resp.status_code} {resp.text[:120]}")
        return None
    except Exception as e:
        print(f"  ! event {serial} error: {e}")
        return None


# ─── CLI ─────────────────────────────────────────────────────────────────────

@click.command()
@click.option('--api-url', default='http://localhost:8000', help='API base URL')
@click.option('--farm', default='sibanyoni', type=click.Choice(list(FARM_PRESETS.keys())),
              help='Farm preset')
@click.option('--beams', default=5, help='Number of perimeter beam sensors')
@click.option('--severity', default='high', type=click.Choice(['critical', 'high', 'medium', 'low', 'info']),
              help='Alert severity for beam crossings')
@click.option('--interval', default=8, help='Seconds between simulation ticks')
@click.option('--duration', default=300, help='Simulation duration (seconds)')
@click.option('--scenario', default='normal', type=click.Choice(['normal', 'theft']),
              help='normal = occasional crossings; theft = crossing burst at one gate')
@click.option('--offline', is_flag=True, help='Register/print only, do not require a live API for events')
@click.option('--seed', default=None, type=int, help='Random seed for reproducible runs')
def main(api_url, farm, beams, severity, interval, duration, scenario, offline, seed):
    """LivestockGuard Beam Sensor Simulator — perimeter crossing sentinels."""
    if seed is not None:
        random.seed(seed)

    preset = FARM_PRESETS[farm]
    farm_id = preset['farm_id']
    positions = perimeter_positions(preset['lat'], preset['lon'], preset['area_hectares'], beams)

    serials = [f"{preset['beam_prefix']}-{i + 1:03d}" for i in range(beams)]
    names = [CHOKEPOINT_NAMES[i] if i < len(CHOKEPOINT_NAMES) else f"Fence Beam {i + 1}"
             for i in range(beams)]

    side_m = math.sqrt(preset['area_hectares'] * 10_000.0)
    print("LivestockGuard Beam Sensor Simulator v1.0 — Perimeter Sentinels")
    print(f"{'-' * 60}")
    print(f"Farm:       {preset['name']}")
    print(f"Border:     ~{preset['area_hectares']}ha  (~{side_m:.0f}m/side, ~{4 * side_m:.0f}m perimeter)")
    print(f"Beams:      {beams} at chokepoints")
    print(f"Severity:   {severity}")
    print(f"Scenario:   {scenario}")
    print(f"Duration:   {duration}s (tick every {interval}s)")
    print(f"Seed:       {seed if seed is not None else 'random'}")
    print(f"API:        {'OFFLINE (register/print only)' if offline else api_url}")
    print()

    # ── Register beams ──
    print("Registering perimeter beam sensors...")
    registered = 0
    for serial, name, pos in zip(serials, names, positions):
        if offline:
            print(f"  (offline) {serial:<14} {name:<20} @ {pos['latitude']:.5f},{pos['longitude']:.5f}")
            registered += 1
            continue
        if register_beam(api_url, farm_id, serial, name, pos, severity):
            print(f"  ok  {serial:<14} {name:<20} @ {pos['latitude']:.5f},{pos['longitude']:.5f}")
            registered += 1
    print(f"Registered/available: {registered}/{beams}\n")

    if offline:
        print("Offline mode — beams laid out, no crossing events sent. Done.")
        return

    # ── Fire crossings ──
    theft_at = duration // 3
    theft_beam = 0  # Main Gate
    theft_fired = False
    crossings = 0
    alerts = 0
    start = time.time()

    print("Simulating crossings (Ctrl+C to stop)...")
    try:
        while time.time() - start < duration:
            elapsed = time.time() - start

            # Theft burst: several rapid "out" crossings at the main gate.
            if scenario == 'theft' and not theft_fired and elapsed >= theft_at:
                theft_fired = True
                print(f"\n  THEFT SCENARIO: burst at {names[theft_beam]} ({serials[theft_beam]})")
                for _ in range(4):
                    res = send_crossing(api_url, serials[theft_beam], 'out',
                                        confidence=random.uniform(0.8, 0.99), battery_pct=88)
                    crossings += 1
                    if res and res.get('alert_created'):
                        alerts += 1
                        print(f"    crossing -> ALERT {res.get('alert_id')}")
                    time.sleep(1.0)
                print()

            # Occasional ambient crossing (livestock/wildlife/false trigger).
            elif random.random() < 0.4:
                idx = random.randrange(beams)
                direction = random.choice(['in', 'out', 'unknown'])
                res = send_crossing(api_url, serials[idx], direction,
                                    confidence=random.uniform(0.5, 0.95),
                                    battery_pct=random.randint(70, 100))
                crossings += 1
                tag = ''
                if res and res.get('alert_created'):
                    alerts += 1
                    tag = f" -> ALERT {res.get('alert_id')}"
                print(f"  {names[idx]:<20} {direction:<8}{tag}")

            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nStopping...")

    print(f"\nDone. crossings={crossings} alerts_created={alerts}")


if __name__ == '__main__':
    main()
