#!/usr/bin/env python3
"""
LivestockGuard Herdsman Gateway Simulator

Simulates a full daily lifecycle for a herdsman with a BLE gateway phone:

  Phase 1 — MORNING KRAAL (100% detection)
    All cattle are packed in the kraal. Gateway scans and sees every animal.

  Phase 2 — DAYTIME GRAZING (progressive detection)
    Cattle scatter to grazing areas. Herdsman patrols and progressively
    detects all animals over time as he walks between groups.

  Phase 3 — EVENING RETURN (100% detection)
    All cattle return to kraal. Gateway confirms full headcount again.

This guarantees that every animal is accounted for at least at morning
and evening, with realistic partial detection during the grazing period.

Usage:
    python gateway_simulator.py --farm lochvaal --animals 10
    python gateway_simulator.py --farm sibanyoni --animals 50
    python gateway_simulator.py --farm lochvaal --seed 42 --offline
"""

import time
import math
import random
import json
from dataclasses import dataclass, field
from typing import List, Optional, Set
from datetime import datetime, timezone

import click
import requests


# ─── Configuration ────────────────────────────────────────────────────────────

FARM_PRESETS = {
    'boschhoek': {
        'lat': -29.12, 'lon': 26.21,
        'name': 'Boschhoek Farm (Free State)',
        'gateway_serial': 'GW-BH-001',
        'farm_id': 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
    },
    'lochvaal': {
        'lat': -26.719088, 'lon': 27.709759,
        'name': 'Loch Vaal Plot 30 (Gauteng)',
        'gateway_serial': 'GW-LV-001',
        'farm_id': 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
    },
    'sibanyoni': {
        'lat': -25.3580560, 'lon': 25.3612750,
        'name': 'Sibanyoni Farm (North West)',
        'gateway_serial': 'GW-SB-001',
        'farm_id': 'dddddddd-1111-2222-3333-555555555555',
    },
}

# BLE simulation parameters
BLE_TX_POWER = -59       # dBm at 1 metre (typical BLE beacon)
BLE_PATH_LOSS_N = 2.2    # Path loss exponent (outdoor with some obstacles)
BLE_MAX_RANGE_M = 100    # Beyond this, tag not detected
BLE_NOISE_DB = 4         # Random RSSI noise (std dev)

# Kraal parameters
KRAAL_RADIUS_M = 15      # All cattle within this radius at kraal


# ─── Simulated Entities ──────────────────────────────────────────────────────

@dataclass
class SimulatedEarTag:
    """A passive BLE ear tag on a cow."""
    mac_address: str
    animal_name: str
    lat: float
    lon: float
    # Target position (for herding movement)
    target_lat: float = 0.0
    target_lon: float = 0.0
    speed_kmh: float = 0.0
    heading_deg: float = 0.0

    def move_towards_target(self, dt_seconds: float, speed_kmh: float = 3.0):
        """Move towards target position (used for herding to/from kraal)."""
        dist = distance_between(self.lat, self.lon, self.target_lat, self.target_lon)
        if dist < 2.0:  # Close enough
            return
        dy = (self.target_lat - self.lat) * 111320.0
        dx = (self.target_lon - self.lon) * 111320.0 * math.cos(math.radians(self.lat))
        bearing = math.atan2(dx, dy)
        # Add slight wander
        bearing += random.gauss(0, 0.1)
        distance_m = min(speed_kmh * (dt_seconds / 3600.0) * 1000.0, dist)
        dlat = (distance_m * math.cos(bearing)) / 111320.0
        dlon = (distance_m * math.sin(bearing)) / (111320.0 * math.cos(math.radians(self.lat)))
        self.lat += dlat
        self.lon += dlon

    def graze(self, dt_seconds: float):
        """Simulate slow grazing movement (random drift)."""
        if random.random() < 0.1:
            self.heading_deg = random.uniform(0, 360)
        self.speed_kmh = random.uniform(0.0, 1.5)
        distance_m = self.speed_kmh * (dt_seconds / 3600.0) * 1000.0
        bearing_rad = math.radians(self.heading_deg)
        dlat = (distance_m * math.cos(bearing_rad)) / 111320.0
        dlon = (distance_m * math.sin(bearing_rad)) / (111320.0 * math.cos(math.radians(self.lat)))
        self.lat += dlat
        self.lon += dlon

    def place_in_kraal(self, kraal_lat: float, kraal_lon: float):
        """Place cow randomly within kraal radius."""
        angle = random.uniform(0, 2 * math.pi)
        r = random.uniform(0, KRAAL_RADIUS_M)
        self.lat = kraal_lat + (r * math.cos(angle)) / 111320.0
        self.lon = kraal_lon + (r * math.sin(angle)) / (111320.0 * math.cos(math.radians(kraal_lat)))


