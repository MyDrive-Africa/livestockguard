from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Query

router = APIRouter()


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
