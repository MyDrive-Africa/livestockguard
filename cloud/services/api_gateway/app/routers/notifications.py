"""
Notification preferences router — CRUD for per-user per-farm notification settings.
"""

import os
import sys
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'shared'))

from livestockguard_common.db_models import NotificationPreference
from app.dependencies import get_db, get_current_user

router = APIRouter(dependencies=[Depends(get_current_user)])


# ─── Schemas ──────────────────────────────────────────

class NotificationPrefCreate(BaseModel):
    farm_id: UUID
    push_enabled: bool = True
    email_enabled: bool = True
    sms_enabled: bool = False
    webhook_enabled: bool = False
    min_severity: str = "medium"
    quiet_start: Optional[str] = None
    quiet_end: Optional[str] = None
    sms_phone: Optional[str] = None
    webhook_url: Optional[str] = None


class NotificationPrefUpdate(BaseModel):
    push_enabled: Optional[bool] = None
    email_enabled: Optional[bool] = None
    sms_enabled: Optional[bool] = None
    webhook_enabled: Optional[bool] = None
    min_severity: Optional[str] = None
    quiet_start: Optional[str] = None
    quiet_end: Optional[str] = None
    sms_phone: Optional[str] = None
    webhook_url: Optional[str] = None


class NotificationPrefResponse(BaseModel):
    id: str
    user_id: str
    farm_id: str
    push_enabled: bool
    email_enabled: bool
    sms_enabled: bool
    webhook_enabled: bool
    min_severity: str
    quiet_start: Optional[str] = None
    quiet_end: Optional[str] = None
    sms_phone: Optional[str] = None
    webhook_url: Optional[str] = None

    class Config:
        from_attributes = True


# ─── Endpoints ────────────────────────────────────────

@router.get("", response_model=List[NotificationPrefResponse])
async def list_preferences(
    farm_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """List notification preferences for the current user."""
    query = select(NotificationPreference).where(
        NotificationPreference.user_id == user["user_id"]
    )
    if farm_id:
        query = query.where(NotificationPreference.farm_id == farm_id)

    result = await db.execute(query)
    prefs = result.scalars().all()

    return [
        NotificationPrefResponse(
            id=str(p.id),
            user_id=str(p.user_id),
            farm_id=str(p.farm_id),
            push_enabled=p.push_enabled,
            email_enabled=p.email_enabled,
            sms_enabled=p.sms_enabled,
            webhook_enabled=p.webhook_enabled,
            min_severity=p.min_severity,
            quiet_start=p.quiet_start,
            quiet_end=p.quiet_end,
            sms_phone=p.sms_phone,
            webhook_url=p.webhook_url,
        )
        for p in prefs
    ]


@router.post("", response_model=NotificationPrefResponse, status_code=201)
async def create_preference(
    pref: NotificationPrefCreate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Create notification preferences for a farm."""
    # Check if already exists
    existing = await db.execute(
        select(NotificationPreference).where(
            NotificationPreference.user_id == user["user_id"],
            NotificationPreference.farm_id == pref.farm_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Preferences already exist for this farm")

    new_pref = NotificationPreference(
        user_id=user["user_id"],
        farm_id=pref.farm_id,
        push_enabled=pref.push_enabled,
        email_enabled=pref.email_enabled,
        sms_enabled=pref.sms_enabled,
        webhook_enabled=pref.webhook_enabled,
        min_severity=pref.min_severity,
        quiet_start=pref.quiet_start,
        quiet_end=pref.quiet_end,
        sms_phone=pref.sms_phone,
        webhook_url=pref.webhook_url,
    )
    db.add(new_pref)
    await db.commit()
    await db.refresh(new_pref)

    return NotificationPrefResponse(
        id=str(new_pref.id),
        user_id=str(new_pref.user_id),
        farm_id=str(new_pref.farm_id),
        push_enabled=new_pref.push_enabled,
        email_enabled=new_pref.email_enabled,
        sms_enabled=new_pref.sms_enabled,
        webhook_enabled=new_pref.webhook_enabled,
        min_severity=new_pref.min_severity,
        quiet_start=new_pref.quiet_start,
        quiet_end=new_pref.quiet_end,
        sms_phone=new_pref.sms_phone,
        webhook_url=new_pref.webhook_url,
    )


@router.put("/{pref_id}", response_model=NotificationPrefResponse)
async def update_preference(
    pref_id: UUID,
    update: NotificationPrefUpdate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Update notification preferences."""
    result = await db.execute(
        select(NotificationPreference).where(
            NotificationPreference.id == pref_id,
            NotificationPreference.user_id == user["user_id"],
        )
    )
    pref = result.scalar_one_or_none()
    if not pref:
        raise HTTPException(status_code=404, detail="Preference not found")

    if update.push_enabled is not None:
        pref.push_enabled = update.push_enabled
    if update.email_enabled is not None:
        pref.email_enabled = update.email_enabled
    if update.sms_enabled is not None:
        pref.sms_enabled = update.sms_enabled
    if update.webhook_enabled is not None:
        pref.webhook_enabled = update.webhook_enabled
    if update.min_severity is not None:
        pref.min_severity = update.min_severity
    if update.quiet_start is not None:
        pref.quiet_start = update.quiet_start
    if update.quiet_end is not None:
        pref.quiet_end = update.quiet_end
    if update.sms_phone is not None:
        pref.sms_phone = update.sms_phone
    if update.webhook_url is not None:
        pref.webhook_url = update.webhook_url

    await db.commit()
    await db.refresh(pref)

    return NotificationPrefResponse(
        id=str(pref.id),
        user_id=str(pref.user_id),
        farm_id=str(pref.farm_id),
        push_enabled=pref.push_enabled,
        email_enabled=pref.email_enabled,
        sms_enabled=pref.sms_enabled,
        webhook_enabled=pref.webhook_enabled,
        min_severity=pref.min_severity,
        quiet_start=pref.quiet_start,
        quiet_end=pref.quiet_end,
        sms_phone=pref.sms_phone,
        webhook_url=pref.webhook_url,
    )


@router.delete("/{pref_id}", status_code=204)
async def delete_preference(
    pref_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Delete notification preferences (resets to defaults)."""
    result = await db.execute(
        select(NotificationPreference).where(
            NotificationPreference.id == pref_id,
            NotificationPreference.user_id == user["user_id"],
        )
    )
    pref = result.scalar_one_or_none()
    if not pref:
        raise HTTPException(status_code=404, detail="Preference not found")

    await db.delete(pref)
    await db.commit()
    return None
