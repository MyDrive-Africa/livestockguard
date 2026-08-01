"""
Baseline Builder — learns normal behaviour patterns per animal.

Runs nightly. Queries the last N days of BLE sighting data and computes:
- daily_distance: average distance an animal moves per day (metres)
- daily_sightings: how often an animal is typically detected per day
- active_hours: hours of the day the animal is typically seen moving
- herd_companions: which other animals are usually seen in the same batch

Stores results in the behaviour_baselines table (UPSERT per animal+metric).
"""

import json
import logging
import math
from datetime import datetime, timezone, timedelta

from sqlalchemy import text

from app.config import BASELINE_WINDOW_DAYS, MIN_SIGHTINGS_FOR_BASELINE
from app.db import async_session

logger = logging.getLogger("analytics_engine.baseline_builder")


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine distance in metres between two GPS points."""
    R = 6371000  # Earth radius in metres
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


async def run_baseline_builder():
    """Compute behaviour baselines for all animals across all farms."""
    logger.info("Starting baseline builder...")
    start_time = datetime.now(timezone.utc)

    async with async_session() as db:
        # Get all farms with active BLE-tagged animals
        farms_query = text("""
            SELECT DISTINCT f.id AS farm_id, f.name AS farm_name
            FROM farms f
            JOIN ble_ear_tags bt ON bt.farm_id = f.id AND bt.status = 'active'
            JOIN animals a ON a.id = bt.animal_id AND a.status = 'active'
        """)
        farms_result = await db.execute(farms_query)
        farms = farms_result.fetchall()

        if not farms:
            logger.info("No farms with active BLE-tagged animals found.")
            return

        total_baselines = 0

        for farm in farms:
            farm_id = str(farm.farm_id)
            logger.info(f"Processing farm: {farm.farm_name} ({farm_id})")

            # Get all active animals with BLE tags on this farm
            animals_query = text("""
                SELECT a.id AS animal_id, a.name AS animal_name
                FROM animals a
                JOIN ble_ear_tags bt ON bt.animal_id = a.id AND bt.status = 'active'
                WHERE a.farm_id = :farm_id AND a.status = 'active'
            """)
            animals_result = await db.execute(animals_query, {"farm_id": farm_id})
            animals = animals_result.fetchall()

            for animal in animals:
                animal_id = str(animal.animal_id)
                baselines_computed = await _compute_animal_baselines(db, farm_id, animal_id, animal.animal_name)
                total_baselines += baselines_computed

            # Compute herd-level baselines
            herd_baselines = await _compute_herd_baselines(db, farm_id)
            total_baselines += herd_baselines

        await db.commit()

    elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
    logger.info(f"Baseline builder complete: {total_baselines} baselines computed in {elapsed:.1f}s")


async def _compute_animal_baselines(db, farm_id: str, animal_id: str, animal_name: str) -> int:
    """Compute all baselines for a single animal. Returns count of baselines upserted."""
    window_start = datetime.now(timezone.utc) - timedelta(days=BASELINE_WINDOW_DAYS)
    count = 0

    # ─── Daily Distance Baseline ──────────────────────────────────────────────
    distance_data = await _compute_daily_distances(db, animal_id, window_start)
    if distance_data and len(distance_data) >= 2:
        distances = [d for d in distance_data if d > 0]
        if distances:
            mean_dist = sum(distances) / len(distances)
            std_dist = (sum((d - mean_dist) ** 2 for d in distances) / len(distances)) ** 0.5
            baseline_value = {
                "mean": round(mean_dist, 1),
                "std_dev": round(std_dist, 1),
                "min": round(min(distances), 1),
                "max": round(max(distances), 1),
                "sample_days": len(distances),
                "daily_values": [round(d, 1) for d in distances[-7:]],  # Last 7 days
            }
            await _upsert_baseline(db, farm_id, animal_id, "daily_distance", baseline_value)
            count += 1

    # ─── Daily Sighting Count Baseline ────────────────────────────────────────
    sighting_counts = await _compute_daily_sighting_counts(db, animal_id, window_start)
    if sighting_counts and len(sighting_counts) >= 2:
        counts = [c for c in sighting_counts if c > 0]
        if counts:
            mean_count = sum(counts) / len(counts)
            std_count = (sum((c - mean_count) ** 2 for c in counts) / len(counts)) ** 0.5
            baseline_value = {
                "mean": round(mean_count, 1),
                "std_dev": round(std_count, 1),
                "min": min(counts),
                "max": max(counts),
                "sample_days": len(counts),
            }
            await _upsert_baseline(db, farm_id, animal_id, "daily_sightings", baseline_value)
            count += 1

    # ─── Active Hours Baseline ────────────────────────────────────────────────
    active_hours = await _compute_active_hours(db, animal_id, window_start)
    if active_hours:
        await _upsert_baseline(db, farm_id, animal_id, "active_hours", active_hours)
        count += 1

    if count > 0:
        logger.debug(f"  {animal_name}: {count} baselines computed")

    return count


async def _compute_daily_distances(db, animal_id: str, window_start: datetime) -> list:
    """Calculate daily movement distance from consecutive BLE sightings."""
    query = text("""
        SELECT DATE(time) AS day,
               array_agg(gateway_latitude ORDER BY time) AS lats,
               array_agg(gateway_longitude ORDER BY time) AS lons
        FROM ble_sightings
        WHERE animal_id = :animal_id
          AND time >= :window_start
          AND gateway_latitude IS NOT NULL
        GROUP BY DATE(time)
        ORDER BY day
    """)
    result = await db.execute(query, {"animal_id": animal_id, "window_start": window_start})
    rows = result.fetchall()

    daily_distances = []
    for row in rows:
        lats = row.lats
        lons = row.lons
        if len(lats) < 2:
            daily_distances.append(0.0)
            continue

        total_dist = 0.0
        for i in range(1, len(lats)):
            if lats[i] and lons[i] and lats[i - 1] and lons[i - 1]:
                d = haversine_m(lats[i - 1], lons[i - 1], lats[i], lons[i])
                # Skip unrealistic jumps (> 5km between consecutive sightings)
                if d < 5000:
                    total_dist += d
        daily_distances.append(total_dist)

    return daily_distances


async def _compute_daily_sighting_counts(db, animal_id: str, window_start: datetime) -> list:
    """Count BLE sightings per day for an animal."""
    query = text("""
        SELECT DATE(time) AS day, COUNT(*) AS cnt
        FROM ble_sightings
        WHERE animal_id = :animal_id
          AND time >= :window_start
        GROUP BY DATE(time)
        ORDER BY day
    """)
    result = await db.execute(query, {"animal_id": animal_id, "window_start": window_start})
    return [row.cnt for row in result.fetchall()]


async def _compute_active_hours(db, animal_id: str, window_start: datetime) -> dict | None:
    """Determine which hours of the day the animal is typically seen."""
    query = text("""
        SELECT EXTRACT(HOUR FROM time)::int AS hour, COUNT(*) AS cnt
        FROM ble_sightings
        WHERE animal_id = :animal_id
          AND time >= :window_start
        GROUP BY hour
        ORDER BY hour
    """)
    result = await db.execute(query, {"animal_id": animal_id, "window_start": window_start})
    rows = result.fetchall()

    if not rows:
        return None

    total = sum(r.cnt for r in rows)
    if total < MIN_SIGHTINGS_FOR_BASELINE:
        return None

    hour_distribution = {r.hour: r.cnt for r in rows}
    peak_hours = sorted(hour_distribution, key=hour_distribution.get, reverse=True)[:5]

    return {
        "hour_distribution": hour_distribution,
        "peak_hours": peak_hours,
        "total_sightings": total,
    }


async def _compute_herd_baselines(db, farm_id: str) -> int:
    """Compute farm-level herd baselines (average herd distance, coverage)."""
    window_start = datetime.now(timezone.utc) - timedelta(days=BASELINE_WINDOW_DAYS)
    count = 0

    # Herd daily coverage: unique animals seen per day
    query = text("""
        SELECT DATE(s.time) AS day, COUNT(DISTINCT s.animal_id) AS unique_animals
        FROM ble_sightings s
        JOIN gateway_devices g ON g.id = s.gateway_id
        WHERE g.farm_id = :farm_id
          AND s.animal_id IS NOT NULL
          AND s.time >= :window_start
        GROUP BY DATE(s.time)
        ORDER BY day
    """)
    result = await db.execute(query, {"farm_id": farm_id, "window_start": window_start})
    rows = result.fetchall()

    if rows and len(rows) >= 2:
        counts = [row.unique_animals for row in rows]
        mean_coverage = sum(counts) / len(counts)
        std_coverage = (sum((c - mean_coverage) ** 2 for c in counts) / len(counts)) ** 0.5
        baseline_value = {
            "mean": round(mean_coverage, 1),
            "std_dev": round(std_coverage, 1),
            "min": min(counts),
            "max": max(counts),
            "sample_days": len(counts),
        }
        await _upsert_baseline(db, farm_id, None, "herd_daily_coverage", baseline_value)
        count += 1

    return count


async def _upsert_baseline(db, farm_id: str, animal_id: str | None, metric_name: str, baseline_value: dict):
    """Insert or update a behaviour baseline."""
    if animal_id:
        query = text("""
            INSERT INTO behaviour_baselines (farm_id, animal_id, metric_name, baseline_value, window_days, computed_at)
            VALUES (:farm_id, :animal_id, :metric_name, :baseline_value, :window_days, NOW())
            ON CONFLICT (farm_id, animal_id, metric_name)
            DO UPDATE SET baseline_value = :baseline_value, window_days = :window_days, computed_at = NOW()
        """)
        await db.execute(query, {
            "farm_id": farm_id,
            "animal_id": animal_id,
            "metric_name": metric_name,
            "baseline_value": json.dumps(baseline_value),
            "window_days": BASELINE_WINDOW_DAYS,
        })
    else:
        # Herd-level baseline (animal_id IS NULL) — need different conflict handling
        query = text("""
            INSERT INTO behaviour_baselines (farm_id, animal_id, metric_name, baseline_value, window_days, computed_at)
            VALUES (:farm_id, NULL, :metric_name, :baseline_value, :window_days, NOW())
            ON CONFLICT (farm_id, animal_id, metric_name)
            DO UPDATE SET baseline_value = :baseline_value, window_days = :window_days, computed_at = NOW()
        """)
        await db.execute(query, {
            "farm_id": farm_id,
            "metric_name": metric_name,
            "baseline_value": json.dumps(baseline_value),
            "window_days": BASELINE_WINDOW_DAYS,
        })
