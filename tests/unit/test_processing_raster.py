from __future__ import annotations

import json
import zipfile
from pathlib import Path

import numpy as np
import pytest
import rasterio
import rioxarray  # noqa: F401  # registers .rio accessor
import xarray as xr
from click.testing import CliRunner
from rasterio.transform import from_bounds
from shapely.geometry import Polygon

from manfredonia_map.processing import base, raster
from manfredonia_map.processing import cli as proc_cli

# --- synthetic-raster helpers ----------------------------------------


def _write_synthetic_geotiff(
    path: Path,
    *,
    crs: str = "EPSG:32632",
    width: int = 100,
    height: int = 80,
    west: float = 1_065_000,
    south: float = 4_605_000,
    east: float = 1_080_000,
    north: float = 4_640_000,
) -> None:
    """Write a small synthetic float32 GeoTIFF with a linear ramp."""
    transform = from_bounds(west, south, east, north, width, height)
    # Linear ramp from -20 (top-left) to +800 (bottom-right) so the
    # hypsometric tint exercises both sea and land stops.
    yy, xx = np.indices((height, width))
    arr = (-20 + (xx / max(width - 1, 1)) * 400 + (yy / max(height - 1, 1)) * 420).astype(
        np.float32
    )
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=height,
        width=width,
        count=1,
        dtype="float32",
        crs=crs,
        transform=transform,
        nodata=-9999,
    ) as ds:
        ds.write(arr, 1)


def _aoi_for_synthetic() -> Polygon:
    """AOI in EPSG:4326 that intersects the synthetic raster."""
    return Polygon(
        [
            (15.81, 41.55),
            (15.95, 41.55),
            (15.95, 41.70),
            (15.81, 41.70),
            (15.81, 41.55),
        ]
    )


# --- hypsometric_tint -----------------------------------------------


def test_hypsometric_tint_shapes_and_dtype():
    arr = np.linspace(-50, 850, 200).reshape(10, 20).astype(np.float32)
    rgba = raster.hypsometric_tint(arr, value_min=-50.0, value_max=850.0)
    assert rgba.shape == (10, 20, 4)
    assert rgba.dtype == np.uint8


def test_hypsometric_tint_alpha_zero_on_nan():
    arr = np.array([[0.0, np.nan], [100.0, 200.0]], dtype=np.float32)
    rgba = raster.hypsometric_tint(arr, value_min=-50.0, value_max=850.0)
    assert rgba[0, 1, 3] == 0
    assert rgba[0, 0, 3] == 255
    assert rgba[1, 1, 3] == 255


def test_hypsometric_tint_clamps_outside_range():
    arr = np.array([[-1000.0, 1e6]], dtype=np.float32)
    rgba = raster.hypsometric_tint(arr, value_min=-50.0, value_max=850.0)
    # Below range → first stop (deep sea blue family)
    assert tuple(rgba[0, 0, :3]) == raster.TERRAIN_STOPS[0][1]
    # Above range → last stop (white summit)
    assert tuple(rgba[0, 1, :3]) == raster.TERRAIN_STOPS[-1][1]


def test_hypsometric_tint_returns_zeros_when_range_is_zero():
    arr = np.full((2, 2), 5.0, dtype=np.float32)
    rgba = raster.hypsometric_tint(arr, value_min=5.0, value_max=5.0)
    # Degenerate range -> all pixels map to the first stop colour.
    assert tuple(rgba[0, 0, :3]) == raster.TERRAIN_STOPS[0][1]
    assert rgba[..., 3].min() == 255


# --- read_raster ----------------------------------------------------


def test_read_raster_loose_geotiff(tmp_path: Path):
    p = tmp_path / "in.tif"
    _write_synthetic_geotiff(p)
    spec = raster.RasterProcessorSpec(
        raster_id="x",
        raw_path=p,
        source_id="x",
        year_data=2024,
    )
    da = raster.read_raster(spec)
    assert da.rio.crs.to_epsg() == 32632
    assert da.shape[-2:] == (80, 100)


def test_read_raster_inside_zip(tmp_path: Path):
    inner_tif = tmp_path / "inner.tif"
    _write_synthetic_geotiff(inner_tif)
    z = tmp_path / "bundle.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.write(inner_tif, arcname="tile/inner.tif")
    spec = raster.RasterProcessorSpec(
        raster_id="x",
        raw_path=z,
        inner_zip_filename="tile/inner.tif",
        source_id="x",
        year_data=2024,
    )
    da = raster.read_raster(spec)
    assert da.rio.crs.to_epsg() == 32632


