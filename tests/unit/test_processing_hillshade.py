from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
import rasterio
import xarray as xr
from click.testing import CliRunner
from rasterio.transform import from_bounds
from shapely.geometry import Polygon

from manfredonia_map.processing import cli as proc_cli
from manfredonia_map.processing import hillshade, raster

# --- compute_hillshade pure-function tests ----------------------------

def test_compute_hillshade_shape_and_dtype():
    elevation = np.linspace(0, 100, 10 * 12).reshape(10, 12).astype(np.float32)
    hs = hillshade.compute_hillshade(elevation, cellsize_x=10.0, cellsize_y=10.0)
    assert hs.shape == elevation.shape
    assert hs.dtype == np.uint8


def test_compute_hillshade_flat_plain_is_uniform():
    elevation = np.full((20, 30), 50.0, dtype=np.float32)
    hs = hillshade.compute_hillshade(elevation, cellsize_x=10.0, cellsize_y=10.0)
    # A flat plain has slope 0 → cos(zenith)·1 + sin(zenith)·0 = cos(zenith).
    # With altitude 45°, cos(45°)*255 ≈ 180. All interior pixels should be
    # this constant (within rounding); skip the 1-pixel border that
    # numpy.gradient evaluates one-sided.
    interior = hs[1:-1, 1:-1]
    assert np.unique(interior).size == 1
    assert 175 <= int(interior[0, 0]) <= 185


def test_compute_hillshade_se_facing_slope_in_shadow():
    # Construct a surface that *rises towards the NW* — elevation
    # increases as x and y decrease (image NW corner is highest, SE
    # corner is lowest). That slope FACES the SE, so the default
    # NW sun leaves it in shadow.
    height, width = 40, 40
    yy, xx = np.indices((height, width))
    elevation = ((width - xx) + (height - yy)).astype(np.float32) * 5.0
    hs = hillshade.compute_hillshade(elevation, cellsize_x=10.0, cellsize_y=10.0)
    interior_mean = int(hs[1:-1, 1:-1].mean())
    flat_value = int(hillshade.compute_hillshade(
        np.full_like(elevation, 50.0), cellsize_x=10.0, cellsize_y=10.0,
    )[1, 1])
    assert interior_mean < flat_value


def test_compute_hillshade_nw_facing_slope_in_light():
    # Mirror: rises towards SE → faces NW → NW sun lights it brightly.
    height, width = 40, 40
    yy, xx = np.indices((height, width))
    elevation = (xx + yy).astype(np.float32) * 5.0
    hs = hillshade.compute_hillshade(elevation, cellsize_x=10.0, cellsize_y=10.0)
    interior_mean = int(hs[1:-1, 1:-1].mean())
    flat_value = int(hillshade.compute_hillshade(
        np.full_like(elevation, 50.0), cellsize_x=10.0, cellsize_y=10.0,
    )[1, 1])
    assert interior_mean > flat_value


def test_compute_hillshade_nan_pixels_zero():
    elevation = np.full((5, 5), 100.0, dtype=np.float32)
    elevation[2, 2] = np.nan
    hs = hillshade.compute_hillshade(elevation, cellsize_x=10.0, cellsize_y=10.0)
    # Center plus immediate neighbours are NaN-tainted via gradient.
    assert hs[2, 2] == 0


def test_compute_hillshade_rejects_non_positive_cellsize():
    elevation = np.zeros((5, 5), dtype=np.float32)
    with pytest.raises(ValueError, match="positive"):
        hillshade.compute_hillshade(elevation, cellsize_x=0.0, cellsize_y=10.0)
    with pytest.raises(ValueError, match="positive"):
        hillshade.compute_hillshade(elevation, cellsize_x=10.0, cellsize_y=-1.0)


# --- grayscale_to_rgba ------------------------------------------------

def test_grayscale_to_rgba_shape_and_alpha():
    gray = np.array([[0, 100, 200]], dtype=np.uint8)
    rgba = hillshade.grayscale_to_rgba(gray)
    assert rgba.shape == (1, 3, 4)
    # First pixel (value=0) is masked → alpha 0; the rest get full alpha.
    assert rgba[0, 0, 3] == 0
    assert rgba[0, 1, 3] == 255
    assert rgba[0, 2, 3] == 255
    # R == G == B == gray value.
    assert tuple(rgba[0, 1, :3]) == (100, 100, 100)


