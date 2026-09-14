"""Unit tests for boundary containment math (no DB/network)."""

from app.containment import Boundary, Containment


# Loch Vaal centre, used as a reference point for the tests.
C_LAT, C_LON = -26.719088, 27.709759


def test_circle_inside_is_safe():
    b = Boundary(shape="circle", buffer_m=15, center_lat=C_LAT, center_lon=C_LON, radius_m=200)
    res = b.evaluate(C_LAT, C_LON)  # dead centre
    assert res.state == Containment.SAFE
    assert res.distance_to_edge_m > 0


def test_circle_just_inside_edge_is_approaching():
    # ~195m north of centre, radius 200, buffer 15 -> within buffer band
    b = Boundary(shape="circle", buffer_m=15, center_lat=C_LAT, center_lon=C_LON, radius_m=200)
    lat = C_LAT + 195 / 111_320.0
    res = b.evaluate(lat, C_LON)
    assert res.state == Containment.APPROACHING


def test_circle_outside_is_breached():
    b = Boundary(shape="circle", buffer_m=15, center_lat=C_LAT, center_lon=C_LON, radius_m=100)
    lat = C_LAT + 250 / 111_320.0  # ~250m north, well outside 100m radius
    res = b.evaluate(lat, C_LON)
    assert res.state == Containment.BREACHED
    assert res.distance_to_edge_m < 0


def _square(half_m: float) -> list[tuple[float, float]]:
    """A square boundary of half-side ``half_m`` around the reference centre."""
    dlat = half_m / 111_320.0
    dlon = half_m / (111_320.0 * abs(__import__("math").cos(__import__("math").radians(C_LAT))))
    return [
        (C_LAT - dlat, C_LON - dlon),
        (C_LAT - dlat, C_LON + dlon),
        (C_LAT + dlat, C_LON + dlon),
        (C_LAT + dlat, C_LON - dlon),
    ]


def test_rectangle_inside_is_safe():
    b = Boundary(shape="rectangle", buffer_m=10, ring=_square(200))
    res = b.evaluate(C_LAT, C_LON)
    assert res.state == Containment.SAFE


def test_rectangle_near_edge_is_approaching():
    b = Boundary(shape="rectangle", buffer_m=20, ring=_square(200))
    lat = C_LAT + 190 / 111_320.0  # ~10m from the north edge
    res = b.evaluate(lat, C_LON)
    assert res.state == Containment.APPROACHING


def test_rectangle_outside_is_breached():
    b = Boundary(shape="rectangle", buffer_m=10, ring=_square(200))
    lat = C_LAT + 300 / 111_320.0  # north of the square
    res = b.evaluate(lat, C_LON)
    assert res.state == Containment.BREACHED


def test_centroid_of_square_is_center():
    b = Boundary(shape="rectangle", buffer_m=10, ring=_square(200))
    clat, clon = b.centroid()
    assert abs(clat - C_LAT) < 1e-6
    assert abs(clon - C_LON) < 1e-6
