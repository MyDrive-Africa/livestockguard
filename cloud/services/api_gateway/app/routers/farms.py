"""
Farm management router — supports multi-location / client onboarding.
"""

import os
import sys
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'shared'))

from livestockguard_common.db_models import Farm
from app.dependencies import get_db

router = APIRouter()


class FarmCreate(BaseModel):
    name: str
    organisation_id: UUID
    province: Optional[str] = None
    district: Optional[str] = None
    plot_number: Optional[str] = None
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    area_hectares: Optional[float] = None
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    timezone: str = "Africa/Johannesburg"


class FarmResponse(BaseModel):
    id: str
    name: str
    organisation_id: str
    province: Optional[str] = None
    district: Optional[str] = None
    plot_number: Optional[str] = None
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    area_hectares: Optional[float] = None
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    timezone: str

    class Config:
        from_attributes = True


@router.get("", response_model=List[FarmResponse])
async def list_farms(
    organisation_id: Optional[UUID] = None,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """List all farms, optionally filtered by organisation."""
    query = select(Farm)
    if organisation_id:
        query = query.where(Farm.organisation_id == organisation_id)
    query = query.limit(limit).offset(offset)

    result = await db.execute(query)
    farms = result.scalars().all()

    return [
        FarmResponse(
            id=str(f.id),
            name=f.name,
            organisation_id=str(f.organisation_id),
            province=f.province,
            district=f.district,
            plot_number=f.plot_number,
            address=f.address,
            latitude=f.latitude,
            longitude=f.longitude,
            area_hectares=f.area_hectares,
            contact_name=f.contact_name,
            contact_phone=f.contact_phone,
            timezone=f.timezone,
        )
        for f in farms
    ]


@router.get("/{farm_id}", response_model=FarmResponse)
async def get_farm(farm_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get a single farm by ID."""
    result = await db.execute(select(Farm).where(Farm.id == farm_id))
    farm = result.scalar_one_or_none()
    if not farm:
        raise HTTPException(status_code=404, detail="Farm not found")

    return FarmResponse(
        id=str(farm.id),
        name=farm.name,
        organisation_id=str(farm.organisation_id),
        province=farm.province,
        district=farm.district,
        plot_number=farm.plot_number,
        address=farm.address,
        latitude=farm.latitude,
        longitude=farm.longitude,
        area_hectares=farm.area_hectares,
        contact_name=farm.contact_name,
        contact_phone=farm.contact_phone,
        timezone=farm.timezone,
    )


@router.post("", response_model=FarmResponse, status_code=201)
async def create_farm(farm: FarmCreate, db: AsyncSession = Depends(get_db)):
    """Create a new farm (onboard a new location/plot)."""
    new_farm = Farm(
        name=farm.name,
        organisation_id=farm.organisation_id,
        province=farm.province,
        district=farm.district,
        plot_number=farm.plot_number,
        address=farm.address,
        latitude=farm.latitude,
        longitude=farm.longitude,
        area_hectares=farm.area_hectares,
        contact_name=farm.contact_name,
        contact_phone=farm.contact_phone,
        timezone=farm.timezone,
    )
    db.add(new_farm)
    await db.commit()
    await db.refresh(new_farm)

    return FarmResponse(
        id=str(new_farm.id),
        name=new_farm.name,
        organisation_id=str(new_farm.organisation_id),
        province=new_farm.province,
        district=new_farm.district,
        plot_number=new_farm.plot_number,
        address=new_farm.address,
        latitude=new_farm.latitude,
        longitude=new_farm.longitude,
        area_hectares=new_farm.area_hectares,
        contact_name=new_farm.contact_name,
        contact_phone=new_farm.contact_phone,
        timezone=new_farm.timezone,
    )
