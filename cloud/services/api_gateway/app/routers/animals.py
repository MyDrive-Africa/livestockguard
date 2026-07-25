"""
Animal management router — wired to real database.
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

from livestockguard_common.db_models import Animal, Device
from app.dependencies import get_db, get_current_user

router = APIRouter(dependencies=[Depends(get_current_user)])


class AnimalCreate(BaseModel):
    name: str
    tag_id: str
    species: str = "cattle"
    breed: Optional[str] = None
    farm_id: UUID
    device_id: Optional[UUID] = None


class AnimalResponse(BaseModel):
    id: str
    name: str
    tag_id: str
    species: str
    breed: Optional[str] = None
    device_serial: Optional[str] = None
    last_latitude: Optional[float] = None
    last_longitude: Optional[float] = None
    last_speed: Optional[float] = None
    battery_level: Optional[int] = None

    class Config:
        from_attributes = True


@router.get("", response_model=List[AnimalResponse])
async def list_animals(
    farm_id: Optional[UUID] = None,
    species: Optional[str] = None,
    limit: int = Query(default=100, le=1000),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """List animals with their latest position."""
    query = select(Animal, Device.serial_number.label("device_serial")).outerjoin(
        Device, Animal.device_id == Device.id
    )

    if farm_id:
        query = query.where(Animal.farm_id == farm_id)
    if species:
        query = query.where(Animal.species == species)

    query = query.limit(limit).offset(offset)
    result = await db.execute(query)
    rows = result.all()

    animals = []
    for row in rows:
        # Get latest position for this animal
        pos_query = text("""
            SELECT latitude, longitude, speed, battery_mv
            FROM positions
            WHERE animal_id = :animal_id
            ORDER BY time DESC LIMIT 1
        """)
        pos_result = await db.execute(pos_query, {"animal_id": str(row.Animal.id)})
        pos = pos_result.first()

        animals.append(AnimalResponse(
            id=str(row.Animal.id),
            name=row.Animal.name,
            tag_id=row.Animal.tag_id,
            species=row.Animal.species,
            breed=row.Animal.breed,
            device_serial=row.device_serial,
            last_latitude=pos.latitude if pos else None,
            last_longitude=pos.longitude if pos else None,
            last_speed=pos.speed if pos else None,
            battery_level=int(pos.battery_mv / 37) if pos and pos.battery_mv else None,
        ))

    return animals


@router.post("", response_model=AnimalResponse, status_code=201)
async def create_animal(animal: AnimalCreate, db: AsyncSession = Depends(get_db)):
    """Register a new animal."""
    new_animal = Animal(
        farm_id=animal.farm_id,
        name=animal.name,
        tag_id=animal.tag_id,
        species=animal.species,
        breed=animal.breed,
        device_id=animal.device_id,
    )
    db.add(new_animal)
    await db.commit()
    await db.refresh(new_animal)

    return AnimalResponse(
        id=str(new_animal.id),
        name=new_animal.name,
        tag_id=new_animal.tag_id,
        species=new_animal.species,
        breed=new_animal.breed,
    )


@router.get("/{animal_id}", response_model=AnimalResponse)
async def get_animal(animal_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get animal details."""
    result = await db.execute(select(Animal).where(Animal.id == animal_id))
    animal = result.scalar_one_or_none()
    if not animal:
        raise HTTPException(status_code=404, detail="Animal not found")

    return AnimalResponse(
        id=str(animal.id),
        name=animal.name,
        tag_id=animal.tag_id,
        species=animal.species,
        breed=animal.breed,
    )


@router.get("/{animal_id}/history")
async def get_animal_history(
    animal_id: UUID,
    hours: int = Query(default=24, le=168),
    limit: int = Query(default=500, le=5000),
    db: AsyncSession = Depends(get_db),
):
    """Get position history for an animal."""
    query = text("""
        SELECT time, latitude, longitude, speed, heading, battery_mv
        FROM positions
        WHERE animal_id = :animal_id
          AND time > NOW() - make_interval(hours => :hours)
        ORDER BY time DESC
        LIMIT :limit
    """)
    result = await db.execute(query, {
        "animal_id": str(animal_id),
        "hours": hours,
        "limit": limit,
    })
    rows = result.fetchall()

    return {
        "animal_id": str(animal_id),
        "positions": [
            {
                "time": row.time.isoformat(),
                "lat": row.latitude,
                "lon": row.longitude,
                "speed": row.speed,
                "heading": row.heading,
            }
            for row in rows
        ],
        "count": len(rows),
    }
