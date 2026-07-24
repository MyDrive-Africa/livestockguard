#!/usr/bin/env python3
"""
LivestockGuard MQTT → Database Writer

Subscribes to device MQTT topics, decodes binary messages,
and writes position/alert data to TimescaleDB.

This is the critical bridge between devices (or simulator) and the database.
"""

import asyncio
import os
import struct
import time
from datetime import datetime, timezone
from typing import Optional

import asyncpg
import paho.mqtt.client as mqtt
import click

# Configuration
MQTT_BROKER = os.environ.get("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://livestockguard:livestockguard_dev@localhost:5432/livestockguard"
)

# Protocol constants
PROTOCOL_VERSION = 0x01
MSG_POSITION_BATCH = 0x01
MSG_GEOFENCE_ALERT = 0x02
MSG_THEFT_ALERT = 0x03
MSG_HEARTBEAT = 0x04

# Globals
db_pool: Optional[asyncpg.Pool] = None
loop: Optional[asyncio.AbstractEventLoop] = None
stats = {"positions": 0, "alerts": 0, "errors": 0}


def crc16_ccitt(data: bytes) -> int:
    """Verify CRC-16/CCITT."""
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


def decode_header(data: bytes) -> dict:
    """Decode message header (11 bytes)."""
    if len(data) < 11:
        return None

    version, msg_type, priority, device_id, timestamp, seq, payload_len = \
        struct.unpack_from('<BBBHIBb', data, 0)

    if version != PROTOCOL_VERSION:
        return None

    return {
        "version": version,
        "msg_type": msg_type,
        "priority": priority,
        "device_id": device_id,
        "timestamp": timestamp,
        "sequence": seq,
        "payload_len": payload_len,
    }


def decode_position_record(data: bytes, offset: int = 0) -> dict:
    """Decode a single position record (16 bytes)."""
    if len(data) < offset + 16:
        return None

    ts, lat_offset, lon_offset, speed, heading, hdop_x10, flags = \
        struct.unpack_from('<iiibbbb', data, offset)

    # Convert offsets back to absolute coordinates
    # (In production, we'd store reference point per device)
    # For simulator, offsets ARE absolute since ref is 0
    lat = lat_offset / 1e7
    lon = lon_offset / 1e7

    return {
        "timestamp": datetime.fromtimestamp(ts, tz=timezone.utc) if ts > 1000000000 else datetime.now(timezone.utc),
        "latitude": lat,
        "longitude": lon,
        "speed": float(speed),
        "heading": float(heading) * 360.0 / 255.0,
        "hdop": float(hdop_x10) / 10.0,
        "flags": flags,
    }


