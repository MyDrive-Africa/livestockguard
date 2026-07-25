#!/usr/bin/env python3
"""
LivestockGuard Device Simulator

Simulates multiple GPS-tagged livestock sending telemetry
to the MQTT broker. Supports various scenarios for testing.
"""

import struct
import time
import math
import random
import json
from dataclasses import dataclass, field
from typing import List, Optional

import click
import paho.mqtt.client as mqtt


# --- Binary Protocol ---

PROTOCOL_VERSION = 0x01
MSG_POSITION_BATCH = 0x01
MSG_GEOFENCE_ALERT = 0x02
MSG_THEFT_ALERT = 0x03
MSG_HEARTBEAT = 0x04

PRIORITY_NORMAL = 1
PRIORITY_CRITICAL = 3


def crc16_ccitt(data: bytes) -> int:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ 0x1021
            else:
                crc <<= 1
            crc &= 0xFFFF
    return crc


def encode_header(msg_type: int, priority: int, device_id: int,
                  timestamp: int, payload_len: int, seq: int) -> bytes:
    return struct.pack('<BBBHIBb',
                      PROTOCOL_VERSION, msg_type, priority,
                      device_id, timestamp, seq, payload_len)


def encode_position_record(timestamp: int, lat_offset: int, lon_offset: int,
                           speed: int, heading: int, hdop_x10: int, flags: int) -> bytes:
    return struct.pack('<iiibbbb', timestamp, lat_offset, lon_offset,
                       speed, heading, hdop_x10, flags)


def encode_message(msg_type: int, priority: int, device_id: int,
                   payload: bytes, seq: int) -> bytes:
    timestamp = int(time.time())
    header = encode_header(msg_type, priority, device_id,
                           timestamp, len(payload), seq)
    msg = header + payload
    crc = crc16_ccitt(msg)
    return msg + struct.pack('>H', crc)


# --- Animal Simulation ---

@dataclass
class SimulatedAnimal:
    device_id: int
    name: str
    lat: float
    lon: float
    speed_kmh: float = 0.0
    heading_deg: float = 0.0
    battery_pct: int = 95
    activity: str = "grazing"
    sequence: int = 0
    ref_lat: Optional[int] = None
    ref_lon: Optional[int] = None

    def move(self, dt_seconds: float):
        """Simulate animal movement based on activity."""
        if self.activity == "grazing":
            self.speed_kmh = random.uniform(0.5, 2.5)
            self.heading_deg += random.uniform(-30, 30)
        elif self.activity == "walking":
            self.speed_kmh = random.uniform(2.0, 5.0)
            self.heading_deg += random.uniform(-10, 10)
        elif self.activity == "resting":
            self.speed_kmh = random.uniform(0.0, 0.3)
        elif self.activity == "transport":
            self.speed_kmh = random.uniform(50, 80)
            # Maintain heading during transport
            self.heading_deg += random.uniform(-2, 2)
        elif self.activity == "breach":
            self.speed_kmh = random.uniform(3.0, 6.0)
            # Move consistently in one direction (out of fence)
            self.heading_deg += random.uniform(-5, 5)

        # Normalize heading
        self.heading_deg = self.heading_deg % 360

        # Calculate displacement
        distance_m = self.speed_kmh * (dt_seconds / 3600.0) * 1000.0
        bearing_rad = math.radians(self.heading_deg)

        # Approximate lat/lon change
        dlat = (distance_m * math.cos(bearing_rad)) / 111320.0
        dlon = (distance_m * math.sin(bearing_rad)) / (111320.0 * math.cos(math.radians(self.lat)))

        self.lat += dlat
        self.lon += dlon

        # Battery drain
        self.battery_pct = max(0, self.battery_pct - random.uniform(0.001, 0.005))

    def encode_position(self) -> bytes:
        """Encode current position as binary message."""
        lat_i = int(self.lat * 1e7)
        lon_i = int(self.lon * 1e7)

        record = struct.pack('<iiiBBBB',
                             int(time.time()),
                             lat_i,
                             lon_i,
                             min(255, int(self.speed_kmh)),
                             int(self.heading_deg * 255 / 360),
                             int(1.2 * 10),  # hdop
                             3)  # 3D fix

        self.sequence = (self.sequence + 1) % 256
        return encode_message(MSG_POSITION_BATCH, PRIORITY_NORMAL,
                              self.device_id, record, self.sequence)

    def encode_theft_alert(self) -> bytes:
        """Encode theft alert."""
        lat_i = int(self.lat * 1e7)
        lon_i = int(self.lon * 1e7)
        payload = struct.pack('<BiiB', 1, lat_i, lon_i, int(self.speed_kmh))
        self.sequence = (self.sequence + 1) % 256
        return encode_message(MSG_THEFT_ALERT, PRIORITY_CRITICAL,
                              self.device_id, payload, self.sequence)

    def encode_breach_alert(self, fence_id: int = 1) -> bytes:
        """Encode geofence breach alert."""
        lat_i = int(self.lat * 1e7)
        lon_i = int(self.lon * 1e7)
        payload = struct.pack('<BBii', fence_id, 2, lat_i, lon_i)  # state=BREACH
        self.sequence = (self.sequence + 1) % 256
        return encode_message(MSG_GEOFENCE_ALERT, PRIORITY_CRITICAL,
                              self.device_id, payload, self.sequence)


