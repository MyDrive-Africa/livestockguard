"""
Report Generator — compiles daily and weekly intelligence reports for farm admin.

Daily report (18:00 SAST):
- Herd status (coverage, animals seen, missing)
- Patrol summary (sessions, duration, coverage)
- Active anomalies and new suggestions
- 7-day trends (movement, coverage, gateway health)

Weekly report (Sunday 19:00 SAST):
- Week-over-week comparisons
- Recurring anomalies
- Patrol efficiency
- Tag health overview

Reports are stored in intelligence_reports table and served via API.
"""

import json
import logging
from datetime import datetime, timezone, timedelta, date
from decimal import Decimal

from sqlalchemy import text

from app import config
from app.db import async_session

logger = logging.getLogger("analytics_engine.report_generator")


class DecimalEncoder(json.JSONEncoder):
    """Handle Decimal types from PostgreSQL aggregates."""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


async def run_report_generator():
    """Generate daily report for all farms. Weekly report on configured day."""
    logger.info("Starting report generator...")
    start_time = datetime.now(timezone.utc)

    async with async_session() as db:
        # Get all farms with BLE activity
        farms_query = text("""
            SELECT DISTINCT f.id AS farm_id, f.name AS farm_name
            FROM farms f
            JOIN gateway_devices g ON g.farm_id = f.id AND g.status = 'active'
        """)
        farms_result = await db.execute(farms_query)
        farms = farms_result.fetchall()

        if not farms:
            logger.info("No active farms found for reporting.")
            return

        today = date.today()
        reports_generated = 0

        for farm in farms:
            farm_id = str(farm.farm_id)

            # Always generate daily report
            daily_exists = await _report_exists(db, farm_id, "daily", today)
            if not daily_exists:
                report = await _generate_daily_report(db, farm_id, farm.farm_name, today)
                if report:
                    await _store_report(db, farm_id, "daily", today, report)
                    reports_generated += 1

            # Generate weekly report on configured day
            now = datetime.now(timezone.utc)
            day_names = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
            if day_names[now.weekday()] == config.WEEKLY_REPORT_DAY:
                weekly_exists = await _report_exists(db, farm_id, "weekly", today)
                if not weekly_exists:
                    report = await _generate_weekly_report(db, farm_id, farm.farm_name, today)
                    if report:
                        await _store_report(db, farm_id, "weekly", today, report)
                        reports_generated += 1

        await db.commit()

    elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
    logger.info(f"Report generator complete: {reports_generated} reports generated in {elapsed:.1f}s")