def test_read_raster_zip_missing_inner_raises(tmp_path: Path):
    z = tmp_path / "bundle.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("readme.txt", "no tif here")
    spec = raster.RasterProcessorSpec(
        raster_id="x",
        raw_path=z,
        inner_zip_filename="nope.tif",
        source_id="x",
        year_data=2024,
    )
    with pytest.raises(FileNotFoundError, match=r"nope\.tif"):
        raster.read_raster(spec)


def test_read_raster_directory_picks_the_single_geotiff(tmp_path: Path):
    d = tmp_path / "emodnet"
    d.mkdir()
    _write_synthetic_geotiff(d / "only.tif")
    spec = raster.RasterProcessorSpec(
        raster_id="x",
        raw_path=d,
        source_id="x",
        year_data=2024,
    )
    da = raster.read_raster(spec)
    assert da.rio.crs.to_epsg() == 32632


def test_read_raster_directory_rejects_multiple_geotiffs(tmp_path: Path):
    d = tmp_path / "emodnet"
    d.mkdir()
    _write_synthetic_geotiff(d / "a.tif")
    _write_synthetic_geotiff(d / "b.tif")
    spec = raster.RasterProcessorSpec(
        raster_id="x",
        raw_path=d,
        source_id="x",
        year_data=2024,
    )
    with pytest.raises(ValueError, match="exactly one GeoTIFF"):
        raster.read_raster(spec)


def test_read_raster_directory_raises_when_empty(tmp_path: Path):
    d = tmp_path / "emodnet"
    d.mkdir()
    spec = raster.RasterProcessorSpec(
        raster_id="x",
        raw_path=d,
        source_id="x",
        year_data=2024,
    )
    with pytest.raises(FileNotFoundError, match="no GeoTIFF"):
        raster.read_raster(spec)


# --- reproject_and_clip --------------------------------------------


def test_reproject_and_clip_to_aoi_reduces_extent(tmp_path: Path):
    p = tmp_path / "in.tif"
    _write_synthetic_geotiff(p)
    spec = raster.RasterProcessorSpec(
        raster_id="x",
        raw_path=p,
        source_id="x",
        year_data=2024,
    )
    da = raster.read_raster(spec)
    clipped = raster.reproject_and_clip(
        da,
        dst_crs=base.ANALYSIS_CRS,
        aoi=_aoi_for_synthetic(),
    )
    assert clipped.rio.crs.to_epsg() == 32633
    assert clipped.shape[-2] > 0
    assert clipped.shape[-1] > 0


# --- end-to-end ----------------------------------------------------


def test_process_raster_writes_zarr_and_cog(tmp_path: Path):
    raw = tmp_path / "in.tif"
    _write_synthetic_geotiff(raw)
    interim = tmp_path / "interim"
    processed = tmp_path / "processed"
    spec = raster.RasterProcessorSpec(
        raster_id="synthetic",
        raw_path=raw,
        source_id="syn",
        year_data=2024,
        value_min=-50.0,
        value_max=850.0,
    )

    zarr_path, cog_path = raster.process_raster(
        spec,
        aoi=_aoi_for_synthetic(),
        interim_dir=interim,
        processed_dir=processed,
    )

    assert zarr_path == interim / "synthetic.zarr"
    assert zarr_path.is_dir()  # Zarr stores are directories.
    # Round-trip the Zarr. We explicitly write without consolidated
    # metadata (see ``write_zarr``), so pass ``consolidated=False`` here
    # to suppress xarray's fallback warning. CRS does not always survive
    # the Zarr round-trip via rioxarray attributes — that is acceptable
    # for the analytical interim store; the published COG carries the
    # authoritative CRS.
    ds = xr.open_zarr(zarr_path, consolidated=False)
    assert "elevation" in ds
    assert ds["elevation"].shape[-1] > 0

    assert cog_path == processed / "synthetic_8bit.tif"
    assert cog_path.exists()
    with rasterio.open(cog_path) as ds:
        assert ds.count == 4
        assert ds.dtypes == ("uint8", "uint8", "uint8", "uint8")
        assert ds.crs.to_epsg() == 32633
        # Small synthetic raster (80x100) → COG driver decides no
        # overviews are needed; real rasters get them. Just check the
        # file is readable and the geometry is sound.
        assert ds.width > 0
        assert ds.height > 0


def test_process_raster_idempotent_on_zarr_replace(tmp_path: Path):
    raw = tmp_path / "in.tif"
    _write_synthetic_geotiff(raw)
    interim = tmp_path / "interim"
    processed = tmp_path / "processed"
    spec = raster.RasterProcessorSpec(
        raster_id="synthetic",
        raw_path=raw,
        source_id="syn",
        year_data=2024,
        value_min=-50.0,
        value_max=850.0,
    )
    raster.process_raster(
        spec,
        aoi=_aoi_for_synthetic(),
        interim_dir=interim,
        processed_dir=processed,
    )
    # Second run must not error on the pre-existing Zarr store.
    raster.process_raster(
        spec,
        aoi=_aoi_for_synthetic(),
        interim_dir=interim,
        processed_dir=processed,
    )


