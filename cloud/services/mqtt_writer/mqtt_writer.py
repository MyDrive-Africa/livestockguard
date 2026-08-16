#!/usr/bin/env python3
"""
LivestockGuard MQTT → Database Writer

Subscribes to device MQTT topics, decodes binary messages,
and writes position/alert data to TimescaleDB.

This is the critical bridge between devices (or simulator) and the database.
"""

import asyncio
import json
import os
import struct
import time
from datetime import datetime, timezone
from typing import Optional

import asyncpg
import paho.mqtt.client as mqtt
import redis.asyncio as aioredis
import click

# Configuration
MQTT_BROKER = os.environ.get("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://livestockguard:livestockguard_dev@localhost:5432/livestockguard"
)
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

# Protocol constants
PROTOCOL_VERSION = 0x01
MSG_POSITION_BATCH = 0x01
MSG_GEOFENCE_ALERT = 0x02
MSG_THEFT_ALERT = 0x03
MSG_HEARTBEAT = 0x04

# Globals
db_pool: Optional[asyncpg.Pool] = None
redis_client: Optional[aioredis.Redis] = None
loop: Optional[asyncio.AbstractEventLoop] = None
stats = {"positions": 0, "alerts": 0, "errors": 0}


def crc16_ccitt(data: bytes) -> int:
    """
    Compute CRC-16/CCITT checksum for binary message integrity verification.

    Args:
        data: Raw bytes to checksum (typically the full message minus the trailing 2 CRC bytes).

    Returns:
        16-bit unsigned integer CRC value. Must match the CRC appended by the device firmware.
    """
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
    """
    Decode the 11-byte binary message header.

    Args:
        data: Raw message bytes (at least 11 bytes required).

    Returns:
        Dict with keys: version, msg_type, priority, device_id, timestamp,
        sequence, payload_len. Returns None if data is too short or version
        does not match PROTOCOL_VERSION (0x01).
    """
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
    """
    Decode a single 16-byte position record from the payload.

    Args:
        data: Raw payload bytes containing one or more position records.
        offset: Byte offset within data where this record starts (default: 0).

    Returns:
        Dict with keys: timestamp (datetime UTC), latitude (float degrees),
        longitude (float degrees), speed (km/h), heading (0-360 degrees),
        hdop (float), flags (uint8). Returns None if insufficient data.
    """
    if len(data) < offset + 16:
        return None

    ts, lat_offset, lon_offset, speed, heading, hdop_x10, flags = \
        struct.unpack_from('<iiiBBBB', data, offset)

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


async def publish_realtime(channel: str, message: dict):
    """
    Publish a real-time event to Redis pub/sub for WebSocket fan-out.

    Args:
        channel: Redis channel name (e.g., 'farm:<uuid>' or 'alerts:incoming').
        message: Dict payload to JSON-serialize and publish.

    Notes:
        Fails silently if Redis is unavailable — real-time updates are
        best-effort and should not block telemetry ingestion.
    """
    global redis_client
    if redis_client is None:
        return
    try:
        await redis_client.publish(channel, json.dumps(message))
    except Exception as e:
        print(f"  WARN Redis publish failed: {e}")


async def write_position(device_id: int, position: dict):
    """
    Persist a decoded GPS position to TimescaleDB and broadcast via Redis.

    Args:
        device_id: Numeric device identifier (u16 from the binary header).
        position: Decoded position dict with keys: timestamp, latitude, longitude,
                  speed, heading, hdop, flags (as returned by decode_position_record).

    Side Effects:
        - INSERTs into the `positions` hypertable (TimescaleDB).
        - Publishes 'position.update' event to Redis `farm:<farm_id>` channel.
        - Increments stats['positions'] on success, stats['errors'] on failure.
        - Auto-registers unknown devices via get_device_uuid.
    """
    global db_pool, stats

    if db_pool is None:
        return

    try:
        async with db_pool.acquire() as conn:
            device_uuid = await get_device_uuid(conn, device_id)
            # Look up linked animal
            row = await conn.fetchrow(
                "SELECT d.animal_id, d.farm_id, a.name as animal_name "
                "FROM devices d LEFT JOIN animals a ON d.animal_id = a.id "
                "WHERE d.id = $1", device_uuid
            )
            animal_id = row["animal_id"] if row else None
            farm_id = row["farm_id"] if row else None
            animal_name = row["animal_name"] if row else f"Device-{device_id:04X}"

            await conn.execute("""
                INSERT INTO positions (time, device_id, animal_id, location, latitude, longitude,
                                       speed, heading, hdop, battery_mv)
                VALUES ($1, $2, $3, ST_SetSRID(ST_MakePoint($5, $4), 4326)::geography,
                        $4, $5, $6, $7, $8, $9)
            """,
                position["timestamp"],
                device_uuid,
                animal_id,
                position["latitude"],
                position["longitude"],
                position["speed"],
                position["heading"],
                position["hdop"],
                3700,  # Default battery mV
            )

        stats["positions"] += 1

        # Publish to Redis for real-time WebSocket distribution
        if farm_id:
            await publish_realtime(f"farm:{farm_id}", {
                "type": "position.update",
                "payload": {
                    "animalId": str(animal_id) if animal_id else str(device_uuid),
                    "animalName": animal_name,
                    "position": {
                        "latitude": position["latitude"],
                        "longitude": position["longitude"],
                        "speed": position["speed"],
                        "heading": position["heading"],
                    },
                    "batteryLevel": int(3700 / 37),  # Convert mV to %
                },
            })
    except Exception as e:
        stats["errors"] += 1
        print(f"  ERROR writing position: {e}")


