"""
Analytics router — heatmap, activity breakdown, distance, and compliance.

Provides time-series analytics from the positions hypertable and geofences.
All endpoints require authentication and accept farm_id + time range filters.
"""

from typing import List, Optional
from uuid import UUID
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_current_user
from app.services.activity_classifier import classify_activity, haversine_distance

router = APIRouter(dependencies=[Depends(get_current_user)])


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _parse_time_range(start: Optional[str], end: Optional[str]) -> tuple[datetime, datetime]:
    """Parse start/end strings or default to last 7 days."""
    now = datetime.now(timezone.utc)
    if end:
        try:
            end_dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
        except ValueError:
            end_dt = now
    else:
        end_dt = now

    if start:
        try:
            start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
        except ValueError:
            start_dt = end_dt - timedelta(days=7)
    else:
        start_dt = end_dt - timedelta(days=7)

    return start_dt, end_dt


# ─── Heatmap ──────────────────────────────────────────────────────────────────


class HeatmapCell(BaseModel):
    lat: float
    lon: float
    count: int


class HeatmapResponse(BaseModel):
    farm_id: str
    resolution: int
    start: str
    end: str
    cells: List[HeatmapCell]


@router.get("/heatmap", response_model=HeatmapResponse)
async def get_heatmap(
    farm_id: UUID,
    start: Optional[str] = None,
    end: Optional[str] = None,
    resolution: int = Query(default=50, ge=10, le=200),
    db: AsyncSession = Depends(get_db),
):
    """
    Get position heatmap data for a farm within a time range.

    Groups positions into grid cells by rounding lat/lon to a resolution-dependent
    precision. Returns cell centers with position counts.
    """
    start_dt, end_dt = _parse_time_range(start, end)

    # Resolution maps to decimal precision: 50 -> ~0.001 (~100m cells)
    # Higher resolution = smaller cells = more decimal places
    cell_size = 1.0 / resolution  # degrees per cell

    query = text("""
        SELECT
            ROUND(CAST(latitude / :cell_size AS NUMERIC), 0) * :cell_size AS cell_lat,
            ROUND(CAST(longitude / :cell_size AS NUMERIC), 0) * :cell_size AS cell_lon,
            COUNT(*) AS count
        FROM positions p
        JOIN animals a ON a.id = p.animal_id
        WHERE a.farm_id = :farm_id
          AND p.time >= :start
          AND p.time <= :end
          AND p.latitude IS NOT NULL
          AND p.longitude IS NOT NULL
        GROUP BY cell_lat, cell_lon
        ORDER BY count DESC
        LIMIT 5000
    """)

    try:
        result = await db.execute(query, {
            "farm_id": str(farm_id),
            "start": start_dt,
            "end": end_dt,
            "cell_size": cell_size,
        })
        rows = result.fetchall()
    except Exception:
        rows = []

    cells = [
        HeatmapCell(lat=float(r.cell_lat), lon=float(r.cell_lon), count=r.count)
        for r in rows
    ]

    return HeatmapResponse(
        farm_id=str(farm_id),
        resolution=resolution,
        start=start_dt.isoformat(),
        end=end_dt.isoformat(),
        cells=cells,
    )


# ─── Activity ─────────────────────────────────────────────────────────────────


class ActivityBucket(BaseModel):
    time_bucket: str
    grazing: int
    resting: int
    walking: int
    running: int
    total: int


class ActivityResponse(BaseModel):
    farm_id: str
    interval: str
    start: str
    end: str
    data: List[ActivityBucket]
    summary: dict


