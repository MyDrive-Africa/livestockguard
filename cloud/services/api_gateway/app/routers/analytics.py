from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_current_user
from app.services.activity_classifier import classify_activity, haversine_distance

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.get("/heatmap")
async def get_heatmap(
    farm_id: UUID,
    start: Optional[str] = None,
    end: Optional[str] = None,
    resolution: int = Query(default=50, ge=10, le=200),
):
    """Get position heatmap data for a farm within a time range."""
    return {
        "farm_id": str(farm_id),
        "resolution": resolution,
        "cells": [],
    }


@router.get("/activity")
async def get_activity(
    farm_id: UUID,
    animal_id: Optional[UUID] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
    interval: str = Query(default="1h"),
):
    """Get activity breakdown (grazing, resting, walking) over time."""
    return {
        "farm_id": str(farm_id),
        "interval": interval,
        "data": [],
    }


@router.get("/distance")
async def get_distance(
    farm_id: UUID,
    animal_id: Optional[UUID] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
    interval: str = Query(default="1d"),
):
    """Get distance travelled by animals over time."""
    return {
        "farm_id": str(farm_id),
        "interval": interval,
        "data": [],
    }


@router.get("/compliance")
async def get_compliance(
    farm_id: UUID,
    geofence_id: Optional[UUID] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
):
    """Get geofence compliance statistics (time inside vs outside)."""
    return {
        "farm_id": str(farm_id),
        "compliance_rate": 0.0,
        "details": [],
    }


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
    - grazing (0.3–2 km/h, high heading variance)
    - walking (2–8 km/h)
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
        # No data — default to resting
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

    # Calculate inter-point distances
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
