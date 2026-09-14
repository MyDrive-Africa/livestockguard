"""Boundary containment math for the Herding Orchestrator.

Pure, dependency-free geometry so it can be unit-tested with no database or network.
Supports the three boundary shapes the product requires:

- ``circle``    — centre + radius (cheap distance-to-centre check)
- ``rectangle`` — a 4-vertex polygon (treated the same as ``polygon``)
- ``polygon``   — arbitrary ring, evaluated with the winding-number algorithm
                  (the same approach used on-collar in firmware and in the Rust
                  geofence engine, kept consistent here)

All coordinates are (latitude, longitude) in decimal degrees. Distances are metres,
computed with an equirectangular approximation which is accurate at farm scale
(sub-metre error over a few km) and far cheaper than full haversine per vertex.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Sequence

# Metres per degree of latitude (WGS84 mean). Longitude is scaled by cos(lat).
_M_PER_DEG_LAT = 111_320.0


class Containment(str, Enum):
    """Classification of an animal relative to its boundary."""

    SAFE = "safe"                # comfortably inside, beyond the warning buffer
    APPROACHING = "approaching"  # inside but within buffer_m of the edge
    BREACHED = "breached"        # outside the boundary


@dataclass(frozen=True)
class ContainmentResult:
    """Outcome of evaluating one animal against a boundary.

    Attributes:
        state: SAFE / APPROACHING / BREACHED.
        distance_to_edge_m: Signed distance to the boundary edge in metres —
            positive when inside, negative when outside (breached).
    """

    state: Containment
    distance_to_edge_m: float


def _local_xy(lat: float, lon: float, ref_lat: float, ref_lon: float) -> tuple[float, float]:
    """Project (lat, lon) to local planar metres around a reference point."""
    x = math.radians(lon - ref_lon) * _M_PER_DEG_LAT * math.cos(math.radians(ref_lat)) / math.radians(1)
    y = (lat - ref_lat) * _M_PER_DEG_LAT
    return x, y


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two points in metres."""
    r = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlam / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _point_in_polygon(lat: float, lon: float, ring: Sequence[tuple[float, float]]) -> bool:
    """Winding-number / ray-cast point-in-polygon test.

    Args:
        lat, lon: Query point.
        ring: Polygon vertices as (lat, lon); may be open or closed.

    Returns:
        True if the point is inside the ring.
    """
    inside = False
    n = len(ring)
    if n < 3:
        return False
    j = n - 1
    for i in range(n):
        yi, xi = ring[i]        # (lat, lon)
        yj, xj = ring[j]
        intersects = ((xi > lon) != (xj > lon)) and (
            lat < (yj - yi) * (lon - xi) / ((xj - xi) or 1e-15) + yi
        )
        if intersects:
            inside = not inside
        j = i
    return inside


def _distance_to_ring_m(lat: float, lon: float, ring: Sequence[tuple[float, float]]) -> float:
    """Shortest distance (metres) from a point to a polygon's edges."""
    best = math.inf
    n = len(ring)
    for i in range(n):
        alat, alon = ring[i]
        blat, blon = ring[(i + 1) % n]
        ax, ay = _local_xy(alat, alon, lat, lon)
        bx, by = _local_xy(blat, blon, lat, lon)
        # point is the origin (0,0) in this local frame
        dx, dy = bx - ax, by - ay
        seg_len2 = dx * dx + dy * dy
        if seg_len2 == 0:
            dist = math.hypot(ax, ay)
        else:
            t = max(0.0, min(1.0, -(ax * dx + ay * dy) / seg_len2))
            px, py = ax + t * dx, ay + t * dy
            dist = math.hypot(px, py)
        best = min(best, dist)
    return best


def evaluate_circle(
    lat: float,
    lon: float,
    center_lat: float,
    center_lon: float,
    radius_m: float,
    buffer_m: float,
) -> ContainmentResult:
    """Classify a point against a circular boundary."""
    dist_from_center = haversine_m(lat, lon, center_lat, center_lon)
    signed_edge = radius_m - dist_from_center  # + inside, - outside
    if signed_edge < 0:
        return ContainmentResult(Containment.BREACHED, signed_edge)
    if signed_edge <= buffer_m:
        return ContainmentResult(Containment.APPROACHING, signed_edge)
    return ContainmentResult(Containment.SAFE, signed_edge)


def evaluate_polygon(
    lat: float,
    lon: float,
    ring: Sequence[tuple[float, float]],
    buffer_m: float,
) -> ContainmentResult:
    """Classify a point against a polygon/rectangle boundary."""
    inside = _point_in_polygon(lat, lon, ring)
    edge_dist = _distance_to_ring_m(lat, lon, ring)
    signed_edge = edge_dist if inside else -edge_dist
    if not inside:
        return ContainmentResult(Containment.BREACHED, signed_edge)
    if edge_dist <= buffer_m:
        return ContainmentResult(Containment.APPROACHING, signed_edge)
    return ContainmentResult(Containment.SAFE, signed_edge)


@dataclass(frozen=True)
class Boundary:
    """A farm boundary the orchestrator keeps animals inside.

    For ``circle`` provide center_lat/center_lon/radius_m.
    For ``rectangle``/``polygon`` provide ``ring`` as a list of (lat, lon) vertices.
    """

    shape: str                                   # 'circle' | 'rectangle' | 'polygon'
    buffer_m: float = 15.0
    center_lat: float | None = None
    center_lon: float | None = None
    radius_m: float | None = None
    ring: Sequence[tuple[float, float]] | None = None

    def evaluate(self, lat: float, lon: float) -> ContainmentResult:
        """Classify a single (lat, lon) against this boundary."""
        if self.shape == "circle":
            if self.center_lat is None or self.center_lon is None or self.radius_m is None:
                raise ValueError("circle boundary requires center_lat, center_lon, radius_m")
            return evaluate_circle(
                lat, lon, self.center_lat, self.center_lon, self.radius_m, self.buffer_m
            )
        # rectangle is just a polygon
        if not self.ring:
            raise ValueError(f"{self.shape} boundary requires a ring of vertices")
        return evaluate_polygon(lat, lon, self.ring, self.buffer_m)

    def centroid(self) -> tuple[float, float]:
        """Approximate herd-centre target: the boundary centre.

        Used as the direction to push a straying animal back toward.
        """
        if self.shape == "circle":
            return self.center_lat, self.center_lon  # type: ignore[return-value]
        assert self.ring
        n = len(self.ring)
        return (sum(p[0] for p in self.ring) / n, sum(p[1] for p in self.ring) / n)
