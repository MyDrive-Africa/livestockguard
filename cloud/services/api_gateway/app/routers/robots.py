"""
Herding Robots router — fleet registry, live status, jobs, and manual control
for the robotic-herdsman layer.

A herding robot is a mobile, non-animal device (typically 4 per farm) that keeps
cattle inside their boundary by driving to a straying animal and nudging it back
with presence and sound. The autonomous decisions are made by the
herding_orchestrator service; this router is the operator/dashboard surface:
register robots, read fleet + job state, and issue manual overrides (including an
emergency stop-all).

Manual commands are published to the same MQTT topic the orchestrator uses
(lg/robot/{serial}/cmd), so a robot honours operator and autopilot orders through
one path.

Endpoints:
    POST /register            Register a robot for a farm (admin/farm_owner)
    GET  /                    List robots (optionally by farm)
    GET  /{serial}            Get one robot + its current job
    GET  /{serial}/telemetry  Recent telemetry trail for a robot
    POST /{serial}/command    Manual override (move_to | return_home | stop | patrol)
    GET  /herding/jobs        Active/recent herding jobs
    GET  /herding/status      Containment summary (robots/jobs) for a farm
    POST /herding/stop-all    Emergency stop: halt the whole fleet on a farm
"""

import json
import os
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

import paho.mqtt.publish as mqtt_publish
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from livestockguard_common.db_models import HerdingRobot, HerdingJob
from app.dependencies import get_db, get_current_user, require_role

router = APIRouter()

MQTT_HOST = os.environ.get("MQTT_HOST", os.environ.get("MQTT_BROKER", "localhost"))
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))
COMMAND_TTL_SEC = int(os.environ.get("HERDING_COMMAND_TTL_SEC", "60"))

VALID_MODELS = {"humanoid", "wheeled", "quadruped"}
# Manual override commands an operator may issue.
VALID_COMMANDS = {"move_to", "return_home", "stop", "patrol", "shepherd"}


# ─── Request/Response Models ─────────────────────────────────────────────────


class RobotRegisterRequest(BaseModel):
    farm_id: UUID
    serial_number: str
    name: str
    model: str = "wheeled"
    home_latitude: Optional[float] = None
    home_longitude: Optional[float] = None
    max_speed_mps: float = 2.0


class RobotResponse(BaseModel):
    id: str
    farm_id: str
    serial_number: str
    name: str
    model: str
    status: str
    last_latitude: Optional[float] = None
    last_longitude: Optional[float] = None
    heading_deg: Optional[float] = None
    battery_pct: Optional[int] = None
    current_job_id: Optional[str] = None
    home_latitude: Optional[float] = None
    home_longitude: Optional[float] = None
    max_speed_mps: float
    last_seen: Optional[str] = None

    class Config:
        from_attributes = True


class RobotCommandRequest(BaseModel):
    command: str = Field(..., description="move_to | return_home | stop | patrol | shepherd")
    latitude: Optional[float] = Field(None, description="Target latitude (for move_to/shepherd)")
    longitude: Optional[float] = Field(None, description="Target longitude (for move_to/shepherd)")


class RobotCommandResponse(BaseModel):
    accepted: bool
    serial: str
    command: str
    published: bool


class JobResponse(BaseModel):
    id: str
    farm_id: str
    robot_id: Optional[str] = None
    job_type: str
    target_animal_id: Optional[str] = None
    target_latitude: Optional[float] = None
    target_longitude: Optional[float] = None
    priority: int
    status: str
    reason: Optional[str] = None
    created_at: Optional[str] = None
    assigned_at: Optional[str] = None
    completed_at: Optional[str] = None

    class Config:
        from_attributes = True


class HerdingStatusResponse(BaseModel):
    farm_id: str
    robots_total: int
    robots_active: int          # enroute or shepherding
    robots_charging: int
    active_jobs: int


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _robot_to_response(r: HerdingRobot) -> RobotResponse:
    return RobotResponse(
        id=str(r.id),
        farm_id=str(r.farm_id),
        serial_number=r.serial_number,
        name=r.name,
        model=r.model,
        status=r.status,
        last_latitude=r.last_latitude,
        last_longitude=r.last_longitude,
        heading_deg=r.heading_deg,
        battery_pct=r.battery_pct,
        current_job_id=str(r.current_job_id) if r.current_job_id else None,
        home_latitude=r.home_latitude,
        home_longitude=r.home_longitude,
        max_speed_mps=r.max_speed_mps,
        last_seen=r.last_seen.isoformat() if r.last_seen else None,
    )


