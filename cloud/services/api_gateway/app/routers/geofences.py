from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Query
from pydantic import BaseModel

router = APIRouter()


class GeofenceCreate(BaseModel):
    name: str
    farm_id: UUID
    geometry: dict  # GeoJSON polygon
    fence_type: str = "inclusion"  # "inclusion" | "exclusion"
    active: bool = True
    alert_on_breach: bool = True


class GeofenceUpdate(BaseModel):
    name: Optional[str] = None
    geometry: Optional[dict] = None
    fence_type: Optional[str] = None
    active: Optional[bool] = None
    alert_on_breach: Optional[bool] = None


class TestPointRequest(BaseModel):
    latitude: float
    longitude: float
    geofence_id: Optional[UUID] = None


@router.get("/")
async def list_geofences(
    farm_id: Optional[UUID] = None,
    active: Optional[bool] = None,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
):
    """List all geofences, optionally filtered by farm or status."""
    return {"geofences": [], "total": 0, "limit": limit, "offset": offset}


@router.post("/", status_code=201)
async def create_geofence(geofence: GeofenceCreate):
    """Create a new geofence."""
    return {"id": "placeholder", **geofence.model_dump()}


@router.get("/{geofence_id}")
async def get_geofence(geofence_id: UUID):
    """Get geofence details."""
    return {"id": str(geofence_id), "name": "", "fence_type": "inclusion"}


@router.put("/{geofence_id}")
async def update_geofence(geofence_id: UUID, update: GeofenceUpdate):
    """Update a geofence."""
    return {"id": str(geofence_id), **update.model_dump(exclude_none=True)}


@router.delete("/{geofence_id}", status_code=204)
async def delete_geofence(geofence_id: UUID):
    """Delete a geofence."""
    return None


@router.post("/test-point")
async def test_point(request: TestPointRequest):
    """Test if a point is inside/outside geofences."""
    return {
        "latitude": request.latitude,
        "longitude": request.longitude,
        "results": [],
    }
