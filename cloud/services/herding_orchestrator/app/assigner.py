"""Robot-to-job assignment for the Herding Orchestrator.

Pure logic (no DB/network) so it is unit-testable. Given the fleet's current state
and a prioritised list of herding targets, decide which robot goes to which job.

Strategy (greedy, cost-based — good enough for a 4-robot fleet):
  - Process targets from highest priority to lowest.
  - For each target, pick the cheapest *available* robot, where
        cost = travel_distance_m / max_speed_mps  (i.e. ETA seconds)
    with a mild penalty for low battery.
  - A robot below MIN_BATTERY_FOR_JOB_PCT is not eligible (it should charge).
  - Robots not assigned a job are told to PATROL (or return home to charge if low).

This keeps at least the most urgent breaches covered first, and never double-books
a robot within a single planning pass.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.containment import haversine_m
from app.planner import HerdingTarget


@dataclass
class RobotState:
    """Minimal robot snapshot the assigner needs."""

    robot_id: str
    serial: str
    lat: float
    lon: float
    battery_pct: int
    max_speed_mps: float = 2.0
    status: str = "idle"


@dataclass
class Assignment:
    """A robot paired with the target it should service (or a patrol/charge order)."""

    robot_id: str
    serial: str
    action: str                      # 'shepherd' | 'intercept' | 'patrol' | 'return_home'
    target: HerdingTarget | None = None


def _eta_seconds(robot: RobotState, lat: float, lon: float) -> float:
    """Rough travel time for a robot to reach a point."""
    dist = haversine_m(robot.lat, robot.lon, lat, lon)
    speed = max(0.1, robot.max_speed_mps)
    return dist / speed


def assign(
    robots: list[RobotState],
    targets: list[HerdingTarget],
    min_battery_for_job_pct: int = 20,
) -> list[Assignment]:
    """Assign robots to the highest-priority targets they can reach.

    Args:
        robots: Current fleet snapshot.
        targets: Prioritised herding targets (highest priority first).
        min_battery_for_job_pct: Robots below this are routed home to charge.

    Returns:
        One Assignment per robot. Unused robots get 'patrol' (or 'return_home'
        if their battery is too low for a job).
    """
    assignments: list[Assignment] = []
    available = {r.robot_id: r for r in robots if r.battery_pct >= min_battery_for_job_pct}

    # Low-battery robots: send home to charge, remove from the pool.
    for r in robots:
        if r.battery_pct < min_battery_for_job_pct:
            assignments.append(Assignment(r.robot_id, r.serial, "return_home"))

    for target in sorted(targets, key=lambda t: t.priority, reverse=True):
        if not available:
            break  # no more free robots; remaining targets wait for the next loop
        best_id = min(
            available,
            key=lambda rid: _eta_seconds(available[rid], target.intercept_lat, target.intercept_lon)
            + (100 - available[rid].battery_pct) * 0.2,  # mild low-battery penalty
        )
        robot = available.pop(best_id)
        assignments.append(
            Assignment(robot.robot_id, robot.serial, target.job_type, target=target)
        )

    # Any still-available robots patrol.
    for robot in available.values():
        assignments.append(Assignment(robot.robot_id, robot.serial, "patrol"))

    return assignments
