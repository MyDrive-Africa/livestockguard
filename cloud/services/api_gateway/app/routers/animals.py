from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Query
from pydantic import BaseModel

router = APIRouter()


class AnimalCreate(BaseModel):
    name: str
    tag_id: str
    breed: Optional[str] = None
    species: str = "cattle"
    date_of_birth: Optional[str] = None
    farm_id: UUID
    device_id: Optional[UUID] = None


class AnimalUpdate(BaseModel):
    name: Optional[str] = None
    breed: Optional[str] = None
    device_id: Optional[UUID] = None
    notes: Optional[str] = None


@router.get("/")
async def list_animals(
    farm_id: Optional[UUID] = None,
    species: Optional[str] = None,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
):
    """List all animals, optionally filtered by farm or species."""
    return {"animals": [], "total": 0, "limit": limit, "offset": offset}


@router.post("/", status_code=201)
async def create_animal(animal: AnimalCreate):
    """Register a new animal."""
    return {"id": "placeholder", **animal.model_dump()}


@router.get("/{animal_id}")
async def get_animal(animal_id: UUID):
    """Get animal details including current position and status."""
    return {"id": str(animal_id), "name": "", "tag_id": "", "species": "cattle"}


@router.put("/{animal_id}")
async def update_animal(animal_id: UUID, update: AnimalUpdate):
    """Update animal information."""
    return {"id": str(animal_id), **update.model_dump(exclude_none=True)}


@router.delete("/{animal_id}", status_code=204)
async def delete_animal(animal_id: UUID):
    """Remove an animal record."""
    return None


@router.get("/{animal_id}/history")
async def get_animal_history(
    animal_id: UUID,
    start: Optional[str] = None,
    end: Optional[str] = None,
    limit: int = Query(default=100, le=1000),
):
    """Get historical position and activity data for an animal."""
    return {
        "animal_id": str(animal_id),
        "positions": [],
        "activities": [],
        "count": 0,
    }