async def _generate_daily_report(db, farm_id: str, farm_name: str, report_date: date) -> dict | None:
    """Generate a structured daily intelligence report."""
    today_start = datetime.combine(report_date, datetime.min.time()).replace(tzinfo=timezone.utc)
    today_end = today_start + timedelta(days=1)

    # ─── Herd Status ─────────────────────────────────────────────────────────
    herd_query = text("""
        SELECT
            (SELECT COUNT(DISTINCT bt.animal_id)
             FROM ble_ear_tags bt
             JOIN animals a ON a.id = bt.animal_id
             WHERE bt.farm_id = :farm_id AND bt.status = 'active' AND a.status = 'active'
            ) AS total_registered,
            (SELECT COUNT(DISTINCT s.animal_id)
             FROM ble_sightings s
             JOIN gateway_devices g ON g.id = s.gateway_id
             WHERE g.farm_id = :farm_id AND s.animal_id IS NOT NULL
               AND s.time >= :today_start AND s.time < :today_end
            ) AS seen_today,
            (SELECT COUNT(*)
             FROM ble_sightings s
             JOIN gateway_devices g ON g.id = s.gateway_id
             WHERE g.farm_id = :farm_id AND s.time >= :today_start AND s.time < :today_end
            ) AS total_sightings
    """)
    herd_result = await db.execute(herd_query, {
        "farm_id": farm_id, "today_start": today_start, "today_end": today_end,
    })
    herd = herd_result.first()

    total_registered = herd.total_registered if herd else 0
    seen_today = herd.seen_today if herd else 0
    total_sightings = herd.total_sightings if herd else 0
    coverage_pct = round((seen_today / total_registered * 100), 1) if total_registered > 0 else 0

    # ─── Patrol Summary ──────────────────────────────────────────────────────
    patrol_query = text("""
        SELECT COUNT(*) AS session_count,
               SUM(EXTRACT(EPOCH FROM (COALESCE(ended_at, NOW()) - started_at)) / 3600) AS total_hours,
               array_agg(herdsman_name) AS herdsmen
        FROM herdsman_sessions
        WHERE farm_id = :farm_id
          AND started_at >= :today_start AND started_at < :today_end
    """)
    patrol_result = await db.execute(patrol_query, {
        "farm_id": farm_id, "today_start": today_start, "today_end": today_end,
    })
    patrol = patrol_result.first()

    patrol_sessions = patrol.session_count if patrol else 0
    patrol_hours = round(patrol.total_hours, 1) if patrol and patrol.total_hours else 0
    herdsmen = list(set(filter(None, patrol.herdsmen or []))) if patrol else []

    # ─── Active Anomalies ────────────────────────────────────────────────────
    anomalies_query = text("""
        SELECT a.anomaly_type, a.severity, a.description, an.name AS animal_name
        FROM anomalies a
        LEFT JOIN animals an ON an.id = a.animal_id
        WHERE a.farm_id = :farm_id AND a.status = 'active'
        ORDER BY
            CASE a.severity WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END,
            a.detected_at DESC
    """)
    anomalies_result = await db.execute(anomalies_query, {"farm_id": farm_id})
    active_anomalies = [
        {
            "type": row.anomaly_type,
            "severity": row.severity,
            "description": row.description,
            "animal_name": row.animal_name,
        }
        for row in anomalies_result.fetchall()
    ]

    # ─── Pending Suggestions ─────────────────────────────────────────────────
    suggestions_query = text("""
        SELECT title, category, priority, recommended_action
        FROM suggestions
        WHERE farm_id = :farm_id AND status = 'pending'
        ORDER BY
            CASE priority WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END
    """)
    suggestions_result = await db.execute(suggestions_query, {"farm_id": farm_id})
    pending_suggestions = [
        {
            "title": row.title,
            "category": row.category,
            "priority": row.priority,
            "action": row.recommended_action,
        }
        for row in suggestions_result.fetchall()
    ]

    # ─── 7-Day Trend (daily coverage) ────────────────────────────────────────
    trend_query = text("""
        SELECT DATE(s.time) AS day, COUNT(DISTINCT s.animal_id) AS unique_animals
        FROM ble_sightings s
        JOIN gateway_devices g ON g.id = s.gateway_id
        WHERE g.farm_id = :farm_id
          AND s.animal_id IS NOT NULL
          AND s.time >= :week_start
        GROUP BY DATE(s.time)
        ORDER BY day
    """)
    week_start = today_start - timedelta(days=7)
    trend_result = await db.execute(trend_query, {"farm_id": farm_id, "week_start": week_start})
    daily_coverage_trend = [
        {"date": row.day.isoformat(), "animals_seen": row.unique_animals}
        for row in trend_result.fetchall()
    ]

    # ─── Gateway Health ──────────────────────────────────────────────────────
    gateway_query = text("""
        SELECT name, last_battery_pct, last_seen
        FROM gateway_devices
        WHERE farm_id = :farm_id AND status = 'active'
    """)
    gateway_result = await db.execute(gateway_query, {"farm_id": farm_id})
    gateways = [
        {
            "name": row.name,
            "battery_pct": row.last_battery_pct,
            "last_seen": row.last_seen.isoformat() if row.last_seen else None,
        }
        for row in gateway_result.fetchall()
    ]

    # ─── Compile Report ──────────────────────────────────────────────────────
    report_content = {
        "farm_name": farm_name,
        "report_date": report_date.isoformat(),
        "herd_status": {
            "total_registered": total_registered,
            "seen_today": seen_today,
            "coverage_pct": coverage_pct,
            "total_sightings": total_sightings,
        },
        "patrol": {
            "sessions": patrol_sessions,
            "total_hours": patrol_hours,
            "herdsmen": herdsmen,
        },
        "anomalies": active_anomalies,
        "suggestions": pending_suggestions,
        "trends": {
            "daily_coverage": daily_coverage_trend,
        },
        "gateway_health": gateways,
    }

    # Build human-readable summary
    summary_lines = [
        f"{farm_name} — Daily Report ({report_date.isoformat()})",
        f"Herd: {seen_today}/{total_registered} animals seen ({coverage_pct}% coverage), {total_sightings} total sightings.",
        f"Patrols: {patrol_sessions} session(s), {patrol_hours}h total.",
    ]
    if active_anomalies:
        summary_lines.append(f"Anomalies: {len(active_anomalies)} active ({sum(1 for a in active_anomalies if a['severity'] == 'high')} high).")
    else:
        summary_lines.append("No anomalies detected.")
    if pending_suggestions:
        summary_lines.append(f"Suggestions: {len(pending_suggestions)} pending actions.")

    summary = " | ".join(summary_lines)

    return {
        "content": report_content,
        "summary": summary,
        "anomaly_count": len(active_anomalies),
        "suggestion_count": len(pending_suggestions),
    }


