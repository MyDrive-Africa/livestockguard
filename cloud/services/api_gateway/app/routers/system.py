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
