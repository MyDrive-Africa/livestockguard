"""
Animal management router — wired to real database.
Supports full inventory lifecycle: create, update, mark deceased, transfer, add newborn.
"""

import os
import sys
from datetime import date
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


# ─── Request/Response Models ─────────────────────────────────────────────────


class AnimalCreate(BaseModel):
    name: str
    tag_id: str
    species: str = "cattle"
    breed: Optional[str] = None
    gender: Optional[str] = None  # 'male' or 'female'
    colour: Optional[str] = None
    description: Optional[str] = None
    date_of_birth: Optional[date] = None
    weight_kg: Optional[float] = None
    photo_url: Optional[str] = None
    farm_id: UUID
    device_id: Optional[UUID] = None
    mother_id: Optional[UUID] = None
    father_id: Optional[UUID] = None


class AnimalUpdate(BaseModel):
    name: Optional[str] = None
    breed: Optional[str] = None
    gender: Optional[str] = None
    colour: Optional[str] = None
    description: Optional[str] = None
    date_of_birth: Optional[date] = None
    weight_kg: Optional[float] = None
    photo_url: Optional[str] = None
    notes: Optional[str] = None
    device_id: Optional[UUID] = None


class AnimalResponse(BaseModel):
    id: str
    name: str
    tag_id: str
    species: str
    breed: Optional[str] = None
    gender: Optional[str] = None
    colour: Optional[str] = None
    description: Optional[str] = None
    photo_url: Optional[str] = None
    weight_kg: Optional[float] = None
    status: str = "active"
    date_of_birth: Optional[str] = None
    mother_id: Optional[str] = None
    father_id: Optional[str] = None
    device_serial: Optional[str] = None
    last_latitude: Optional[float] = None
    last_longitude: Optional[float] = None
    last_speed: Optional[float] = None
    battery_level: Optional[int] = None

    class Config:
        from_attributes = True


class MarkDeceasedRequest(BaseModel):
    reason: Optional[str] = None
    date_of_death: Optional[date] = None


class TransferRequest(BaseModel):
    target_farm_id: UUID
    reason: Optional[str] = None
    transfer_date: Optional[date] = None


class NewbornRequest(BaseModel):
    name: str
    tag_id: str
    gender: Optional[str] = None
    colour: Optional[str] = None
    description: Optional[str] = None
    date_of_birth: Optional[date] = None
    breed: Optional[str] = None
    mother_id: UUID
    father_id: Optional[UUID] = None


# ─── Helper ──────────────────────────────────────────────────────────────────


def _animal_to_response(animal: Animal, device_serial: Optional[str] = None,
                        pos=None) -> AnimalResponse:
    """Convert Animal ORM instance to response model."""
    return AnimalResponse(
        id=str(animal.id),
        name=animal.name,
        tag_id=animal.tag_id,
        species=animal.species,
        breed=animal.breed,
        gender=animal.gender,
        colour=animal.colour,
        description=animal.description,
        photo_url=animal.photo_url,
        weight_kg=animal.weight_kg,
        status=animal.status or "active",
        date_of_birth=animal.date_of_birth.isoformat() if animal.date_of_birth else None,
        mother_id=str(animal.mother_id) if animal.mother_id else None,
        father_id=str(animal.father_id) if animal.father_id else None,
        device_serial=device_serial,
        last_latitude=pos.latitude if pos else None,
        last_longitude=pos.longitude if pos else None,
        last_speed=pos.speed if pos else None,
        battery_level=int(pos.battery_mv / 37) if pos and pos.battery_mv else None,
    )


# ─── List & Get ──────────────────────────────────────────────────────────────