# --- _coerce_xarray ---------------------------------------------------

def test_coerce_xarray_passes_ndarray_through():
    arr = np.zeros((3, 3))
    assert hillshade._coerce_xarray(arr) is arr


def test_coerce_xarray_unwraps_dataarray():
    da = xr.DataArray(np.ones((2, 2)))
    out = hillshade._coerce_xarray(da)
    assert isinstance(out, np.ndarray)
    assert out.shape == (2, 2)


# --- end-to-end via the synthetic raster helper ----------------------

def _write_synthetic_geotiff(path: Path) -> None:
    width, height = 100, 80
    west, south, east, north = 1_065_000, 4_605_000, 1_080_000, 4_640_000
    transform = from_bounds(west, south, east, north, width, height)
    yy, xx = np.indices((height, width))
    arr = (-20 + (xx / max(width - 1, 1)) * 400
           + (yy / max(height - 1, 1)) * 420).astype(np.float32)
    with rasterio.open(
        path, "w", driver="GTiff", height=height, width=width,
        count=1, dtype="float32", crs="EPSG:32632", transform=transform,
        nodata=-9999,
    ) as ds:
        ds.write(arr, 1)


def _aoi_for_synthetic() -> Polygon:
    return Polygon([
        (15.81, 41.55), (15.95, 41.55), (15.95, 41.70), (15.81, 41.70),
        (15.81, 41.55),
    ])


def test_process_hillshade_writes_cog(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    raw = tmp_path / "in.tif"
    _write_synthetic_geotiff(raw)
    monkeypatch.setitem(
        raster.PROCESSORS, "fake",
        raster.RasterProcessorSpec(
            raster_id="fake", raw_path=raw, source_id="syn",
            year_data=2024, value_min=-50.0, value_max=850.0,
        ),
    )

    out = hillshade.process_hillshade(
        "fake", _aoi_for_synthetic(), processed_dir=tmp_path / "processed",
    )
    assert out == tmp_path / "processed" / "fake_hillshade_8bit.tif"
    with rasterio.open(out) as ds:
        assert ds.count == 4
        assert ds.dtypes == ("uint8", "uint8", "uint8", "uint8")
        assert ds.crs.to_epsg() == 32633


def test_process_hillshade_rejects_unknown_id(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(raster, "PROCESSORS", {})
    with pytest.raises(KeyError, match="unknown raster_id"):
        hillshade.process_hillshade("nope", aoi=_aoi_for_synthetic())


# --- CLI -------------------------------------------------------------

def _write_aoi_file(tmp_path: Path) -> Path:
    p = tmp_path / "aoi.geojson"
    p.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "crs": {"type": "name", "properties": {"name": "EPSG:4326"}},
                "features": [
                    {
                        "type": "Feature",
                        "properties": {},
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [
                                [
                                    [15.81, 41.55], [15.95, 41.55],
                                    [15.95, 41.70], [15.81, 41.70],
                                    [15.81, 41.55],
                                ]
                            ],
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return p


def test_cli_hillshade_runs_end_to_end(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    raw = tmp_path / "in.tif"
    _write_synthetic_geotiff(raw)
    monkeypatch.setitem(
        raster.PROCESSORS, "fake",
        raster.RasterProcessorSpec(
            raster_id="fake", raw_path=raw, source_id="syn",
            year_data=2024, value_min=-50.0, value_max=850.0,
        ),
    )
    aoi = _write_aoi_file(tmp_path)
    out_dir = tmp_path / "processed"
    result = CliRunner().invoke(
        proc_cli.process_hillshade_cmd,
        ["fake", "--aoi", str(aoi), "--processed-dir", str(out_dir)],
    )
    assert result.exit_code == 0, result.output
    assert (out_dir / "fake_hillshade_8bit.tif").exists()


def test_cli_hillshade_unknown_raster_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(raster, "PROCESSORS", {})
    aoi = _write_aoi_file(tmp_path)
    result = CliRunner().invoke(
        proc_cli.process_hillshade_cmd,
        ["nope", "--aoi", str(aoi), "--processed-dir", str(tmp_path / "processed")],
    )
    assert result.exit_code != 0
    assert "unknown raster_id" in result.output
