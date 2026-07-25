"""
Activity classification algorithm for livestock.

Classifies animal activity based on GPS telemetry data:
- Resting: speed < 0.3 km/h, low heading variance
- Grazing: speed 0.3–2.0 km/h, high heading variance (zig-zag pattern)
- Walking: speed 2.0–8.0 km/h, moderate heading variance
- Running: speed > 8.0 km/h

Uses a sliding window approach over position history.
"""

import math
from dataclasses import dataclass
from typing import Optional


@dataclass
class ActivityResult:
    activity: str          # 'resting', 'grazing', 'walking', 'running'
    confidence: float      # 0.0 - 1.0
    avg_speed: float       # km/h
    max_speed: float       # km/h
    distance_m: float      # total distance in meters
    heading_variance: float  # degrees variance


# Speed thresholds (km/h) — tuned for cattle
SPEED_RESTING_MAX = 0.3
SPEED_GRAZING_MAX = 2.0
SPEED_WALKING_MAX = 8.0
# Above SPEED_WALKING_MAX = running

# Heading variance thresholds (degrees²)
HEADING_VARIANCE_GRAZING = 2000.0  # High variance = direction changes = grazing


def classify_activity(
    speeds: list[float],
    headings: list[float],
    distances_m: list[float],
) -> ActivityResult:
    """
    Classify animal activity from a window of telemetry samples.

    Args:
        speeds: List of speed values in km/h
        headings: List of heading values in degrees (0-360)
        distances_m: List of inter-point distances in meters

    Returns:
        ActivityResult with classification and metrics
    """
    if not speeds:
        return ActivityResult(
            activity='resting', confidence=0.5,
            avg_speed=0, max_speed=0, distance_m=0, heading_variance=0
        )

    avg_speed = sum(speeds) / len(speeds)
    max_speed = max(speeds)
    total_distance = sum(distances_m) if distances_m else 0
    h_variance = _heading_variance(headings) if headings else 0

    # Classification logic
    if avg_speed < SPEED_RESTING_MAX:
        activity = 'resting'
        confidence = min(1.0, 1.0 - (avg_speed / SPEED_RESTING_MAX))
    elif avg_speed < SPEED_GRAZING_MAX:
        # Distinguish grazing from slow walking by heading variance
        if h_variance > HEADING_VARIANCE_GRAZING:
            activity = 'grazing'
            confidence = min(1.0, h_variance / (HEADING_VARIANCE_GRAZING * 2))
        else:
            activity = 'walking'
            confidence = 0.6
    elif avg_speed < SPEED_WALKING_MAX:
        activity = 'walking'
        confidence = min(1.0, avg_speed / SPEED_WALKING_MAX)
    else:
        activity = 'running'
        confidence = min(1.0, avg_speed / 15.0)  # Cap at 15 km/h

    return ActivityResult(
        activity=activity,
        confidence=round(confidence, 2),
        avg_speed=round(avg_speed, 2),
        max_speed=round(max_speed, 2),
        distance_m=round(total_distance, 1),
        heading_variance=round(h_variance, 1),
    )


def _heading_variance(headings: list[float]) -> float:
    """Calculate circular variance of headings (handles 360° wrap-around)."""
    if len(headings) < 2:
        return 0.0

    # Calculate heading changes (delta between consecutive headings)
    deltas = []
    for i in range(1, len(headings)):
        delta = headings[i] - headings[i - 1]
        # Normalize to -180..180
        delta = (delta + 180) % 360 - 180
        deltas.append(delta)

    if not deltas:
        return 0.0

    mean_delta = sum(deltas) / len(deltas)
    variance = sum((d - mean_delta) ** 2 for d in deltas) / len(deltas)
    return variance


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two GPS points in meters."""
    R = 6371000  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c