# --- Scenarios ---

def run_normal_scenario(animals: List[SimulatedAnimal], client: mqtt.Client,
                        duration_sec: int, interval_sec: int):
    """Normal grazing scenario."""
    print(f"Running NORMAL scenario: {len(animals)} animals, {duration_sec}s duration")
    elapsed = 0
    while elapsed < duration_sec:
        for animal in animals:
            # Randomly change activity
            if random.random() < 0.05:
                animal.activity = random.choice(["grazing", "grazing", "walking", "resting"])

            animal.move(interval_sec)
            msg = animal.encode_position()
            topic = f"lg/up/{animal.device_id:04X}/telemetry"
            client.publish(topic, msg, qos=1)
            print(f"  [{animal.name}] {animal.activity} @ ({animal.lat:.5f}, {animal.lon:.5f}) "
                  f"speed={animal.speed_kmh:.1f} km/h batt={animal.battery_pct:.0f}%")

        time.sleep(interval_sec)
        elapsed += interval_sec


def run_theft_scenario(animals: List[SimulatedAnimal], client: mqtt.Client,
                       duration_sec: int, interval_sec: int):
    """Theft scenario: one animal suddenly on vehicle."""
    print(f"Running THEFT scenario")
    thief_animal = animals[0]
    thief_animal.activity = "transport"
    thief_animal.heading_deg = random.uniform(0, 360)

    elapsed = 0
    alert_sent = False
    while elapsed < duration_sec:
        for animal in animals:
            animal.move(interval_sec)
            msg = animal.encode_position()
            topic = f"lg/up/{animal.device_id:04X}/telemetry"
            client.publish(topic, msg, qos=1)

            if animal == thief_animal:
                print(f"  [{animal.name}] THEFT! speed={animal.speed_kmh:.0f} km/h "
                      f"@ ({animal.lat:.5f}, {animal.lon:.5f})")
                if not alert_sent and elapsed > 30:
                    alert_msg = animal.encode_theft_alert()
                    client.publish(f"lg/up/{animal.device_id:04X}/alert", alert_msg, qos=2)
                    print(f"  >>> THEFT ALERT SENT <<<")
                    alert_sent = True
            else:
                animal.activity = random.choice(["grazing", "resting"])

        time.sleep(interval_sec)
        elapsed += interval_sec


def run_breach_scenario(animals: List[SimulatedAnimal], client: mqtt.Client,
                        duration_sec: int, interval_sec: int):
    """Geofence breach scenario: one animal walks out."""
    print(f"Running BREACH scenario")
    breach_animal = animals[0]
    breach_animal.activity = "breach"
    breach_animal.heading_deg = 180  # Walk south

    elapsed = 0
    alert_sent = False
    while elapsed < duration_sec:
        for animal in animals:
            animal.move(interval_sec)
            msg = animal.encode_position()
            topic = f"lg/up/{animal.device_id:04X}/telemetry"
            client.publish(topic, msg, qos=1)

            if animal == breach_animal:
                print(f"  [{animal.name}] BREACHING! "
                      f"@ ({animal.lat:.5f}, {animal.lon:.5f})")
                if not alert_sent and elapsed > 60:
                    alert_msg = animal.encode_breach_alert()
                    client.publish(f"lg/up/{animal.device_id:04X}/alert", alert_msg, qos=2)
                    print(f"  >>> GEOFENCE BREACH ALERT SENT <<<")
                    alert_sent = True

        time.sleep(interval_sec)
        elapsed += interval_sec


# --- CLI ---

