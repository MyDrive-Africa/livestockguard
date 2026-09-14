"""
Missing Animal Detector — raises major alerts for animals that stop being detected.

Runs on a short interval. For each farm, finds animals with an active BLE ear tag
whose most recent sighting is older than a threshold (or that have never been seen),
and raises an alert so the herdsman/owner is notified that stock is unaccounted for.

Unlike the analytics anomalies (which write to the `anomalies` table for the
intelligence dashboard), this job writes to the operational `alerts` table AND
publishes to the Redis `alerts:incoming` channel so the alert_engine dispatches
push / SMS / email — the same pipeline geofence-breach and theft alerts use.

Behaviour:
- Severity is CRITICAL ("major") once an animal is missing beyond the threshold.
- De-duplicated: won't create a second active `animal_missing` alert for the same
  animal while one is already open.
- Self-healing: when an animal is detected again, its open `animal_missing` alert
  is auto-resolved.
- Startup grace: on a freshly-seeded database with zero sightings ever recorded,
  the job stays quiet unless MISSING_ALERT_ON_NEVER_SEEN is enabled, so a bare
  demo stack doesn't immediately fire 65 alerts before any simulator runs.
"""

import json
import logging
from datetime import datetime, timezone

from sqlalchemy import text

from app import config
from app.db import async_session
from app.redis_bus import publish_alert_incoming

logger = logging.getLogger("analytics_engine.missing_animal_detector")


async def run_missing_animal_detector():
    """Detect undetected animals across all farms and raise/resolve alerts."""
    logger.info("Starting missing-animal detector...")
    start_time = datetime.now(timezone.utc)
    raised = 0
    resolved = 0

    async with async_session() as db:
        farms_result = await db.execute(text("SELECT id, name FROM farms"))
        farms = farms_result.fetchall()

        for farm in farms:
            farm_id = str(farm.id)

            # Skip alerting on a farm that has never recorded a single sighting,
            # unless explicitly configured to alert on never-seen animals. This
            # prevents a bare/demo stack (seed data, no simulator yet) from firing
            # an alert storm before any detection pipeline has run.
            if not config.MISSING_ALERT_ON_NEVER_SEEN:
                any_sightings = await db.execute(text("""
                    SELECT 1
                    FROM ble_sightings s
                    JOIN gateway_devices g ON g.id = s.gateway_id
                    WHERE g.farm_id = :farm_id
                    LIMIT 1
                """), {"farm_id": farm_id})
                if any_sightings.first() is None:
                    logger.debug(f"Farm {farm.name}: no sightings ever — skipping missing check")
                    continue

            r, v = await _check_farm(db, farm_id, farm.name)
            raised += r
            resolved += v

        await db.commit()

    elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
    logger.info(
        f"Missing-animal detector complete: {raised} raised, {resolved} resolved in {elapsed:.1f}s"
    )
    return raised, resolved


async def _check_farm(db, farm_id: str, farm_name: str) -> tuple[int, int]:
    """Raise alerts for newly-missing animals and resolve alerts for recovered ones."""
    threshold_hours = config.MISSING_ALERT_THRESHOLD_HOURS

    # 1) Auto-resolve: any active animal_missing alert whose animal has been seen
    #    again within the threshold window.
    resolve_result = await db.execute(text("""
        UPDATE alerts
        SET status = 'resolved', resolved_at = NOW(),
            resolution_notes = 'Auto-resolved: animal detected again'
        WHERE farm_id = :farm_id
          AND alert_type = 'animal_missing'
          AND status = 'active'
          AND animal_id IN (
              SELECT DISTINCT s.animal_id
              FROM ble_sightings s
              JOIN gateway_devices g ON g.id = s.gateway_id
              WHERE g.farm_id = :farm_id
                AND s.animal_id IS NOT NULL
                AND s.time >= NOW() - (:threshold_hours * INTERVAL '1 hour')
          )
        RETURNING id
    """), {"farm_id": farm_id, "threshold_hours": threshold_hours})
    resolved = len(resolve_result.fetchall())

    # 2) Find animals (active + active BLE tag) whose latest sighting is older than
    #    the threshold, or that have never been seen. Exclude any that already have
    #    an open animal_missing alert (dedup).
    missing_result = await db.execute(text("""
        WITH tagged AS (
            SELECT a.id AS animal_id, a.name AS animal_name
            FROM animals a
            JOIN ble_ear_tags bt ON bt.animal_id = a.id AND bt.status = 'active'
            WHERE a.farm_id = :farm_id AND a.status = 'active'
        ),
        last_seen AS (
            SELECT s.animal_id, MAX(s.time) AS last_time
            FROM ble_sightings s
            JOIN gateway_devices g ON g.id = s.gateway_id
            WHERE g.farm_id = :farm_id AND s.animal_id IS NOT NULL
            GROUP BY s.animal_id
        )
        SELECT t.animal_id, t.animal_name, ls.last_time
        FROM tagged t
        LEFT JOIN last_seen ls ON ls.animal_id = t.animal_id
        WHERE (ls.last_time IS NULL OR ls.last_time < NOW() - (:threshold_hours * INTERVAL '1 hour'))
          AND NOT EXISTS (
              SELECT 1 FROM alerts al
              WHERE al.animal_id = t.animal_id
                AND al.alert_type = 'animal_missing'
                AND al.status = 'active'
          )
    """), {"farm_id": farm_id, "threshold_hours": threshold_hours})
    missing = missing_result.fetchall()

    now = datetime.now(timezone.utc)
    raised = 0
    for row in missing:
        animal_id = str(row.animal_id)
        if row.last_time is not None:
            hours = round((now - row.last_time).total_seconds() / 3600, 1)
            last_seen_iso = row.last_time.isoformat()
            message = (
                f"{row.animal_name} has not been detected for {hours}h "
                f"(threshold {threshold_hours}h)."
            )
        else:
            hours = None
            last_seen_iso = None
            message = f"{row.animal_name} has never been detected by any gateway."

        metadata = {
            "animal_name": row.animal_name,
            "hours_missing": hours,
            "last_seen": last_seen_iso,
            "threshold_hours": threshold_hours,
        }

        # Insert into the operational alerts table (shows on the dashboard list).
        insert_result = await db.execute(text("""
            INSERT INTO alerts (farm_id, animal_id, alert_type, severity, status, message, metadata)
            VALUES (:farm_id, :animal_id, 'animal_missing', :severity, 'active', :message, :metadata)
            RETURNING id
        """), {
            "farm_id": farm_id,
            "animal_id": animal_id,
            "severity": config.MISSING_ALERT_SEVERITY,
            "message": message,
            "metadata": json.dumps(metadata),
        })
        alert_id = insert_result.scalar_one()
        raised += 1

        # Publish to the alert engine for push / SMS / email dispatch. device_id is
        # required by the engine's event schema; missing-animal alerts are not tied
        # to a device, so we send the animal id as the correlation key.
        await publish_alert_incoming({
            "alert_type": "animal_missing",
            "severity": config.MISSING_ALERT_SEVERITY,
            "device_id": animal_id,
            "farm_id": farm_id,
            "animal_id": animal_id,
            "message": message,
            "metadata": {**metadata, "alert_id": str(alert_id)},
            "timestamp": now.timestamp(),
        })
        logger.info(f"  Missing: {row.animal_name} (farm {farm_name})")

    return raised, resolved
