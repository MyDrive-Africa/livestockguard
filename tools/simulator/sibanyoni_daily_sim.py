#!/usr/bin/env python3
"""
LivestockGuard — Herdsman Daily Routine Simulator (Sibanyoni Farm, North West)

Realistic cattle movement for 50 head on a 50-hectare farm near Lichtenburg.
Cattle form natural sub-groups (clusters), with leaders, followers, and stragglers.
Herd spreads asymmetrically — not a uniform circle around the herdsman.

Schedule (configurable):
  Night:  Cattle in kraal
  06:00:  Kraal gate opens → cattle move to water/feeding troughs
  06:30-07:00: Feeding/watering at troughs (inside yard)
  07:00-07:30: Walk to main gate, exit property
  07:30+: Herdsman leads herd along road to communal grazing
  12:00-13:00: Midday rest under trees
  13:00-16:00: Afternoon grazing
  16:00: Return via road back to main gate
  16:30-17:00: Enter property, water stop
  17:00-17:30: Walk to kraal, settle for night
  17:30: All in kraal

Herd dynamics:
  - Cattle split into 4-6 sub-groups of varying size
  - Each sub-group has a "lead cow" others follow loosely
  - Sub-groups graze at different distances/directions from herdsman
  - Some cows are stragglers (slow, lag behind)
  - Clusters drift and reform over time
  - All cattle kept within 50-hectare boundary during on-farm phases

Usage:
    python sibanyoni_daily_sim.py                     # Normal day
    python sibanyoni_daily_sim.py --scenario theft    # Theft at 10am
    python sibanyoni_daily_sim.py --scenario breach   # Cow exits range
    python sibanyoni_daily_sim.py --speed 360         # 12h in 2min
    python sibanyoni_daily_sim.py --offline           # No API calls
"""

import time
import math
import random
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import click
import requests


# ─── Farm Layout (Sibanyoni Farm, North West) ─────────────────────────────────
# Centre: -25.3580560, 25.3612750
# 50 hectares (~707m x 707m)
# Property boundary: lat -25.35486 to -25.36125, lon 25.35774 to 25.36481

# Kraal (night enclosure, ~60m x 50m, northern part of property)
KRAAL_CENTER = (-25.35805, 25.36127)
KRAAL_RADIUS_M = 25

# Feeding area / water troughs (east of kraal, inside yard)
FEEDING_AREA = (-25.35810, 25.36200)
FEEDING_RADIUS_M = 30

# Property boundary (50ha)
PROPERTY_BOUNDS = {
    'min_lat': -25.36125, 'max_lat': -25.35486,
    'min_lon': 25.35774, 'max_lon': 25.36481,
}

# Main gate (south-east corner — access road)
GATE_POSITION = (-25.36050, 25.36400)

# Road waypoints from gate to communal grazing (following actual road network)
ROAD_FROM_GATE = [
    (-25.36100, 25.36480),   # Just outside gate on dirt road
    (-25.36200, 25.36550),   # Road heading south-east
    (-25.36350, 25.36600),   # Road bend
]

# Grazing areas (communal land around the farm, reached via roads)
GRAZING_AREAS = [
    {
        'name': 'North communal veld (past neighbour)',
        'waypoints': [(-25.36100, 25.36480), (-25.35800, 25.36550), (-25.35500, 25.36500)],
        'center': (-25.35400, 25.36450),
        'spread_m': 200,
    },
    {
        'name': 'East riverside (along stream)',
        'waypoints': [(-25.36100, 25.36480), (-25.36150, 25.36700), (-25.36100, 25.36900)],
        'center': (-25.36050, 25.37000),
        'spread_m': 180,
    },
    {
        'name': 'South pasture (communal grazing)',
        'waypoints': [(-25.36200, 25.36550), (-25.36400, 25.36600), (-25.36600, 25.36550)],
        'center': (-25.36700, 25.36500),
        'spread_m': 250,
    },
    {
        'name': 'West bushveld (along fence line)',
        'waypoints': [(-25.36100, 25.36480), (-25.36050, 25.36300), (-25.36000, 25.36100)],
        'center': (-25.35950, 25.35900),
        'spread_m': 160,
    },
]

