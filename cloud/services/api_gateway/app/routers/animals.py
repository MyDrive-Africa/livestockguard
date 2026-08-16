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
    last_latitude: Optional[float] = None
    last_longitude: Optional[float] = None


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
    """
    Convert Animal ORM instance to API response model.

    Args:
        animal: SQLAlchemy Animal model instance from the database.
        device_serial: Serial number of the GPS collar assigned to this animal (if any).
        pos: Latest position row (from the positions hypertable) with attributes:
             latitude, longitude, speed, battery_mv. Can be None if no GPS fix recorded.

    Returns:
        AnimalResponse Pydantic model ready for JSON serialization.
    """
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
    """
    List animals with their latest position. Filterable by farm, species, status, gender.

    Args:
        farm_id: Filter by farm UUID (optional — returns all farms if omitted).
        species: Filter by species string (e.g., 'cattle', 'sheep').
        status: Filter by status ('active', 'sold', 'deceased'). Defaults to 'active' if omitted.
        gender: Filter by gender ('male', 'female').
        limit: Maximum number of results (default 100, max 1000).
        offset: Pagination offset for cursor-based paging.
        db: Async database session (injected).

    Returns:
        List of AnimalResponse objects, each including the latest GPS position if available.
    """
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
        # Get latest position for this animal (GPS collar first, then BLE gateway fallback)
        pos_query = text("""
            SELECT latitude, longitude, speed, battery_mv
            FROM positions
            WHERE animal_id = :animal_id
            ORDER BY time DESC LIMIT 1
        """)
        pos_result = await db.execute(pos_query, {"animal_id": str(row.Animal.id)})
        pos = pos_result.first()

        # BLE fallback: if no GPS position, check ble_sightings for gateway coords
        if not pos:
            ble_query = text("""
                SELECT COALESCE(estimated_latitude, gateway_latitude) AS latitude,
                       COALESCE(estimated_longitude, gateway_longitude) AS longitude,
                       gateway_speed AS speed, NULL::int AS battery_mv
                FROM ble_sightings
                WHERE animal_id = :animal_id
                ORDER BY time DESC LIMIT 1
            """)
            ble_result = await db.execute(ble_query, {"animal_id": str(row.Animal.id)})
            pos = ble_result.first()

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

    # Get latest position (GPS first, BLE fallback)
    pos_query = text("""
        SELECT latitude, longitude, speed, battery_mv
        FROM positions
        WHERE animal_id = :animal_id
        ORDER BY time DESC LIMIT 1
    """)
    pos_result = await db.execute(pos_query, {"animal_id": str(animal_id)})
    pos = pos_result.first()

    if not pos:
        ble_query = text("""
            SELECT COALESCE(estimated_latitude, gateway_latitude) AS latitude,
                   COALESCE(estimated_longitude, gateway_longitude) AS longitude,
                   gateway_speed AS speed, NULL::int AS battery_mv
            FROM ble_sightings
            WHERE animal_id = :animal_id
            ORDER BY time DESC LIMIT 1
        """)
        ble_result = await db.execute(ble_query, {"animal_id": str(animal_id)})
        pos = ble_result.first()

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
    """Update animal details (name, breed, weight, photo, etc.).
    Admin/farmowner can also set last_latitude/last_longitude to manually correct position."""
    result = await db.execute(select(Animal).where(Animal.id == animal_id))
    animal = result.scalar_one_or_none()
    if not animal:
        raise HTTPException(status_code=404, detail="Animal not found")

    update_data = updates.model_dump(exclude_unset=True)

    # Handle manual location update — insert into positions table
    new_lat = update_data.pop("last_latitude", None)
    new_lon = update_data.pop("last_longitude", None)
    if new_lat is not None and new_lon is not None:
        # Use the animal's linked device_id for the position record.
        # If no device is linked, try to find any device on the same farm as a placeholder.
        device_id = str(animal.device_id) if animal.device_id else None
        if not device_id:
            fallback = await db.execute(text("""
                SELECT id FROM devices WHERE farm_id = :farm_id LIMIT 1
            """), {"farm_id": str(animal.farm_id)})
            row = fallback.first()
            if row:
                device_id = str(row.id)

        if device_id:
            await db.execute(text("""
                INSERT INTO positions (animal_id, device_id, time, latitude, longitude, location, speed, heading, battery_mv)
                VALUES (:animal_id, :device_id::uuid, NOW(), :lat, :lon, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography, 0, 0, NULL)
            """), {"animal_id": str(animal_id), "device_id": device_id, "lat": new_lat, "lon": new_lon})

    for field, value in update_data.items():
        setattr(animal, field, value)

    await db.commit()
    await db.refresh(animal)

    # Re-fetch position to include the manual update
    pos_query = text("""
        SELECT latitude, longitude, speed, battery_mv
        FROM positions
        WHERE animal_id = :animal_id
        ORDER BY time DESC LIMIT 1
    """)
    pos_result = await db.execute(pos_query, {"animal_id": str(animal_id)})
    pos = pos_result.first()

    if not pos:
        ble_query = text("""
            SELECT COALESCE(estimated_latitude, gateway_latitude) AS latitude,
                   COALESCE(estimated_longitude, gateway_longitude) AS longitude,
                   gateway_speed AS speed, NULL::int AS battery_mv
            FROM ble_sightings
            WHERE animal_id = :animal_id
            ORDER BY time DESC LIMIT 1
        """)
        ble_result = await db.execute(ble_query, {"animal_id": str(animal_id)})
        pos = ble_result.first()

    return _animal_to_response(animal, pos=pos)


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
    date: Optional[str] = Query(default=None, description="Specific date (YYYY-MM-DD) to get trail for that day"),
    limit: int = Query(default=500, le=5000),
    db: AsyncSession = Depends(get_db),
):
    """Get position history for an animal (GPS or BLE gateway positions).
    
    If 'date' is provided, returns trail for that specific day.
    Otherwise returns last N hours.
    """
    # Build time filter
    if date:
        # Specific day: from 00:00 to 23:59:59 on that date
        time_filter = "AND time >= :start_date AND time < :start_date + INTERVAL '1 day'"
        time_params = {"animal_id": str(animal_id), "start_date": date, "limit": limit}
    else:
        time_filter = "AND time > NOW() - make_interval(hours => :hours)"
        time_params = {"animal_id": str(animal_id), "hours": hours, "limit": limit}

    # Try GPS positions first
    query = text(f"""
        SELECT time, latitude, longitude, speed, heading, battery_mv
        FROM positions
        WHERE animal_id = :animal_id
          {time_filter}
        ORDER BY time DESC
        LIMIT :limit
    """)
    result = await db.execute(query, time_params)
    rows = result.fetchall()

    # BLE fallback: if no GPS history, get positions from ble_sightings
    if not rows:
        ble_query = text(f"""
            SELECT time, gateway_latitude AS latitude, gateway_longitude AS longitude,
                   gateway_speed AS speed, 0 AS heading, NULL AS battery_mv
            FROM ble_sightings
            WHERE animal_id = :animal_id
              {time_filter}
            ORDER BY time DESC
            LIMIT :limit
        """)
        ble_result = await db.execute(ble_query, time_params)
        rows = ble_result.fetchall()

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