def _job_to_response(j: HerdingJob) -> JobResponse:
    return JobResponse(
        id=str(j.id),
        farm_id=str(j.farm_id),
        robot_id=str(j.robot_id) if j.robot_id else None,
        job_type=j.job_type,
        target_animal_id=str(j.target_animal_id) if j.target_animal_id else None,
        target_latitude=j.target_latitude,
        target_longitude=j.target_longitude,
        priority=j.priority,
        status=j.status,
        reason=j.reason,
        created_at=j.created_at.isoformat() if j.created_at else None,
        assigned_at=j.assigned_at.isoformat() if j.assigned_at else None,
        completed_at=j.completed_at.isoformat() if j.completed_at else None,
    )


def _publish_command(serial: str, payload: dict) -> bool:
    """Publish a command to a robot over MQTT. Best-effort; returns success.

    Uses paho's one-shot publish helper so the router needs no long-lived client.
    A failure to publish (broker down) is reported to the caller rather than
    raising, so the operator sees it was not delivered.
    """
    try:
        qos = 2 if payload.get("cmd") == "stop" else 1
        mqtt_publish.single(
            topic=f"lg/robot/{serial}/cmd",
            payload=json.dumps(payload),
            qos=qos,
            hostname=MQTT_HOST,
            port=MQTT_PORT,
        )
        return True
    except Exception:
        return False


# ─── Robot Registration & Read ───────────────────────────────────────────────


