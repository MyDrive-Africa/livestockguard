"""
Suggestion Engine — converts active anomalies into actionable recommendations.

Runs after each anomaly detection cycle. For each active anomaly that doesn't
already have a pending suggestion, creates a prioritised, human-readable
recommendation with a specific action the farm admin should take.

Suggestions have an expiry (default 7 days) and can be accepted or dismissed
by the admin via the API.
"""

import json
import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy import text

from app import config
from app.db import async_session

logger = logging.getLogger("analytics_engine.suggestion_engine")

# Mapping: anomaly_type → suggestion template
SUGGESTION_TEMPLATES = {
    "reduced_movement": {
        "category": "health",
        "priority": "high",
        "title_template": "{animal_name} — movement declining",
        "description_template": (
            "{animal_name} has moved significantly less than normal. "
            "Today: {today_distance}m vs baseline average: {baseline_mean}m. "
            "This could indicate lameness, illness, or late-stage pregnancy."
        ),
        "action": "Schedule a physical check on this animal. Look for signs of lameness, injury, or illness. Check pregnancy records if applicable.",
    },
    "isolation": {
        "category": "health",
        "priority": "medium",
        "title_template": "{animal_name} — not seen by gateway",
        "description_template": (
            "{animal_name} has not been detected by any gateway in {hours}h "
            "while other animals are being tracked normally. "
            "The animal may be out of BLE range, stuck, or in distress."
        ),
        "action": "Send herdsman to locate this animal. Check last known position. Look for fence breaks or areas where the animal could be trapped.",
    },
    "patrol_gap": {
        "category": "operational",
        "priority": "medium",
        "title_template": "No patrol in {days} days",
        "description_template": (
            "No herdsman patrol has been recorded in the last {days} days. "
            "Animals are not being monitored, and any issues (illness, escape, theft) "
            "will go undetected until the next patrol."
        ),
        "action": "Schedule a patrol session immediately. If the herdsman is unavailable, arrange a substitute or perform a drive-by check.",
    },
    "night_movement": {
        "category": "security",
        "priority": "high",
        "title_template": "{animal_name} — night activity detected",
        "description_template": (
            "{animal_name} was detected {sightings} times during night hours. "
            "Cattle should be resting at night. This could indicate predator disturbance, "
            "theft attempt, or a fence break causing animals to roam."
        ),
        "action": "Check farm perimeter and CCTV. Verify all animals are accounted for in the morning count. Consider increasing night security.",
    },
}


async def run_suggestion_engine():
    """Create suggestions for all active anomalies that don't have one yet."""
    logger.info("Starting suggestion engine...")
    start_time = datetime.now(timezone.utc)
    total_suggestions = 0

    async with async_session() as db:
        # Get active anomalies without a pending suggestion
        query = text("""
            SELECT a.id AS anomaly_id, a.farm_id, a.animal_id, a.anomaly_type,
                   a.severity, a.description AS anomaly_description, a.evidence,
                   an.name AS animal_name
            FROM anomalies a
            LEFT JOIN animals an ON an.id = a.animal_id
            WHERE a.status = 'active'
              AND NOT EXISTS (
                  SELECT 1 FROM suggestions s
                  WHERE s.anomaly_id = a.id AND s.status = 'pending'
              )
        """)
        result = await db.execute(query)
        anomalies = result.fetchall()

        if not anomalies:
            logger.info("No new anomalies to process.")
            return

        for anomaly in anomalies:
            suggestion_created = await _create_suggestion_for_anomaly(db, anomaly)
            if suggestion_created:
                total_suggestions += 1

        # Expire old suggestions past their expiry date
        await _expire_stale_suggestions(db)

        await db.commit()

    elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
    logger.info(f"Suggestion engine complete: {total_suggestions} new suggestions created in {elapsed:.1f}s")


async def _create_suggestion_for_anomaly(db, anomaly) -> bool:
    """Create a suggestion from an anomaly using templates."""
    template = SUGGESTION_TEMPLATES.get(anomaly.anomaly_type)
    if not template:
        logger.warning(f"No template for anomaly type: {anomaly.anomaly_type}")
        return False

    evidence = json.loads(anomaly.evidence) if isinstance(anomaly.evidence, str) else anomaly.evidence
    animal_name = anomaly.animal_name or "Unknown animal"

    # Build template variables
    template_vars = {
        "animal_name": animal_name,
        "today_distance": evidence.get("today_distance_m", "?"),
        "baseline_mean": evidence.get("baseline_mean_m", "?"),
        "hours": evidence.get("hours_since_last_seen", evidence.get("threshold_hours", "?")),
        "days": evidence.get("days_since_last_patrol", evidence.get("threshold_days", "?")),
        "sightings": evidence.get("night_sightings", "?"),
    }

    try:
        title = template["title_template"].format(**template_vars)
        description = template["description_template"].format(**template_vars)
    except (KeyError, ValueError) as e:
        logger.warning(f"Template formatting error for {anomaly.anomaly_type}: {e}")
        title = f"{animal_name} — {anomaly.anomaly_type.replace('_', ' ')}"
        description = anomaly.anomaly_description

    expires_at = datetime.now(timezone.utc) + timedelta(days=config.SUGGESTION_EXPIRY_DAYS)

    query = text("""
        INSERT INTO suggestions
            (farm_id, anomaly_id, category, priority, title, description,
             recommended_action, evidence, status, expires_at)
        VALUES
            (:farm_id, :anomaly_id, :category, :priority, :title, :description,
             :action, :evidence, 'pending', :expires_at)
    """)
    await db.execute(query, {
        "farm_id": str(anomaly.farm_id),
        "anomaly_id": str(anomaly.anomaly_id),
        "category": template["category"],
        "priority": template["priority"],
        "title": title,
        "description": description,
        "action": template["action"],
        "evidence": json.dumps(evidence),
        "expires_at": expires_at,
    })

    logger.info(f"  Suggestion: [{template['priority']}] {title}")
    return True


async def _expire_stale_suggestions(db):
    """Mark suggestions past their expiry date as expired."""
    query = text("""
        UPDATE suggestions
        SET status = 'expired'
        WHERE status = 'pending' AND expires_at < NOW()
    """)
    result = await db.execute(query)
    if result.rowcount > 0:
        logger.info(f"  Expired {result.rowcount} stale suggestions")
