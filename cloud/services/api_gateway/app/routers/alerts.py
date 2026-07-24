from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Query
from pydantic import BaseModel

router = APIRouter()


class AcknowledgeRequest(BaseModel):
    acknowledged_by: UUID
    notes: Optional[str] = None


class ResolveRequest(BaseModel):
    resolved_by: UUID
    resolution_notes: Optional[str] = None


@router.get("/")
async def list_alerts(
    farm_id: Optional[UUID] = None,
    severity: Optional[str] = None,
    status: Optional[str] = None,
    alert_type: Optional[str] = None,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
):
    """List alerts with optional filters by farm, severity, status, or type."""
    return {"alerts": [], "total": 0, "limit": limit, "offset": offset}


@router.get("/{alert_id}")
async def get_alert(alert_id: UUID):
    """Get detailed information about a specific alert."""
    return {
        "id": str(alert_id),
        "alert_type": "",
        "severity": "",
        "status": "active",
    }


@router.put("/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: UUID, request: AcknowledgeRequest):
    """Acknowledge an alert."""
    return {
        "id": str(alert_id),
        "status": "acknowledged",
        "acknowledged_by": str(request.acknowledged_by),
    }


@router.put("/{alert_id}/resolve")
async def resolve_alert(alert_id: UUID, request: ResolveRequest):
    """Resolve an alert with optional resolution notes."""
    return {
        "id": str(alert_id),
        "status": "resolved",
        "resolved_by": str(request.resolved_by),
        "resolution_notes": request.resolution_notes,
    }
