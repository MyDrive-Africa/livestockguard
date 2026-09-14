#!/usr/bin/env python3
"""
LivestockGuard Robotic Herdsman Simulator

Simulates a small fleet of autonomous herding robots (default 4 per farm) plus a
drifting herd, so the Herding Orchestrator brain can be exercised end-to-end with
zero hardware — the same philosophy as simulator.py and gateway_simulator.py.

Each virtual robot:
  - connects to MQTT and SUBSCRIBES to  lg/robot/{serial}/cmd
  - on a command, drives toward the target at its max speed (presence + sound)
  - PUBLISHES telemetry to  lg/robot/{serial}/telemetry  (~1 Hz) which mqtt_writer
    persists to robot_telemetry
  - acks commands on  lg/robot/{serial}/ack
  - drains battery and returns to its home dock to charge when low

The herd is simulated locally: cattle wander inside the boundary and, in the
breach/theft scenarios, one drifts outward — giving the orchestrator something to
react to. Cattle positions are published as GPS telemetry on the standard
lg/up/{id:04X}/telemetry topic so they flow through the normal pipeline.

Examples:
    python3 robot_simulator.py --farm lochvaal --scenario contain
    python3 robot_simulator.py --farm lochvaal --scenario breach --seed 42
    python3 robot_simulator.py --farm sibanyoni --robots 4 --duration 300
"""

import json
import math
import random
import struct
import time
from dataclasses import dataclass, field
from typing import Optional

import click
import paho.mqtt.client as mqtt

# Reuse the binary GPS encoder from the existing collar simulator so simulated
# cattle positions flow through the exact same MQTT Writer decode path.
from simulator import encode_message, MSG_POSITION_BATCH, PRIORITY_NORMAL

M_PER_DEG_LAT = 111_320.0

# `robot_prefix` must match the serials registered in the DB (scripts/seed_robots.sql),
# e.g. Loch Vaal robots are ROBO-LV-01.. — not derivable from farm_key[:2].
FARM_PRESETS = {
    "boschhoek": {"lat": -29.12, "lon": 26.21, "name": "Boschhoek Farm (Free State)",
                  "device_base": 0x1000, "robot_base": 0x9100, "robot_prefix": "BH"},
    "lochvaal": {"lat": -26.719088, "lon": 27.709759, "name": "Loch Vaal Plot 30 (Gauteng)",
                 "device_base": 0x2000, "robot_base": 0x9200, "robot_prefix": "LV"},
    "sibanyoni": {"lat": -25.3580560, "lon": 25.3612750, "name": "Sibanyoni Farm (North West)",
                  "device_base": 0x3000, "robot_base": 0x9300, "robot_prefix": "SI"},
}

CATTLE_NAMES = [
    "Bella", "Storm", "Thunder", "Daisy", "Rosie", "Midnight", "Patches", "Duke",
    "Princess", "Rocky", "Amber", "Shadow", "Spirit", "Blaze", "Pepper",
]


# --------------------------------------------------------------------------- #
# Geometry helpers                                                            #
# --------------------------------------------------------------------------- #

def offset(lat: float, lon: float, bearing_deg: float, distance_m: float) -> tuple[float, float]:
    """Point ``distance_m`` from (lat, lon) along ``bearing_deg``."""
    br = math.radians(bearing_deg)
    dlat = (distance_m * math.cos(br)) / M_PER_DEG_LAT
    dlon = (distance_m * math.sin(br)) / (M_PER_DEG_LAT * math.cos(math.radians(lat)))
    return lat + dlat, lon + dlon


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlam / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def bearing_to(from_lat: float, from_lon: float, to_lat: float, to_lon: float) -> float:
    y = math.sin(math.radians(to_lon - from_lon)) * math.cos(math.radians(to_lat))
    x = math.cos(math.radians(from_lat)) * math.sin(math.radians(to_lat)) - math.sin(
        math.radians(from_lat)
    ) * math.cos(math.radians(to_lat)) * math.cos(math.radians(to_lon - from_lon))
    return (math.degrees(math.atan2(y, x)) + 360) % 360


# --------------------------------------------------------------------------- #
# Simulated robot                                                             #
# --------------------------------------------------------------------------- #