@router.get("/activity", response_model=ActivityResponse)
async def get_activity(
    farm_id: UUID,
    animal_id: Optional[UUID] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
    interval: str = Query(default="1h", description="Time bucket: 1h, 6h, 1d"),
    db: AsyncSession = Depends(get_db),
):
    """
    Get activity breakdown (grazing, resting, walking, running) over time.

    Classifies each position point by speed into activity categories and
    aggregates into time buckets.
    """
    start_dt, end_dt = _parse_time_range(start, end)

    # Map interval string to PostgreSQL interval
    interval_map = {"1h": "1 hour", "6h": "6 hours", "1d": "1 day"}
    pg_interval = interval_map.get(interval, "1 hour")

    animal_filter = ""
    params: dict = {
        "farm_id": str(farm_id),
        "start": start_dt,
        "end": end_dt,
    }
    if animal_id:
        animal_filter = "AND p.animal_id = :animal_id"
        params["animal_id"] = str(animal_id)

    # Classify positions by speed thresholds into activity types per time bucket
    query = text(f"""
        SELECT
            time_bucket('{pg_interval}', p.time) AS bucket,
            COUNT(*) FILTER (WHERE COALESCE(p.speed, 0) < 0.3) AS resting,
            COUNT(*) FILTER (WHERE p.speed >= 0.3 AND p.speed < 2.0) AS grazing,
            COUNT(*) FILTER (WHERE p.speed >= 2.0 AND p.speed < 8.0) AS walking,
            COUNT(*) FILTER (WHERE p.speed >= 8.0) AS running,
            COUNT(*) AS total
        FROM positions p
        JOIN animals a ON a.id = p.animal_id
        WHERE a.farm_id = :farm_id
          AND p.time >= :start
          AND p.time <= :end
          {animal_filter}
        GROUP BY bucket
        ORDER BY bucket ASC
    """)

    try:
        result = await db.execute(query, params)
        rows = result.fetchall()
    except Exception:
        rows = []

    buckets = [
        ActivityBucket(
            time_bucket=r.bucket.isoformat(),
            grazing=r.grazing,
            resting=r.resting,
            walking=r.walking,
            running=r.running,
            total=r.total,
        )
        for r in rows
    ]

    # Compute overall summary percentages
    total_points = sum(b.total for b in buckets) or 1
    summary = {
        "grazing_pct": round(sum(b.grazing for b in buckets) / total_points * 100, 1),
        "resting_pct": round(sum(b.resting for b in buckets) / total_points * 100, 1),
        "walking_pct": round(sum(b.walking for b in buckets) / total_points * 100, 1),
        "running_pct": round(sum(b.running for b in buckets) / total_points * 100, 1),
    }

    return ActivityResponse(
        farm_id=str(farm_id),
        interval=interval,
        start=start_dt.isoformat(),
        end=end_dt.isoformat(),
        data=buckets,
        summary=summary,
    )


# ─── Distance ─────────────────────────────────────────────────────────────────


class DistanceBucket(BaseModel):
    time_bucket: str
    distance_km: float
    animals_active: int


class DistanceAnimalDetail(BaseModel):
    animal_id: str
    animal_name: Optional[str]
    distance_km: float


class DistanceResponse(BaseModel):
    farm_id: str
    interval: str
    start: str
    end: str
    total_distance_km: float
    data: List[DistanceBucket]
    top_animals: List[DistanceAnimalDetail]