CATTLE_NAMES = [
    "Bella", "Storm", "Thunder", "Daisy", "Rosie",
    "Midnight", "Patches", "Duke", "Princess", "Rocky",
    "Amber", "Shadow", "Spirit", "Blaze", "Pepper",
]

# Pre-configured farm locations
FARM_PRESETS = {
    'boschhoek': {'lat': -29.12, 'lon': 26.21, 'name': 'Boschhoek Farm (Free State)', 'device_base': 0x1000},
    'lochvaal': {'lat': -26.719088, 'lon': 27.709759, 'name': 'Loch Vaal Plot 30 (Gauteng)', 'device_base': 0x2000},
}


@click.command()
@click.option('--broker', default='localhost', help='MQTT broker address')
@click.option('--port', default=1883, help='MQTT broker port')
@click.option('--animals', default=5, help='Number of animals to simulate')
@click.option('--farm-lat', default=None, type=float, help='Farm centre latitude (overrides --farm)')
@click.option('--farm-lon', default=None, type=float, help='Farm centre longitude (overrides --farm)')
@click.option('--farm', default=None, type=click.Choice(list(FARM_PRESETS.keys())),
              help='Use a pre-configured farm location')
@click.option('--device-base', default=None, type=int,
              help='Base device ID (hex). Default: 0x1000 for boschhoek, 0x2000 for lochvaal')
@click.option('--scenario', default='normal',
              type=click.Choice(['normal', 'theft', 'breach', 'night']),
              help='Simulation scenario')
@click.option('--duration', default=300, help='Duration in seconds')
@click.option('--interval', default=15, help='Report interval in seconds')
def main(broker, port, animals, farm_lat, farm_lon, farm, device_base, scenario, duration, interval):
    """LivestockGuard Device Simulator

    Supports multiple farms. Use --farm for presets or --farm-lat/--farm-lon for custom coords.

    Examples:
      python simulator.py --farm boschhoek --animals 5
      python simulator.py --farm lochvaal --animals 10
      python simulator.py --farm-lat -26.719088 --farm-lon 27.709759 --animals 50
    """
    # Resolve farm location
    if farm and farm in FARM_PRESETS:
        preset = FARM_PRESETS[farm]
        if farm_lat is None:
            farm_lat = preset['lat']
        if farm_lon is None:
            farm_lon = preset['lon']
        if device_base is None:
            device_base = preset['device_base']
        farm_name = preset['name']
    else:
        if farm_lat is None:
            farm_lat = -29.12
        if farm_lon is None:
            farm_lon = 26.21
        farm_name = f"Custom ({farm_lat:.4f}, {farm_lon:.4f})"

    if device_base is None:
        device_base = 0x1000

    print(f"LivestockGuard Simulator v1.1")
    print(f"Broker: {broker}:{port}")
    print(f"Farm: {farm_name}")
    print(f"Animals: {animals}, Scenario: {scenario}")
    print(f"Farm centre: ({farm_lat}, {farm_lon})")
    print(f"Device ID base: 0x{device_base:04X}")
    print()

    # Connect to MQTT
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="lg-simulator")
    client.connect(broker, port, 60)
    client.loop_start()
    print("Connected to MQTT broker")

    # Create simulated animals
    sim_animals = []
    for i in range(animals):
        name = CATTLE_NAMES[i % len(CATTLE_NAMES)]
        # Scatter around farm centre (within ~500m)
        lat = farm_lat + random.uniform(-0.005, 0.005)
        lon = farm_lon + random.uniform(-0.005, 0.005)
        animal = SimulatedAnimal(
            device_id=device_base + i,
            name=name,
            lat=lat,
            lon=lon,
            battery_pct=random.randint(60, 100),
        )
        sim_animals.append(animal)
        print(f"  Created: {name} (device={animal.device_id:04X}) @ ({lat:.5f}, {lon:.5f})")

    print(f"\nStarting simulation ({duration}s, interval={interval}s)...\n")

    try:
        if scenario == 'normal':
            run_normal_scenario(sim_animals, client, duration, interval)
        elif scenario == 'theft':
            run_theft_scenario(sim_animals, client, duration, interval)
        elif scenario == 'breach':
            run_breach_scenario(sim_animals, client, duration, interval)
        elif scenario == 'night':
            # Same as normal but sets timestamp to 2am
            run_normal_scenario(sim_animals, client, duration, interval)
    except KeyboardInterrupt:
        print("\nSimulation stopped by user")
    finally:
        client.loop_stop()
        client.disconnect()
        print("Disconnected from MQTT broker")


if __name__ == '__main__':
    main()
