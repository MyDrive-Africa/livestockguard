#!/usr/bin/env python3
"""
LivestockGuard Herdsman Gateway Simulator

Simulates a herdsman walking through a farm with a phone/gateway device,
collecting BLE advertisement pings from passive cattle ear tags and
sending batch sightings to the cloud API.

The herdsman walks a patrol route. Animals are scattered around the farm.
As the herdsman moves within BLE range (~100m), their ear tags are "detected"
with realistic RSSI values based on distance.

Usage:
    python gateway_simulator.py --farm lochvaal --animals 10
    python gateway_simulator.py --api-url http://localhost:8000 --gateway-serial GW-LV-001
"""

import time
import math
import random
import json
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime, timezone

import click
import requests


# ─── Configuration ────────────────────────────────────────────────────────────

FARM_PRESETS = {
    'boschhoek': {
        'lat': -29.12, 'lon': 26.21,
        'name': 'Boschhoek Farm (Free State)',
        'gateway_serial': 'GW-BH-001',
    },
    'lochvaal': {
        'lat': -26.719088, 'lon': 27.709759,
        'name': 'Loch Vaal Plot 30 (Gauteng)',
        'gateway_serial': 'GW-LV-001',
    },
    'sibanyoni': {
        'lat': -25.3580560, 'lon': 25.3612750,
        'name': 'Sibanyoni Farm (North West)',
        'gateway_serial': 'GW-SB-001',
    },
}

# BLE simulation parameters
BLE_TX_POWER = -59       # dBm at 1 metre (typical BLE beacon)
BLE_PATH_LOSS_N = 2.2    # Path loss exponent (outdoor with some obstacles)
BLE_MAX_RANGE_M = 100    # Beyond this, tag not detected
BLE_NOISE_DB = 4         # Random RSSI noise (std dev)


# ─── Simulated Entities ──────────────────────────────────────────────────────

@dataclass
class SimulatedEarTag:
    """A passive BLE ear tag on a cow."""
    mac_address: str
    animal_name: str
    lat: float
    lon: float
    # Animals move slowly while grazing
    speed_kmh: float = 0.0
    heading_deg: float = 0.0

    def move(self, dt_seconds: float):
        """Simulate slow grazing movement."""
        if random.random() < 0.1:
            self.heading_deg = random.uniform(0, 360)
        self.speed_kmh = random.uniform(0.0, 1.5)

        distance_m = self.speed_kmh * (dt_seconds / 3600.0) * 1000.0
        bearing_rad = math.radians(self.heading_deg)
        dlat = (distance_m * math.cos(bearing_rad)) / 111320.0
        dlon = (distance_m * math.sin(bearing_rad)) / (111320.0 * math.cos(math.radians(self.lat)))
        self.lat += dlat
        self.lon += dlon


@dataclass
class SimulatedGateway:
    """The herdsman's phone/device walking a patrol."""
    serial: str
    lat: float
    lon: float
    battery_pct: int = 85
    speed_kmh: float = 4.0  # Walking speed
    heading_deg: float = 0.0
    # Patrol waypoints
    waypoints: List[tuple] = field(default_factory=list)
    waypoint_idx: int = 0

    def move(self, dt_seconds: float):
        """Move towards next waypoint."""
        if not self.waypoints:
            # Random walk if no waypoints
            self.heading_deg += random.uniform(-15, 15)
            self.speed_kmh = random.uniform(3.0, 5.0)
        else:
            # Move towards current waypoint
            target = self.waypoints[self.waypoint_idx]
            dy = (target[0] - self.lat) * 111320.0
            dx = (target[1] - self.lon) * 111320.0 * math.cos(math.radians(self.lat))
            dist_to_target = math.sqrt(dx * dx + dy * dy)

            if dist_to_target < 20:  # Reached waypoint
                self.waypoint_idx = (self.waypoint_idx + 1) % len(self.waypoints)
                return

            self.heading_deg = math.degrees(math.atan2(dx, dy)) % 360
            self.speed_kmh = 4.0

        distance_m = self.speed_kmh * (dt_seconds / 3600.0) * 1000.0
        bearing_rad = math.radians(self.heading_deg)
        dlat = (distance_m * math.cos(bearing_rad)) / 111320.0
        dlon = (distance_m * math.sin(bearing_rad)) / (111320.0 * math.cos(math.radians(self.lat)))
        self.lat += dlat
        self.lon += dlon

        # Battery drain
        self.battery_pct = max(0, self.battery_pct - random.uniform(0.001, 0.003))


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
    # RSSI = TxPower - 10 * n * log10(d)
    rssi = BLE_TX_POWER - 10 * BLE_PATH_LOSS_N * math.log10(distance_m)
    # Add noise
    rssi += random.gauss(0, BLE_NOISE_DB)
    return max(-120, min(-30, int(rssi)))


