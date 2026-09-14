"""Unit tests for robot-to-job assignment (no DB/network)."""

from app.assigner import Assignment, RobotState, assign
from app.planner import HerdingTarget

C_LAT, C_LON = -26.719088, 27.709759


def _target(animal_id: str, lat: float, lon: float, priority: int) -> HerdingTarget:
    return HerdingTarget(
        animal_id=animal_id,
        animal_name=animal_id,
        animal_lat=lat,
        animal_lon=lon,
        intercept_lat=lat,
        intercept_lon=lon,
        priority=priority,
        job_type="shepherd",
        reason="test",
        members=[animal_id],
    )


def test_nearest_robot_gets_the_job():
    near = RobotState("r_near", "ROBO-01", C_LAT, C_LON, battery_pct=90)
    far = RobotState("r_far", "ROBO-02", C_LAT + 0.01, C_LON, battery_pct=90)
    target = _target("a1", C_LAT, C_LON, priority=100)

    assignments = assign([near, far], [target])
    by_robot = {a.robot_id: a for a in assignments}
    assert by_robot["r_near"].action == "shepherd"
    assert by_robot["r_near"].target is target
    assert by_robot["r_far"].action == "patrol"  # no job left -> patrol


def test_low_battery_robot_is_sent_home():
    weak = RobotState("r_weak", "ROBO-03", C_LAT, C_LON, battery_pct=5)
    ok = RobotState("r_ok", "ROBO-04", C_LAT + 0.02, C_LON, battery_pct=80)
    target = _target("a1", C_LAT, C_LON, priority=100)

    assignments = assign([weak, ok], [target], min_battery_for_job_pct=20)
    by_robot = {a.robot_id: a for a in assignments}
    assert by_robot["r_weak"].action == "return_home"
    # The healthy (but further) robot still takes the job since weak is ineligible.
    assert by_robot["r_ok"].action == "shepherd"


def test_highest_priority_targets_assigned_first_when_robots_scarce():
    r1 = RobotState("r1", "ROBO-01", C_LAT, C_LON, battery_pct=90)
    low = _target("low", C_LAT, C_LON, priority=40)
    high = _target("high", C_LAT, C_LON, priority=100)

    assignments = assign([r1], [low, high])
    working = [a for a in assignments if a.target is not None]
    assert len(working) == 1
    assert working[0].target.animal_id == "high"


def test_idle_robots_patrol():
    r1 = RobotState("r1", "ROBO-01", C_LAT, C_LON, battery_pct=90)
    assignments = assign([r1], [])
    assert assignments[0].action == "patrol"
