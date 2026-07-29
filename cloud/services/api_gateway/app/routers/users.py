"""
User management router — admin can add/edit users, change passwords, assign roles.
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
from app.dependencies import get_db, get_current_user
from app.routers.auth import pwd_context

router = APIRouter(dependencies=[Depends(get_current_user)])


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
    role: str = "viewer"  # owner, manager, viewer, herdsman


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
    """Create a new user (admin only)."""
    if user["role"] not in ("owner", "admin", "manager"):
        raise HTTPException(status_code=403, detail="Only managers+ can create users")

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
    """Update user details (name, role, active status)."""
    if user["role"] not in ("owner", "admin", "manager"):
        raise HTTPException(status_code=403, detail="Only managers+ can edit users")

    result = await db.execute(select(User).where(User.id == user_id))
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

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
    if str(user_id) != user["user_id"] and user["role"] not in ("owner", "admin"):
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
    """Deactivate a user (soft delete)."""
    if user["role"] not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Only admins can delete users")

    result = await db.execute(select(User).where(User.id == user_id))
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    target.active = False
    await db.commit()
    return None