@dataclass
class SimRobot:
    serial: str
    device_id: int
    lat: float
    lon: float
    home_lat: float
    home_lon: float
    max_speed_mps: float = 2.0
    battery_pct: float = 100.0
    heading_deg: float = 0.0
    state: str = "patrolling"
    target: Optional[tuple[float, float]] = None
    deterrent: Optional[str] = None

    def apply_command(self, payload: dict) -> None:
        """React to a command from the orchestrator."""
        cmd = payload.get("cmd", "patrol")
        self.deterrent = payload.get("deterrent")
        tgt = payload.get("target")
        if cmd in ("move_to", "shepherd", "investigate") and tgt:
            self.target = (tgt["lat"], tgt["lon"])
            self.state = "shepherding" if cmd == "shepherd" else "enroute"
        elif cmd == "return_home":
            self.target = (self.home_lat, self.home_lon)
            self.state = "charging"
        elif cmd == "stop":
            self.target = None
            self.state = "idle"
        else:  # patrol
            self.target = None
            self.state = "patrolling"

    def step(self, dt: float) -> None:
        """Advance the robot one tick."""
        if self.target:
            tlat, tlon = self.target
            dist = haversine_m(self.lat, self.lon, tlat, tlon)
            if dist < 2.0:
                # Arrived. If charging, top up; else hold at the intercept point.
                if self.state == "charging":
                    self.battery_pct = min(100.0, self.battery_pct + 5.0 * dt)
                    if self.battery_pct >= 99:
                        self.state = "patrolling"
                        self.target = None
            else:
                self.heading_deg = bearing_to(self.lat, self.lon, tlat, tlon)
                travel = min(dist, self.max_speed_mps * dt)
                self.lat, self.lon = offset(self.lat, self.lon, self.heading_deg, travel)
        else:
            # Gentle idle drift while patrolling.
            if self.state == "patrolling":
                self.heading_deg = (self.heading_deg + random.uniform(-20, 20)) % 360
                self.lat, self.lon = offset(self.lat, self.lon, self.heading_deg,
                                            self.max_speed_mps * dt * 0.3)

        # Battery: driving costs more than idling; charging handled above.
        if self.state != "charging":
            drain = 0.02 if self.target else 0.005
            self.battery_pct = max(0.0, self.battery_pct - drain * dt)

    def telemetry(self) -> dict:
        return {
            "serial": self.serial,
            "lat": round(self.lat, 7),
            "lon": round(self.lon, 7),
            "heading_deg": round(self.heading_deg, 1),
            "speed_mps": self.max_speed_mps if self.target else 0.0,
            "battery_pct": int(self.battery_pct),
            "state": self.state,
            "deterrent": self.deterrent,
            "ts": int(time.time()),
        }


# --------------------------------------------------------------------------- #
# Simulated cattle (local — gives the brain something to react to)            #
# --------------------------------------------------------------------------- #

@dataclass
class SimCow:
    device_id: int
    name: str
    lat: float
    lon: float
    straying: bool = False
    heading_deg: float = 0.0
    sequence: int = 0

    def step(self, dt: float, center: tuple[float, float]) -> None:
        if self.straying:
            # Walk steadily away from centre (breach/theft).
            b = bearing_to(center[0], center[1], self.lat, self.lon)
            speed = 4.0  # m/s, driven off
            self.lat, self.lon = offset(self.lat, self.lon, b, speed * dt)
        else:
            self.heading_deg = (self.heading_deg + random.uniform(-40, 40)) % 360
            self.lat, self.lon = offset(self.lat, self.lon, self.heading_deg, random.uniform(0.3, 1.5) * dt)

    def encode(self) -> bytes:
        record = struct.pack(
            "<iiiBBBB",
            int(time.time()), int(self.lat * 1e7), int(self.lon * 1e7),
            2, int(self.heading_deg * 255 / 360), 12, 3,
        )
        self.sequence = (self.sequence + 1) % 256
        return encode_message(MSG_POSITION_BATCH, PRIORITY_NORMAL, self.device_id, record, self.sequence)


# --------------------------------------------------------------------------- #
# Simulator runner                                                            #
# --------------------------------------------------------------------------- #

