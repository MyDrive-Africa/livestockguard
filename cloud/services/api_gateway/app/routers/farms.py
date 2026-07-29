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


# ─── Farm Schedule (Admin-configurable daily routine) ─────────────────────────


class FarmScheduleResponse(BaseModel):
    farm_id: str
    kraal_open_time: str
    feeding_duration_min: int
    exit_gate_time: str
    return_start_time: str
    gate_enter_time: str
    water_stop_duration_min: int
    kraal_settle_time: str
    night_mode: str


class FarmScheduleUpdate(BaseModel):
    kraal_open_time: Optional[str] = None
    feeding_duration_min: Optional[int] = None
    exit_gate_time: Optional[str] = None
    return_start_time: Optional[str] = None
    gate_enter_time: Optional[str] = None
    water_stop_duration_min: Optional[int] = None
    kraal_settle_time: Optional[str] = None
    night_mode: Optional[str] = None


@router.get("/{farm_id}/schedule", response_model=FarmScheduleResponse)
async def get_farm_schedule(farm_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get the daily schedule configuration for a farm."""
    from sqlalchemy import text
    result = await db.execute(
        text("SELECT * FROM farm_schedule WHERE farm_id = :farm_id"),
        {"farm_id": str(farm_id)},
    )
    row = result.first()
    if not row:
        # Return defaults
        return FarmScheduleResponse(
            farm_id=str(farm_id),
            kraal_open_time="08:30",
            feeding_duration_min=50,
            exit_gate_time="09:20",
            return_start_time="16:30",
            gate_enter_time="17:00",
            water_stop_duration_min=20,
            kraal_settle_time="17:45",
            night_mode="dry",
        )

    return FarmScheduleResponse(
        farm_id=str(farm_id),
        kraal_open_time=str(row.kraal_open_time)[:5],
        feeding_duration_min=row.feeding_duration_min,
        exit_gate_time=str(row.exit_gate_time)[:5],
        return_start_time=str(row.return_start_time)[:5],
        gate_enter_time=str(row.gate_enter_time)[:5],
        water_stop_duration_min=row.water_stop_duration_min,
        kraal_settle_time=str(row.kraal_settle_time)[:5],
        night_mode=row.night_mode,
    )


@router.put("/{farm_id}/schedule", response_model=FarmScheduleResponse)
async def update_farm_schedule(farm_id: UUID, update: FarmScheduleUpdate, db: AsyncSession = Depends(get_db)):
    """Update the daily schedule for a farm. Admin sets kraal open/close times."""
    from sqlalchemy import text

    # Upsert
    await db.execute(text("""
        INSERT INTO farm_schedule (farm_id, kraal_open_time, feeding_duration_min, exit_gate_time,
            return_start_time, gate_enter_time, water_stop_duration_min, kraal_settle_time, night_mode)
        VALUES (:farm_id, :kraal_open, :feed_dur, :exit_time, :return_time, :gate_enter, :water_dur, :settle, :night_mode)
        ON CONFLICT (farm_id) DO UPDATE SET
            kraal_open_time = COALESCE(:kraal_open, farm_schedule.kraal_open_time),
            feeding_duration_min = COALESCE(:feed_dur_upd, farm_schedule.feeding_duration_min),
            exit_gate_time = COALESCE(:exit_time, farm_schedule.exit_gate_time),
            return_start_time = COALESCE(:return_time, farm_schedule.return_start_time),
            gate_enter_time = COALESCE(:gate_enter, farm_schedule.gate_enter_time),
            water_stop_duration_min = COALESCE(:water_dur_upd, farm_schedule.water_stop_duration_min),
            kraal_settle_time = COALESCE(:settle, farm_schedule.kraal_settle_time),
            night_mode = COALESCE(:night_mode, farm_schedule.night_mode),
            updated_at = NOW()
    """), {
        "farm_id": str(farm_id),
        "kraal_open": update.kraal_open_time or "08:30",
        "feed_dur": update.feeding_duration_min or 50,
        "feed_dur_upd": update.feeding_duration_min,
        "exit_time": update.exit_gate_time or "09:20",
        "return_time": update.return_start_time or "16:30",
        "gate_enter": update.gate_enter_time or "17:00",
        "water_dur": update.water_stop_duration_min or 20,
        "water_dur_upd": update.water_stop_duration_min,
        "settle": update.kraal_settle_time or "17:45",
        "night_mode": update.night_mode or "dry",
    })
    await db.commit()

    return await get_farm_schedule(farm_id, db)
