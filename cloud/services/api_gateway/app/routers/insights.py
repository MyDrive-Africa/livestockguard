"""
Analytics Intelligence router — anomalies, suggestions, reports, and baselines.

Surfaces the intelligence layer to the farm admin dashboard:
- Active anomalies with evidence
- Actionable suggestions (accept/dismiss)
- Daily/weekly intelligence reports
- Behaviour baselines (for transparency/debug)
"""

from typing import List, Optional
from uuid import UUID
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_current_user

router = APIRouter(dependencies=[Depends(get_current_user)])


# ─── Response Models ──────────────────────────────────────────────────────────


class AnomalyResponse(BaseModel):
    id: str
    farm_id: str
    animal_id: Optional[str] = None
    animal_name: Optional[str] = None
    anomaly_type: str
    severity: str
    status: str
    description: str
    evidence: dict
    detected_at: str
    resolved_at: Optional[str] = None


class SuggestionResponse(BaseModel):
    id: str
    farm_id: str
    anomaly_id: Optional[str] = None
    category: str
    priority: str
    title: str
    description: str
    recommended_action: str
    evidence: Optional[dict] = None
    status: str
    created_at: str
    expires_at: Optional[str] = None


class ReportSummaryResponse(BaseModel):
    id: str
    farm_id: str
    report_type: str
    report_date: str
    summary: str
    anomaly_count: int
    suggestion_count: int
    generated_at: str


class ReportDetailResponse(BaseModel):
    id: str
    farm_id: str
    report_type: str
    report_date: str
    content: dict
    summary: str
    anomaly_count: int
    suggestion_count: int
    generated_at: str


class BaselineResponse(BaseModel):
    id: str
    farm_id: str
    animal_id: Optional[str] = None
    animal_name: Optional[str] = None
    metric_name: str
    baseline_value: dict
    window_days: int
    computed_at: str


class InsightsDashboard(BaseModel):
    """Combined overview for the dashboard insights panel."""
    anomalies_active: int
    anomalies_high: int
    suggestions_pending: int
    suggestions_high: int
    latest_report_date: Optional[str] = None
    latest_report_summary: Optional[str] = None
    anomalies: List[AnomalyResponse]
    suggestions: List[SuggestionResponse]


# ─── Insights Dashboard (Combined) ───────────────────────────────────────────