async def _generate_weekly_report(db, farm_id: str, farm_name: str, report_date: date) -> dict | None:
    """Generate a weekly summary comparing this week to last week."""
    week_end = datetime.combine(report_date, datetime.min.time()).replace(tzinfo=timezone.utc)
    week_start = week_end - timedelta(days=7)
    prev_week_start = week_start - timedelta(days=7)

    # This week stats
    this_week = await _week_stats(db, farm_id, week_start, week_end)
    # Last week stats
    last_week = await _week_stats(db, farm_id, prev_week_start, week_start)

    # Anomaly history for the week
    anomaly_query = text("""
        SELECT anomaly_type, COUNT(*) AS count,
               COUNT(DISTINCT animal_id) AS unique_animals
        FROM anomalies
        WHERE farm_id = :farm_id
          AND detected_at >= :week_start AND detected_at < :week_end
        GROUP BY anomaly_type
    """)
    anomaly_result = await db.execute(anomaly_query, {
        "farm_id": farm_id, "week_start": week_start, "week_end": week_end,
    })
    anomaly_summary = [
        {"type": row.anomaly_type, "count": row.count, "unique_animals": row.unique_animals}
        for row in anomaly_result.fetchall()
    ]

    report_content = {
        "farm_name": farm_name,
        "report_date": report_date.isoformat(),
        "period": f"{week_start.date().isoformat()} to {week_end.date().isoformat()}",
        "this_week": this_week,
        "last_week": last_week,
        "comparison": {
            "coverage_change": round(this_week["avg_daily_coverage"] - last_week["avg_daily_coverage"], 1),
            "sightings_change_pct": _pct_change(last_week["total_sightings"], this_week["total_sightings"]),
            "patrol_hours_change": round(this_week["total_patrol_hours"] - last_week["total_patrol_hours"], 1),
        },
        "anomaly_summary": anomaly_summary,
    }

    summary = (
        f"{farm_name} — Weekly Report ({week_start.date()} to {report_date}). "
        f"Avg coverage: {this_week['avg_daily_coverage']:.0f} animals/day "
        f"({'↗' if this_week['avg_daily_coverage'] > last_week['avg_daily_coverage'] else '↘'} vs last week). "
        f"Patrols: {this_week['total_patrol_hours']:.1f}h total. "
        f"Anomalies this week: {sum(a['count'] for a in anomaly_summary)}."
    )

    return {
        "content": report_content,
        "summary": summary,
        "anomaly_count": sum(a["count"] for a in anomaly_summary),
        "suggestion_count": 0,
    }


