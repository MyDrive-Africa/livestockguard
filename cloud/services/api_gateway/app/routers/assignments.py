"""
Farm assignment router — manage user↔farm access (who can access which farm).

Access rules:
  - Admin: can assign/revoke anyone to any farm in the org
  - Farm Owner: can assign/revoke herdsmen and viewers to their farm
  - Herdsman/Viewer: no assignment permissions
"""

import os
import sys
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'shared'))

from livestockguard_common.db_models import Farm, User, UserFarmAssignment
from app.dependencies import get_db, get_current_user, get_user_farms, ROLE_HIERARCHY

router = APIRouter(dependencies=[Depends(get_current_user)])


# ─── Schemas ──────────────────────────────────────────

class AssignmentCreate(BaseModel):
    user_id: UUID
    farm_id: UUID
    role_at_farm: str  # 'farm_owner', 'herdsman', 'viewer'


class AssignmentResponse(BaseModel):
    id: str
    user_id: str
    farm_id: str
    farm_name: Optional[str] = None
    user_name: Optional[str] = None
    user_email: Optional[str] = None
    role_at_farm: str
    assigned_by: Optional[str] = None
    assigned_at: str
    revoked_at: Optional[str] = None

    class Config:
        from_attributes = True


class MyFarmsResponse(BaseModel):
    farm_id: str
    farm_name: str
    role_at_farm: str


# ─── Endpoints ────────────────────────────────────────

@router.get("/me/farms", response_model=List[MyFarmsResponse])
async def get_my_farms(
    farms: List[dict] = Depends(get_user_farms),
):
    """
    Get the list of farms the current user can access.

    - Admin: all farms in org
    - Farm owner / herdsman / viewer: only assigned farms
    """
    return [MyFarmsResponse(**f) for f in farms]


@router.get("/farms/{farm_id}/assignments", response_model=List[AssignmentResponse])
async def list_farm_assignments(
    farm_id: UUID,
    include_revoked: bool = Query(default=False),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all user assignments for a farm. Admin or farm_owner of that farm only."""
    await _check_assignment_permission(user, farm_id, db)

    query = (
        select(UserFarmAssignment, User, Farm)
        .join(User, UserFarmAssignment.user_id == User.id)
        .join(Farm, UserFarmAssignment.farm_id == Farm.id)
        .where(UserFarmAssignment.farm_id == farm_id)
    )
    if not include_revoked:
        query = query.where(UserFarmAssignment.revoked_at.is_(None))

    result = await db.execute(query)
    rows = result.all()

    return [
        AssignmentResponse(
            id=str(assignment.id),
            user_id=str(assignment.user_id),
            farm_id=str(assignment.farm_id),
            farm_name=farm.name,
            user_name=target_user.full_name,
            user_email=target_user.email,
            role_at_farm=assignment.role_at_farm,
            assigned_by=str(assignment.assigned_by) if assignment.assigned_by else None,
            assigned_at=assignment.assigned_at.isoformat(),
            revoked_at=assignment.revoked_at.isoformat() if assignment.revoked_at else None,
        )
        for assignment, target_user, farm in rows
    ]


@router.post("/farms/{farm_id}/assignments", response_model=AssignmentResponse, status_code=201)
async def assign_user_to_farm(
    farm_id: UUID,
    req: AssignmentCreate,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Assign a user to a farm with a specific role.

    - Admin: can assign any role (farm_owner, herdsman, viewer)
    - Farm Owner: can assign herdsman or viewer to their farm only
    """
    await _check_assignment_permission(user, farm_id, db)

    # Farm owners can only assign herdsman or viewer
    if user["role"] != "admin" and req.role_at_farm == "farm_owner":
        raise HTTPException(
            status_code=403,
            detail="Only admin can assign farm_owner role",
        )

    # Validate role_at_farm
    if req.role_at_farm not in ("farm_owner", "herdsman", "viewer"):
        raise HTTPException(
            status_code=400,
            detail="role_at_farm must be one of: farm_owner, herdsman, viewer",
        )

    # Validate the target user exists and is in the same org
    target = await db.execute(select(User).where(User.id == req.user_id))
    target_user = target.scalar_one_or_none()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    # Validate the farm exists
    farm_result = await db.execute(select(Farm).where(Farm.id == farm_id))
    farm = farm_result.scalar_one_or_none()
    if not farm:
        raise HTTPException(status_code=404, detail="Farm not found")

    # Check for existing active assignment
    existing = await db.execute(
        select(UserFarmAssignment).where(
            UserFarmAssignment.user_id == req.user_id,
            UserFarmAssignment.farm_id == farm_id,
            UserFarmAssignment.revoked_at.is_(None),
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail="User already has an active assignment to this farm. Revoke it first to change role.",
        )

    # Create assignment
    assignment = UserFarmAssignment(
        user_id=req.user_id,
        farm_id=farm_id,
        role_at_farm=req.role_at_farm,
        assigned_by=UUID(user["user_id"]),
    )
    db.add(assignment)
    await db.commit()
    await db.refresh(assignment)

    return AssignmentResponse(
        id=str(assignment.id),
        user_id=str(assignment.user_id),
        farm_id=str(assignment.farm_id),
        farm_name=farm.name,
        user_name=target_user.full_name,
        user_email=target_user.email,
        role_at_farm=assignment.role_at_farm,
        assigned_by=str(assignment.assigned_by) if assignment.assigned_by else None,
        assigned_at=assignment.assigned_at.isoformat(),
        revoked_at=None,
    )


@router.delete("/farms/{farm_id}/assignments/{user_id}", status_code=200)
async def revoke_farm_assignment(
    farm_id: UUID,
    user_id: UUID,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Revoke a user's access to a farm (soft delete — sets revoked_at).

    - Admin: can revoke anyone
    - Farm Owner: can revoke herdsman/viewer from their farm
    """
    await _check_assignment_permission(user, farm_id, db)

    result = await db.execute(
        select(UserFarmAssignment).where(
            UserFarmAssignment.user_id == user_id,
            UserFarmAssignment.farm_id == farm_id,
            UserFarmAssignment.revoked_at.is_(None),
        )
    )
    assignment = result.scalar_one_or_none()
    if not assignment:
        raise HTTPException(status_code=404, detail="No active assignment found")

    # Farm owners cannot revoke other farm_owners
    if user["role"] != "admin" and assignment.role_at_farm == "farm_owner":
        raise HTTPException(
            status_code=403,
            detail="Only admin can revoke farm_owner assignments",
        )

    assignment.revoked_at = datetime.now(timezone.utc)
    await db.commit()

    return {"detail": "Assignment revoked", "user_id": str(user_id), "farm_id": str(farm_id)}


# ─── Helpers ──────────────────────────────────────────

async def _check_assignment_permission(user: dict, farm_id: UUID, db: AsyncSession):
    """
    Verify the requesting user has permission to manage assignments on this farm.
    Admin: always allowed.
    Farm Owner: allowed only if they have an active farm_owner assignment to this farm.
    Others: denied.
    """
    if user["role"] == "admin":
        return  # Admin can manage any farm

    # Check if user is farm_owner of this specific farm
    result = await db.execute(
        select(UserFarmAssignment).where(
            UserFarmAssignment.user_id == UUID(user["user_id"]),
            UserFarmAssignment.farm_id == farm_id,
            UserFarmAssignment.role_at_farm == "farm_owner",
            UserFarmAssignment.revoked_at.is_(None),
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=403,
            detail="Only admin or farm_owner of this farm can manage assignments",
        )
