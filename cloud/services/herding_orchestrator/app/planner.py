"""Herding planner — turns containment results into prioritised herding jobs.

Pure logic (no DB/network) so it is unit-testable. The planner answers:
  "Which animals need a robot, how urgent is each, and where should the robot
   stand to gently push the animal back toward the herd centre?"

The interception point is placed on the *far* side of the animal from the boundary
centre — i.e. between the animal and the edge it is drifting toward — so the robot's
presence and sound nudge the animal inward, the way a herdsman positions themselves.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from app.containment import Boundary, Containment, ContainmentResult, haversine_m

# Priority scores. Higher = more urgent. Breaches always outrank approaches.
PRIORITY_BREACHED = 100
PRIORITY_APPROACHING = 40


@dataclass
class AnimalState:
    """Minimal animal snapshot the planner needs."""

    animal_id: str
    name: str
    lat: float
    lon: float
    value_weight: float = 1.0  # optional: high-value animals (bulls) score higher


@dataclass
class HerdingTarget:
    """A planned job before it is assigned to a robot."""

    animal_id: str
    animal_name: str
    animal_lat: float
    animal_lon: float
    intercept_lat: float
    intercept_lon: float
    priority: int
    job_type: str          # 'intercept' | 'shepherd'
    reason: str
    members: list[str] = field(default_factory=list)  # animal ids in a merged cluster


def _offset_point(lat: float, lon: float, bearing_deg: float, distance_m: float) -> tuple[float, float]:
    """Return a point ``distance_m`` from (lat, lon) along ``bearing_deg``."""
    m_per_deg_lat = 111_320.0
    br = math.radians(bearing_deg)
    dlat = (distance_m * math.cos(br)) / m_per_deg_lat
    dlon = (distance_m * math.sin(br)) / (m_per_deg_lat * math.cos(math.radians(lat)))
    return lat + dlat, lon + dlon


def _bearing_deg(from_lat: float, from_lon: float, to_lat: float, to_lon: float) -> float:
    """Initial compass bearing from one point to another, degrees 0-360."""
    y = math.sin(math.radians(to_lon - from_lon)) * math.cos(math.radians(to_lat))
    x = math.cos(math.radians(from_lat)) * math.sin(math.radians(to_lat)) - math.sin(
        math.radians(from_lat)
    ) * math.cos(math.radians(to_lat)) * math.cos(math.radians(to_lon - from_lon))
    return (math.degrees(math.atan2(y, x)) + 360) % 360


def _intercept_point(animal: AnimalState, boundary: Boundary, standoff_m: float = 12.0) -> tuple[float, float]:
    """Where the robot should stand to push this animal back inward.

    Positioned ``standoff_m`` beyond the animal, on the line from the herd centre
    through the animal (i.e. on the animal's boundary-facing side).
    """
    c_lat, c_lon = boundary.centroid()
    bearing_center_to_animal = _bearing_deg(c_lat, c_lon, animal.lat, animal.lon)
    return _offset_point(animal.lat, animal.lon, bearing_center_to_animal, standoff_m)


def plan_targets(
    animals: list[AnimalState],
    results: dict[str, ContainmentResult],
    boundary: Boundary,
    cluster_merge_radius_m: float = 40.0,
) -> list[HerdingTarget]:
    """Build a prioritised list of herding targets.

    Args:
        animals: Current animal snapshots.
        results: Map of animal_id -> ContainmentResult (from containment.evaluate).
        boundary: The farm boundary.
        cluster_merge_radius_m: Animals nearer than this are merged into one job.

    Returns:
        Targets sorted by priority (highest first). SAFE animals are excluded.
    """
    targets: list[HerdingTarget] = []
    for a in animals:
        res = results.get(a.animal_id)
        if res is None or res.state == Containment.SAFE:
            continue

        if res.state == Containment.BREACHED:
            base = PRIORITY_BREACHED
            job_type = "shepherd"
            reason = f"{a.name} breached boundary ({abs(res.distance_to_edge_m):.0f}m outside)"
        else:  # APPROACHING
            base = PRIORITY_APPROACHING
            job_type = "intercept"
            reason = f"{a.name} approaching edge ({res.distance_to_edge_m:.0f}m to boundary)"

        # Closer to / further past the edge => more urgent. value_weight nudges bulls up.
        urgency = base - res.distance_to_edge_m + (a.value_weight - 1.0) * 10
        i_lat, i_lon = _intercept_point(a, boundary)
        targets.append(
            HerdingTarget(
                animal_id=a.animal_id,
                animal_name=a.name,
                animal_lat=a.lat,
                animal_lon=a.lon,
                intercept_lat=i_lat,
                intercept_lon=i_lon,
                priority=int(round(urgency)),
                job_type=job_type,
                reason=reason,
                members=[a.animal_id],
            )
        )

    merged = _merge_clusters(targets, cluster_merge_radius_m)
    merged.sort(key=lambda t: t.priority, reverse=True)
    return merged


def _merge_clusters(targets: list[HerdingTarget], radius_m: float) -> list[HerdingTarget]:
    """Merge targets whose animals are within ``radius_m`` into one shepherding job.

    One robot can nudge a small bunched group. The merged job keeps the highest
    priority and its intercept point, and records all member animal ids.
    """
    if not targets:
        return []
    # Greedy: process highest priority first, absorb nearby lower-priority targets.
    ordered = sorted(targets, key=lambda t: t.priority, reverse=True)
    used: set[int] = set()
    result: list[HerdingTarget] = []
    for i, lead in enumerate(ordered):
        if i in used:
            continue
        members = list(lead.members)
        for j in range(i + 1, len(ordered)):
            if j in used:
                continue
            other = ordered[j]
            if haversine_m(lead.animal_lat, lead.animal_lon, other.animal_lat, other.animal_lon) <= radius_m:
                members.extend(other.members)
                used.add(j)
        used.add(i)
        if len(members) > 1:
            lead = HerdingTarget(
                animal_id=lead.animal_id,
                animal_name=f"{lead.animal_name} +{len(members) - 1}",
                animal_lat=lead.animal_lat,
                animal_lon=lead.animal_lon,
                intercept_lat=lead.intercept_lat,
                intercept_lon=lead.intercept_lon,
                priority=lead.priority,
                job_type="shepherd",
                reason=lead.reason + f" (cluster of {len(members)})",
                members=members,
            )
        result.append(lead)
    return result