@dataclass
class SimulatedGateway:
    """The herdsman's phone/device."""
    serial: str
    lat: float
    lon: float
    battery_pct: int = 95
    speed_kmh: float = 4.0
    heading_deg: float = 0.0
    waypoints: List[tuple] = field(default_factory=list)
    waypoint_idx: int = 0

    def move_to(self, target_lat: float, target_lon: float, dt_seconds: float):
        """Move gateway towards a specific point."""
        dist = distance_between(self.lat, self.lon, target_lat, target_lon)
        if dist < 3.0:
            self.lat = target_lat
            self.lon = target_lon
            return True  # Arrived
        dy = (target_lat - self.lat) * 111320.0
        dx = (target_lon - self.lon) * 111320.0 * math.cos(math.radians(self.lat))
        bearing = math.atan2(dx, dy)
        distance_m = min(self.speed_kmh * (dt_seconds / 3600.0) * 1000.0, dist)
        dlat = (distance_m * math.cos(bearing)) / 111320.0
        dlon = (distance_m * math.sin(bearing)) / (111320.0 * math.cos(math.radians(self.lat)))
        self.lat += dlat
        self.lon += dlon
        self.battery_pct = max(0, self.battery_pct - random.uniform(0.001, 0.003))
        return False  # Still moving

    def move_patrol(self, dt_seconds: float):
        """Move through patrol waypoints sequentially."""
        if not self.waypoints:
            return
        target = self.waypoints[self.waypoint_idx]
        arrived = self.move_to(target[0], target[1], dt_seconds)
        if arrived:
            self.waypoint_idx = (self.waypoint_idx + 1) % len(self.waypoints)


# ─── BLE Physics ─────────────────────────────────────────────────────────────

