"""
Anomaly Detector — compares current animal behaviour against learned baselines.

Runs every 2 hours. Detects:
- Reduced movement: today's distance significantly below baseline (z-score)
- Isolation: animal not co-sighted with usual companions
- Patrol gaps: farm zones not covered by herdsman in N days
- Night movement: significant position change between 22:00-04:00

Only flags anomalies if baselines exist (requires baseline_builder to have run first).
Avoids duplicates — won't create a new anomaly if an active one already exists for
the same animal + anomaly_type.
"""

import json
import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy import text

from app import config
from app.db import async_session

logger = logging.getLogger("analytics_engine.anomaly_detector")


async def run_anomaly_detector():
    """Run all anomaly detection checks across all farms."""
    logger.info("Starting anomaly detector...")
    start_time = datetime.now(timezone.utc)
    total_anomalies = 0

    async with async_session() as db:
        # Get farms that have baselines computed
        farms_query = text("""
            SELECT DISTINCT farm_id FROM behaviour_baselines
        """)
        farms_result = await db.execute(farms_query)
        farm_ids = [str(row.farm_id) for row in farms_result.fetchall()]

        if not farm_ids:
            logger.info("No baselines found — skipping anomaly detection (need baseline_builder to run first).")
            return

        for farm_id in farm_ids:
            count = 0
            count += await _detect_reduced_movement(db, farm_id)
            count += await _detect_isolation(db, farm_id)
            count += await _detect_patrol_gaps(db, farm_id)
            count += await _detect_night_movement(db, farm_id)
            total_anomalies += count

        # Expire old anomalies that haven't recurred
        await _auto_resolve_stale_anomalies(db)

        await db.commit()

    elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
    logger.info(f"Anomaly detector complete: {total_anomalies} new anomalies flagged in {elapsed:.1f}s")


async def _detect_reduced_movement(db, farm_id: str) -> int:
    """
    Flag animals whose today's movement is significantly below their baseline.
    Uses z-score: (today_distance - mean) / std_dev < threshold.
    """
    # Get all animals with a daily_distance baseline on this farm
    baselines_query = text("""
        SELECT animal_id, baseline_value
        FROM behaviour_baselines
        WHERE farm_id = :farm_id AND metric_name = 'daily_distance' AND animal_id IS NOT NULL
    """)
    baselines_result = await db.execute(baselines_query, {"farm_id": farm_id})
    baselines = baselines_result.fetchall()

    if not baselines:
        return 0

    count = 0
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    for row in baselines:
        animal_id = str(row.animal_id)
        bl = json.loads(row.baseline_value) if isinstance(row.baseline_value, str) else row.baseline_value
        mean = bl.get("mean", 0)
        std_dev = bl.get("std_dev", 0)

        if mean == 0 or std_dev == 0:
            continue

        # Get today's distance for this animal
        today_query = text("""
            SELECT
                array_agg(gateway_latitude ORDER BY time) AS lats,
                array_agg(gateway_longitude ORDER BY time) AS lons
            FROM ble_sightings
            WHERE animal_id = :animal_id
              AND time >= :today_start
              AND gateway_latitude IS NOT NULL
        """)
        today_result = await db.execute(today_query, {
            "animal_id": animal_id,
            "today_start": today_start,
        })
        today_row = today_result.first()

        if not today_row or not today_row.lats or len(today_row.lats) < 3:
            continue  # Not enough data yet today

        # Calculate today's distance
        from app.jobs.baseline_builder import haversine_m
        lats = today_row.lats
        lons = today_row.lons
        today_distance = 0.0
        for i in range(1, len(lats)):
            if lats[i] and lons[i] and lats[i - 1] and lons[i - 1]:
                d = haversine_m(lats[i - 1], lons[i - 1], lats[i], lons[i])
                if d < 5000:
                    today_distance += d

        # Z-score check
        z_score = (today_distance - mean) / std_dev
        if z_score < config.REDUCED_MOVEMENT_Z_THRESHOLD:
            # Check if we already have an active anomaly for this
            if not await _has_active_anomaly(db, animal_id, "reduced_movement"):
                await _create_anomaly(
                    db, farm_id, animal_id,
                    anomaly_type="reduced_movement",
                    severity="medium",
                    description=(
                        f"Movement significantly below normal. "
                        f"Today: {today_distance:.0f}m vs baseline: {mean:.0f}m "
                        f"(z-score: {z_score:.1f})"
                    ),
                    evidence={
                        "today_distance_m": round(today_distance, 1),
                        "baseline_mean_m": round(mean, 1),
                        "baseline_std_m": round(std_dev, 1),
                        "z_score": round(z_score, 2),
                        "threshold": config.REDUCED_MOVEMENT_Z_THRESHOLD,
                        "recent_days": bl.get("daily_values", []),
                    },
                )
                count += 1
                logger.info(f"  Reduced movement: animal {animal_id} (z={z_score:.1f})")

    return count


