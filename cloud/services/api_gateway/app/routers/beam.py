"""
Beam Sensor router — handles fixed perimeter break-beam sensors and their
line-crossing events.

A beam sensor is mounted at a chokepoint along a farm border (gate, fence gap,
drainage line, known theft path). When something crosses the invisible line
between its transmitter and receiver posts, the beam breaks and the edge
controller posts a crossing event to this API.

Unlike the virtual geofence (a polygon containment check), a beam detects an
instantaneous line crossing. It complements GPS/BLE geofencing: the polygon
watches the whole area, the beams watch the gaps. This is the interim
"border sentinel" layer while a physical fence/wall is built section by section.

Endpoints:
    POST /register        Register a beam sensor for a farm
    GET  /                List beam sensors (optionally by farm)
    GET  /{serial}        Get one beam sensor + recent crossings
    POST /event           Ingest a crossing event (fires an alert)
"""

import os
import sys
import json
import uuid
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'shared'))

from livestockguard_common.db_models import BeamSensor, BeamCrossing, Animal
from app.dependencies import get_db

router = APIRouter()

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

VALID_SEVERITIES = {"critical", "high", "medium", "low", "info"}


# ─── Request/Response Models ─────────────────────────────────────────────────


class BeamRegisterRequest(BaseModel):
    farm_id: UUID
    serial_number: str
    name: str
    beam_type: str = "infrared"  # infrared | microwave | laser
    latitude: float = Field(..., description="Mount (transmitter post) latitude")
    longitude: float = Field(..., description="Mount (transmitter post) longitude")
    span_start_latitude: Optional[float] = None
    span_start_longitude: Optional[float] = None
    span_end_latitude: Optional[float] = None
    span_end_longitude: Optional[float] = None
    orientation_deg: Optional[float] = None
    span_length_m: Optional[float] = None
    breach_severity: str = "high"
    geofence_id: Optional[UUID] = None


class BeamResponse(BaseModel):
    id: str
    farm_id: str
    geofence_id: Optional[str] = None
    serial_number: str
    name: str
    beam_type: str
    latitude: float
    longitude: float
    span_start_latitude: Optional[float] = None
    span_start_longitude: Optional[float] = None
    span_end_latitude: Optional[float] = None
    span_end_longitude: Optional[float] = None
    orientation_deg: Optional[float] = None
    span_length_m: Optional[float] = None
    breach_severity: str
    alert_on_crossing: bool
    status: str
    last_seen: Optional[str] = None
    last_battery_pct: Optional[int] = None

    class Config:
        from_attributes = True


class BeamEventRequest(BaseModel):
    """A single line-crossing event reported by a beam sensor's edge controller."""
    beam_serial: str = Field(..., description="Beam sensor serial number")
    direction: str = Field("unknown", description="'in' | 'out' | 'unknown'")
    confidence: Optional[float] = Field(None, description="Detection confidence 0.0-1.0")
    battery_pct: Optional[int] = None
    timestamp: Optional[str] = None  # ISO format; defaults to server time if omitted


class BeamEventResponse(BaseModel):
    accepted: bool
    beam_sensor_id: str
    alert_created: bool
    alert_id: Optional[str] = None
    timestamp: str


# ─── Redis helper ────────────────────────────────────────────────────────────