@router.get("", response_model=List[AnimalResponse])
async def list_animals(
    farm_id: Optional[UUID] = None,
    species: Optional[str] = None,
    status: Optional[str] = None,
    gender: Optional[str] = None,
    limit: int = Query(default=100, le=1000),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """List animals with their latest position. Filterable by farm, species, status, gender."""
    query = select(Animal, Device.serial_number.label("device_serial")).outerjoin(
        Device, Animal.device_id == Device.id
    )

    if farm_id:
        query = query.where(Animal.farm_id == farm_id)
    if species:
        query = query.where(Animal.species == species)
    if status:
        query = query.where(Animal.status == status)
    else:
        # Default: only show active animals
        query = query.where(Animal.status == "active")
    if gender:
        query = query.where(Animal.gender == gender)

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

        animals.append(_animal_to_response(row.Animal, row.device_serial, pos))

    return animals


@router.get("/{animal_id}", response_model=AnimalResponse)
async def get_animal(animal_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get full animal details including inventory fields."""
    result = await db.execute(
        select(Animal, Device.serial_number.label("device_serial"))
        .outerjoin(Device, Animal.device_id == Device.id)
        .where(Animal.id == animal_id)
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Animal not found")

    # Get latest position
    pos_query = text("""
        SELECT latitude, longitude, speed, battery_mv
        FROM positions
        WHERE animal_id = :animal_id
        ORDER BY time DESC LIMIT 1
    """)
    pos_result = await db.execute(pos_query, {"animal_id": str(animal_id)})
    pos = pos_result.first()

    return _animal_to_response(row.Animal, row.device_serial, pos)


# ─── Create & Update ─────────────────────────────────────────────────────────


@router.post("", response_model=AnimalResponse, status_code=201)
async def create_animal(animal: AnimalCreate, db: AsyncSession = Depends(get_db)):
    """Register a new animal."""
    new_animal = Animal(
        farm_id=animal.farm_id,
        name=animal.name,
        tag_id=animal.tag_id,
        species=animal.species,
        breed=animal.breed,
        gender=animal.gender,
        colour=animal.colour,
        description=animal.description,
        date_of_birth=animal.date_of_birth,
        weight_kg=animal.weight_kg,
        photo_url=animal.photo_url,
        device_id=animal.device_id,
        mother_id=animal.mother_id,
        father_id=animal.father_id,
        status="active",
        acquired_date=date.today(),
    )
    db.add(new_animal)
    await db.commit()
    await db.refresh(new_animal)

    return _animal_to_response(new_animal)


@router.patch("/{animal_id}", response_model=AnimalResponse)
async def update_animal(animal_id: UUID, updates: AnimalUpdate, db: AsyncSession = Depends(get_db)):
    """Update animal details (name, breed, weight, photo, etc.)."""
    result = await db.execute(select(Animal).where(Animal.id == animal_id))
    animal = result.scalar_one_or_none()
    if not animal:
        raise HTTPException(status_code=404, detail="Animal not found")

    update_data = updates.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(animal, field, value)

    await db.commit()
    await db.refresh(animal)

    return _animal_to_response(animal)


# ─── Lifecycle Actions ────────────────────────────────────────────────────────


@router.post("/{animal_id}/deceased", response_model=AnimalResponse)
async def mark_deceased(animal_id: UUID, req: MarkDeceasedRequest, db: AsyncSession = Depends(get_db)):
    """Mark an animal as deceased. Soft-deletes — keeps history."""
    result = await db.execute(select(Animal).where(Animal.id == animal_id))
    animal = result.scalar_one_or_none()
    if not animal:
        raise HTTPException(status_code=404, detail="Animal not found")
    if animal.status != "active":
        raise HTTPException(status_code=400, detail=f"Animal is already {animal.status}")

    animal.status = "deceased"
    animal.removed_date = req.date_of_death or date.today()
    animal.removal_reason = req.reason or "Deceased"
    # Unlink device so it can be reassigned
    animal.device_id = None

    await db.commit()
    await db.refresh(animal)

    return _animal_to_response(animal)


@router.post("/{animal_id}/transfer", response_model=AnimalResponse)
async def transfer_animal(animal_id: UUID, req: TransferRequest, db: AsyncSession = Depends(get_db)):
    """Transfer (sell) an animal to another farm. Keeps record on source farm as 'transferred'."""
    result = await db.execute(select(Animal).where(Animal.id == animal_id))
    animal = result.scalar_one_or_none()
    if not animal:
        raise HTTPException(status_code=404, detail="Animal not found")
    if animal.status != "active":
        raise HTTPException(status_code=400, detail=f"Animal is already {animal.status}")

    # Mark as transferred on the source farm
    animal.status = "transferred"
    animal.removed_date = req.transfer_date or date.today()
    animal.removal_reason = req.reason or f"Transferred to farm {req.target_farm_id}"
    old_device_id = animal.device_id
    animal.device_id = None

    # Create a new record on the target farm
    new_animal = Animal(
        farm_id=req.target_farm_id,
        name=animal.name,
        tag_id=animal.tag_id,
        species=animal.species,
        breed=animal.breed,
        gender=animal.gender,
        colour=animal.colour,
        description=animal.description,
        date_of_birth=animal.date_of_birth,
        weight_kg=animal.weight_kg,
        photo_url=animal.photo_url,
        notes=f"Transferred from farm {animal.farm_id} on {animal.removed_date}",
        mother_id=animal.mother_id,
        father_id=animal.father_id,
        status="active",
        acquired_date=req.transfer_date or date.today(),
    )
    db.add(new_animal)
    await db.commit()
    await db.refresh(animal)
    await db.refresh(new_animal)

    return _animal_to_response(new_animal)


@router.post("/{animal_id}/newborn", response_model=AnimalResponse, status_code=201)
async def register_newborn(animal_id: UUID, req: NewbornRequest, db: AsyncSession = Depends(get_db)):
    """Register a newborn calf linked to this animal (mother). The animal_id in the path is the mother."""
    # Verify mother exists
    result = await db.execute(select(Animal).where(Animal.id == animal_id))
    mother = result.scalar_one_or_none()
    if not mother:
        raise HTTPException(status_code=404, detail="Mother animal not found")

    new_calf = Animal(
        farm_id=mother.farm_id,
        name=req.name,
        tag_id=req.tag_id,
        species=mother.species,
        breed=req.breed or mother.breed,
        gender=req.gender,
        colour=req.colour,
        description=req.description,
        date_of_birth=req.date_of_birth or date.today(),
        mother_id=req.mother_id,
        father_id=req.father_id,
        status="active",
        acquired_date=date.today(),
    )
    db.add(new_calf)
    await db.commit()
    await db.refresh(new_calf)

    return _animal_to_response(new_calf)


# ─── History ─────────────────────────────────────────────────────────────────


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


# ─── Offspring (lineage query) ───────────────────────────────────────────────


@router.get("/{animal_id}/offspring", response_model=List[AnimalResponse])
async def get_offspring(animal_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get all offspring of an animal (as mother or father)."""
    query = select(Animal).where(
        (Animal.mother_id == animal_id) | (Animal.father_id == animal_id)
    )
    result = await db.execute(query)
    offspring = result.scalars().all()

    return [_animal_to_response(calf) for calf in offspring]