@router.get("/distance", response_model=DistanceResponse)
async def get_distance(
    farm_id: UUID,
    animal_id: Optional[UUID] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
    interval: str = Query(default="1d", description="Time bucket: 1h, 6h, 1d"),
    db: AsyncSession = Depends(get_db),
):
    """
    Get distance travelled by animals over time.

    Computes haversine distance between consecutive positions per animal,
    then aggregates into time buckets.
    """
    start_dt, end_dt = _parse_time_range(start, end)

    interval_map = {"1h": "1 hour", "6h": "6 hours", "1d": "1 day"}
    pg_interval = interval_map.get(interval, "1 day")

    animal_filter = ""
    params: dict = {
        "farm_id": str(farm_id),
        "start": start_dt,
        "end": end_dt,
    }
    if animal_id:
        animal_filter = "AND p.animal_id = :animal_id"
        params["animal_id"] = str(animal_id)

    # Use LAG window function to get previous position, then compute distance
    query = text(f"""
        WITH position_pairs AS (
            SELECT
                p.animal_id,
                p.time,
                p.latitude,
                p.longitude,
                LAG(p.latitude) OVER (PARTITION BY p.animal_id ORDER BY p.time) AS prev_lat,
                LAG(p.longitude) OVER (PARTITION BY p.animal_id ORDER BY p.time) AS prev_lon
            FROM positions p
            JOIN animals a ON a.id = p.animal_id
            WHERE a.farm_id = :farm_id
              AND p.time >= :start
              AND p.time <= :end
              AND p.latitude IS NOT NULL
              AND p.longitude IS NOT NULL
              {animal_filter}
        ),
        distances AS (
            SELECT
                animal_id,
                time,
                CASE WHEN prev_lat IS NOT NULL THEN
                    6371000 * 2 * ASIN(SQRT(
                        POWER(SIN(RADIANS(latitude - prev_lat) / 2), 2) +
                        COS(RADIANS(prev_lat)) * COS(RADIANS(latitude)) *
                        POWER(SIN(RADIANS(longitude - prev_lon) / 2), 2)
                    ))
                ELSE 0 END AS dist_m
            FROM position_pairs
        )
        SELECT
            time_bucket('{pg_interval}', time) AS bucket,
            ROUND(CAST(SUM(dist_m) / 1000.0 AS NUMERIC), 2) AS distance_km,
            COUNT(DISTINCT animal_id) AS animals_active
        FROM distances
        WHERE dist_m < 10000
        GROUP BY bucket
        ORDER BY bucket ASC
    """)

    try:
        result = await db.execute(query, params)
        rows = result.fetchall()
    except Exception:
        rows = []

    buckets = [
        DistanceBucket(
            time_bucket=r.bucket.isoformat(),
            distance_km=float(r.distance_km),
            animals_active=r.animals_active,
        )
        for r in rows
    ]

    total_km = sum(b.distance_km for b in buckets)

    # Top animals by distance
    top_query = text(f"""
        WITH position_pairs AS (
            SELECT
                p.animal_id,
                p.latitude,
                p.longitude,
                LAG(p.latitude) OVER (PARTITION BY p.animal_id ORDER BY p.time) AS prev_lat,
                LAG(p.longitude) OVER (PARTITION BY p.animal_id ORDER BY p.time) AS prev_lon
            FROM positions p
            JOIN animals a ON a.id = p.animal_id
            WHERE a.farm_id = :farm_id
              AND p.time >= :start
              AND p.time <= :end
              AND p.latitude IS NOT NULL
              {animal_filter}
        ),
        distances AS (
            SELECT
                animal_id,
                CASE WHEN prev_lat IS NOT NULL THEN
                    6371000 * 2 * ASIN(SQRT(
                        POWER(SIN(RADIANS(latitude - prev_lat) / 2), 2) +
                        COS(RADIANS(prev_lat)) * COS(RADIANS(latitude)) *
                        POWER(SIN(RADIANS(longitude - prev_lon) / 2), 2)
                    ))
                ELSE 0 END AS dist_m
            FROM position_pairs
        )
        SELECT
            d.animal_id,
            a.name AS animal_name,
            ROUND(CAST(SUM(d.dist_m) / 1000.0 AS NUMERIC), 2) AS distance_km
        FROM distances d
        JOIN animals a ON a.id = d.animal_id
        WHERE d.dist_m < 10000
        GROUP BY d.animal_id, a.name
        ORDER BY distance_km DESC
        LIMIT 10
    """)

    try:
        top_result = await db.execute(top_query, params)
        top_rows = top_result.fetchall()
    except Exception:
        top_rows = []

    top_animals = [
        DistanceAnimalDetail(
            animal_id=str(r.animal_id),
            animal_name=r.animal_name,
            distance_km=float(r.distance_km),
        )
        for r in top_rows
    ]

    return DistanceResponse(
        farm_id=str(farm_id),
        interval=interval,
        start=start_dt.isoformat(),
        end=end_dt.isoformat(),
        total_distance_km=round(total_km, 2),
        data=buckets,
        top_animals=top_animals,
    )


# ─── Compliance ───────────────────────────────────────────────────────────────


class ComplianceDetail(BaseModel):
    geofence_id: str
    geofence_name: str
    total_points: int
    inside_points: int
    compliance_rate: float


class ComplianceResponse(BaseModel):
    farm_id: str
    start: str
    end: str
    overall_compliance: float
    details: List[ComplianceDetail]


