"""
Herdsman Gateway router — handles BLE ear tag sighting ingestion,
gateway registration, and status queries.

The herdsman carries a gateway device (phone or dedicated hardware) that:
1. Scans for BLE advertisements from passive cattle ear tags
2. Records its own GPS position
3. Sends batch sightings to this API at regular intervals
"""

import os
import sys
from datetime import datetime, timezone, date
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, text, func, update
from sqlalchemy.ext.asyncio import AsyncSession

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'shared'))

from livestockguard_common.db_models import (
    GatewayDevice, BleEarTag, BleSighting, HerdsmanSession, Animal,
)
from app.dependencies import get_db

router = APIRouter()


# ─── Request/Response Models ─────────────────────────────────────────────────


class BleTagSighting(BaseModel):
    """Single BLE tag detection within a batch."""
    mac_address: str = Field(..., description="BLE MAC address e.g. AA:BB:CC:DD:EE:FF")
    rssi: int = Field(..., description="Signal strength in dBm (e.g. -65)")
    timestamp: Optional[str] = None  # ISO format; defaults to server time if omitted


class BatchSightingRequest(BaseModel):
    """Batch of BLE sightings from a gateway device."""
    gateway_serial: str = Field(..., description="Gateway serial number")
    latitude: float = Field(..., description="Gateway GPS latitude")
    longitude: float = Field(..., description="Gateway GPS longitude")
    altitude: Optional[float] = None
    speed: Optional[float] = None  # km/h (herdsman walking speed)
    battery_pct: Optional[int] = None
    session_id: Optional[str] = None  # Active patrol session UUID
    sightings: List[BleTagSighting] = Field(..., description="BLE tags detected in this scan")


class BatchSightingResponse(BaseModel):
    accepted: int  # Number of sightings stored
    resolved: int  # Number resolved to a known animal
    unresolved_macs: List[str]  # MACs not mapped to any animal
    gateway_id: str
    timestamp: str


class GatewayRegisterRequest(BaseModel):
    farm_id: UUID
    serial_number: str
    name: str
    device_type: str = "phone"  # phone | dedicated_hardware
    herdsman_name: Optional[str] = None
    herdsman_phone: Optional[str] = None
    ble_scan_interval_ms: int = 5000
    report_interval_sec: int = 30


class GatewayResponse(BaseModel):
    id: str
    farm_id: str
    serial_number: str
    name: str
    device_type: str
    herdsman_name: Optional[str] = None
    herdsman_phone: Optional[str] = None
    status: str
    last_seen: Optional[str] = None
    last_latitude: Optional[float] = None
    last_longitude: Optional[float] = None
    last_battery_pct: Optional[int] = None
    ble_scan_interval_ms: int
    report_interval_sec: int
    max_ble_range_m: int
    animals_in_range: int = 0

    class Config:
        from_attributes = True


class AnimalSighting(BaseModel):
    animal_id: str
    animal_name: str
    tag_id: str
    mac_address: str
    last_seen: str
    rssi: int
    estimated_distance_m: Optional[float] = None
    latitude: float
    longitude: float


class GatewayStatusResponse(BaseModel):
    gateway: GatewayResponse
    active_session: Optional[dict] = None
    recent_animals: List[AnimalSighting]
    total_sightings_today: int
    unique_animals_today: int


class BleTagRegisterRequest(BaseModel):
    farm_id: UUID
    animal_id: Optional[UUID] = None
    mac_address: str
    tag_name: Optional[str] = None
    manufacturer: Optional[str] = None


class BleTagResponse(BaseModel):
    id: str
    farm_id: str
    animal_id: Optional[str] = None
    animal_name: Optional[str] = None
    mac_address: str
    tag_name: Optional[str] = None
    status: str

    class Config:
        from_attributes = True


class SessionStartRequest(BaseModel):
    gateway_serial: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    herdsman_name: Optional[str] = None


class SessionEndRequest(BaseModel):
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    notes: Optional[str] = None


# ─── Batch Sighting Ingestion ─────────────────────────────────────────────────