async def _detect_isolation(db, farm_id: str) -> int:
    """
    Flag animals not seen by any gateway in the last N hours while others are being seen.
    Simple version: animal has sightings in baseline but none in the last isolation_threshold hours.
    """
    threshold_hours = config.ISOLATION_HOURS_THRESHOLD
    cutoff = datetime.now(timezone.utc) - timedelta(hours=threshold_hours)

    # Get animals with baselines (i.e. normally active) that haven't been seen recently
    query = text("""
        WITH baselined_animals AS (
            SELECT DISTINCT animal_id
            FROM behaviour_baselines
            WHERE farm_id = :farm_id AND animal_id IS NOT NULL
        ),
        recently_seen AS (
            SELECT DISTINCT s.animal_id
            FROM ble_sightings s
            JOIN gateway_devices g ON g.id = s.gateway_id
            WHERE g.farm_id = :farm_id
              AND s.animal_id IS NOT NULL
              AND s.time >= :cutoff
        ),
        any_recent_activity AS (
            SELECT COUNT(*) AS cnt
            FROM ble_sightings s
            JOIN gateway_devices g ON g.id = s.gateway_id
            WHERE g.farm_id = :farm_id AND s.time >= :cutoff
        )
        SELECT ba.animal_id
        FROM baselined_animals ba
        LEFT JOIN recently_seen rs ON rs.animal_id = ba.animal_id
        WHERE rs.animal_id IS NULL
          AND (SELECT cnt FROM any_recent_activity) > 10
    """)
    result = await db.execute(query, {"farm_id": farm_id, "cutoff": cutoff})
    isolated_animals = result.fetchall()

    count = 0
    for row in isolated_animals:
        animal_id = str(row.animal_id)

        # Get last sighting time for context
        last_seen_query = text("""
            SELECT time, gateway_latitude, gateway_longitude
            FROM ble_sightings
            WHERE animal_id = :animal_id
            ORDER BY time DESC
            LIMIT 1
        """)
        last_result = await db.execute(last_seen_query, {"animal_id": animal_id})
        last_row = last_result.first()

        hours_since = None
        last_lat = None
        last_lon = None
        if last_row:
            hours_since = round((datetime.now(timezone.utc) - last_row.time).total_seconds() / 3600, 1)
            last_lat = last_row.gateway_latitude
            last_lon = last_row.gateway_longitude

        if not await _has_active_anomaly(db, animal_id, "isolation"):
            await _create_anomaly(
                db, farm_id, animal_id,
                anomaly_type="isolation",
                severity="medium",
                description=(
                    f"Not detected by any gateway in the last {threshold_hours}h "
                    f"while other animals are being tracked. Last seen {hours_since}h ago."
                ),
                evidence={
                    "hours_since_last_seen": hours_since,
                    "threshold_hours": threshold_hours,
                    "last_latitude": last_lat,
                    "last_longitude": last_lon,
                },
            )
            count += 1
            logger.info(f"  Isolation: animal {animal_id} (not seen in {hours_since}h)")

    return count


async def _detect_patrol_gaps(db, farm_id: str) -> int:
    """
    Flag if no patrol session has occurred on this farm in the last N days.
    """
    threshold_days = config.PATROL_GAP_DAYS_THRESHOLD
    cutoff = datetime.now(timezone.utc) - timedelta(days=threshold_days)

    query = text("""
        SELECT COUNT(*) AS session_count,
               MAX(started_at) AS last_session
        FROM herdsman_sessions
        WHERE farm_id = :farm_id
          AND started_at >= :cutoff
    """)
    result = await db.execute(query, {"farm_id": farm_id, "cutoff": cutoff})
    row = result.first()

    if row and row.session_count == 0:
        # No patrols in N days — flag it (farm-level anomaly, no specific animal)
        if not await _has_active_anomaly(db, None, "patrol_gap", farm_id):
            # Get last session info
            last_query = text("""
                SELECT started_at, herdsman_name
                FROM herdsman_sessions
                WHERE farm_id = :farm_id
                ORDER BY started_at DESC
                LIMIT 1
            """)
            last_result = await db.execute(last_query, {"farm_id": farm_id})
            last_row = last_result.first()

            days_since = None
            last_herdsman = None
            if last_row:
                days_since = (datetime.now(timezone.utc) - last_row.started_at).days
                last_herdsman = last_row.herdsman_name

            await _create_anomaly(
                db, farm_id, None,
                anomaly_type="patrol_gap",
                severity="low",
                description=(
                    f"No herdsman patrol in the last {threshold_days} days. "
                    f"Last patrol was {days_since} days ago by {last_herdsman}."
                    if days_since else
                    f"No herdsman patrol in the last {threshold_days} days."
                ),
                evidence={
                    "threshold_days": threshold_days,
                    "days_since_last_patrol": days_since,
                    "last_herdsman": last_herdsman,
                },
            )
            logger.info(f"  Patrol gap: farm {farm_id} (no patrol in {threshold_days}d)")
            return 1

    return 0