# BLE parameters
BLE_TX_POWER = -59
BLE_PATH_LOSS_N = 2.2
BLE_MAX_RANGE_M = 100
BLE_NOISE_DB = 4

# Registered MACs (match seed_data.sql — 50 tags for Sibanyoni)
REGISTERED_MACS = [f'B1:C2:D3:E4:F5:{i:02d}' for i in range(1, 51)]


# ─── Herd Dynamics ────────────────────────────────────────────────────────────

@dataclass
class SubGroup:
    """A cluster of cattle that move together loosely."""
    group_id: int
    leader_idx: int                # Index of the lead cow in this group
    member_indices: List[int]      # Indices into main cows list
    offset_heading: float          # Direction offset from herdsman (degrees)
    offset_distance_m: float       # How far this cluster drifts from herdsman
    cohesion: float                # How tightly members stick together (0.3-0.9)
    drift_speed: float             # How fast the group centre drifts (m/s)
    # Live state
    anchor_lat: float = 0.0
    anchor_lon: float = 0.0

    def update_anchor(self, herdsman_lat: float, herdsman_lon: float):
        """Update the sub-group's anchor point relative to herdsman."""
        # Slowly drift the offset heading (wind, grass, terrain)
        self.offset_heading += random.gauss(0, 2.0)
        self.offset_heading %= 360
        # Vary the distance slightly
        self.offset_distance_m += random.gauss(0, 3.0)
        self.offset_distance_m = max(10, min(self.offset_distance_m, 300))

        bearing_rad = math.radians(self.offset_heading)
        dlat = (self.offset_distance_m * math.cos(bearing_rad)) / 111320.0
        dlon = (self.offset_distance_m * math.sin(bearing_rad)) / (
            111320.0 * math.cos(math.radians(herdsman_lat)))
        self.anchor_lat = herdsman_lat + dlat
        self.anchor_lon = herdsman_lon + dlon


def create_sub_groups(num_animals: int, num_groups: int = 5) -> List[SubGroup]:
    """Split cattle into asymmetric sub-groups with varied sizes."""
    indices = list(range(num_animals))
    random.shuffle(indices)

    # Assign groups with non-uniform sizes (some groups larger than others)
    group_sizes = []
    remaining = num_animals
    for g in range(num_groups - 1):
        # Each group gets between 15% and 35% of remaining
        size = max(2, int(remaining * random.uniform(0.15, 0.35)))
        size = min(size, remaining - (num_groups - g - 1))
        group_sizes.append(size)
        remaining -= size
    group_sizes.append(remaining)  # Last group gets the rest

    groups = []
    offset = 0
    for g_id, size in enumerate(group_sizes):
        members = indices[offset:offset + size]
        leader = members[0]  # First member is leader
        # Spread groups in different directions, not evenly spaced
        heading = random.uniform(0, 360)
        distance = random.uniform(20, 180)
        cohesion = random.uniform(0.3, 0.85)

        groups.append(SubGroup(
            group_id=g_id,
            leader_idx=leader,
            member_indices=members,
            offset_heading=heading,
            offset_distance_m=distance,
            cohesion=cohesion,
            drift_speed=random.uniform(0.02, 0.12),
        ))
        offset += size

    return groups


# ─── Entities ─────────────────────────────────────────────────────────────────

