"""
User management router — admin/farm_owner can add/edit users, change passwords, assign roles.

Role model:
  - admin: can create any user role, manage all users in org
  - farm_owner: can create herdsman/viewer users for their farms
  - herdsman/viewer: no user management permissions
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

from livestockguard_common.db_models import User
from app.dependencies import get_db, get_current_user, ROLE_HIERARCHY
from app.routers.auth import pwd_context

router = APIRouter(dependencies=[Depends(get_current_user)])

# Valid roles in the system
VALID_ROLES = ("admin", "farm_owner", "herdsman", "viewer")


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    active: bool
    last_login: Optional[str] = None
    created_at: Optional[str] = None

    class Config:
        from_attributes = True


class UserCreate(BaseModel):
    email: str
    password: str
    full_name: str
    role: str = "viewer"  # admin, farm_owner, herdsman, viewer


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    role: Optional[str] = None
    active: Optional[bool] = None
    email: Optional[str] = None


class PasswordChange(BaseModel):
    new_password: str


@router.get("", response_model=List[UserResponse])
async def list_users(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """List all users in the same organisation."""
    # Get current user's org
    current = await db.execute(select(User).where(User.id == UUID(user["user_id"])))
    current_user = current.scalar_one_or_none()
    if not current_user:
        raise HTTPException(status_code=404, detail="User not found")

    result = await db.execute(
        select(User).where(User.organisation_id == current_user.organisation_id)
    )
    users = result.scalars().all()

    return [
        UserResponse(
            id=str(u.id),
            email=u.email,
            full_name=u.full_name,
            role=u.role,
            active=u.active,
            last_login=u.last_login.isoformat() if u.last_login else None,
            created_at=u.created_at.isoformat() if u.created_at else None,
        )
        for u in users
    ]


@router.post("", response_model=UserResponse, status_code=201)
async def create_user(
    req: UserCreate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """
    Create a new user in the organisation.

    Permissions:
      - admin: can create users with any role
      - farm_owner: can create herdsman or viewer users only
      - herdsman/viewer: cannot create users
    """
    # Check permission to create users
    if user["role"] not in ("admin", "farm_owner"):
        raise HTTPException(status_code=403, detail="Only admin or farm_owner can create users")

    # Validate requested role
    if req.role not in VALID_ROLES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid role. Must be one of: {', '.join(VALID_ROLES)}",
        )

    # Farm owners can only create herdsman or viewer
    if user["role"] == "farm_owner" and req.role not in ("herdsman", "viewer"):
        raise HTTPException(
            status_code=403,
            detail="Farm owners can only create herdsman or viewer users",
        )

    # Get org from current user
    current = await db.execute(select(User).where(User.id == UUID(user["user_id"])))
    current_user = current.scalar_one_or_none()

    # Check email uniqueness
    existing = await db.execute(select(User).where(User.email == req.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already in use")

    new_user = User(
        organisation_id=current_user.organisation_id,
        email=req.email,
        password_hash=pwd_context.hash(req.password),
        full_name=req.full_name,
        role=req.role,
        active=True,
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    return UserResponse(
        id=str(new_user.id),
        email=new_user.email,
        full_name=new_user.full_name,
        role=new_user.role,
        active=new_user.active,
        created_at=new_user.created_at.isoformat() if new_user.created_at else None,
    )


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID,
    req: UserUpdate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """
    Update user details (name, role, active status).

    Permissions:
      - admin: can edit any user
      - farm_owner: can edit herdsman/viewer users only
    """
    if user["role"] not in ("admin", "farm_owner"):
        raise HTTPException(status_code=403, detail="Only admin or farm_owner can edit users")

    result = await db.execute(select(User).where(User.id == user_id))
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    # Farm owners cannot edit admin or other farm_owners
    if user["role"] == "farm_owner" and target.role in ("admin", "farm_owner"):
        raise HTTPException(
            status_code=403,
            detail="Farm owners cannot edit admin or other farm_owner users",
        )

    # Validate role if being changed
    if req.role is not None:
        if req.role not in VALID_ROLES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid role. Must be one of: {', '.join(VALID_ROLES)}",
            )
        # Farm owners cannot promote to admin or farm_owner
        if user["role"] == "farm_owner" and req.role not in ("herdsman", "viewer"):
            raise HTTPException(
                status_code=403,
                detail="Farm owners can only assign herdsman or viewer roles",
            )

    if req.full_name is not None:
        target.full_name = req.full_name
    if req.role is not None:
        target.role = req.role
    if req.active is not None:
        target.active = req.active
    if req.email is not None:
        target.email = req.email

    await db.commit()
    await db.refresh(target)

    return UserResponse(
        id=str(target.id),
        email=target.email,
        full_name=target.full_name,
        role=target.role,
        active=target.active,
        last_login=target.last_login.isoformat() if target.last_login else None,
        created_at=target.created_at.isoformat() if target.created_at else None,
    )


@router.post("/{user_id}/password")
async def change_password(
    user_id: UUID,
    req: PasswordChange,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Change a user's password (admin or self)."""
    # Allow self-change or admin change
    if str(user_id) != user["user_id"] and user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Can only change own password or admin required")

    result = await db.execute(select(User).where(User.id == user_id))
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    target.password_hash = pwd_context.hash(req.new_password)
    await db.commit()

    return {"status": "password_changed", "user_id": str(user_id)}


@router.delete("/{user_id}", status_code=204)
async def delete_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Deactivate a user (soft delete). Admin only."""
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Only admin can deactivate users")

    result = await db.execute(select(User).where(User.id == user_id))
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    target.active = False
    await db.commit()
    return None