class RobotFleetSimulator:
    def __init__(self, broker: str, port: int, farm_key: str, n_robots: int,
                 n_cattle: int, boundary_radius_m: float, scenario: str):
        preset = FARM_PRESETS[farm_key]
        self.center = (preset["lat"], preset["lon"])
        self.radius = boundary_radius_m
        self.scenario = scenario
        self.client = mqtt.Client(client_id=f"robot_sim_{farm_key}")
        self.client.on_message = self._on_message
        self.broker, self.port = broker, port

        # Spawn robots evenly around the boundary, docked at their home posts.
        self.robots: dict[str, SimRobot] = {}
        for i in range(n_robots):
            bearing = (360 / n_robots) * i
            hlat, hlon = offset(*self.center, bearing, self.radius * 0.9)
            serial = f"ROBO-{preset['robot_prefix']}-{i + 1:02d}"
            self.robots[serial] = SimRobot(
                serial=serial, device_id=preset["robot_base"] + i,
                lat=hlat, lon=hlon, home_lat=hlat, home_lon=hlon,
            )

        # Spawn cattle inside the boundary.
        self.cattle: list[SimCow] = []
        for i in range(n_cattle):
            b = random.uniform(0, 360)
            d = random.uniform(0, self.radius * 0.6)
            clat, clon = offset(*self.center, b, d)
            self.cattle.append(SimCow(preset["device_base"] + i,
                                      CATTLE_NAMES[i % len(CATTLE_NAMES)], clat, clon))

    def _on_message(self, client, userdata, msg):
        parts = msg.topic.split("/")
        if len(parts) >= 4 and parts[1] == "robot" and parts[3] == "cmd":
            serial = parts[2]
            robot = self.robots.get(serial)
            if robot:
                try:
                    payload = json.loads(msg.payload.decode())
                except (ValueError, UnicodeDecodeError):
                    return
                robot.apply_command(payload)
                client.publish(f"lg/robot/{serial}/ack",
                               json.dumps({"serial": serial, "cmd": payload.get("cmd"),
                                           "ts": int(time.time())}), qos=1)
                print(f"  [{serial}] <- {payload.get('cmd')} "
                      f"{'@ ' + str(payload.get('target')) if payload.get('target') else ''}")

    def connect(self) -> None:
        self.client.connect(self.broker, self.port, keepalive=30)
        for serial in self.robots:
            self.client.subscribe(f"lg/robot/{serial}/cmd", qos=1)
        self.client.loop_start()
        print(f"Robot fleet connected: {len(self.robots)} robots, {len(self.cattle)} cattle")

    def _trigger_scenario(self, elapsed: float) -> None:
        if self.scenario in ("breach", "theft") and 20 <= elapsed < 22:
            stray = self.cattle[0]
            stray.straying = True
            label = "THEFT (driven off)" if self.scenario == "theft" else "BREACH (drifting out)"
            print(f"  >>> SCENARIO: {stray.name} started {label} <<<")

    def run(self, duration_sec: int, tick_sec: float) -> None:
        elapsed = 0.0
        last_telem = 0.0
        while elapsed < duration_sec:
            self._trigger_scenario(elapsed)

            # Advance cattle + publish their GPS through the normal pipeline.
            for cow in self.cattle:
                cow.step(tick_sec, self.center)
                self.client.publish(f"lg/up/{cow.device_id:04X}/telemetry", cow.encode(), qos=1)

            # Advance robots + publish telemetry ~1 Hz.
            for robot in self.robots.values():
                robot.step(tick_sec)
            if elapsed - last_telem >= 1.0:
                for robot in self.robots.values():
                    self.client.publish(f"lg/robot/{robot.serial}/telemetry",
                                        json.dumps(robot.telemetry()), qos=1)
                last_telem = elapsed
                self._print_status(elapsed)

            time.sleep(tick_sec)
            elapsed += tick_sec

        self.client.loop_stop()
        self.client.disconnect()
        print("Simulation complete.")

    def _print_status(self, elapsed: float) -> None:
        breached = sum(1 for c in self.cattle
                       if haversine_m(c.lat, c.lon, *self.center) > self.radius)
        busy = sum(1 for r in self.robots.values() if r.target)
        print(f"[t={elapsed:5.0f}s] cattle_outside={breached} robots_active={busy}/{len(self.robots)}")


@click.command()
@click.option("--broker", default="localhost", help="MQTT broker address")
@click.option("--port", default=1883, help="MQTT broker port")
@click.option("--farm", default="lochvaal", type=click.Choice(list(FARM_PRESETS.keys())))
@click.option("--robots", default=4, help="Number of herding robots")
@click.option("--cattle", default=10, help="Number of simulated cattle")
@click.option("--radius", default=200.0, help="Circular boundary radius (metres)")
@click.option("--scenario", default="contain",
              type=click.Choice(["contain", "breach", "theft", "night-kraal"]))
@click.option("--duration", default=180, help="Run duration (seconds)")
@click.option("--tick", default=1.0, help="Simulation tick (seconds)")
@click.option("--seed", default=None, type=int, help="Random seed for reproducible runs")
def main(broker, port, farm, robots, cattle, radius, scenario, duration, tick, seed):
    """Run the robotic herdsman fleet simulator."""
    if seed is not None:
        random.seed(seed)
    preset = FARM_PRESETS[farm]
    print("=" * 60)
    print(" LivestockGuard Robotic Herdsman Simulator")
    print(f" Farm: {preset['name']}")
    print(f" Fleet: {robots} robots | Herd: {cattle} cattle | Boundary: {radius:.0f}m circle")
    print(f" Scenario: {scenario} | Duration: {duration}s")
    print("=" * 60)

    sim = RobotFleetSimulator(broker, port, farm, robots, cattle, radius, scenario)
    try:
        sim.connect()
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: could not connect to MQTT broker at {broker}:{port} ({exc})")
        print("Start the stack first (make start) or pass --broker.")
        return
    sim.run(duration, tick)


if __name__ == "__main__":
    main()
