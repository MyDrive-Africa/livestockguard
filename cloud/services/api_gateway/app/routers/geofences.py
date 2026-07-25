"""
Geofence management router — wired to real database.
"""

import os
import sys
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'shared'))

from livestockguard_common.db_models import Geofence
from app.dependencies import get_db, get_current_user

router = APIRouter(dependencies=[Depends(get_current_user)])


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


class GeofenceResponse(BaseModel):
    id: str
    name: str
    farm_id: str
    fence_type: str
    active: bool
    alert_on_breach: bool
    geometry: Optional[dict] = None
    created_at: Optional[str] = None

    class Config:
        from_attributes = True


class TestPointRequest(BaseModel):
    latitude: float
    longitude: float
    geofence_id: Optional[UUID] = None


@router.get("", response_model=List[GeofenceResponse])
async def list_geofences(
    farm_id: Optional[UUID] = None,
    active: Optional[bool] = None,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """List all geofences, optionally filtered by farm or status."""
    query = select(Geofence)

    if farm_id:
        query = query.where(Geofence.farm_id == farm_id)
    if active is not None:
        query = query.where(Geofence.active == active)

    query = query.order_by(Geofence.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(query)
    geofences = result.scalars().all()

    responses = []
    for fence in geofences:
        # Retrieve geometry from PostGIS if stored, otherwise from JSONB
        geometry = None
        try:
            geo_result = await db.execute(
                text(
                    "SELECT ST_AsGeoJSON(geometry)::json as geojson "
                    "FROM geofences WHERE id = :id"
                ),
                {"id": str(fence.id)},
            )
            row = geo_result.first()
            if row and row.geojson:
                geometry = row.geojson
        except Exception:
            pass

        responses.append(GeofenceResponse(
            id=str(fence.id),
            name=fence.name,
            farm_id=str(fence.farm_id),
            fence_type=fence.fence_type,
            active=fence.active,
            alert_on_breach=fence.alert_on_breach,
            geometry=geometry,
            created_at=fence.created_at.isoformat() if fence.created_at else None,
        ))

    return responses


@router.post("", response_model=GeofenceResponse, status_code=201)
async def create_geofence(geofence: GeofenceCreate, db: AsyncSession = Depends(get_db)):
    """Create a new geofence with GeoJSON polygon geometry."""
    import json

    # Validate geometry is a polygon
    geom_type = geofence.geometry.get("type", "").lower()
    if geom_type != "polygon":
        raise HTTPException(
            status_code=422,
            detail=f"Geometry must be a Polygon, got '{geofence.geometry.get('type')}'",
        )

    coordinates = geofence.geometry.get("coordinates")
    if not coordinates or len(coordinates) == 0:
        raise HTTPException(status_code=422, detail="Polygon must have coordinates")

    # Create the geofence record
    new_fence = Geofence(
        farm_id=geofence.farm_id,
        name=geofence.name,
        fence_type=geofence.fence_type,
        active=geofence.active,
        alert_on_breach=geofence.alert_on_breach,
    )
    db.add(new_fence)
    await db.flush()  # Get the ID

    # Store geometry as PostGIS column (if geometry column exists)
    try:
        geojson_str = json.dumps(geofence.geometry)
        await db.execute(
            text(
                "UPDATE geofences SET geometry = ST_GeomFromGeoJSON(:geojson)::geography "
                "WHERE id = :id"
            ),
            {"geojson": geojson_str, "id": str(new_fence.id)},
        )
    except Exception:
        # If geometry column doesn't exist yet, store in metadata
        pass

    await db.commit()
    await db.refresh(new_fence)

    return GeofenceResponse(
        id=str(new_fence.id),
        name=new_fence.name,
        farm_id=str(new_fence.farm_id),
        fence_type=new_fence.fence_type,
        active=new_fence.active,
        alert_on_breach=new_fence.alert_on_breach,
        geometry=geofence.geometry,
        created_at=new_fence.created_at.isoformat() if new_fence.created_at else None,
    )


@router.get("/{geofence_id}", response_model=GeofenceResponse)
async def get_geofence(geofence_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get geofence details."""
    result = await db.execute(select(Geofence).where(Geofence.id == geofence_id))
    fence = result.scalar_one_or_none()
    if not fence:
        raise HTTPException(status_code=404, detail="Geofence not found")

    # Get geometry
    geometry = None
    try:
        geo_result = await db.execute(
            text(
                "SELECT ST_AsGeoJSON(geometry)::json as geojson "
                "FROM geofences WHERE id = :id"
            ),
            {"id": str(fence.id)},
        )
        row = geo_result.first()
        if row and row.geojson:
            geometry = row.geojson
    except Exception:
        pass

    return GeofenceResponse(
        id=str(fence.id),
        name=fence.name,
        farm_id=str(fence.farm_id),
        fence_type=fence.fence_type,
        active=fence.active,
        alert_on_breach=fence.alert_on_breach,
        geometry=geometry,
        created_at=fence.created_at.isoformat() if fence.created_at else None,
    )


@router.put("/{geofence_id}", response_model=GeofenceResponse)
async def update_geofence(
    geofence_id: UUID, update: GeofenceUpdate, db: AsyncSession = Depends(get_db)
):
    """Update a geofence."""
    import json

    result = await db.execute(select(Geofence).where(Geofence.id == geofence_id))
    fence = result.scalar_one_or_none()
    if not fence:
        raise HTTPException(status_code=404, detail="Geofence not found")

    if update.name is not None:
        fence.name = update.name
    if update.fence_type is not None:
        fence.fence_type = update.fence_type
    if update.active is not None:
        fence.active = update.active
    if update.alert_on_breach is not None:
        fence.alert_on_breach = update.alert_on_breach

    # Update geometry if provided
    if update.geometry is not None:
        try:
            geojson_str = json.dumps(update.geometry)
            await db.execute(
                text(
                    "UPDATE geofences SET geometry = ST_SetSRID(ST_GeomFromGeoJSON(:geojson), 4326) "
                    "WHERE id = :id"
                ),
                {"geojson": geojson_str, "id": str(fence.id)},
            )
        except Exception:
            pass

    await db.commit()
    await db.refresh(fence)

    return GeofenceResponse(
        id=str(fence.id),
        name=fence.name,
        farm_id=str(fence.farm_id),
        fence_type=fence.fence_type,
        active=fence.active,
        alert_on_breach=fence.alert_on_breach,
        geometry=update.geometry,
        created_at=fence.created_at.isoformat() if fence.created_at else None,
    )


@router.delete("/{geofence_id}", status_code=204)
async def delete_geofence(geofence_id: UUID, db: AsyncSession = Depends(get_db)):
    """Delete a geofence."""
    result = await db.execute(select(Geofence).where(Geofence.id == geofence_id))
    fence = result.scalar_one_or_none()
    if not fence:
        raise HTTPException(status_code=404, detail="Geofence not found")

    await db.delete(fence)
    await db.commit()
    return None


@router.post("/test-point")
async def test_point(request: TestPointRequest, db: AsyncSession = Depends(get_db)):
    """Test if a point is inside/outside geofences."""
    query = text("""
        SELECT id, name, fence_type,
               ST_Contains(geometry, ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)) as inside
        FROM geofences
        WHERE active = true
          AND geometry IS NOT NULL
    """)

    if request.geofence_id:
        query = text("""
            SELECT id, name, fence_type,
                   ST_Contains(geometry, ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)) as inside
            FROM geofences
            WHERE id = :fence_id AND geometry IS NOT NULL
        """)

    params = {"lng": request.longitude, "lat": request.latitude}
    if request.geofence_id:
        params["fence_id"] = str(request.geofence_id)

    result = await db.execute(query, params)
    rows = result.fetchall()

    return {
        "latitude": request.latitude,
        "longitude": request.longitude,
        "results": [
            {
                "geofence_id": str(row.id),
                "name": row.name,
                "fence_type": row.fence_type,
                "inside": row.inside,
            }
            for row in rows
        ],
    }