def distance_between(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance in metres between two GPS points."""
    dy = (lat2 - lat1) * 111320.0
    dx = (lon2 - lon1) * 111320.0 * math.cos(math.radians(lat1))
    return math.sqrt(dx * dx + dy * dy)


def rssi_from_distance(distance_m: float) -> int:
    """Calculate simulated RSSI from distance using log-distance path loss model."""
    if distance_m < 0.5:
        distance_m = 0.5
    rssi = BLE_TX_POWER - 10 * BLE_PATH_LOSS_N * math.log10(distance_m)
    rssi += random.gauss(0, BLE_NOISE_DB)
    return max(-120, min(-30, int(rssi)))


def generate_mac() -> str:
    """Generate a random BLE MAC address."""
    return ':'.join(f'{random.randint(0, 255):02X}' for _ in range(6))


# ─── API Client ──────────────────────────────────────────────────────────────

def fetch_registered_tags(api_url: str, farm_id: str) -> Optional[List[dict]]:
    """Fetch registered BLE tags from the API for a given farm."""
    try:
        resp = requests.get(f"{api_url}/api/gateway/tags", params={"farm_id": farm_id}, timeout=10)
        if resp.status_code == 200:
            tags = resp.json()
            if tags:
                return [{"mac_address": t["mac_address"], "animal_name": t.get("animal_name") or t["mac_address"]}
                        for t in tags if t.get("status", "active") == "active"]
        return None
    except Exception:
        return None


def send_batch(api_url: str, gateway_serial: str, gateway: SimulatedGateway,
               sightings: List[dict], session_id: Optional[str] = None):
    """Send a batch of BLE sightings to the API."""
    payload = {
        "gateway_serial": gateway_serial,
        "latitude": gateway.lat,
        "longitude": gateway.lon,
        "speed": gateway.speed_kmh,
        "battery_pct": int(gateway.battery_pct),
        "session_id": session_id,
        "sightings": sightings,
    }
    try:
        resp = requests.post(f"{api_url}/api/gateway/batch", json=payload, timeout=10)
        if resp.status_code == 200:
            return resp.json()
        else:
            print(f"  [API] Error {resp.status_code}: {resp.text[:100]}")
            return None
    except requests.exceptions.ConnectionError:
        print(f"  [API] Connection refused — is the API running at {api_url}?")
        return None
    except Exception as e:
        print(f"  [API] Error: {e}")
        return None


def start_session(api_url: str, gateway_serial: str, lat: float, lon: float,
                  herdsman_name: str) -> Optional[str]:
    """Start a patrol session, returns session_id."""
    try:
        resp = requests.post(f"{api_url}/api/gateway/sessions/start", json={
            "gateway_serial": gateway_serial,
            "latitude": lat,
            "longitude": lon,
            "herdsman_name": herdsman_name,
        }, timeout=10)
        if resp.status_code == 201:
            return resp.json().get("session_id")
    except Exception as e:
        print(f"  [API] Session start failed: {e}")
    return None


def end_session(api_url: str, session_id: str, lat: float, lon: float):
    """End a patrol session."""
    try:
        requests.post(f"{api_url}/api/gateway/sessions/{session_id}/end", json={
            "latitude": lat,
            "longitude": lon,
        }, timeout=10)
    except Exception:
        pass


# ─── Daily Phases ─────────────────────────────────────────────────────────────

def generate_grazing_clusters(farm_lat: float, farm_lon: float, num_animals: int,
                              num_clusters: int = 4) -> List[tuple]:
    """Generate grazing cluster positions around the farm.

    Returns list of (lat, lon) centres where cattle groups will graze.
    Clusters are placed 150-300m from farm centre in different directions.
    """
    clusters = []
    for i in range(num_clusters):
        angle = (2 * math.pi * i / num_clusters) + random.uniform(-0.3, 0.3)
        dist_m = random.uniform(150, 300)
        dlat = (dist_m * math.cos(angle)) / 111320.0
        dlon = (dist_m * math.sin(angle)) / (111320.0 * math.cos(math.radians(farm_lat)))
        clusters.append((farm_lat + dlat, farm_lon + dlon))
    return clusters


# ─── CLI ─────────────────────────────────────────────────────────────────────

@click.command()
@click.option('--api-url', default='http://localhost:8000', help='API base URL')
@click.option('--farm', default='lochvaal', type=click.Choice(list(FARM_PRESETS.keys())),
              help='Farm preset')
@click.option('--gateway-serial', default=None, help='Gateway serial (auto from preset)')
@click.option('--herdsman', default='Teboho Mpeki', help='Herdsman name')
@click.option('--animals', default=10, help='Number of ear-tagged animals')
@click.option('--scan-interval', default=5, help='BLE scan interval (seconds)')
@click.option('--report-interval', default=30, help='API report interval (seconds)')
@click.option('--duration', default=600, help='Simulation duration (seconds)')
@click.option('--offline', is_flag=True, help='Run without API (print output only)')
@click.option('--seed', default=None, type=int, help='Random seed for reproducible runs')
def main(api_url, farm, gateway_serial, herdsman, animals, scan_interval,
         report_interval, duration, offline, seed):
    """LivestockGuard Herdsman Gateway Simulator — Daily Lifecycle

    Simulates a full day: morning kraal check (100% detection), daytime
    grazing patrol (progressive detection), evening return (100% again).

    All cattle are guaranteed to be fully accounted for at morning and evening.
    """
    if seed is not None:
        random.seed(seed)

    preset = FARM_PRESETS[farm]
    farm_lat = preset['lat']
    farm_lon = preset['lon']
    if not gateway_serial:
        gateway_serial = preset['gateway_serial']

    # Duration split: 20% morning kraal, 60% daytime patrol, 20% evening return
    morning_duration = int(duration * 0.20)
    patrol_duration = int(duration * 0.60)
    evening_duration = duration - morning_duration - patrol_duration

    print(f"LivestockGuard Gateway Simulator v2.0 — Daily Lifecycle")
    print(f"{'─' * 60}")
    print(f"Farm:       {preset['name']}")
    print(f"Gateway:    {gateway_serial}")
    print(f"Herdsman:   {herdsman}")
    print(f"Animals:    {animals} (BLE ear tags)")
    print(f"BLE Scan:   every {scan_interval}s")
    print(f"API Report: every {report_interval}s")
    print(f"Duration:   {duration}s (morning {morning_duration}s | patrol {patrol_duration}s | evening {evening_duration}s)")
    print(f"Seed:       {seed if seed is not None else 'random'}")
    print(f"API:        {'OFFLINE (print only)' if offline else api_url}")
    print()

    # ─── Setup: Create tags ───────────────────────────────────────────────
    tags: List[SimulatedEarTag] = []

    registered_tags = None
    if not offline and preset.get('farm_id'):
        print(f"Fetching registered BLE tags from API...")
        registered_tags = fetch_registered_tags(api_url, preset['farm_id'])
        if registered_tags:
            print(f"  Found {len(registered_tags)} registered tags in database")
        else:
            print(f"  No registered tags found — using random MACs")

    num_tags = animals
    if registered_tags:
        num_tags = min(animals, len(registered_tags))
        for i in range(num_tags):
            rt = registered_tags[i]
            tags.append(SimulatedEarTag(
                mac_address=rt['mac_address'],
                animal_name=rt['animal_name'],
                lat=farm_lat, lon=farm_lon,
            ))
    else:
        for i in range(num_tags):
            mac = generate_mac()
            tags.append(SimulatedEarTag(
                mac_address=mac,
                animal_name=f"Cow-{i + 1:03d}",
                lat=farm_lat, lon=farm_lon,
            ))

    # Place all cattle in kraal for morning
    for tag in tags:
        tag.place_in_kraal(farm_lat, farm_lon)

    # Create gateway at kraal
    gateway = SimulatedGateway(serial=gateway_serial, lat=farm_lat, lon=farm_lon)
    gateway.speed_kmh = 5.0  # Brisk walking pace for patrol

    # Generate grazing clusters for daytime
    num_clusters = max(3, min(6, num_tags // 5))  # 3-6 clusters
    grazing_clusters = generate_grazing_clusters(farm_lat, farm_lon, num_tags, num_clusters)

    # Assign cattle to clusters for daytime grazing
    cluster_assignments = [i % num_clusters for i in range(num_tags)]
    random.shuffle(cluster_assignments)

    print(f"\n  Grazing clusters: {num_clusters} groups")
    for i, c in enumerate(grazing_clusters):
        count = cluster_assignments.count(i)
        dist = distance_between(farm_lat, farm_lon, c[0], c[1])
        print(f"    Cluster {i+1}: ({c[0]:.5f}, {c[1]:.5f}) — {count} cattle, {dist:.0f}m from kraal")

    print(f"\n{'─' * 60}")

    # Start session
    session_id = None
    if not offline:
        session_id = start_session(api_url, gateway_serial, gateway.lat, gateway.lon, herdsman)
        if session_id:
            print(f"Session started: {session_id}")
        else:
            print("(Could not start session — gateway may not be registered)")

    # ─── Simulation Loop ──────────────────────────────────────────────────
    elapsed = 0
    scan_buffer: List[dict] = []
    last_report_time = 0
    total_detections = 0
    unique_detected: Set[str] = set()
    phase = "MORNING"

    # Patrol waypoints: visit each grazing cluster then return
    patrol_waypoints = grazing_clusters.copy()
    gateway.waypoints = patrol_waypoints
    gateway.waypoint_idx = 0

    try:
        while elapsed < duration:
            # ── Determine phase ──
            if elapsed < morning_duration:
                phase = "MORNING"
            elif elapsed < morning_duration + patrol_duration:
                if phase == "MORNING":
                    # Transition: scatter cattle to grazing clusters
                    phase = "PATROL"
                    print(f"\n  ── PHASE: DAYTIME PATROL ── Cattle scattering to grazing areas...")
                    for i, tag in enumerate(tags):
                        cluster_idx = cluster_assignments[i]
                        c = grazing_clusters[cluster_idx]
                        # Scatter within 50m of cluster centre
                        angle = random.uniform(0, 2 * math.pi)
                        r = random.uniform(0, 50)
                        tag.target_lat = c[0] + (r * math.cos(angle)) / 111320.0
                        tag.target_lon = c[1] + (r * math.sin(angle)) / (111320.0 * math.cos(math.radians(c[0])))
                    # Gateway starts moving to first cluster
                    gateway.waypoint_idx = 0
            else:
                if phase == "PATROL":
                    # Transition: cattle return to kraal
                    phase = "EVENING"
                    print(f"\n  ── PHASE: EVENING RETURN ── Cattle returning to kraal...")
                    for tag in tags:
                        # Target: tight cluster at kraal centre
                        angle = random.uniform(0, 2 * math.pi)
                        r = random.uniform(0, KRAAL_RADIUS_M * 0.5)
                        tag.target_lat = farm_lat + (r * math.cos(angle)) / 111320.0
                        tag.target_lon = farm_lon + (r * math.sin(angle)) / (111320.0 * math.cos(math.radians(farm_lat)))
                    # Gateway goes straight back to kraal
                    gateway.lat = farm_lat
                    gateway.lon = farm_lon

            # ── Move entities based on phase ──
            if phase == "MORNING":
                # Cattle stay in kraal (tiny drift), gateway stands at kraal
                for tag in tags:
                    # Tiny movement within kraal
                    angle = random.uniform(0, 2 * math.pi)
                    drift = random.uniform(0, 0.5)  # <0.5m
                    tag.lat += (drift * math.cos(angle)) / 111320.0
                    tag.lon += (drift * math.sin(angle)) / (111320.0 * math.cos(math.radians(tag.lat)))

            elif phase == "PATROL":
                # Cattle move towards/graze at their assigned clusters
                for i, tag in enumerate(tags):
                    dist_to_target = distance_between(tag.lat, tag.lon, tag.target_lat, tag.target_lon)
                    if dist_to_target > 5.0:
                        tag.move_towards_target(scan_interval, speed_kmh=3.0)
                    else:
                        tag.graze(scan_interval)
                # Gateway patrols between clusters
                gateway.move_patrol(scan_interval)

            elif phase == "EVENING":
                # Cattle are being herded back — move faster
                for tag in tags:
                    tag.move_towards_target(scan_interval, speed_kmh=6.0)
                # Gateway stays at kraal, waiting for cattle to arrive
                gateway.lat = farm_lat
                gateway.lon = farm_lon

            # ── BLE scan ──
            scan_detections = 0
            scan_macs: List[str] = []
            for tag in tags:
                dist = distance_between(gateway.lat, gateway.lon, tag.lat, tag.lon)
                if dist <= BLE_MAX_RANGE_M:
                    rssi = rssi_from_distance(dist)
                    scan_buffer.append({
                        "mac_address": tag.mac_address,
                        "rssi": rssi,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
                    scan_detections += 1
                    total_detections += 1
                    unique_detected.add(tag.mac_address)
                    scan_macs.append(tag.animal_name)

            # Print scan result
            phase_tag = f"[{phase:7s}]"
            print(f"  [{elapsed:4d}s] {phase_tag} Gateway @ ({gateway.lat:.5f}, {gateway.lon:.5f}) "
                  f"| Scan: {scan_detections}/{num_tags} "
                  f"| Unique seen: {len(unique_detected)}/{num_tags} "
                  f"| Battery: {gateway.battery_pct:.0f}%")

            # Report to API at intervals
            if elapsed - last_report_time >= report_interval and scan_buffer:
                print(f"  >>> Sending batch: {len(scan_buffer)} sightings to API...")
                if not offline:
                    result = send_batch(api_url, gateway_serial, gateway, scan_buffer, session_id)
                    if result:
                        print(f"      Accepted: {result['accepted']}, "
                              f"Resolved: {result['resolved']}, "
                              f"Unresolved MACs: {len(result['unresolved_macs'])}")
                else:
                    print(f"      [OFFLINE] Would send {len(scan_buffer)} sightings")
                scan_buffer = []
                last_report_time = elapsed

            time.sleep(scan_interval)
            elapsed += scan_interval

            # Phase transition announcements
            if elapsed == morning_duration:
                print(f"\n  ── Morning kraal check complete: {len(unique_detected)}/{num_tags} cattle accounted for ──")

    except KeyboardInterrupt:
        print("\n\nSimulation stopped by user")

    # Send any remaining buffer
    if scan_buffer:
        if not offline:
            send_batch(api_url, gateway_serial, gateway, scan_buffer, session_id)
        scan_buffer = []

    # End session
    if session_id and not offline:
        end_session(api_url, session_id, gateway.lat, gateway.lon)
        print(f"\nSession ended: {session_id}")

    print(f"\n{'─' * 60}")
    print(f"Simulation complete:")
    print(f"  Duration:         {elapsed}s")
    print(f"  Total detections: {total_detections}")
    print(f"  Unique cattle:    {len(unique_detected)}/{num_tags} "
          f"({'ALL ACCOUNTED' if len(unique_detected) == num_tags else 'MISSING: ' + str(num_tags - len(unique_detected))})")
    print(f"  Final position:   ({gateway.lat:.5f}, {gateway.lon:.5f})")
    print(f"  Battery:          {gateway.battery_pct:.0f}%")


if __name__ == '__main__':
    main()