async def write_alert(device_id: int, alert_type: str, severity: str, message: str):
    """
    Persist an alert to PostgreSQL and broadcast via Redis for real-time + notification dispatch.

    Args:
        device_id: Numeric device identifier (u16 from the binary header).
        alert_type: Alert category string (e.g., 'geofence_breach', 'theft_detected').
        severity: Alert severity level ('critical', 'high', 'medium', 'low', 'info').
        message: Human-readable alert description shown in the dashboard.

    Side Effects:
        - INSERTs into the `alerts` table with status='active'.
        - Publishes 'alert.created' event to Redis `farm:<farm_id>` channel (dashboard WebSocket).
        - Publishes to Redis `alerts:incoming` channel (Alert Engine picks up for email/push/SMS).
        - Increments stats['alerts'] on success, stats['errors'] on failure.
    """
    global db_pool, stats

    if db_pool is None:
        return

    try:
        async with db_pool.acquire() as conn:
            device_uuid = await get_device_uuid(conn, device_id)
            # Get farm_id and animal info from device
            row = await conn.fetchrow(
                "SELECT d.farm_id, d.animal_id, a.name as animal_name "
                "FROM devices d LEFT JOIN animals a ON d.animal_id = a.id "
                "WHERE d.id = $1", device_uuid
            )
            farm_id = row["farm_id"] if row else None
            animal_name = row["animal_name"] if row else None

            if farm_id is None:
                return

            alert_id = await conn.fetchval("""
                INSERT INTO alerts (farm_id, device_id, alert_type, severity, status, message)
                VALUES ($1, $2, $3, $4, 'active', $5)
                RETURNING id
            """, farm_id, device_uuid, alert_type, severity, message)

        stats["alerts"] += 1

        # Publish alert to Redis for WebSocket distribution
        if farm_id:
            await publish_realtime(f"farm:{farm_id}", {
                "type": "alert.created",
                "payload": {
                    "id": str(alert_id),
                    "alert_type": alert_type,
                    "severity": severity,
                    "status": "active",
                    "message": message,
                    "animal_name": animal_name,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                },
            })

            # Also publish to alert engine channel for email/push/SMS dispatch
            await publish_realtime("alerts:incoming", {
                "alert_type": alert_type,
                "severity": severity,
                "device_id": f"{device_id:04X}",
                "farm_id": str(farm_id),
                "animal_id": str(row["animal_id"]) if row and row["animal_id"] else None,
                "message": message,
                "metadata": {
                    "alert_id": str(alert_id),
                    "animal_name": animal_name,
                },
                "timestamp": datetime.now(timezone.utc).timestamp(),
            })
    except Exception as e:
        stats["errors"] += 1
        print(f"  ERROR writing alert: {e}")


async def get_device_uuid(conn, device_id: int):
    """
    Resolve a numeric device ID to its PostgreSQL UUID, auto-registering if unknown.

    Args:
        conn: Active asyncpg connection (from pool.acquire()).
        device_id: Numeric device identifier (u16) — converted to hex serial (e.g., '001A').

    Returns:
        UUID of the device row in the `devices` table.

    Notes:
        If no device exists with the given serial, one is auto-created with
        type='collar', status='active', assigned to the first available farm.
        Also updates `last_seen` timestamp on every lookup.
    """
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
    """
    MQTT message callback — decode binary payload and dispatch to async DB writer.

    Args:
        client: paho-mqtt Client instance.
        userdata: User-defined data (unused).
        msg: MQTTMessage with .topic (str) and .payload (bytes).

    Processing pipeline:
        1. Verify minimum message length (header + CRC = 13 bytes).
        2. Validate CRC-16/CCITT integrity.
        3. Decode header to determine message type.
        4. For MSG_POSITION_BATCH: decode each 16-byte position record, write to DB.
        5. For MSG_GEOFENCE_ALERT: create a critical geofence breach alert.
        6. For MSG_THEFT_ALERT: create a critical theft alert.
        7. For MSG_HEARTBEAT: no-op (device last_seen updated via get_device_uuid).
    """
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
    global db_pool, redis_client, loop
    loop = asyncio.get_event_loop()

    # Connect to database
    print(f"Connecting to database: {db_url.split('@')[1] if '@' in db_url else db_url}")
    db_pool = await asyncpg.create_pool(db_url, min_size=2, max_size=10)
    print("Database connected")

    # Connect to Redis for real-time pub/sub
    print(f"Connecting to Redis: {REDIS_URL}")
    redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)
    await redis_client.ping()
    print("Redis connected")

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