async def _publish_alert(farm_id: str, alert_id: str, beam_serial: str,
                         severity: str, message: str, metadata: dict) -> None:
    """Publish a beam-crossing alert to Redis for real-time + notification fan-out.

    Publishes to two channels, mirroring mqtt_writer.write_alert:
      - farm:{farm_id}    → dashboard WebSocket (live map/alert feed)
      - alerts:incoming   → Alert Engine (push / SMS / email dispatch)

    Best-effort: if Redis is unavailable the alert row is still persisted and
    surfaces via the DB/REST alerts endpoints.
    """
    try:
        redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)

        await redis_client.publish(f"farm:{farm_id}", json.dumps({
            "type": "alert.created",
            "payload": {
                "id": alert_id,
                "alert_type": "beam_crossing",
                "severity": severity,
                "status": "active",
                "message": message,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        }))

        await redis_client.publish("alerts:incoming", json.dumps({
            "alert_type": "beam_crossing",
            "severity": severity,
            "device_id": beam_serial,
            "farm_id": farm_id,
            "animal_id": None,
            "message": message,
            "metadata": metadata,
            "timestamp": datetime.now(timezone.utc).timestamp(),
        }))

        await redis_client.aclose()
    except Exception:
        # Non-fatal — DB row already persisted.
        pass


def _to_response(beam: BeamSensor) -> BeamResponse:
    return BeamResponse(
        id=str(beam.id),
        farm_id=str(beam.farm_id),
        geofence_id=str(beam.geofence_id) if beam.geofence_id else None,
        serial_number=beam.serial_number,
        name=beam.name,
        beam_type=beam.beam_type,
        latitude=beam.latitude,
        longitude=beam.longitude,
        span_start_latitude=beam.span_start_latitude,
        span_start_longitude=beam.span_start_longitude,
        span_end_latitude=beam.span_end_latitude,
        span_end_longitude=beam.span_end_longitude,
        orientation_deg=beam.orientation_deg,
        span_length_m=beam.span_length_m,
        breach_severity=beam.breach_severity,
        alert_on_crossing=beam.alert_on_crossing,
        status=beam.status,
        last_seen=beam.last_seen.isoformat() if beam.last_seen else None,
        last_battery_pct=beam.last_battery_pct,
    )


# ─── Beam Registration ───────────────────────────────────────────────────────


@router.post("/register", response_model=BeamResponse, status_code=201)
async def register_beam(req: BeamRegisterRequest, db: AsyncSession = Depends(get_db)):
    """Register a new beam sensor for a farm."""
    existing = await db.execute(
        select(BeamSensor).where(BeamSensor.serial_number == req.serial_number)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Beam sensor with this serial number already exists")

    if req.beam_type not in ("infrared", "microwave", "laser"):
        raise HTTPException(status_code=422, detail="beam_type must be one of: infrared, microwave, laser")
    if req.breach_severity not in VALID_SEVERITIES:
        raise HTTPException(status_code=422, detail=f"breach_severity must be one of: {', '.join(sorted(VALID_SEVERITIES))}")

    beam = BeamSensor(
        farm_id=req.farm_id,
        geofence_id=req.geofence_id,
        serial_number=req.serial_number,
        name=req.name,
        beam_type=req.beam_type,
        latitude=req.latitude,
        longitude=req.longitude,
        span_start_latitude=req.span_start_latitude,
        span_start_longitude=req.span_start_longitude,
        span_end_latitude=req.span_end_latitude,
        span_end_longitude=req.span_end_longitude,
        orientation_deg=req.orientation_deg,
        span_length_m=req.span_length_m,
        breach_severity=req.breach_severity,
        status="active",
    )
    db.add(beam)
    await db.commit()
    await db.refresh(beam)

    # Snapshot the response now, while the ORM object is attached and current.
    # (Building it after the optional PostGIS update avoids lazy-load IO if that
    # update fails and the session is rolled back.)
    response = _to_response(beam)

    # Populate the PostGIS span linestring if both endpoints were provided.
    # Wrapped so a non-PostGIS backend (e.g. the SQLite test harness) does not
    # fail registration — the explicit span_* columns are still stored.
    if None not in (req.span_start_latitude, req.span_start_longitude,
                    req.span_end_latitude, req.span_end_longitude):
        try:
            await db.execute(text("""
                UPDATE beam_sensors
                SET span = ST_SetSRID(ST_MakeLine(
                        ST_MakePoint(:s_lon, :s_lat),
                        ST_MakePoint(:e_lon, :e_lat)
                    ), 4326)::geography
                WHERE id = :id
            """), {
                "s_lon": req.span_start_longitude, "s_lat": req.span_start_latitude,
                "e_lon": req.span_end_longitude, "e_lat": req.span_end_latitude,
                "id": str(beam.id),
            })
            await db.commit()
        except Exception:
            await db.rollback()

    return response


@router.get("", response_model=List[BeamResponse])
async def list_beams(
    farm_id: Optional[UUID] = None,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """List registered beam sensors, optionally filtered by farm and status."""
    query = select(BeamSensor)
    if farm_id:
        query = query.where(BeamSensor.farm_id == farm_id)
    if status:
        query = query.where(BeamSensor.status == status)
    query = query.order_by(BeamSensor.created_at.desc())

    result = await db.execute(query)
    return [_to_response(b) for b in result.scalars().all()]


@router.get("/{serial}", response_model=BeamResponse)
async def get_beam(serial: str, db: AsyncSession = Depends(get_db)):
    """Get a single beam sensor by serial number."""
    result = await db.execute(
        select(BeamSensor).where(BeamSensor.serial_number == serial)
    )
    beam = result.scalar_one_or_none()
    if not beam:
        raise HTTPException(status_code=404, detail=f"Beam sensor '{serial}' not found")
    return _to_response(beam)


# ─── Crossing Event Ingestion ────────────────────────────────────────────────


@router.post("/event", response_model=BeamEventResponse)
async def ingest_beam_event(req: BeamEventRequest, db: AsyncSession = Depends(get_db)):
    """Ingest a line-crossing event from a beam sensor.

    Stores the crossing in the beam_crossings time-series table and, when the
    beam is configured to alert, creates an alert row and publishes it to Redis
    so the dashboard updates live and the Alert Engine dispatches push/SMS/email.
    """
    result = await db.execute(
        select(BeamSensor).where(BeamSensor.serial_number == req.beam_serial)
    )
    beam = result.scalar_one_or_none()
    if not beam:
        raise HTTPException(status_code=404, detail=f"Beam sensor '{req.beam_serial}' not found. Register it first.")

    if req.direction not in ("in", "out", "unknown"):
        raise HTTPException(status_code=422, detail="direction must be one of: in, out, unknown")

    # Resolve event time (device-supplied or server time).
    now = datetime.now(timezone.utc)
    event_time = now
    if req.timestamp:
        try:
            event_time = datetime.fromisoformat(req.timestamp.replace("Z", "+00:00"))
        except ValueError:
            pass

    # Update beam last-seen / battery.
    beam.last_seen = now
    if req.battery_pct is not None:
        beam.last_battery_pct = req.battery_pct

    # Store the crossing (time-series, no cooldown — every crossing is logged).
    crossing = BeamCrossing(
        time=event_time,
        beam_sensor_id=beam.id,
        farm_id=beam.farm_id,
        direction=req.direction,
        confidence=req.confidence,
        beam_battery_pct=req.battery_pct,
        metadata_={"beam_serial": beam.serial_number, "beam_name": beam.name},
    )
    db.add(crossing)

    alert_created = False
    alert_id: Optional[str] = None

    if beam.alert_on_crossing and beam.status == "active":
        severity = beam.breach_severity if beam.breach_severity in VALID_SEVERITIES else "high"
        direction_note = f" ({req.direction})" if req.direction != "unknown" else ""
        message = f"Perimeter crossing detected at {beam.name}{direction_note}"
        metadata = {
            "beam_serial": beam.serial_number,
            "beam_name": beam.name,
            "direction": req.direction,
            "latitude": beam.latitude,
            "longitude": beam.longitude,
        }

        # Generate the id explicitly so the INSERT works on both PostgreSQL
        # (which has a uuid_generate_v4() default) and the SQLite test harness
        # (which applies id defaults at the ORM layer, not for raw SQL).
        alert_id = str(uuid.uuid4())
        await db.execute(text("""
            INSERT INTO alerts (id, farm_id, alert_type, severity, status, message, metadata)
            VALUES (:id, :farm_id, 'beam_crossing', :severity, 'active', :message, :metadata)
        """), {
            "id": alert_id,
            "farm_id": str(beam.farm_id),
            "severity": severity,
            "message": message,
            "metadata": json.dumps(metadata),
        })
        alert_created = True

    await db.commit()

    # Publish outside the DB transaction so notification fan-out never blocks ingestion.
    if alert_created and alert_id:
        await _publish_alert(
            farm_id=str(beam.farm_id),
            alert_id=alert_id,
            beam_serial=beam.serial_number,
            severity=severity,
            message=message,
            metadata=metadata,
        )

    return BeamEventResponse(
        accepted=True,
        beam_sensor_id=str(beam.id),
        alert_created=alert_created,
        alert_id=alert_id,
        timestamp=now.isoformat(),
    )