def generate_mac() -> str:
    """Generate a random BLE MAC address."""
    return ':'.join(f'{random.randint(0, 255):02X}' for _ in range(6))


# ─── API Client ──────────────────────────────────────────────────────────────

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
            data = resp.json()
            return data
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
def main(api_url, farm, gateway_serial, herdsman, animals, scan_interval,
         report_interval, duration, offline):
    """LivestockGuard Herdsman Gateway Simulator

    Simulates a herdsman walking with a phone that collects BLE pings
    from passive cattle ear tags and sends batches to the cloud API.
    """
    preset = FARM_PRESETS[farm]
    farm_lat = preset['lat']
    farm_lon = preset['lon']
    if not gateway_serial:
        gateway_serial = preset['gateway_serial']

    print(f"LivestockGuard Gateway Simulator v1.0")
    print(f"{'─' * 50}")
    print(f"Farm:       {preset['name']}")
    print(f"Gateway:    {gateway_serial}")
    print(f"Herdsman:   {herdsman}")
    print(f"Animals:    {animals} (BLE ear tags)")
    print(f"BLE Scan:   every {scan_interval}s")
    print(f"API Report: every {report_interval}s")
    print(f"Duration:   {duration}s")
    print(f"API:        {'OFFLINE (print only)' if offline else api_url}")
    print()

    # Create patrol waypoints (rectangle around farm centre)
    offset = 0.003  # ~300m
    waypoints = [
        (farm_lat - offset, farm_lon - offset),
        (farm_lat - offset, farm_lon + offset),
        (farm_lat + offset, farm_lon + offset),
        (farm_lat + offset, farm_lon - offset),
    ]

    # Create gateway
    gateway = SimulatedGateway(
        serial=gateway_serial,
        lat=farm_lat - offset,
        lon=farm_lon - offset,
        waypoints=waypoints,
    )

    # Create animals scattered around farm
    tags: List[SimulatedEarTag] = []
    for i in range(animals):
        mac = generate_mac()
        lat = farm_lat + random.uniform(-offset * 1.5, offset * 1.5)
        lon = farm_lon + random.uniform(-offset * 1.5, offset * 1.5)
        name = f"Cow-{i + 1:03d}"
        tags.append(SimulatedEarTag(mac_address=mac, animal_name=name, lat=lat, lon=lon))
        print(f"  Tag: {mac} → {name} @ ({lat:.5f}, {lon:.5f})")

    print(f"\nGateway starting at ({gateway.lat:.5f}, {gateway.lon:.5f})")
    print(f"{'─' * 50}")

    # Start session
    session_id = None
    if not offline:
        session_id = start_session(api_url, gateway_serial, gateway.lat, gateway.lon, herdsman)
        if session_id:
            print(f"Session started: {session_id}")
        else:
            print("(Could not start session — gateway may not be registered)")

    # Run simulation
    elapsed = 0
    scan_buffer: List[dict] = []
    last_report_time = 0
    total_detections = 0

    try:
        while elapsed < duration:
            # Move entities
            gateway.move(scan_interval)
            for tag in tags:
                tag.move(scan_interval)

            # BLE scan: detect tags within range
            scan_detections = 0
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

            # Print scan result
            print(f"  [{elapsed:4d}s] Gateway @ ({gateway.lat:.5f}, {gateway.lon:.5f}) "
                  f"| BLE scan: {scan_detections}/{animals} tags in range "
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

    except KeyboardInterrupt:
        print("\n\nSimulation stopped by user")

    # End session
    if session_id and not offline:
        end_session(api_url, session_id, gateway.lat, gateway.lon)
        print(f"\nSession ended: {session_id}")

    print(f"\n{'─' * 50}")
    print(f"Simulation complete:")
    print(f"  Duration:    {elapsed}s")
    print(f"  Detections:  {total_detections}")
    print(f"  Final pos:   ({gateway.lat:.5f}, {gateway.lon:.5f})")
    print(f"  Battery:     {gateway.battery_pct:.0f}%")


if __name__ == '__main__':
    main()
