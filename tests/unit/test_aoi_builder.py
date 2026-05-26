from __future__ import annotations

import pytest
from shapely.geometry import LineString, Point, Polygon

from manfredonia_map.aoi import builder


def test_buffered_aoi_grows_in_every_direction():
    src = Polygon([(15.90, 41.60), (15.91, 41.60), (15.91, 41.61), (15.90, 41.61), (15.90, 41.60)])
    out = builder.build_buffered_aoi(src, "EPSG:4326", buffer_m=1000.0)
    src_b, out_b = src.bounds, out.bounds
    assert out_b[0] < src_b[0]
    assert out_b[1] < src_b[1]
    assert out_b[2] > src_b[2]
    assert out_b[3] > src_b[3]
    assert out.contains(src)


def test_buffered_aoi_is_deterministic():
    src = Polygon([(15.90, 41.60), (15.91, 41.60), (15.91, 41.61), (15.90, 41.61)])
    a = builder.build_buffered_aoi(src, "EPSG:4326", buffer_m=1000.0)
    b = builder.build_buffered_aoi(src, "EPSG:4326", buffer_m=1000.0)
    assert a.equals_exact(b, tolerance=0.0)


def test_coastal_band_returns_none_when_no_coastline():
    assert builder.build_coastal_band(None, None, band_m=2000.0) is None


def test_coastal_band_raises_when_crs_missing():
    with pytest.raises(ValueError, match="coastline_crs"):
        builder.build_coastal_band(LineString([(0, 0), (1, 1)]), None, band_m=100.0)


def test_coastal_band_buffers_a_line():
    coast = LineString([(15.90, 41.60), (15.95, 41.65)])
    band = builder.build_coastal_band(coast, "EPSG:4326", band_m=2000.0)
    assert band is not None
    assert band.area > 0


def test_near_coast_falls_back_to_buffered_when_no_inclusions():
    src = Polygon([(15.90, 41.60), (15.91, 41.60), (15.91, 41.61), (15.90, 41.61)])
    out = builder.build_near_coast_aoi(src, coastal_band=None, mandatory_features=[])
    assert out.equals(src)


def test_near_coast_intersects_coastal_band():
    src = Polygon([(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)])
    band = Polygon([(2, 2), (8, 2), (8, 8), (2, 8), (2, 2)])
    out = builder.build_near_coast_aoi(src, coastal_band=band, mandatory_features=[])
    assert out.equals(band)


def test_near_coast_unions_mandatory_with_band_inside_buffered():
    src = Polygon([(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)])
    band = Polygon([(2, 2), (4, 2), (4, 4), (2, 4), (2, 2)])
    mandatory = [Polygon([(6, 6), (9, 6), (9, 9), (6, 9), (6, 6)])]
    out = builder.build_near_coast_aoi(src, coastal_band=band, mandatory_features=mandatory)
    assert out.contains(Point(3, 3))
    assert out.contains(Point(7, 7))
    assert not out.contains(Point(5, 5))


def test_near_coast_mandatory_extends_beyond_buffered():
    # Mandatory features sit (partly) outside the buffered AOI; the new
    # semantics is that they extend it rather than being clipped away —
    # the user explicitly wants those features on the map.
    src = Polygon([(0, 0), (5, 0), (5, 5), (0, 5), (0, 0)])
    mandatory = [Polygon([(3, 3), (10, 3), (10, 10), (3, 10), (3, 3)])]
    out = builder.build_near_coast_aoi(src, coastal_band=None, mandatory_features=mandatory)
    assert out.contains(Point(4, 4))  # inside src
    assert out.contains(Point(8, 8))  # outside src but inside mandatory → included
    assert out.contains(Point(0.5, 0.5))  # original src corner still included


def test_near_coast_mandatory_included_even_when_band_intersects_to_empty():
    # Band intersects to nothing inside src, but mandatory still wins.
    src = Polygon([(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)])
    band = Polygon([(10, 10), (11, 10), (11, 11), (10, 11), (10, 10)])
    mandatory = [Polygon([(20, 20), (21, 20), (21, 21), (20, 21), (20, 20)])]
    out = builder.build_near_coast_aoi(src, coastal_band=band, mandatory_features=mandatory)
    assert out.contains(Point(20.5, 20.5))
    assert not out.contains(Point(10.5, 10.5))  # band missed → not included
    assert not out.contains(Point(0.5, 0.5))  # src not in band → dropped


def test_near_coast_ignores_empty_geometries():
    src = Polygon([(0, 0), (5, 0), (5, 5), (0, 5)])
    empty = Polygon()
    out = builder.build_near_coast_aoi(src, coastal_band=empty, mandatory_features=[empty])
    # Both inclusions empty → falls back to buffered.
    assert out.equals(src)