async def _week_stats(db, farm_id: str, start: datetime, end: datetime) -> dict:
    """Get aggregate stats for a week period."""
    query = text("""
        SELECT
            COUNT(*) AS total_sightings,
            COUNT(DISTINCT s.animal_id) AS unique_animals_week,
            COUNT(DISTINCT DATE(s.time)) AS active_days
        FROM ble_sightings s
        JOIN gateway_devices g ON g.id = s.gateway_id
        WHERE g.farm_id = :farm_id
          AND s.animal_id IS NOT NULL
          AND s.time >= :start AND s.time < :end
    """)
    result = await db.execute(query, {"farm_id": farm_id, "start": start, "end": end})
    row = result.first()

    # Daily coverage average
    daily_query = text("""
        SELECT AVG(daily_count) AS avg_daily
        FROM (
            SELECT DATE(s.time) AS day, COUNT(DISTINCT s.animal_id) AS daily_count
            FROM ble_sightings s
            JOIN gateway_devices g ON g.id = s.gateway_id
            WHERE g.farm_id = :farm_id AND s.animal_id IS NOT NULL
              AND s.time >= :start AND s.time < :end
            GROUP BY DATE(s.time)
        ) sub
    """)
    daily_result = await db.execute(daily_query, {"farm_id": farm_id, "start": start, "end": end})
    daily_row = daily_result.first()

    # Patrol hours
    patrol_query = text("""
        SELECT COALESCE(SUM(EXTRACT(EPOCH FROM (COALESCE(ended_at, NOW()) - started_at)) / 3600), 0) AS hours
        FROM herdsman_sessions
        WHERE farm_id = :farm_id AND started_at >= :start AND started_at < :end
    """)
    patrol_result = await db.execute(patrol_query, {"farm_id": farm_id, "start": start, "end": end})
    patrol_row = patrol_result.first()

    return {
        "total_sightings": row.total_sightings if row else 0,
        "unique_animals": row.unique_animals_week if row else 0,
        "active_days": row.active_days if row else 0,
        "avg_daily_coverage": round(daily_row.avg_daily, 1) if daily_row and daily_row.avg_daily else 0,
        "total_patrol_hours": round(patrol_row.hours, 1) if patrol_row else 0,
    }


def _pct_change(old: float, new: float) -> float:
    """Calculate percentage change, handling zero division."""
    if old == 0:
        return 100.0 if new > 0 else 0.0
    return round((new - old) / old * 100, 1)


async def _report_exists(db, farm_id: str, report_type: str, report_date: date) -> bool:
    """Check if a report already exists for this farm/type/date."""
    query = text("""
        SELECT 1 FROM intelligence_reports
        WHERE farm_id = :farm_id AND report_type = :report_type AND report_date = :report_date
        LIMIT 1
    """)
    result = await db.execute(query, {
        "farm_id": farm_id, "report_type": report_type, "report_date": report_date,
    })
    return result.first() is not None


async def _store_report(db, farm_id: str, report_type: str, report_date: date, report: dict):
    """Store a compiled report in the database."""
    query = text("""
        INSERT INTO intelligence_reports
            (farm_id, report_type, report_date, content, summary, anomaly_count, suggestion_count)
        VALUES
            (:farm_id, :report_type, :report_date, :content, :summary, :anomaly_count, :suggestion_count)
        ON CONFLICT (farm_id, report_type, report_date) DO UPDATE SET
            content = :content, summary = :summary,
            anomaly_count = :anomaly_count, suggestion_count = :suggestion_count,
            generated_at = NOW()
    """)
    await db.execute(query, {
        "farm_id": farm_id,
        "report_type": report_type,
        "report_date": report_date,
        "content": json.dumps(report["content"], cls=DecimalEncoder),
        "summary": report["summary"],
        "anomaly_count": report["anomaly_count"],
        "suggestion_count": report["suggestion_count"],
    })
    logger.info(f"  Stored {report_type} report for {report['content']['farm_name']}")