# --- registry -------------------------------------------------------


def test_processors_registry_has_expected_ids():
    assert {"tinitaly_dtm", "emodnet_bathymetry"} <= set(raster.PROCESSORS)
    for rid, spec in raster.PROCESSORS.items():
        assert spec.raster_id == rid


# --- CLI ------------------------------------------------------------


def _seed_synthetic_aoi(tmp_path: Path) -> Path:
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
                                    [15.81, 41.55],
                                    [15.95, 41.55],
                                    [15.95, 41.70],
                                    [15.81, 41.70],
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


def _seed_synthetic_registry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    raw = tmp_path / "in.tif"
    _write_synthetic_geotiff(raw)
    fake_spec = raster.RasterProcessorSpec(
        raster_id="fake",
        raw_path=raw,
        source_id="syn",
        year_data=2024,
        value_min=-50.0,
        value_max=850.0,
    )
    monkeypatch.setitem(raster.PROCESSORS, "fake", fake_spec)
    return raw, _seed_synthetic_aoi(tmp_path)


def test_cli_process_raster_dispatches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _, aoi = _seed_synthetic_registry(tmp_path, monkeypatch)
    result = CliRunner().invoke(
        proc_cli.process_raster_cmd,
        [
            "fake",
            "--aoi",
            str(aoi),
            "--interim-dir",
            str(tmp_path / "interim"),
            "--processed-dir",
            str(tmp_path / "processed"),
        ],
    )
    assert result.exit_code == 0, result.output
    assert (tmp_path / "interim" / "fake.zarr").is_dir()
    assert (tmp_path / "processed" / "fake_8bit.tif").exists()


def test_cli_process_raster_unknown_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(raster, "PROCESSORS", {})
    aoi = _seed_synthetic_aoi(tmp_path)
    result = CliRunner().invoke(
        proc_cli.process_raster_cmd,
        [
            "nope",
            "--aoi",
            str(aoi),
            "--interim-dir",
            str(tmp_path / "interim"),
            "--processed-dir",
            str(tmp_path / "processed"),
        ],
    )
    assert result.exit_code != 0
    assert "unknown raster_id" in result.output


def test_cli_rasters_all_skips_listed_ids(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    raw_a = tmp_path / "a.tif"
    raw_b = tmp_path / "b.tif"
    _write_synthetic_geotiff(raw_a)
    _write_synthetic_geotiff(raw_b)
    monkeypatch.setattr(
        raster,
        "PROCESSORS",
        {
            "a": raster.RasterProcessorSpec(
                raster_id="a",
                raw_path=raw_a,
                source_id="s",
                year_data=2024,
                value_min=-50.0,
                value_max=850.0,
            ),
            "b": raster.RasterProcessorSpec(
                raster_id="b",
                raw_path=raw_b,
                source_id="s",
                year_data=2024,
                value_min=-50.0,
                value_max=850.0,
            ),
        },
    )
    aoi = _seed_synthetic_aoi(tmp_path)
    result = CliRunner().invoke(
        proc_cli.process_rasters_all,
        [
            "--aoi",
            str(aoi),
            "--interim-dir",
            str(tmp_path / "interim"),
            "--processed-dir",
            str(tmp_path / "processed"),
            "--skip",
            "b",
        ],
    )
    assert result.exit_code == 0, result.output
    assert (tmp_path / "processed" / "a_8bit.tif").exists()
    assert not (tmp_path / "processed" / "b_8bit.tif").exists()


def test_cli_rasters_all_collects_failures(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    raw_good = tmp_path / "good.tif"
    _write_synthetic_geotiff(raw_good)
    monkeypatch.setattr(
        raster,
        "PROCESSORS",
        {
            "good": raster.RasterProcessorSpec(
                raster_id="good",
                raw_path=raw_good,
                source_id="s",
                year_data=2024,
                value_min=-50.0,
                value_max=850.0,
            ),
            "bad": raster.RasterProcessorSpec(
                raster_id="bad",
                raw_path=tmp_path / "missing.tif",
                source_id="s",
                year_data=2024,
            ),
        },
    )
    aoi = _seed_synthetic_aoi(tmp_path)
    result = CliRunner().invoke(
        proc_cli.process_rasters_all,
        [
            "--aoi",
            str(aoi),
            "--interim-dir",
            str(tmp_path / "interim"),
            "--processed-dir",
            str(tmp_path / "processed"),
        ],
    )
    assert result.exit_code != 0
    assert "bad" in result.output
    assert (tmp_path / "processed" / "good_8bit.tif").exists()