@router.get("/dashboard", response_model=InsightsDashboard)
async def get_insights_dashboard(
    farm_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get combined insights overview for the dashboard panel."""
    fid = str(farm_id)

    # Active anomalies
    anomalies_query = text("""
        SELECT a.id, a.farm_id, a.animal_id, an.name AS animal_name,
               a.anomaly_type, a.severity, a.status, a.description,
               a.evidence, a.detected_at, a.resolved_at
        FROM anomalies a
        LEFT JOIN animals an ON an.id = a.animal_id
        WHERE a.farm_id = :farm_id AND a.status = 'active'
        ORDER BY
            CASE a.severity WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END,
            a.detected_at DESC
        LIMIT 20
    """)
    anomalies_result = await db.execute(anomalies_query, {"farm_id": fid})
    anomalies = [
        AnomalyResponse(
            id=str(r.id), farm_id=str(r.farm_id),
            animal_id=str(r.animal_id) if r.animal_id else None,
            animal_name=r.animal_name,
            anomaly_type=r.anomaly_type, severity=r.severity, status=r.status,
            description=r.description,
            evidence=r.evidence if isinstance(r.evidence, dict) else {},
            detected_at=r.detected_at.isoformat(),
            resolved_at=r.resolved_at.isoformat() if r.resolved_at else None,
        )
        for r in anomalies_result.fetchall()
    ]

    # Pending suggestions
    suggestions_query = text("""
        SELECT id, farm_id, anomaly_id, category, priority, title,
               description, recommended_action, evidence, status, created_at, expires_at
        FROM suggestions
        WHERE farm_id = :farm_id AND status = 'pending'
        ORDER BY
            CASE priority WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END,
            created_at DESC
        LIMIT 20
    """)
    suggestions_result = await db.execute(suggestions_query, {"farm_id": fid})
    suggestions = [
        SuggestionResponse(
            id=str(r.id), farm_id=str(r.farm_id),
            anomaly_id=str(r.anomaly_id) if r.anomaly_id else None,
            category=r.category, priority=r.priority,
            title=r.title, description=r.description,
            recommended_action=r.recommended_action,
            evidence=r.evidence if isinstance(r.evidence, dict) else None,
            status=r.status,
            created_at=r.created_at.isoformat(),
            expires_at=r.expires_at.isoformat() if r.expires_at else None,
        )
        for r in suggestions_result.fetchall()
    ]

    # Latest report
    report_query = text("""
        SELECT report_date, summary
        FROM intelligence_reports
        WHERE farm_id = :farm_id
        ORDER BY report_date DESC, generated_at DESC
        LIMIT 1
    """)
    report_result = await db.execute(report_query, {"farm_id": fid})
    report_row = report_result.first()

    return InsightsDashboard(
        anomalies_active=len(anomalies),
        anomalies_high=sum(1 for a in anomalies if a.severity == "high"),
        suggestions_pending=len(suggestions),
        suggestions_high=sum(1 for s in suggestions if s.priority == "high"),
        latest_report_date=report_row.report_date.isoformat() if report_row else None,
        latest_report_summary=report_row.summary if report_row else None,
        anomalies=anomalies,
        suggestions=suggestions,
    )


# ─── Anomalies ───────────────────────────────────────────────────────────────


@router.get("/anomalies", response_model=List[AnomalyResponse])
async def list_anomalies(
    farm_id: UUID,
    status: Optional[str] = Query(default=None, description="Filter: active, acknowledged, resolved, dismissed"),
    severity: Optional[str] = Query(default=None),
    animal_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db),
):
    """List anomalies for a farm."""
    conditions = ["a.farm_id = :farm_id"]
    params = {"farm_id": str(farm_id)}

    if status:
        conditions.append("a.status = :status")
        params["status"] = status
    if severity:
        conditions.append("a.severity = :severity")
        params["severity"] = severity
    if animal_id:
        conditions.append("a.animal_id = :animal_id")
        params["animal_id"] = str(animal_id)

    where_clause = " AND ".join(conditions)
    query = text(f"""
        SELECT a.id, a.farm_id, a.animal_id, an.name AS animal_name,
               a.anomaly_type, a.severity, a.status, a.description,
               a.evidence, a.detected_at, a.resolved_at
        FROM anomalies a
        LEFT JOIN animals an ON an.id = a.animal_id
        WHERE {where_clause}
        ORDER BY a.detected_at DESC
        LIMIT 50
    """)
    result = await db.execute(query, params)
    return [
        AnomalyResponse(
            id=str(r.id), farm_id=str(r.farm_id),
            animal_id=str(r.animal_id) if r.animal_id else None,
            animal_name=r.animal_name,
            anomaly_type=r.anomaly_type, severity=r.severity, status=r.status,
            description=r.description,
            evidence=r.evidence if isinstance(r.evidence, dict) else {},
            detected_at=r.detected_at.isoformat(),
            resolved_at=r.resolved_at.isoformat() if r.resolved_at else None,
        )
        for r in result.fetchall()
    ]


@router.put("/anomalies/{anomaly_id}/acknowledge")
async def acknowledge_anomaly(anomaly_id: UUID, db: AsyncSession = Depends(get_db)):
    """Mark an anomaly as acknowledged (seen by admin)."""
    result = await db.execute(
        text("UPDATE anomalies SET status = 'acknowledged' WHERE id = :id AND status = 'active' RETURNING id"),
        {"id": str(anomaly_id)},
    )
    if not result.first():
        raise HTTPException(status_code=404, detail="Anomaly not found or not active")
    await db.commit()
    return {"status": "acknowledged", "id": str(anomaly_id)}


@router.put("/anomalies/{anomaly_id}/dismiss")
async def dismiss_anomaly(anomaly_id: UUID, db: AsyncSession = Depends(get_db)):
    """Dismiss an anomaly as false positive."""
    result = await db.execute(
        text("UPDATE anomalies SET status = 'dismissed', resolved_at = NOW() WHERE id = :id AND status IN ('active', 'acknowledged') RETURNING id"),
        {"id": str(anomaly_id)},
    )
    if not result.first():
        raise HTTPException(status_code=404, detail="Anomaly not found or already resolved")
    await db.commit()
    return {"status": "dismissed", "id": str(anomaly_id)}


# ─── Suggestions ─────────────────────────────────────────────────────────────


@router.get("/suggestions", response_model=List[SuggestionResponse])
async def list_suggestions(
    farm_id: UUID,
    status: Optional[str] = Query(default="pending"),
    category: Optional[str] = Query(default=None),
    priority: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    """List suggestions for a farm."""
    conditions = ["farm_id = :farm_id"]
    params = {"farm_id": str(farm_id)}

    if status:
        conditions.append("status = :status")
        params["status"] = status
    if category:
        conditions.append("category = :category")
        params["category"] = category
    if priority:
        conditions.append("priority = :priority")
        params["priority"] = priority

    where_clause = " AND ".join(conditions)
    query = text(f"""
        SELECT id, farm_id, anomaly_id, category, priority, title,
               description, recommended_action, evidence, status, created_at, expires_at
        FROM suggestions
        WHERE {where_clause}
        ORDER BY
            CASE priority WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END,
            created_at DESC
        LIMIT 50
    """)
    result = await db.execute(query, params)
    return [
        SuggestionResponse(
            id=str(r.id), farm_id=str(r.farm_id),
            anomaly_id=str(r.anomaly_id) if r.anomaly_id else None,
            category=r.category, priority=r.priority,
            title=r.title, description=r.description,
            recommended_action=r.recommended_action,
            evidence=r.evidence if isinstance(r.evidence, dict) else None,
            status=r.status,
            created_at=r.created_at.isoformat(),
            expires_at=r.expires_at.isoformat() if r.expires_at else None,
        )
        for r in result.fetchall()
    ]


@router.put("/suggestions/{suggestion_id}/accept")
async def accept_suggestion(suggestion_id: UUID, db: AsyncSession = Depends(get_db)):
    """Mark a suggestion as accepted/actioned."""
    result = await db.execute(
        text("UPDATE suggestions SET status = 'accepted', actioned_at = NOW() WHERE id = :id AND status = 'pending' RETURNING id"),
        {"id": str(suggestion_id)},
    )
    if not result.first():
        raise HTTPException(status_code=404, detail="Suggestion not found or not pending")
    await db.commit()
    return {"status": "accepted", "id": str(suggestion_id)}


@router.put("/suggestions/{suggestion_id}/dismiss")
async def dismiss_suggestion(suggestion_id: UUID, db: AsyncSession = Depends(get_db)):
    """Dismiss a suggestion."""
    result = await db.execute(
        text("UPDATE suggestions SET status = 'dismissed', actioned_at = NOW() WHERE id = :id AND status = 'pending' RETURNING id"),
        {"id": str(suggestion_id)},
    )
    if not result.first():
        raise HTTPException(status_code=404, detail="Suggestion not found or not pending")
    await db.commit()
    return {"status": "dismissed", "id": str(suggestion_id)}


# ─── Reports ─────────────────────────────────────────────────────────────────


@router.get("/reports", response_model=List[ReportSummaryResponse])
async def list_reports(
    farm_id: UUID,
    report_type: Optional[str] = Query(default=None, description="daily or weekly"),
    limit: int = Query(default=14, le=60),
    db: AsyncSession = Depends(get_db),
):
    """List intelligence reports for a farm."""
    conditions = ["farm_id = :farm_id"]
    params = {"farm_id": str(farm_id), "limit": limit}

    if report_type:
        conditions.append("report_type = :report_type")
        params["report_type"] = report_type

    where_clause = " AND ".join(conditions)
    query = text(f"""
        SELECT id, farm_id, report_type, report_date, summary,
               anomaly_count, suggestion_count, generated_at
        FROM intelligence_reports
        WHERE {where_clause}
        ORDER BY report_date DESC
        LIMIT :limit
    """)
    result = await db.execute(query, params)
    return [
        ReportSummaryResponse(
            id=str(r.id), farm_id=str(r.farm_id),
            report_type=r.report_type,
            report_date=r.report_date.isoformat(),
            summary=r.summary,
            anomaly_count=r.anomaly_count,
            suggestion_count=r.suggestion_count,
            generated_at=r.generated_at.isoformat(),
        )
        for r in result.fetchall()
    ]


@router.get("/reports/latest", response_model=Optional[ReportDetailResponse])
async def get_latest_report(
    farm_id: UUID,
    report_type: str = Query(default="daily"),
    db: AsyncSession = Depends(get_db),
):
    """Get the most recent report for a farm."""
    query = text("""
        SELECT id, farm_id, report_type, report_date, content, summary,
               anomaly_count, suggestion_count, generated_at
        FROM intelligence_reports
        WHERE farm_id = :farm_id AND report_type = :report_type
        ORDER BY report_date DESC
        LIMIT 1
    """)
    result = await db.execute(query, {"farm_id": str(farm_id), "report_type": report_type})
    r = result.first()
    if not r:
        return None

    return ReportDetailResponse(
        id=str(r.id), farm_id=str(r.farm_id),
        report_type=r.report_type,
        report_date=r.report_date.isoformat(),
        content=r.content if isinstance(r.content, dict) else {},
        summary=r.summary,
        anomaly_count=r.anomaly_count,
        suggestion_count=r.suggestion_count,
        generated_at=r.generated_at.isoformat(),
    )


@router.get("/reports/{report_id}", response_model=ReportDetailResponse)
async def get_report(report_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get a specific report by ID."""
    query = text("""
        SELECT id, farm_id, report_type, report_date, content, summary,
               anomaly_count, suggestion_count, generated_at
        FROM intelligence_reports
        WHERE id = :id
    """)
    result = await db.execute(query, {"id": str(report_id)})
    r = result.first()
    if not r:
        raise HTTPException(status_code=404, detail="Report not found")

    return ReportDetailResponse(
        id=str(r.id), farm_id=str(r.farm_id),
        report_type=r.report_type,
        report_date=r.report_date.isoformat(),
        content=r.content if isinstance(r.content, dict) else {},
        summary=r.summary,
        anomaly_count=r.anomaly_count,
        suggestion_count=r.suggestion_count,
        generated_at=r.generated_at.isoformat(),
    )


# ─── Baselines (Transparency) ────────────────────────────────────────────────


@router.get("/baselines", response_model=List[BaselineResponse])
async def list_baselines(
    farm_id: UUID,
    animal_id: Optional[UUID] = None,
    metric_name: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """View computed behaviour baselines (for transparency/debugging)."""
    conditions = ["b.farm_id = :farm_id"]
    params = {"farm_id": str(farm_id)}

    if animal_id:
        conditions.append("b.animal_id = :animal_id")
        params["animal_id"] = str(animal_id)
    if metric_name:
        conditions.append("b.metric_name = :metric_name")
        params["metric_name"] = metric_name

    where_clause = " AND ".join(conditions)
    query = text(f"""
        SELECT b.id, b.farm_id, b.animal_id, an.name AS animal_name,
               b.metric_name, b.baseline_value, b.window_days, b.computed_at
        FROM behaviour_baselines b
        LEFT JOIN animals an ON an.id = b.animal_id
        WHERE {where_clause}
        ORDER BY b.animal_id, b.metric_name
        LIMIT 100
    """)
    result = await db.execute(query, params)
    return [
        BaselineResponse(
            id=str(r.id), farm_id=str(r.farm_id),
            animal_id=str(r.animal_id) if r.animal_id else None,
            animal_name=r.animal_name,
            metric_name=r.metric_name,
            baseline_value=r.baseline_value if isinstance(r.baseline_value, dict) else {},
            window_days=r.window_days,
            computed_at=r.computed_at.isoformat(),
        )
        for r in result.fetchall()
    ]