@router.get("/compliance", response_model=ComplianceResponse)
async def get_compliance(
    farm_id: UUID,
    geofence_id: Optional[UUID] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Get geofence compliance statistics (time inside vs outside).

    For each geofence, checks what percentage of position points fall within
    the geofence polygon using PostGIS ST_Contains.
    """
    start_dt, end_dt = _parse_time_range(start, end)

    geofence_filter = ""
    params: dict = {
        "farm_id": str(farm_id),
        "start": start_dt,
        "end": end_dt,
    }
    if geofence_id:
        geofence_filter = "AND g.id = :geofence_id"
        params["geofence_id"] = str(geofence_id)

    query = text(f"""
        SELECT
            g.id AS geofence_id,
            g.name AS geofence_name,
            COUNT(p.*) AS total_points,
            COUNT(p.*) FILTER (
                WHERE ST_Contains(
                    g.geometry,
                    ST_SetSRID(ST_MakePoint(p.longitude, p.latitude), 4326)
                )
            ) AS inside_points
        FROM geofences g
        CROSS JOIN LATERAL (
            SELECT pos.latitude, pos.longitude
            FROM positions pos
            JOIN animals a ON a.id = pos.animal_id
            WHERE a.farm_id = :farm_id
              AND pos.time >= :start
              AND pos.time <= :end
              AND pos.latitude IS NOT NULL
              AND pos.longitude IS NOT NULL
        ) p
        WHERE g.farm_id = :farm_id
          AND g.geometry IS NOT NULL
          {geofence_filter}
        GROUP BY g.id, g.name
    """)

    try:
        result = await db.execute(query, params)
        rows = result.fetchall()
    except Exception:
        rows = []

    details = []
    total_all = 0
    inside_all = 0

    for r in rows:
        total = r.total_points or 0
        inside = r.inside_points or 0
        rate = round(inside / total * 100, 1) if total > 0 else 0.0
        details.append(ComplianceDetail(
            geofence_id=str(r.geofence_id),
            geofence_name=r.geofence_name,
            total_points=total,
            inside_points=inside,
            compliance_rate=rate,
        ))
        total_all += total
        inside_all += inside

    overall = round(inside_all / total_all * 100, 1) if total_all > 0 else 0.0

    return ComplianceResponse(
        farm_id=str(farm_id),
        start=start_dt.isoformat(),
        end=end_dt.isoformat(),
        overall_compliance=overall,
        details=details,
    )


# ─── Activity Classification (Single Animal) ─────────────────────────────────


class ActivityClassification(BaseModel):
    animal_id: str
    activity: str
    confidence: float
    avg_speed: float
    max_speed: float
    distance_m: float
    heading_variance: float


@router.get("/activity/classify/{animal_id}", response_model=ActivityClassification)
async def classify_animal_activity(
    animal_id: UUID,
    window_minutes: int = Query(default=30, ge=5, le=240),
    db: AsyncSession = Depends(get_db),
):
    """
    Classify the current activity of an animal based on recent GPS data.

    Uses a sliding window of the last N minutes of position data to infer:
    - resting (< 0.3 km/h)
    - grazing (0.3-2 km/h, high heading variance)
    - walking (2-8 km/h)
    - running (> 8 km/h)
    """
    query = text("""
        SELECT latitude, longitude, speed, heading
        FROM positions
        WHERE animal_id = :animal_id
          AND time > NOW() - make_interval(mins => :window)
        ORDER BY time ASC
        LIMIT 500
    """)

    try:
        result = await db.execute(query, {"animal_id": str(animal_id), "window": window_minutes})
        rows = result.fetchall()
    except Exception:
        rows = []

    if not rows:
        return ActivityClassification(
            animal_id=str(animal_id),
            activity="resting",
            confidence=0.5,
            avg_speed=0.0,
            max_speed=0.0,
            distance_m=0.0,
            heading_variance=0.0,
        )

    speeds = [r.speed for r in rows if r.speed is not None]
    headings = [r.heading for r in rows if r.heading is not None]

    distances = []
    for i in range(1, len(rows)):
        if rows[i].latitude and rows[i - 1].latitude:
            d = haversine_distance(
                rows[i - 1].latitude, rows[i - 1].longitude,
                rows[i].latitude, rows[i].longitude,
            )
            distances.append(d)

    classification = classify_activity(speeds, headings, distances)

    return ActivityClassification(
        animal_id=str(animal_id),
        activity=classification.activity,
        confidence=classification.confidence,
        avg_speed=classification.avg_speed,
        max_speed=classification.max_speed,
        distance_m=classification.distance_m,
        heading_variance=classification.heading_variance,
    )