@dataclass
class Cow:
    name: str
    mac: str
    lat: float
    lon: float
    # Personality traits (set once at creation)
    is_straggler: bool = False    # Slow, lags behind
    wander_factor: float = 1.0   # How much this cow wanders (0.5-2.0)
    speed_factor: float = 1.0    # Individual speed multiplier
    # Movement state
    heading: float = 0.0         # Current heading (degrees)
    _heading_inertia: float = 0.0

    def move_towards(self, target_lat, target_lon, speed_mps, dt):
        dy = (target_lat - self.lat) * 111320.0
        dx = (target_lon - self.lon) * 111320.0 * math.cos(math.radians(self.lat))
        dist = math.sqrt(dx * dx + dy * dy)
        if dist < 2:
            return True
        # Stragglers move at 60-80% speed
        actual_speed = speed_mps * self.speed_factor
        if self.is_straggler:
            actual_speed *= random.uniform(0.6, 0.8)
        move_dist = min(actual_speed * dt, dist)
        ratio = move_dist / dist
        self.lat += (target_lat - self.lat) * ratio
        self.lon += (target_lon - self.lon) * ratio
        # Add natural wandering noise (varies by cow personality)
        noise = 0.000006 * self.wander_factor
        self.lat += random.gauss(0, noise)
        self.lon += random.gauss(0, noise)
        return False

    def graze(self, dt, anchor_lat=None, anchor_lon=None, spread_m=80):
        """Slow random movement simulating grazing behaviour with drift towards anchor."""
        speed = random.uniform(0.05, 0.3) * self.wander_factor
        # Bias heading towards anchor if drifted too far
        if anchor_lat is not None:
            dx = (anchor_lon - self.lon) * 111320.0 * math.cos(math.radians(self.lat))
            dy = (anchor_lat - self.lat) * 111320.0
            dist_to_anchor = math.sqrt(dx * dx + dy * dy)
            if dist_to_anchor > spread_m * 0.7:
                # Pull back towards anchor
                pull_heading = math.degrees(math.atan2(dx, dy))
                self._heading_inertia = pull_heading + random.gauss(0, 25)
            else:
                self._heading_inertia += random.gauss(0, 40)
        else:
            self._heading_inertia += random.gauss(0, 45)

        self.heading = self._heading_inertia % 360
        dist = speed * dt
        self.lat += (dist * math.cos(math.radians(self.heading))) / 111320.0
        self.lon += (dist * math.sin(math.radians(self.heading))) / (
            111320.0 * math.cos(math.radians(self.lat)))

    def random_in_kraal(self):
        angle = random.uniform(0, 2 * math.pi)
        r = random.uniform(0, KRAAL_RADIUS_M)
        self.lat = KRAAL_CENTER[0] + (r * math.cos(angle)) / 111320.0
        self.lon = KRAAL_CENTER[1] + (r * math.sin(angle)) / (
            111320.0 * math.cos(math.radians(KRAAL_CENTER[0])))

    def random_near(self, center, radius_m):
        angle = random.uniform(0, 2 * math.pi)
        r = random.uniform(0, radius_m)
        self.lat = center[0] + (r * math.cos(angle)) / 111320.0
        self.lon = center[1] + (r * math.sin(angle)) / (
            111320.0 * math.cos(math.radians(center[0])))


def clamp_to_property(cow: Cow):
    """Keep cow within the 50-hectare property boundary (soft bounce)."""
    margin = 0.00005  # ~5m inside fence
    clamped = False
    if cow.lat < PROPERTY_BOUNDS['min_lat'] + margin:
        cow.lat = PROPERTY_BOUNDS['min_lat'] + margin + random.uniform(0, 0.00008)
        cow._heading_inertia = random.uniform(330, 390) % 360  # Push north
        clamped = True
    elif cow.lat > PROPERTY_BOUNDS['max_lat'] - margin:
        cow.lat = PROPERTY_BOUNDS['max_lat'] - margin - random.uniform(0, 0.00008)
        cow._heading_inertia = random.uniform(150, 210)  # Push south
        clamped = True
    if cow.lon < PROPERTY_BOUNDS['min_lon'] + margin:
        cow.lon = PROPERTY_BOUNDS['min_lon'] + margin + random.uniform(0, 0.00008)
        cow._heading_inertia = random.uniform(60, 120)  # Push east
        clamped = True
    elif cow.lon > PROPERTY_BOUNDS['max_lon'] - margin:
        cow.lon = PROPERTY_BOUNDS['max_lon'] - margin - random.uniform(0, 0.00008)
        cow._heading_inertia = random.uniform(240, 300)  # Push west
        clamped = True
    return clamped


