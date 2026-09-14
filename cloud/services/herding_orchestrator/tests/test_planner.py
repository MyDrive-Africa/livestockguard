"""Unit tests for the herding planner (no DB/network)."""

from app.containment import Boundary, Containment, ContainmentResult
from app.planner import (
    PRIORITY_APPROACHING,
    PRIORITY_BREACHED,
    AnimalState,
    plan_targets,
)

C_LAT, C_LON = -26.719088, 27.709759


def _boundary() -> Boundary:
    return Boundary(shape="circle", buffer_m=15, center_lat=C_LAT, center_lon=C_LON, radius_m=200)


def test_safe_animals_produce_no_targets():
    animals = [AnimalState("a1", "Bella", C_LAT, C_LON)]
    results = {"a1": ContainmentResult(Containment.SAFE, 180.0)}
    assert plan_targets(animals, results, _boundary()) == []


def test_breach_outranks_approach():
    animals = [
        AnimalState("a1", "Bella", C_LAT + 0.003, C_LON),   # breached (north)
        AnimalState("a2", "Storm", C_LAT + 0.0017, C_LON),  # approaching
    ]
    results = {
        "a1": ContainmentResult(Containment.BREACHED, -20.0),
        "a2": ContainmentResult(Containment.APPROACHING, 10.0),
    }
    targets = plan_targets(animals, results, _boundary())
    assert len(targets) == 2
    assert targets[0].animal_id == "a1"  # breach first
    assert targets[0].priority > targets[1].priority
    assert targets[0].priority >= PRIORITY_BREACHED - 20
    assert targets[1].priority <= PRIORITY_APPROACHING


def test_intercept_point_is_outside_the_animal():
    # The robot should stand further from centre than the animal (boundary-facing side).
    animals = [AnimalState("a1", "Bella", C_LAT + 0.0018, C_LON)]
    results = {"a1": ContainmentResult(Containment.APPROACHING, 5.0)}
    t = plan_targets(animals, results, _boundary())[0]
    # intercept latitude should be north of (further from centre than) the animal
    assert t.intercept_lat > animals[0].lat


def test_nearby_animals_merge_into_one_cluster_job():
    # Two breached animals ~10m apart -> one merged shepherd job.
    animals = [
        AnimalState("a1", "Bella", C_LAT + 0.003, C_LON),
        AnimalState("a2", "Storm", C_LAT + 0.003 + 5 / 111_320.0, C_LON),
    ]
    results = {
        "a1": ContainmentResult(Containment.BREACHED, -20.0),
        "a2": ContainmentResult(Containment.BREACHED, -19.0),
    }
    targets = plan_targets(animals, results, _boundary(), cluster_merge_radius_m=40)
    assert len(targets) == 1
    assert targets[0].job_type == "shepherd"
    assert set(targets[0].members) == {"a1", "a2"}