@router.post("/register", response_model=RobotResponse, status_code=201)
async def register_robot(
    req: RobotRegisterRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role("farm_owner")),
):
    """Register a new herding robot for a farm (admin/farm_owner only)."""
    if req.model not in VALID_MODELS:
        raise HTTPException(status_code=422, detail=f"model must be one of: {', '.join(sorted(VALID_MODELS))}")

    existing = await db.execute(
        select(HerdingRobot).where(HerdingRobot.serial_number == req.serial_number)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Robot with this serial number already exists")

    robot = HerdingRobot(
        farm_id=req.farm_id,
        serial_number=req.serial_number,
        name=req.name,
        model=req.model,
        status="offline",
        home_latitude=req.home_latitude,
        home_longitude=req.home_longitude,
        last_latitude=req.home_latitude,
        last_longitude=req.home_longitude,
        max_speed_mps=req.max_speed_mps,
        capabilities={"audio": True, "presence": True},
    )
    db.add(robot)
    await db.commit()
    await db.refresh(robot)
    return _robot_to_response(robot)


@router.get("", response_model=List[RobotResponse])
async def list_robots(
    farm_id: Optional[UUID] = None,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """List registered robots, optionally filtered by farm and status."""
    query = select(HerdingRobot)
    if farm_id:
        query = query.where(HerdingRobot.farm_id == farm_id)
    if status:
        query = query.where(HerdingRobot.status == status)
    query = query.order_by(HerdingRobot.serial_number)
    result = await db.execute(query)
    return [_robot_to_response(r) for r in result.scalars().all()]


@router.get("/herding/jobs", response_model=List[JobResponse])
async def list_jobs(
    farm_id: Optional[UUID] = None,
    status: Optional[str] = Query(None, description="Filter by job status"),
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """List herding jobs, most recent first."""
    query = select(HerdingJob)
    if farm_id:
        query = query.where(HerdingJob.farm_id == farm_id)
    if status:
        query = query.where(HerdingJob.status == status)
    query = query.order_by(HerdingJob.created_at.desc()).limit(limit)
    result = await db.execute(query)
    return [_job_to_response(j) for j in result.scalars().all()]


@router.get("/herding/status", response_model=HerdingStatusResponse)
async def herding_status(
    farm_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Fleet + job summary for a farm (for the dashboard Herding panel)."""
    result = await db.execute(
        select(HerdingRobot).where(HerdingRobot.farm_id == farm_id)
    )
    robots = result.scalars().all()

    jobs_result = await db.execute(
        select(HerdingJob).where(
            HerdingJob.farm_id == farm_id,
            HerdingJob.status.in_(("pending", "assigned", "active")),
        )
    )
    active_jobs = len(jobs_result.scalars().all())

    return HerdingStatusResponse(
        farm_id=str(farm_id),
        robots_total=len(robots),
        robots_active=sum(1 for r in robots if r.status in ("enroute", "shepherding")),
        robots_charging=sum(1 for r in robots if r.status == "charging"),
        active_jobs=active_jobs,
    )


@router.post("/herding/stop-all", response_model=dict)
async def stop_all(
    farm_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role("farm_owner")),
):
    """Emergency stop: publish a stop command to every robot on a farm.

    Safety control — halts the fleet immediately. Also flips each robot's status
    to 'idle' so the dashboard reflects the halt even before telemetry catches up.
    """
    result = await db.execute(
        select(HerdingRobot).where(HerdingRobot.farm_id == farm_id)
    )
    robots = result.scalars().all()

    payload = {
        "v": 1,
        "cmd": "stop",
        "issued_at": datetime.now(timezone.utc).isoformat(),
        "ttl_sec": COMMAND_TTL_SEC,
    }
    published = 0
    for r in robots:
        if _publish_command(r.serial_number, payload):
            published += 1
        r.status = "idle"
    await db.commit()

    return {"farm_id": str(farm_id), "robots": len(robots), "commands_published": published}


@router.get("/{serial}", response_model=RobotResponse)
async def get_robot(serial: str, db: AsyncSession = Depends(get_db),
                    user: dict = Depends(get_current_user)):
    """Get a single robot by serial number."""
    result = await db.execute(
        select(HerdingRobot).where(HerdingRobot.serial_number == serial)
    )
    robot = result.scalar_one_or_none()
    if not robot:
        raise HTTPException(status_code=404, detail=f"Robot '{serial}' not found")
    return _robot_to_response(robot)


@router.get("/{serial}/telemetry", response_model=List[dict])
async def get_robot_telemetry(
    serial: str,
    limit: int = Query(100, le=1000),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Recent telemetry trail for a robot (newest first)."""
    result = await db.execute(
        select(HerdingRobot).where(HerdingRobot.serial_number == serial)
    )
    robot = result.scalar_one_or_none()
    if not robot:
        raise HTTPException(status_code=404, detail=f"Robot '{serial}' not found")

    rows = await db.execute(
        text("""
            SELECT time, latitude, longitude, heading_deg, speed_mps, battery_pct, state
            FROM robot_telemetry
            WHERE robot_id = :rid
            ORDER BY time DESC
            LIMIT :lim
        """),
        {"rid": str(robot.id), "lim": limit},
    )
    return [
        {
            "time": r.time.isoformat() if r.time else None,
            "latitude": r.latitude,
            "longitude": r.longitude,
            "heading_deg": r.heading_deg,
            "speed_mps": r.speed_mps,
            "battery_pct": r.battery_pct,
            "state": r.state,
        }
        for r in rows
    ]


@router.post("/{serial}/command", response_model=RobotCommandResponse)
async def command_robot(
    serial: str,
    req: RobotCommandRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role("farm_owner")),
):
    """Issue a manual override command to a robot (admin/farm_owner only).

    Published to the same MQTT topic the orchestrator uses, so operator and
    autopilot commands travel one path. move_to/shepherd require target coords.
    """
    if req.command not in VALID_COMMANDS:
        raise HTTPException(status_code=422, detail=f"command must be one of: {', '.join(sorted(VALID_COMMANDS))}")

    result = await db.execute(
        select(HerdingRobot).where(HerdingRobot.serial_number == serial)
    )
    robot = result.scalar_one_or_none()
    if not robot:
        raise HTTPException(status_code=404, detail=f"Robot '{serial}' not found")

    payload: dict = {
        "v": 1,
        "cmd": req.command,
        "issued_at": datetime.now(timezone.utc).isoformat(),
        "ttl_sec": COMMAND_TTL_SEC,
        "source": "operator",
    }
    if req.command in ("move_to", "shepherd"):
        if req.latitude is None or req.longitude is None:
            raise HTTPException(status_code=422, detail=f"{req.command} requires latitude and longitude")
        payload["target"] = {"lat": req.latitude, "lon": req.longitude}
        payload["deterrent"] = "audio_high" if req.command == "shepherd" else "audio_low"

    published = _publish_command(serial, payload)
    return RobotCommandResponse(accepted=True, serial=serial, command=req.command, published=published)
