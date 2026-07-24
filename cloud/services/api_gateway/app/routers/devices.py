from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

router = APIRouter()


class DeviceCreate(BaseModel):
    serial_number: str
    device_type: str  # "collar" | "eartag"
    firmware_version: Optional[str] = None


class DeviceUpdate(BaseModel):
    name: Optional[str] = None
    animal_id: Optional[UUID] = None
    firmware_version: Optional[str] = None


class DeviceConfig(BaseModel):
    report_interval_s: int = 300
    gnss_mode: str = "adaptive"
    geofence_check_interval_s: int = 60
    acceleration_threshold_mg: int = 500


class DeviceCommand(BaseModel):
    command: str  # "reboot" | "locate" | "update_firmware" | "factory_reset"
    params: Optional[dict] = None


class ActivateRequest(BaseModel):
    serial_number: str
    activation_code: str
    farm_id: UUID


@router.get("/")
async def list_devices(
    farm_id: Optional[UUID] = None,
    device_type: Optional[str] = None,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
):
    """List all devices, optionally filtered by farm or type."""
    return {"devices": [], "total": 0, "limit": limit, "offset": offset}


@router.post("/", status_code=201)
async def create_device(device: DeviceCreate):
    """Register a new device."""
    return {"id": "placeholder", **device.model_dump()}


@router.get("/{device_id}")
async def get_device(device_id: UUID):
    """Get device details."""
    return {"id": str(device_id), "serial_number": "", "device_type": "collar"}


@router.put("/{device_id}")
async def update_device(device_id: UUID, update: DeviceUpdate):
    """Update device metadata."""
    return {"id": str(device_id), **update.model_dump(exclude_none=True)}


@router.delete("/{device_id}", status_code=204)
async def delete_device(device_id: UUID):
    """Remove a device."""
    return None


@router.get("/{device_id}/positions")
async def get_device_positions(
    device_id: UUID,
    start: Optional[str] = None,
    end: Optional[str] = None,
    limit: int = Query(default=100, le=1000),
):
    """Get historical position data for a device."""
    return {"device_id": str(device_id), "positions": [], "count": 0}


@router.put("/{device_id}/config")
async def update_device_config(device_id: UUID, config: DeviceConfig):
    """Update device configuration (pushed via MQTT)."""
    return {"device_id": str(device_id), "config": config.model_dump()}


@router.post("/{device_id}/command")
async def send_device_command(device_id: UUID, command: DeviceCommand):
    """Send a command to a device."""
    return {"device_id": str(device_id), "command": command.command, "status": "queued"}


@router.post("/activate")
async def activate_device(request: ActivateRequest):
    """Activate a device with an activation code and assign to farm."""
    return {"serial_number": request.serial_number, "status": "activated"}