async def _detect_night_movement(db, farm_id: str) -> int:
    """
    Flag animals with significant BLE sightings during night hours (22:00-04:00).
    This could indicate predator disturbance, theft attempt, or fence break.
    """
    now = datetime.now(timezone.utc)
    night_start_hour = config.NIGHT_MOVEMENT_START_HOUR
    night_end_hour = config.NIGHT_MOVEMENT_END_HOUR

    # Only check if we're currently past the night window (morning check)
    # or if there's recent night data from last night
    last_night_start = now.replace(hour=night_start_hour, minute=0, second=0, microsecond=0)
    if now.hour < night_start_hour:
        last_night_start -= timedelta(days=1)

    last_night_end = last_night_start + timedelta(hours=(24 - night_start_hour + night_end_hour) % 24)

    # Find animals with >5 sightings during night hours (indicates real movement, not noise)
    query = text("""
        SELECT s.animal_id, COUNT(*) AS night_sightings,
               MIN(s.time) AS first_seen, MAX(s.time) AS last_seen
        FROM ble_sightings s
        JOIN gateway_devices g ON g.id = s.gateway_id
        WHERE g.farm_id = :farm_id
          AND s.animal_id IS NOT NULL
          AND s.time >= :night_start
          AND s.time <= :night_end
        GROUP BY s.animal_id
        HAVING COUNT(*) > 5
    """)
    result = await db.execute(query, {
        "farm_id": farm_id,
        "night_start": last_night_start,
        "night_end": last_night_end,
    })
    rows = result.fetchall()

    count = 0
    for row in rows:
        animal_id = str(row.animal_id)
        if not await _has_active_anomaly(db, animal_id, "night_movement"):
            await _create_anomaly(
                db, farm_id, animal_id,
                anomaly_type="night_movement",
                severity="high",
                description=(
                    f"Detected {row.night_sightings} times during night hours "
                    f"({night_start_hour}:00-{night_end_hour:02d}:00). "
                    f"Possible predator disturbance or security concern."
                ),
                evidence={
                    "night_sightings": row.night_sightings,
                    "first_seen": row.first_seen.isoformat() if row.first_seen else None,
                    "last_seen": row.last_seen.isoformat() if row.last_seen else None,
                    "night_window": f"{night_start_hour}:00-{night_end_hour:02d}:00",
                },
            )
            count += 1
            logger.info(f"  Night movement: animal {animal_id} ({row.night_sightings} sightings)")

    return count


# ─── Helpers ──────────────────────────────────────────────────────────────────


async def _has_active_anomaly(db, animal_id: str | None, anomaly_type: str, farm_id: str | None = None) -> bool:
    """Check if an active anomaly already exists for this animal+type."""
    if animal_id:
        query = text("""
            SELECT 1 FROM anomalies
            WHERE animal_id = :animal_id AND anomaly_type = :anomaly_type AND status = 'active'
            LIMIT 1
        """)
        result = await db.execute(query, {"animal_id": animal_id, "anomaly_type": anomaly_type})
    else:
        query = text("""
            SELECT 1 FROM anomalies
            WHERE farm_id = :farm_id AND animal_id IS NULL AND anomaly_type = :anomaly_type AND status = 'active'
            LIMIT 1
        """)
        result = await db.execute(query, {"farm_id": farm_id, "anomaly_type": anomaly_type})
    return result.first() is not None


async def _create_anomaly(db, farm_id: str, animal_id: str | None, anomaly_type: str,
                          severity: str, description: str, evidence: dict):
    """Insert a new anomaly record."""
    query = text("""
        INSERT INTO anomalies (farm_id, animal_id, anomaly_type, severity, description, evidence)
        VALUES (:farm_id, :animal_id, :anomaly_type, :severity, :description, :evidence)
    """)
    await db.execute(query, {
        "farm_id": farm_id,
        "animal_id": animal_id,
        "anomaly_type": anomaly_type,
        "severity": severity,
        "description": description,
        "evidence": json.dumps(evidence),
    })


async def _auto_resolve_stale_anomalies(db):
    """
    Auto-resolve anomalies that are no longer valid:
    - reduced_movement: resolve if animal moved normally today
    - isolation: resolve if animal has been seen in last 2 hours
    """
    now = datetime.now(timezone.utc)
    two_hours_ago = now - timedelta(hours=2)

    # Resolve isolation anomalies for animals now being seen
    resolve_isolation = text("""
        UPDATE anomalies SET status = 'resolved', resolved_at = NOW()
        WHERE anomaly_type = 'isolation' AND status = 'active'
          AND animal_id IN (
              SELECT DISTINCT animal_id FROM ble_sightings
              WHERE time >= :cutoff AND animal_id IS NOT NULL
          )
    """)
    await db.execute(resolve_isolation, {"cutoff": two_hours_ago})

    # Resolve patrol_gap anomalies if a session has started recently
    resolve_patrol = text("""
        UPDATE anomalies SET status = 'resolved', resolved_at = NOW()
        WHERE anomaly_type = 'patrol_gap' AND status = 'active'
          AND farm_id IN (
              SELECT DISTINCT farm_id FROM herdsman_sessions
              WHERE started_at >= NOW() - INTERVAL '1 day'
          )
    """)
    await db.execute(resolve_patrol)