# ─── CSV Import ───────────────────────────────────────────────────────────────


class CsvImportRow(BaseModel):
    name: str
    tag_id: str
    species: str = "cattle"
    breed: Optional[str] = None
    gender: Optional[str] = None
    colour: Optional[str] = None
    description: Optional[str] = None
    date_of_birth: Optional[str] = None
    weight_kg: Optional[float] = None


class CsvImportRequest(BaseModel):
    farm_id: UUID
    animals: List[CsvImportRow]


class CsvImportResult(BaseModel):
    imported: int
    skipped: int
    errors: List[str]


@router.post("/import/csv", response_model=CsvImportResult)
async def import_animals_csv(
    request: CsvImportRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Bulk import animals from a parsed CSV payload.

    Accepts a list of animal records (pre-parsed by the frontend) and batch-inserts
    them into the database. Skips rows with duplicate tag_ids (within this farm).

    Expected CSV columns: name, tag_id, species, breed, gender, colour,
    description, date_of_birth (YYYY-MM-DD), weight_kg
    """
    farm_id = request.farm_id
    imported = 0
    skipped = 0
    errors: List[str] = []

    # Get existing tag_ids for this farm to avoid duplicates
    existing_result = await db.execute(
        select(Animal.tag_id).where(Animal.farm_id == farm_id, Animal.status == "active")
    )
    existing_tags = {row[0] for row in existing_result.all()}

    for i, row in enumerate(request.animals):
        row_num = i + 1

        # Validate required fields
        if not row.name or not row.tag_id:
            errors.append(f"Row {row_num}: name and tag_id are required")
            skipped += 1
            continue

        # Skip duplicates
        if row.tag_id in existing_tags:
            errors.append(f"Row {row_num}: tag_id '{row.tag_id}' already exists")
            skipped += 1
            continue

        # Parse date_of_birth if provided
        dob = None
        if row.date_of_birth:
            try:
                dob = date.fromisoformat(row.date_of_birth)
            except ValueError:
                errors.append(f"Row {row_num}: invalid date_of_birth '{row.date_of_birth}'")

        # Validate gender
        gender = row.gender.lower() if row.gender else None
        if gender and gender not in ("male", "female"):
            gender = None

        try:
            new_animal = Animal(
                farm_id=farm_id,
                name=row.name.strip(),
                tag_id=row.tag_id.strip(),
                species=row.species or "cattle",
                breed=row.breed,
                gender=gender,
                colour=row.colour,
                description=row.description,
                date_of_birth=dob,
                weight_kg=row.weight_kg,
                status="active",
            )
            db.add(new_animal)
            existing_tags.add(row.tag_id)
            imported += 1
        except Exception as e:
            errors.append(f"Row {row_num}: {str(e)}")
            skipped += 1

    if imported > 0:
        await db.commit()

    return CsvImportResult(imported=imported, skipped=skipped, errors=errors[:20])