@router.post("/batch", response_model=BatchSightingResponse)
async def ingest_batch(req: BatchSightingRequest, db: AsyncSession = Depends(get_db)):
    """
    Ingest a batch of BLE sightings from a gateway device.

    The gateway sends its GPS position and all BLE MACs it detected.
    The system resolves MACs to known animals and stores positions.
    """
    # Find gateway by serial
    result = await db.execute(
        select(GatewayDevice).where(GatewayDevice.serial_number == req.gateway_serial)
    )
    gateway = result.scalar_one_or_none()
    if not gateway:
        raise HTTPException(status_code=404, detail=f"Gateway '{req.gateway_serial}' not found. Register it first.")

    # Update gateway last-seen position
    gateway.last_seen = datetime.now(timezone.utc)
    gateway.last_latitude = req.latitude
    gateway.last_longitude = req.longitude
    gateway.last_battery_pct = req.battery_pct

    # Pre-load BLE tag→animal mapping for this farm
    tag_result = await db.execute(
        select(BleEarTag).where(
            BleEarTag.farm_id == gateway.farm_id,
            BleEarTag.status == "active",
        )
    )
    tags = {t.mac_address.upper(): t for t in tag_result.scalars().all()}

    now = datetime.now(timezone.utc)
    accepted = 0
    resolved = 0
    unresolved_macs = []

    for sighting in req.sightings:
        mac = sighting.mac_address.upper()
        tag = tags.get(mac)
        animal_id = tag.animal_id if tag else None

        # Calculate estimated distance from RSSI (log-distance path loss model)
        # d = 10 ^ ((TxPower - RSSI) / (10 * n))
        # Assuming TxPower=-59 dBm at 1m, n=2.0 (free space)
        tx_power = -59
        n = 2.0
        estimated_distance = None
        if sighting.rssi < 0:
            estimated_distance = round(10 ** ((tx_power - sighting.rssi) / (10 * n)), 1)

        # Parse timestamp or use server time
        sighting_time = now
        if sighting.timestamp:
            try:
                sighting_time = datetime.fromisoformat(sighting.timestamp.replace('Z', '+00:00'))
            except ValueError:
                pass

        # Insert sighting
        new_sighting = BleSighting(
            time=sighting_time,
            gateway_id=gateway.id,
            ble_tag_id=tag.id if tag else None,
            mac_address=mac,
            animal_id=animal_id,
            rssi=sighting.rssi,
            estimated_distance_m=estimated_distance,
            gateway_latitude=req.latitude,
            gateway_longitude=req.longitude,
            gateway_altitude=req.altitude,
            gateway_speed=req.speed,
            gateway_battery_pct=req.battery_pct,
        )
        db.add(new_sighting)
        accepted += 1

        if animal_id:
            resolved += 1
        else:
            if mac not in unresolved_macs:
                unresolved_macs.append(mac)

    # Update session counters if session is active
    if req.session_id:
        session_result = await db.execute(
            select(HerdsmanSession).where(
                HerdsmanSession.id == req.session_id,
                HerdsmanSession.status == "active",
            )
        )
        session = session_result.scalar_one_or_none()
        if session:
            session.total_sightings = (session.total_sightings or 0) + accepted
            session.animals_seen = (session.animals_seen or 0) + resolved

    await db.commit()

    # Also insert into positions table so animals show on the main map
    # (uses gateway GPS as the animal's position)
    if resolved > 0:
        for sighting in req.sightings:
            mac = sighting.mac_address.upper()
            tag = tags.get(mac)
            if tag and tag.animal_id:
                await db.execute(text("""
                    INSERT INTO positions (time, device_id, animal_id, location, latitude, longitude, altitude, speed, signal_rssi)
                    VALUES (:time, NULL, :animal_id,
                            ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
                            :lat, :lon, :alt, :speed, :rssi)
                """), {
                    "time": now.isoformat(),
                    "animal_id": str(tag.animal_id),
                    "lat": req.latitude,
                    "lon": req.longitude,
                    "alt": req.altitude,
                    "speed": req.speed,
                    "rssi": sighting.rssi,
                })
        await db.commit()

    return BatchSightingResponse(
        accepted=accepted,
        resolved=resolved,
        unresolved_macs=unresolved_macs,
        gateway_id=str(gateway.id),
        timestamp=now.isoformat(),
    )


# ─── Gateway Registration ────────────────────────────────────────────────────