def is_on_property(lat: float, lon: float) -> bool:
    """Check if a position is within farm boundary."""
    return (PROPERTY_BOUNDS['min_lat'] <= lat <= PROPERTY_BOUNDS['max_lat'] and
            PROPERTY_BOUNDS['min_lon'] <= lon <= PROPERTY_BOUNDS['max_lon'])


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
    if dist < 0.5:
        dist = 0.5
    rssi = BLE_TX_POWER - 10 * BLE_PATH_LOSS_N * math.log10(dist)
    rssi += random.gauss(0, BLE_NOISE_DB)
    return max(-120, min(-30, int(rssi)))


def herd_spread_position(herdsman_lat, herdsman_lon, group: SubGroup,
                         cow_idx_in_group: int, total_in_group: int) -> Tuple[float, float]:
    """
    Generate a target position for a cow within its sub-group.
    Cows closer to the front of the group list are closer to the leader.
    Creates a natural elongated, asymmetric cluster rather than a circle.
    """
    # Position relative to group anchor
    group_spread = 15 + (cow_idx_in_group / max(1, total_in_group)) * 35  # 15-50m from anchor
    # Non-uniform angle — elongated along the group's drift direction
    base_angle = math.radians(group.offset_heading)
    # Elongate: stretch along heading axis
    along = random.gauss(0, group_spread * 0.6)
    across = random.gauss(0, group_spread * 0.3)
    dlat = (along * math.cos(base_angle) + across * math.sin(base_angle)) / 111320.0
    dlon = (along * math.sin(base_angle) - across * math.cos(base_angle)) / (
        111320.0 * math.cos(math.radians(herdsman_lat)))
    return (group.anchor_lat + dlat, group.anchor_lon + dlon)


