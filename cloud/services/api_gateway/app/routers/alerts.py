"""
Alerts router — wired to real database.
"""

import os
import sys
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'shared'))

from livestockguard_common.db_models import Alert, Animal
from app.dependencies import get_db, get_current_user

router = APIRouter(dependencies=[Depends(get_current_user)])


class AlertResponse(BaseModel):
    id: str
    alert_type: str
    severity: str
    status: str
    message: Optional[str] = None
    animal_name: Optional[str] = None
    created_at: str

    class Config:
        from_attributes = True


@router.get("", response_model=List[AlertResponse])
async def list_alerts(
    farm_id: Optional[UUID] = None,
    status: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = Query(default=50, le=500),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """List alerts with filters."""
    query = select(Alert, Animal.name.label("animal_name")).outerjoin(
        Animal, Alert.animal_id == Animal.id
    ).order_by(Alert.created_at.desc())

    if farm_id:
        query = query.where(Alert.farm_id == farm_id)
    if status:
        query = query.where(Alert.status == status)
    if severity:
        query = query.where(Alert.severity == severity)

    query = query.limit(limit).offset(offset)
    result = await db.execute(query)
    rows = result.all()

    return [
        AlertResponse(
            id=str(row.Alert.id),
            alert_type=row.Alert.alert_type,
            severity=row.Alert.severity,
            status=row.Alert.status,
            message=row.Alert.message,
            animal_name=row.animal_name,
            created_at=row.Alert.created_at.isoformat(),
        )
        for row in rows
    ]


@router.put("/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: UUID, db: AsyncSession = Depends(get_db)):
    """Acknowledge an alert."""
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    alert.status = "acknowledged"
    alert.acknowledged_at = datetime.now(timezone.utc)
    await db.commit()

    return {"status": "acknowledged", "id": str(alert_id)}


@router.put("/{alert_id}/resolve")
async def resolve_alert(alert_id: UUID, db: AsyncSession = Depends(get_db)):
    """Resolve an alert."""
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    alert.status = "resolved"
    alert.resolved_at = datetime.now(timezone.utc)
    await db.commit()

    return {"status": "resolved", "id": str(alert_id)}
