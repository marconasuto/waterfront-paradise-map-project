from __future__ import annotations

from shapely.geometry import Polygon

from manfredonia_map.aoi import sanity


def test_sanity_check_point_returns_shapely_point():
    c = sanity.SanityCheck("x", lon=15.9, lat=41.6)
    p = c.point()
    assert (p.x, p.y) == (15.9, 41.6)


def test_default_checks_all_inside_a_large_box():
    box = Polygon([(15.0, 41.0), (16.5, 41.0), (16.5, 42.0), (15.0, 42.0), (15.0, 41.0)])
    results = sanity.run_checks(box)
    assert results == {c.name: True for c in sanity.DEFAULT_CHECKS}


def test_default_checks_all_outside_a_unit_square_in_atlantic():
    box = Polygon([(-10, -10), (-9, -10), (-9, -9), (-10, -9), (-10, -10)])
    results = sanity.run_checks(box)
    assert all(value is False for value in results.values())


def test_custom_checks_are_respected():
    box = Polygon([(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)])
    custom = (
        sanity.SanityCheck("inside_origin", lon=0.5, lat=0.5),
        sanity.SanityCheck("outside_far", lon=10.0, lat=10.0),
    )
    out = sanity.run_checks(box, checks=custom)
    assert out == {"inside_origin": True, "outside_far": False}