def send_batch(api_url, gateway_serial, herdsman, sightings, session_id=None):
    if not sightings:
        return None
    total_accepted = 0
    total_resolved = 0
    # Send in smaller batches (10 per request to avoid overload)
    chunk_size = 10
    for i in range(0, len(sightings), chunk_size):
        chunk = sightings[i:i+chunk_size]
        payload = {
            "gateway_serial": gateway_serial,
            "latitude": herdsman.lat,
            "longitude": herdsman.lon,
            "speed": herdsman.speed_kmh,
            "battery_pct": int(herdsman.battery),
            "session_id": session_id,
            "sightings": [
                {
                    "mac_address": s["mac_address"],
                    "rssi": s["rssi"],
                    "latitude": s.get("_lat"),
                    "longitude": s.get("_lon"),
                }
                for s in chunk
            ],
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
@click.option('--gateway-serial', default='GW-SB-001')
@click.option('--animals', default=50)
@click.option('--speed', default=120, help='Time multiplier (120=12h in 6min, 360=12h in 2min)')
@click.option('--scenario', default='normal', type=click.Choice(['normal', 'theft', 'breach']))
@click.option('--offline', is_flag=True)
@click.option('--scan-interval', default=5, help='Real seconds per tick')
@click.option('--report-interval', default=20, help='Real seconds between API batches')
@click.option('--kraal-open', default=6.0, help='Hour kraal gate opens (6.0=06:00)')
@click.option('--exit-time', default=7.0, help='Hour cattle exit main gate (7.0=07:00)')
@click.option('--return-time', default=16.0, help='Hour cattle start returning (16.0=16:00)')
@click.option('--settle-time', default=17.5, help='Hour cattle settled in kraal (17.5=17:30)')
def main(api_url, gateway_serial, animals, speed, scenario, offline,
         scan_interval, report_interval, kraal_open, exit_time, return_time, settle_time):
    """Simulate a realistic herdsman day at Sibanyoni Farm (North West)."""

    animals = min(animals, len(REGISTERED_MACS))

    print(f"LivestockGuard — Sibanyoni Farm Daily Simulator")
    print(f"{'═' * 60}")
    print(f"Farm:        Sibanyoni Farm (-25.358056, 25.361275)")
    print(f"Province:    North West (near Lichtenburg)")
    print(f"Area:        50 hectares")
    print(f"Gateway:     {gateway_serial}")
    print(f"Herdsman:    Sibanyoni Herdsman")
    print(f"Cattle:      {animals}")
    print(f"Scenario:    {scenario}")
    print(f"Schedule:    Kraal open {kraal_open:.1f}h, Exit {exit_time:.1f}h, Return {return_time:.1f}h, Settle {settle_time:.1f}h")
    print(f"Speed:       {speed}x")
    print(f"API:         {'OFFLINE' if offline else api_url}")
    print(f"{'═' * 60}\n")

    # Create cattle (all start in kraal)
    cows = []
    for i in range(animals):
        cow = Cow(name=f"SB-{i+1:03d}", mac=REGISTERED_MACS[i], lat=0, lon=0)
        cow.random_in_kraal()
        cows.append(cow)

    # Herdsman starts near kraal
    herdsman = Herdsman(lat=KRAAL_CENTER[0] + 0.0002, lon=KRAAL_CENTER[1] - 0.0003)

    # Pick today's grazing area
    todays_grazing = random.choice(GRAZING_AREAS)
    grazing_waypoints = todays_grazing['waypoints']
    grazing_center = todays_grazing['center']
    return_waypoints = list(reversed(grazing_waypoints)) + [GATE_POSITION]

    print(f"  Grazing:   {todays_grazing['name']}")
    print(f"  Route:     {len(grazing_waypoints)} waypoints (following roads)")
    print(f"  Overnight: Kraal\n")

    # Schedule phases
    schedule = [
        (4.0,          'night',        "Cattle in kraal (night)"),
        (kraal_open,   'feeding',      "Kraal open → feeding/watering at troughs"),
        (exit_time,    'to_gate',      "Walking to main gate"),
        (exit_time+0.3,'exit_road',    "Following road to grazing area"),
        (exit_time+1.0,'grazing',      f"Grazing: {todays_grazing['name']}"),
        (12.0,         'rest',         "Midday rest (shade under trees)"),
        (13.0,         'grazing2',     "Afternoon grazing"),
        (return_time,  'return_road',  "Returning via road to gate"),
        (return_time+0.5,'enter_gate', "Entering through main gate"),
        (return_time+0.7,'water_stop', "Water stop at troughs"),
        (settle_time,  'to_kraal',     "Walking to kraal"),
        (settle_time+0.25,'night_end', "Settled for night"),
    ]

    # Simulation loop
    sim_time = 4.0 * 3600
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
                "herdsman_name": "Sibanyoni Herdsman",
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

            # Determine current phase
            for i, (start_h, _, _) in enumerate(schedule):
                if sim_hour >= start_h:
                    current_phase_idx = i
            phase_key = schedule[current_phase_idx][1]
            phase_label = schedule[current_phase_idx][2]

            # ── Phase logic ──
            if phase_key in ('night', 'night_end'):
                herdsman.speed_kmh = 0

            elif phase_key == 'feeding':
                for cow in cows:
                    cow.move_towards(
                        FEEDING_AREA[0] + random.uniform(-0.00020, 0.00020),
                        FEEDING_AREA[1] + random.uniform(-0.00020, 0.00020),
                        0.4, sim_dt)
                herdsman.move_towards(FEEDING_AREA[0], FEEDING_AREA[1], 0.8, sim_dt)

            elif phase_key == 'to_gate':
                for cow in cows:
                    cow.move_towards(GATE_POSITION[0], GATE_POSITION[1], 0.7, sim_dt)
                herdsman.move_towards(GATE_POSITION[0], GATE_POSITION[1], 1.0, sim_dt)

            elif phase_key == 'exit_road':
                if not herdsman_on_road:
                    herdsman.waypoint_idx = 0
                    herdsman_on_road = True
                herdsman.follow_waypoints(grazing_waypoints, 1.3, sim_dt)
                for cow in cows:
                    cow.move_towards(
                        herdsman.lat + random.uniform(-0.0004, 0.0004),
                        herdsman.lon + random.uniform(-0.0004, 0.0004),
                        random.uniform(0.9, 1.3), sim_dt)

            elif phase_key in ('grazing', 'grazing2'):
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
                if herdsman_on_road:
                    herdsman.waypoint_idx = 0
                    herdsman_on_road = False
                herdsman.follow_waypoints(return_waypoints, 1.3, sim_dt)
                for cow in cows:
                    cow.move_towards(
                        herdsman.lat + random.uniform(-0.0003, 0.0003),
                        herdsman.lon + random.uniform(-0.0003, 0.0003),
                        random.uniform(0.9, 1.2), sim_dt)

            elif phase_key == 'enter_gate':
                for cow in cows:
                    cow.move_towards(GATE_POSITION[0], GATE_POSITION[1], 0.8, sim_dt)
                herdsman.move_towards(GATE_POSITION[0], GATE_POSITION[1], 1.0, sim_dt)

            elif phase_key == 'water_stop':
                for cow in cows:
                    cow.move_towards(
                        FEEDING_AREA[0] + random.uniform(-0.00015, 0.00015),
                        FEEDING_AREA[1] + random.uniform(-0.00015, 0.00015),
                        0.5, sim_dt)
                herdsman.move_towards(FEEDING_AREA[0], FEEDING_AREA[1], 0.8, sim_dt)

            elif phase_key == 'to_kraal':
                for cow in cows:
                    cow.move_towards(KRAAL_CENTER[0], KRAAL_CENTER[1], 0.6, sim_dt)
                herdsman.move_towards(KRAAL_CENTER[0], KRAAL_CENTER[1], 0.8, sim_dt)

            # ── Scenario overrides ──
            if scenario == 'theft' and sim_hour >= 10.0:
                # First 2 cows stolen (driven away quickly)
                for stolen in cows[:2]:
                    stolen.lat -= 0.0015 * (sim_dt / 60)
                    stolen.lon += 0.001 * (sim_dt / 60)
                if 10.0 <= sim_hour < 10.05:
                    print(f"  {'':6} 🚨 THEFT: {cows[0].name} & {cows[1].name} taken at speed!")

            elif scenario == 'breach' and sim_hour >= 11.0:
                # One cow wanders outside property boundary
                breach_cow = cows[0]
                breach_cow.lat += 0.0005 * (sim_dt / 60)
                breach_cow.lon -= 0.0003 * (sim_dt / 60)
                if 11.0 <= sim_hour < 11.05:
                    print(f"  {'':6} ⚠️  BREACH: {breach_cow.name} leaving property boundary!")

            # ── BLE scan (herdsman detects nearby cattle) ──
            detected = 0
            for cow in cows:
                dist = distance_m(herdsman.lat, herdsman.lon, cow.lat, cow.lon)
                if dist <= BLE_MAX_RANGE_M:
                    rssi = rssi_from_distance(dist)
                    # Use the cow's actual position with slight GPS-like noise
                    # This gives each cow a unique, realistic location on the map
                    gps_noise_lat = random.gauss(0, 0.000015)  # ~1.7m noise
                    gps_noise_lon = random.gauss(0, 0.000015)
                    batch_buffer.append({
                        "mac_address": cow.mac,
                        "rssi": rssi,
                        "_lat": cow.lat + gps_noise_lat,
                        "_lon": cow.lon + gps_noise_lon,
                    })
                    detected += 1
            total_sightings += detected

            print(f"  {h:02d}:{m:02d}  {phase_label:<40} {detected:>2}/{animals:<4} "
                  f"({herdsman.lat:.5f}, {herdsman.lon:.5f})")

            # Send batch to API
            now = time.time()
            if now - last_report >= report_interval and batch_buffer:
                if not offline:
                    result = send_batch(api_url, gateway_serial, herdsman, batch_buffer, session_id)
                    if result:
                        print(f"  {'':6} → API: {result['accepted']} accepted, {result['resolved']} resolved")
                else:
                    print(f"  {'':6} → [OFFLINE] {len(batch_buffer)} sightings buffered")
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
    print(f"Day complete (Sibanyoni Farm):")
    print(f"  Total BLE detections: {total_sightings}")
    print(f"  Battery remaining:    {herdsman.battery:.0f}%")
    print(f"  Final position:       Kraal")
    print(f"  Route taken:          {todays_grazing['name']}")
    print(f"  Cattle:               {animals} head")


if __name__ == '__main__':
    main()