@router.post("/register", response_model=GatewayResponse, status_code=201)
async def register_gateway(req: GatewayRegisterRequest, db: AsyncSession = Depends(get_db)):
    """Register a new gateway device for a farm."""
    # Check if serial already exists
    existing = await db.execute(
        select(GatewayDevice).where(GatewayDevice.serial_number == req.serial_number)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Gateway with this serial number already exists")

    gateway = GatewayDevice(
        farm_id=req.farm_id,
        serial_number=req.serial_number,
        name=req.name,
        device_type=req.device_type,
        herdsman_name=req.herdsman_name,
        herdsman_phone=req.herdsman_phone,
        ble_scan_interval_ms=req.ble_scan_interval_ms,
        report_interval_sec=req.report_interval_sec,
        status="active",
    )
    db.add(gateway)
    await db.commit()
    await db.refresh(gateway)

    return GatewayResponse(
        id=str(gateway.id),
        farm_id=str(gateway.farm_id),
        serial_number=gateway.serial_number,
        name=gateway.name,
        device_type=gateway.device_type,
        herdsman_name=gateway.herdsman_name,
        herdsman_phone=gateway.herdsman_phone,
        status=gateway.status,
        ble_scan_interval_ms=gateway.ble_scan_interval_ms,
        report_interval_sec=gateway.report_interval_sec,
        max_ble_range_m=gateway.max_ble_range_m,
    )


# ─── BLE Tag Registration ────────────────────────────────────────────────────


@router.post("/tags", response_model=BleTagResponse, status_code=201)
async def register_ble_tag(req: BleTagRegisterRequest, db: AsyncSession = Depends(get_db)):
    """Register a new BLE ear tag and optionally link it to an animal."""
    existing = await db.execute(
        select(BleEarTag).where(BleEarTag.mac_address == req.mac_address.upper())
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="BLE tag with this MAC already registered")

    tag = BleEarTag(
        farm_id=req.farm_id,
        animal_id=req.animal_id,
        mac_address=req.mac_address.upper(),
        tag_name=req.tag_name,
        manufacturer=req.manufacturer,
        installed_date=date.today(),
        status="active",
    )
    db.add(tag)
    await db.commit()
    await db.refresh(tag)

    # Get animal name if linked
    animal_name = None
    if tag.animal_id:
        animal_result = await db.execute(select(Animal.name).where(Animal.id == tag.animal_id))
        row = animal_result.first()
        if row:
            animal_name = row.name

    return BleTagResponse(
        id=str(tag.id),
        farm_id=str(tag.farm_id),
        animal_id=str(tag.animal_id) if tag.animal_id else None,
        animal_name=animal_name,
        mac_address=tag.mac_address,
        tag_name=tag.tag_name,
        status=tag.status,
    )


@router.get("/tags", response_model=List[BleTagResponse])
async def list_ble_tags(
    farm_id: Optional[UUID] = None,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """List registered BLE ear tags."""
    query = select(BleEarTag, Animal.name.label("animal_name")).outerjoin(
        Animal, BleEarTag.animal_id == Animal.id
    )
    if farm_id:
        query = query.where(BleEarTag.farm_id == farm_id)
    if status:
        query = query.where(BleEarTag.status == status)

    result = await db.execute(query)
    rows = result.all()

    return [
        BleTagResponse(
            id=str(row.BleEarTag.id),
            farm_id=str(row.BleEarTag.farm_id),
            animal_id=str(row.BleEarTag.animal_id) if row.BleEarTag.animal_id else None,
            animal_name=row.animal_name,
            mac_address=row.BleEarTag.mac_address,
            tag_name=row.BleEarTag.tag_name,
            status=row.BleEarTag.status,
        )
        for row in rows
    ]


# ─── Gateway Status ──────────────────────────────────────────────────────────


@router.get("/status/{gateway_serial}", response_model=GatewayStatusResponse)
async def get_gateway_status(gateway_serial: str, db: AsyncSession = Depends(get_db)):
    """Get gateway status including recent animal sightings."""
    result = await db.execute(
        select(GatewayDevice).where(GatewayDevice.serial_number == gateway_serial)
    )
    gateway = result.scalar_one_or_none()
    if not gateway:
        raise HTTPException(status_code=404, detail="Gateway not found")

    # Get recent animal sightings (last 1 hour, deduplicated by animal)
    recent_query = text("""
        SELECT DISTINCT ON (s.animal_id)
            s.animal_id, a.name AS animal_name, a.tag_id,
            s.mac_address, s.time AS last_seen, s.rssi,
            s.estimated_distance_m, s.gateway_latitude, s.gateway_longitude
        FROM ble_sightings s
        JOIN animals a ON a.id = s.animal_id
        WHERE s.gateway_id = :gateway_id
          AND s.animal_id IS NOT NULL
          AND s.time > NOW() - INTERVAL '1 hour'
        ORDER BY s.animal_id, s.time DESC
    """)
    recent_result = await db.execute(recent_query, {"gateway_id": str(gateway.id)})
    recent_rows = recent_result.fetchall()

    recent_animals = [
        AnimalSighting(
            animal_id=str(row.animal_id),
            animal_name=row.animal_name,
            tag_id=row.tag_id,
            mac_address=row.mac_address,
            last_seen=row.last_seen.isoformat(),
            rssi=row.rssi,
            estimated_distance_m=row.estimated_distance_m,
            latitude=row.gateway_latitude,
            longitude=row.gateway_longitude,
        )
        for row in recent_rows
    ]

    # Today's stats
    stats_query = text("""
        SELECT
            COUNT(*) AS total_sightings,
            COUNT(DISTINCT animal_id) AS unique_animals
        FROM ble_sightings
        WHERE gateway_id = :gateway_id
          AND time > CURRENT_DATE
    """)
    stats_result = await db.execute(stats_query, {"gateway_id": str(gateway.id)})
    stats = stats_result.first()

    # Active session
    session_result = await db.execute(
        select(HerdsmanSession).where(
            HerdsmanSession.gateway_id == gateway.id,
            HerdsmanSession.status == "active",
        ).order_by(HerdsmanSession.started_at.desc()).limit(1)
    )
    active_session = session_result.scalar_one_or_none()
    session_data = None
    if active_session:
        session_data = {
            "id": str(active_session.id),
            "started_at": active_session.started_at.isoformat(),
            "herdsman_name": active_session.herdsman_name,
            "animals_seen": active_session.animals_seen,
            "total_sightings": active_session.total_sightings,
        }

    return GatewayStatusResponse(
        gateway=GatewayResponse(
            id=str(gateway.id),
            farm_id=str(gateway.farm_id),
            serial_number=gateway.serial_number,
            name=gateway.name,
            device_type=gateway.device_type,
            herdsman_name=gateway.herdsman_name,
            herdsman_phone=gateway.herdsman_phone,
            status=gateway.status,
            last_seen=gateway.last_seen.isoformat() if gateway.last_seen else None,
            last_latitude=gateway.last_latitude,
            last_longitude=gateway.last_longitude,
            last_battery_pct=gateway.last_battery_pct,
            ble_scan_interval_ms=gateway.ble_scan_interval_ms,
            report_interval_sec=gateway.report_interval_sec,
            max_ble_range_m=gateway.max_ble_range_m,
            animals_in_range=len(recent_animals),
        ),
        active_session=session_data,
        recent_animals=recent_animals,
        total_sightings_today=stats.total_sightings if stats else 0,
        unique_animals_today=stats.unique_animals if stats else 0,
    )


# ─── List Gateways ───────────────────────────────────────────────────────────


@router.get("", response_model=List[GatewayResponse])
async def list_gateways(
    farm_id: Optional[UUID] = None,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """List all gateway devices for a farm."""
    query = select(GatewayDevice)
    if farm_id:
        query = query.where(GatewayDevice.farm_id == farm_id)
    if status:
        query = query.where(GatewayDevice.status == status)

    result = await db.execute(query)
    gateways = result.scalars().all()

    return [
        GatewayResponse(
            id=str(g.id),
            farm_id=str(g.farm_id),
            serial_number=g.serial_number,
            name=g.name,
            device_type=g.device_type,
            herdsman_name=g.herdsman_name,
            herdsman_phone=g.herdsman_phone,
            status=g.status,
            last_seen=g.last_seen.isoformat() if g.last_seen else None,
            last_latitude=g.last_latitude,
            last_longitude=g.last_longitude,
            last_battery_pct=g.last_battery_pct,
            ble_scan_interval_ms=g.ble_scan_interval_ms,
            report_interval_sec=g.report_interval_sec,
            max_ble_range_m=g.max_ble_range_m,
        )
        for g in gateways
    ]


# ─── Sessions (Patrol Tracking) ──────────────────────────────────────────────


@router.post("/sessions/start", status_code=201)
async def start_session(req: SessionStartRequest, db: AsyncSession = Depends(get_db)):
    """Start a new herdsman patrol session."""
    gw_result = await db.execute(
        select(GatewayDevice).where(GatewayDevice.serial_number == req.gateway_serial)
    )
    gateway = gw_result.scalar_one_or_none()
    if not gateway:
        raise HTTPException(status_code=404, detail="Gateway not found")

    session = HerdsmanSession(
        gateway_id=gateway.id,
        farm_id=gateway.farm_id,
        herdsman_name=req.herdsman_name or gateway.herdsman_name,
        start_latitude=req.latitude,
        start_longitude=req.longitude,
        status="active",
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)

    return {
        "session_id": str(session.id),
        "gateway_id": str(gateway.id),
        "started_at": session.started_at.isoformat(),
        "herdsman_name": session.herdsman_name,
    }


@router.post("/sessions/{session_id}/end")
async def end_session(session_id: UUID, req: SessionEndRequest, db: AsyncSession = Depends(get_db)):
    """End a patrol session."""
    result = await db.execute(
        select(HerdsmanSession).where(HerdsmanSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.status != "active":
        raise HTTPException(status_code=400, detail="Session is not active")

    session.status = "completed"
    session.ended_at = datetime.now(timezone.utc)
    session.end_latitude = req.latitude
    session.end_longitude = req.longitude
    session.notes = req.notes

    await db.commit()
    await db.refresh(session)

    return {
        "session_id": str(session.id),
        "status": session.status,
        "started_at": session.started_at.isoformat(),
        "ended_at": session.ended_at.isoformat(),
        "animals_seen": session.animals_seen,
        "total_sightings": session.total_sightings,
    }