async def write_position(device_id: int, position: dict):
    """Write a position record to TimescaleDB."""
    global db_pool, stats

    if db_pool is None:
        return

    try:
        async with db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO positions (time, device_id, latitude, longitude,
                                       speed, heading, hdop, battery_mv)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """,
                position["timestamp"],
                # Map device_id int to UUID (lookup or create)
                await get_device_uuid(conn, device_id),
                position["latitude"],
                position["longitude"],
                position["speed"],
                position["heading"],
                position["hdop"],
                3700,  # Default battery mV
            )
        stats["positions"] += 1
    except Exception as e:
        stats["errors"] += 1
        print(f"  ERROR writing position: {e}")


async def write_alert(device_id: int, alert_type: str, severity: str, message: str):
    """Write an alert record."""
    global db_pool, stats

    if db_pool is None:
        return

    try:
        async with db_pool.acquire() as conn:
            device_uuid = await get_device_uuid(conn, device_id)
            # Get farm_id from device
            farm_id = await conn.fetchval(
                "SELECT farm_id FROM devices WHERE id = $1", device_uuid
            )
            if farm_id is None:
                return

            await conn.execute("""
                INSERT INTO alerts (farm_id, device_id, alert_type, severity, status, message)
                VALUES ($1, $2, $3, $4, 'active', $5)
            """, farm_id, device_uuid, alert_type, severity, message)
        stats["alerts"] += 1
    except Exception as e:
        stats["errors"] += 1
        print(f"  ERROR writing alert: {e}")


async def get_device_uuid(conn, device_id: int):
    """Look up device UUID from serial number (device_id as hex)."""
    serial = f"{device_id:04X}"
    uuid = await conn.fetchval(
        "SELECT id FROM devices WHERE serial_number = $1", serial
    )
    if uuid is None:
        # Auto-register device if not found
        uuid = await conn.fetchval("""
            INSERT INTO devices (serial_number, device_type, status, farm_id)
            SELECT $1, 'collar', 'active', (SELECT id FROM farms LIMIT 1)
            ON CONFLICT (serial_number) DO UPDATE SET last_seen = NOW()
            RETURNING id
        """, serial)
    else:
        await conn.execute(
            "UPDATE devices SET last_seen = NOW() WHERE id = $1", uuid
        )
    return uuid


def on_message(client, userdata, msg):
    """MQTT message callback — decode and dispatch to DB writer."""
    global loop

    try:
        data = msg.payload
        if len(data) < 13:  # Minimum: header + CRC
            return

        # Verify CRC
        msg_body = data[:-2]
        received_crc = struct.unpack_from('>H', data, len(data) - 2)[0]
        computed_crc = crc16_ccitt(msg_body)

        if received_crc != computed_crc:
            stats["errors"] += 1
            return

        # Decode header
        header = decode_header(data)
        if header is None:
            return

        device_id = header["device_id"]
        msg_type = header["msg_type"]
        payload = data[11:-2]  # Between header and CRC

        if msg_type == MSG_POSITION_BATCH:
            # Decode position records
            record_size = 16
            for offset in range(0, len(payload), record_size):
                position = decode_position_record(payload, offset)
                if position:
                    asyncio.run_coroutine_threadsafe(
                        write_position(device_id, position), loop
                    )

        elif msg_type == MSG_GEOFENCE_ALERT:
            message = f"Geofence breach detected (device {device_id:04X})"
            asyncio.run_coroutine_threadsafe(
                write_alert(device_id, "geofence_breach", "critical", message), loop
            )
            print(f"  🚨 GEOFENCE BREACH: device {device_id:04X}")

        elif msg_type == MSG_THEFT_ALERT:
            message = f"Theft detected - vehicle speed (device {device_id:04X})"
            asyncio.run_coroutine_threadsafe(
                write_alert(device_id, "theft_detected", "critical", message), loop
            )
            print(f"  🚨 THEFT ALERT: device {device_id:04X}")

        elif msg_type == MSG_HEARTBEAT:
            # Just update last_seen (handled in get_device_uuid)
            pass

    except Exception as e:
        stats["errors"] += 1
        print(f"  ERROR processing message: {e}")


def on_connect(client, userdata, flags, reason_code, properties):
    """MQTT connected — subscribe to device topics."""
    print(f"Connected to MQTT broker (rc={reason_code})")
    client.subscribe("lg/up/+/telemetry", qos=1)
    client.subscribe("lg/up/+/alert", qos=2)
    print("Subscribed to: lg/up/+/telemetry, lg/up/+/alert")


async def print_stats():
    """Periodically print ingestion stats."""
    while True:
        await asyncio.sleep(30)
        print(f"  [STATS] positions={stats['positions']} "
              f"alerts={stats['alerts']} errors={stats['errors']}")


async def main_async(broker: str, port: int, db_url: str):
    """Async main loop."""
    global db_pool, loop
    loop = asyncio.get_event_loop()

    # Connect to database
    print(f"Connecting to database: {db_url.split('@')[1] if '@' in db_url else db_url}")
    db_pool = await asyncpg.create_pool(db_url, min_size=2, max_size=10)
    print("Database connected")

    # Start MQTT client
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="lg-mqtt-writer")
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(broker, port, 60)
    client.loop_start()

    print(f"\nMQTT Writer running. Listening for device messages...")
    print(f"Stats printed every 30 seconds.\n")

    # Run stats printer
    await print_stats()


@click.command()
@click.option('--broker', default=MQTT_BROKER, help='MQTT broker address')
@click.option('--port', default=MQTT_PORT, help='MQTT broker port')
@click.option('--db-url', default=DATABASE_URL, help='PostgreSQL connection URL')
def main(broker, port, db_url):
    """LivestockGuard MQTT → Database Writer"""
    print("LivestockGuard MQTT Writer v1.0")
    print(f"MQTT: {broker}:{port}")
    print(f"Database: {db_url.split('@')[1] if '@' in db_url else db_url}")
    print()

    try:
        asyncio.run(main_async(broker, port, db_url))
    except KeyboardInterrupt:
        print("\nShutting down...")


if __name__ == '__main__':
    main()
