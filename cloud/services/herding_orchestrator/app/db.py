"""Data access for the Herding Orchestrator.

Loads the inputs each control-loop pass needs — the fleet, the latest animal
positions, and each farm's boundary — and persists the jobs the orchestrator
creates. Uses asyncpg directly (like mqtt_writer) since this is a hot loop with
simple queries and no ORM benefit.

Kept behind small typed helpers so the control loop in ``main.py`` reads cleanly
and the pieces can be tested/mocked independently.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import asyncpg

from app import config
from app.assigner import RobotState
from app.containment import Boundary
from app.planner import AnimalState

logger = logging.getLogger("herding_orchestrator.db")

# The DATABASE_URL default is SQLAlchemy-style (postgresql+asyncpg://...).
# asyncpg wants a plain postgresql:// DSN, so normalise it.
_DSN = config.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")


async def connect_pool() -> asyncpg.Pool:
    """Create an asyncpg connection pool."""
    return await asyncpg.create_pool(dsn=_DSN, min_size=1, max_size=5)


async def load_active_farms(pool: asyncpg.Pool) -> list[str]:
    """Return farm ids that have at least one registered herding robot."""
    rows = await pool.fetch("SELECT DISTINCT farm_id FROM herding_robots")
    return [str(r["farm_id"]) for r in rows]


async def load_fleet(pool: asyncpg.Pool, farm_id: str) -> list[RobotState]:
    """Load the robot fleet for a farm as assigner RobotState snapshots."""
    rows = await pool.fetch(
        """
        SELECT id, serial_number, last_latitude, last_longitude,
               COALESCE(battery_pct, 100) AS battery_pct,
               max_speed_mps, status
        FROM herding_robots
        WHERE farm_id = $1 AND status <> 'fault'
        """,
        farm_id,
    )
    fleet: list[RobotState] = []
    for r in rows:
        if r["last_latitude"] is None or r["last_longitude"] is None:
            continue  # robot hasn't reported a position yet
        fleet.append(
            RobotState(
                robot_id=str(r["id"]),
                serial=r["serial_number"],
                lat=r["last_latitude"],
                lon=r["last_longitude"],
                battery_pct=r["battery_pct"],
                max_speed_mps=r["max_speed_mps"] or 2.0,
                status=r["status"],
            )
        )
    return fleet


async def load_recent_animals(pool: asyncpg.Pool, farm_id: str) -> list[AnimalState]:
    """Load the latest position per animal on a farm (within MAX_POSITION_AGE_SEC).

    Uses DISTINCT ON to pick the newest row per animal from the positions hypertable.
    """
    rows = await pool.fetch(
        """
        SELECT DISTINCT ON (p.animal_id)
               p.animal_id, a.name, p.latitude, p.longitude, p.time
        FROM positions p
        JOIN animals a ON a.id = p.animal_id
        WHERE a.farm_id = $1
          AND p.time > NOW() - ($2 || ' seconds')::interval
        ORDER BY p.animal_id, p.time DESC
        """,
        farm_id,
        str(int(config.MAX_POSITION_AGE_SEC)),
    )
    return [
        AnimalState(
            animal_id=str(r["animal_id"]),
            name=r["name"] or str(r["animal_id"])[:8],
            lat=r["latitude"],
            lon=r["longitude"],
        )
        for r in rows
    ]


async def load_boundary(pool: asyncpg.Pool, farm_id: str) -> Boundary | None:
    """Load the active containment boundary for a farm.

    Prefers a circle (centre+radius) if present, else the polygon/rectangle geometry.
    Returns None if the farm has no active geofence to contain against.
    """
    row = await pool.fetchrow(
        """
        SELECT shape, center_latitude, center_longitude, radius_m,
               COALESCE(buffer_m, $2) AS buffer_m,
               ST_AsGeoJSON(geometry) AS geojson
        FROM geofences
        WHERE farm_id = $1 AND active = TRUE
        ORDER BY created_at DESC
        LIMIT 1
        """,
        farm_id,
        config.DEFAULT_BUFFER_M,
    )
    if row is None:
        return None

    if row["shape"] == "circle" and row["center_latitude"] is not None:
        return Boundary(
            shape="circle",
            buffer_m=row["buffer_m"],
            center_lat=row["center_latitude"],
            center_lon=row["center_longitude"],
            radius_m=row["radius_m"],
        )

    ring = _ring_from_geojson(row["geojson"])
    if not ring:
        return None
    return Boundary(shape=row["shape"] or "polygon", buffer_m=row["buffer_m"], ring=ring)


def _ring_from_geojson(geojson: str | None) -> list[tuple[float, float]] | None:
    """Extract the outer ring as (lat, lon) tuples from a GeoJSON Polygon string."""
    if not geojson:
        return None
    import json

    try:
        geom = json.loads(geojson)
    except (ValueError, TypeError):
        return None
    if geom.get("type") != "Polygon" or not geom.get("coordinates"):
        return None
    # GeoJSON is [lon, lat]; containment expects (lat, lon).
    return [(pt[1], pt[0]) for pt in geom["coordinates"][0]]


async def persist_job(pool: asyncpg.Pool, farm_id: str, robot_id: str, action: str, target) -> None:
    """Insert a herding_jobs row for an assigned job and link it to the robot.

    ``target`` is a planner.HerdingTarget or None (for patrol/return_home).
    """
    now = datetime.now(timezone.utc)
    job_type = action if action in ("shepherd", "intercept", "patrol", "return_kraal", "investigate") else "patrol"
    target_animal = getattr(target, "animal_id", None) if target else None
    t_lat = getattr(target, "intercept_lat", None) if target else None
    t_lon = getattr(target, "intercept_lon", None) if target else None
    priority = getattr(target, "priority", 0) if target else 0
    reason = getattr(target, "reason", action) if target else action

    job_id = await pool.fetchval(
        """
        INSERT INTO herding_jobs
            (farm_id, robot_id, job_type, target_animal_id, target_latitude,
             target_longitude, priority, status, reason, assigned_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7, 'assigned', $8, $9)
        RETURNING id
        """,
        farm_id, robot_id, job_type, target_animal, t_lat, t_lon, priority, reason, now,
    )
    await pool.execute(
        "UPDATE herding_robots SET current_job_id = $1, updated_at = NOW() WHERE id = $2",
        job_id, robot_id,
    )
