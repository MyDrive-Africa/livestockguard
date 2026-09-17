"""
System monitoring endpoints — API health, DB stats, performance metrics.
"""

import os
import sys
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'shared'))

from app.dependencies import get_db

router = APIRouter()


@router.get("/status")
async def system_status(db: AsyncSession = Depends(get_db)):
    """System health and performance metrics for the admin dashboard."""
    now = datetime.now(timezone.utc)

    # DB stats
    try:
        # Total counts
        counts = await db.execute(text("""
            SELECT
                (SELECT COUNT(*) FROM animals WHERE status = 'active') AS animals,
                (SELECT COUNT(*) FROM devices) AS devices,
                (SELECT COUNT(*) FROM geofences WHERE active = true) AS geofences,
                (SELECT COUNT(*) FROM gateway_devices WHERE status = 'active') AS gateways,
                (SELECT COUNT(*) FROM ble_ear_tags WHERE status = 'active') AS ble_tags,
                (SELECT COUNT(*) FROM alerts WHERE status = 'active') AS active_alerts
        """))
        row = counts.first()

        # Last activity timestamps
        timestamps = await db.execute(text("""
            SELECT
                (SELECT MAX(time) FROM positions) AS last_gps_position,
                (SELECT MAX(time) FROM ble_sightings) AS last_ble_sighting,
                (SELECT MAX(created_at) FROM alerts) AS last_alert,
                (SELECT MAX(last_seen) FROM gateway_devices) AS last_gateway_ping
        """))
        ts_row = timestamps.first()

        # DB size
        db_size = await db.execute(text("""
            SELECT pg_size_pretty(pg_database_size('livestockguard')) AS db_size
        """))
        size_row = db_size.first()

        # Position count (last 24h)
        recent = await db.execute(text("""
            SELECT
                (SELECT COUNT(*) FROM positions WHERE time > NOW() - INTERVAL '24 hours') AS gps_24h,
                (SELECT COUNT(*) FROM ble_sightings WHERE time > NOW() - INTERVAL '24 hours') AS ble_24h
        """))
        recent_row = recent.first()

    except Exception as e:
        return {"status": "error", "detail": str(e)}

    return {
        "status": "healthy",
        "timestamp": now.isoformat(),
        "counts": {
            "animals": row.animals if row else 0,
            "devices": row.devices if row else 0,
            "geofences": row.geofences if row else 0,
            "gateways": row.gateways if row else 0,
            "ble_tags": row.ble_tags if row else 0,
            "active_alerts": row.active_alerts if row else 0,
        },
        "last_activity": {
            "gps_position": ts_row.last_gps_position.isoformat() if ts_row and ts_row.last_gps_position else None,
            "ble_sighting": ts_row.last_ble_sighting.isoformat() if ts_row and ts_row.last_ble_sighting else None,
            "alert": ts_row.last_alert.isoformat() if ts_row and ts_row.last_alert else None,
            "gateway_ping": ts_row.last_gateway_ping.isoformat() if ts_row and ts_row.last_gateway_ping else None,
        },
        "volume_24h": {
            "gps_positions": recent_row.gps_24h if recent_row else 0,
            "ble_sightings": recent_row.ble_24h if recent_row else 0,
        },
        "database": {
            "size": size_row.db_size if size_row else "unknown",
        },
    }


@router.get("/simulation-status")
async def simulation_status(db: AsyncSession = Depends(get_db)):
    """
    Per-farm simulation preflight.

    For each farm that has a BLE gateway, report whether data is actually
    flowing right now: how many sightings landed today, how many distinct
    animals were seen, whether a herdsman session is currently active, and when
    the farm's gateway was last heard from. Powers the dashboard "simulation
    mode" banner so an idle/stopped simulator is obvious at a glance instead of
    looking like a scanning failure.

    A farm is considered `stale` when it has registered BLE tags but zero
    sightings today (the classic "nothing is being detected" symptom).
    """
    now = datetime.now(timezone.utc)

    # One pass over farms that own a gateway. Left-join today's sightings and
    # any active session so farms with no activity still appear (as stale).
    query = text("""
        SELECT
            f.id::text                                   AS farm_id,
            f.name                                       AS farm_name,
            g.serial_number                              AS gateway_serial,
            g.last_seen                                  AS gateway_last_seen,
            COALESCE(tags.tag_count, 0)                  AS registered_tags,
            COALESCE(today.sightings, 0)                 AS sightings_today,
            COALESCE(today.animals, 0)                   AS animals_today,
            (sess.session_id IS NOT NULL)                AS session_active
        FROM gateway_devices g
        JOIN farms f ON f.id = g.farm_id
        LEFT JOIN (
            SELECT bt.farm_id, COUNT(*) AS tag_count
            FROM ble_ear_tags bt
            WHERE bt.status = 'active'
            GROUP BY bt.farm_id
        ) tags ON tags.farm_id = g.farm_id
        LEFT JOIN (
            SELECT s.gateway_id,
                   COUNT(*) AS sightings,
                   COUNT(DISTINCT s.animal_id) AS animals
            FROM ble_sightings s
            WHERE s.time >= CURRENT_DATE
            GROUP BY s.gateway_id
        ) today ON today.gateway_id = g.id
        LEFT JOIN LATERAL (
            SELECT hs.id AS session_id
            FROM herdsman_sessions hs
            WHERE hs.gateway_id = g.id AND hs.status = 'active'
            ORDER BY hs.started_at DESC
            LIMIT 1
        ) sess ON true
        WHERE g.status = 'active'
        ORDER BY f.name
    """)

    try:
        rows = (await db.execute(query)).fetchall()
    except Exception as e:
        return {"status": "error", "detail": str(e), "farms": []}

    farms = []
    any_active = False
    any_stale = False
    for r in rows:
        # "stale" = has tags to detect but nothing seen today.
        stale = r.registered_tags > 0 and r.sightings_today == 0
        active = r.sightings_today > 0 or r.session_active
        any_active = any_active or active
        any_stale = any_stale or stale
        farms.append({
            "farm_id": r.farm_id,
            "farm_name": r.farm_name,
            "gateway_serial": r.gateway_serial,
            "gateway_last_seen": r.gateway_last_seen.isoformat() if r.gateway_last_seen else None,
            "registered_tags": r.registered_tags,
            "sightings_today": r.sightings_today,
            "animals_today": r.animals_today,
            "session_active": bool(r.session_active),
            "stale": stale,
        })

    # Overall verdict for the banner headline.
    if not farms:
        overall = "no_gateways"
    elif any_active and not any_stale:
        overall = "healthy"
    elif any_active and any_stale:
        overall = "partial"
    else:
        overall = "idle"

    return {
        "status": "ok",
        "overall": overall,
        "timestamp": now.isoformat(),
        "farm_count": len(farms),
        "active_farm_count": sum(1 for f in farms if not f["stale"] and (f["sightings_today"] > 0 or f["session_active"])),
        "stale_farm_count": sum(1 for f in farms if f["stale"]),
        "farms": farms,
    }
