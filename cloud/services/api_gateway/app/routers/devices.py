"""
Device management router — wired to real database.
"""

import json
import os
import sys
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

import paho.mqtt.publish as mqtt_publish
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'shared'))

from livestockguard_common.db_models import Device, Animal
from app.dependencies import get_db, get_current_user

router = APIRouter(dependencies=[Depends(get_current_user)])


class DeviceResponse(BaseModel):
    id: str
    serial_number: str
    device_type: str
    firmware_version: Optional[str] = None
    status: str
    battery_level: Optional[int] = None
    last_seen: Optional[str] = None
    animal_name: Optional[str] = None

    class Config:
        from_attributes = True


class DeviceCommand(BaseModel):
    command: str
    priority: str = "normal"
    params: dict = {}


@router.get("", response_model=List[DeviceResponse])
async def list_devices(
    farm_id: Optional[UUID] = None,
    status: Optional[str] = None,
    limit: int = Query(default=100, le=1000),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """List all devices with optional filters."""
    query = select(Device, Animal.name.label("animal_name")).outerjoin(
        Animal, Device.animal_id == Animal.id
    )

    if farm_id:
        query = query.where(Device.farm_id == farm_id)
    if status:
        query = query.where(Device.status == status)

    query = query.limit(limit).offset(offset)
    result = await db.execute(query)
    rows = result.all()

    return [
        DeviceResponse(
            id=str(row.Device.id),
            serial_number=row.Device.serial_number,
            device_type=row.Device.device_type,
            firmware_version=row.Device.firmware_version,
            status=row.Device.status,
            battery_level=row.Device.battery_level,
            last_seen=row.Device.last_seen.isoformat() if row.Device.last_seen else None,
            animal_name=row.animal_name,
        )
        for row in rows
    ]


@router.get("/{device_id}", response_model=DeviceResponse)
async def get_device(device_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get a single device."""
    result = await db.execute(
        select(Device, Animal.name.label("animal_name"))
        .outerjoin(Animal, Device.animal_id == Animal.id)
        .where(Device.id == device_id)
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Device not found")

    return DeviceResponse(
        id=str(row.Device.id),
        serial_number=row.Device.serial_number,
        device_type=row.Device.device_type,
        firmware_version=row.Device.firmware_version,
        status=row.Device.status,
        battery_level=row.Device.battery_level,
        last_seen=row.Device.last_seen.isoformat() if row.Device.last_seen else None,
        animal_name=row.animal_name,
    )


@router.get("/{device_id}/positions")
async def get_device_positions(
    device_id: UUID,
    from_time: Optional[str] = None,
    to_time: Optional[str] = None,
    limit: int = Query(default=100, le=10000),
    db: AsyncSession = Depends(get_db),
):
    """Get position history for a device from TimescaleDB."""
    query = text("""
        SELECT time, latitude, longitude, altitude, speed, heading,
               battery_mv, signal_rssi
        FROM positions
        WHERE device_id = :device_id
        ORDER BY time DESC
        LIMIT :limit
    """)
    params = {"device_id": str(device_id), "limit": limit}

    result = await db.execute(query, params)
    rows = result.fetchall()

    positions = [
        {
            "time": row.time.isoformat(),
            "latitude": row.latitude,
            "longitude": row.longitude,
            "altitude": row.altitude,
            "speed_kmh": row.speed,
            "heading_deg": row.heading,
            "battery_mv": row.battery_mv,
            "signal_rssi": row.signal_rssi,
        }
        for row in rows
    ]

    return {"device_id": str(device_id), "positions": positions, "count": len(positions)}


@router.post("/{device_id}/command")
async def send_device_command(
    device_id: UUID,
    command: DeviceCommand,
    db: AsyncSession = Depends(get_db),
):
    """
    Send a command to a device via MQTT.

    The command is published to the MQTT topic lg/cmd/{serial_number} as JSON.
    The device (or simulator) subscribes to its command topic and processes it
    on the next check-in.
    """
    # Verify device exists and get its serial number
    result = await db.execute(select(Device).where(Device.id == device_id))
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    # Build command payload
    payload = json.dumps({
        "command": command.command,
        "priority": command.priority,
        "params": command.params,
        "issued_at": datetime.now(timezone.utc).isoformat(),
        "device_id": str(device_id),
    })

    # Publish to MQTT broker
    mqtt_broker = os.environ.get("MQTT_BROKER", "localhost")
    mqtt_port = int(os.environ.get("MQTT_PORT", "1883"))
    topic = f"lg/cmd/{device.serial_number}"

    try:
        mqtt_publish.single(
            topic,
            payload=payload,
            hostname=mqtt_broker,
            port=mqtt_port,
            qos=1,
        )
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to deliver command to MQTT broker: {str(e)}",
        )

    return {
        "status": "delivered",
        "device_id": str(device_id),
        "serial_number": device.serial_number,
        "command": command.command,
        "topic": topic,
    }
