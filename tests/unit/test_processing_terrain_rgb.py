"""Unit tests for ``manfredonia_map.processing.terrain_rgb``.

The encoder is the hot path Mapbox itself relies on; we cover the
forward formula, the round-trip (encode → decode), NaN handling, and
clamping so refactors can't quietly shift the encoding.
"""

from __future__ import annotations

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

from manfredonia_map.processing import cli as proc_cli
from manfredonia_map.processing import terrain_rgb

# --- helpers ---------------------------------------------------------


def _write_float_geotiff(
    path,
    *,
    arr: np.ndarray,
    crs: str = "EPSG:4326",
    west: float = 15.79,
    south: float = 41.48,
    east: float = 16.06,
    north: float = 41.70,
) -> None:
    height, width = arr.shape
    transform = from_bounds(west, south, east, north, width, height)
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
        nodata=np.float32(np.nan),
    ) as ds:
        ds.write(arr.astype(np.float32), 1)


# --- encode_terrain_rgb ----------------------------------------------


class TestEncodeTerrainRgb:
    def test_zero_metres_encodes_to_the_anchor_value(self) -> None:
        # 0 m → (-10000 + n*0.1) = 0 → n = 100_000 = 0x0186A0 → R=1, G=134, B=160
        rgb = terrain_rgb.encode_terrain_rgb(np.array([[0.0]]))
        assert rgb.shape == (3, 1, 1)
        assert rgb[0, 0, 0] == 1
        assert rgb[1, 0, 0] == 134
        assert rgb[2, 0, 0] == 160

    def test_round_trip_recovers_input(self) -> None:
        elev = np.array([[-100.0, -10.0, 0.0, 50.0, 250.0, 840.0]], dtype=np.float64)
        decoded = terrain_rgb.decode_terrain_rgb(terrain_rgb.encode_terrain_rgb(elev))
        np.testing.assert_allclose(decoded, elev, atol=0.05)

    def test_round_trip_handles_deep_bathymetry(self) -> None:
        # EMODnet AOI hits ~-16 m; cover deeper for good measure.
        elev = np.array([[-9000.0, -500.0, -16.0]], dtype=np.float64)
        decoded = terrain_rgb.decode_terrain_rgb(terrain_rgb.encode_terrain_rgb(elev))
        np.testing.assert_allclose(decoded, elev, atol=0.05)

    def test_nan_pixels_get_the_spec_nodata_triplet(self) -> None:
        elev = np.array([[np.nan, 100.0]])
        rgb = terrain_rgb.encode_terrain_rgb(elev)
        assert (rgb[0, 0, 0], rgb[1, 0, 0], rgb[2, 0, 0]) == (1, 134, 160)
        # The non-NaN cell is encoded normally.
        assert (rgb[0, 0, 1], rgb[1, 0, 1], rgb[2, 0, 1]) != (1, 134, 160)

    def test_out_of_range_inputs_clamp_safely(self) -> None:
        # Elevations beyond ±10 km clamp to the valid 24-bit window
        # rather than wrapping into garbage pixels.
        elev = np.array([[-1e9, 1e9]])
        rgb = terrain_rgb.encode_terrain_rgb(elev)
        # Underflow → (0, 0, 0); overflow → (255, 255, 255)
        assert tuple(rgb[:, 0, 0].tolist()) == (0, 0, 0)
        assert tuple(rgb[:, 0, 1].tolist()) == (255, 255, 255)

    def test_int_input_is_promoted_to_float(self) -> None:
        elev = np.array([[100]], dtype=np.int32)
        rgb = terrain_rgb.encode_terrain_rgb(elev)
        decoded = terrain_rgb.decode_terrain_rgb(rgb)
        assert decoded[0, 0] == pytest.approx(100.0, abs=0.05)

    def test_input_array_is_not_mutated(self) -> None:
        elev = np.array([[42.5]], dtype=np.float64)
        before = elev.copy()
        terrain_rgb.encode_terrain_rgb(elev)
        np.testing.assert_array_equal(elev, before)


# --- merge_dtm_bathy --------------------------------------------------


class TestMergeDtmBathy:
    def _aoi(self) -> Polygon:
        return Polygon(
            [
                (15.80, 41.50),
                (16.05, 41.50),
                (16.05, 41.69),
                (15.80, 41.69),
                (15.80, 41.50),
            ]
        )

    def _open(self, path, **kw):
        import rioxarray as rxr  # noqa: PLC0415

        return rxr.open_rasterio(path, masked=True, **kw)

    def test_dtm_takes_precedence_on_overlap(self, tmp_path) -> None:
        # DTM has values, bathy would otherwise paint over them.
        dtm_arr = np.full((10, 10), 500.0, dtype=np.float32)
        bathy_arr = np.full((10, 10), -50.0, dtype=np.float32)
        dtm_path = tmp_path / "dtm.tif"
        bathy_path = tmp_path / "bathy.tif"
        _write_float_geotiff(dtm_path, arr=dtm_arr)
        _write_float_geotiff(bathy_path, arr=bathy_arr)

        dtm = self._open(dtm_path)
        bathy = self._open(bathy_path)
        merged = terrain_rgb.merge_dtm_bathy(dtm, bathy, aoi=self._aoi())
        # DTM was finite everywhere — every pixel should carry its value.
        assert np.nanmin(merged.values) == pytest.approx(500.0, rel=0.05)

    def test_bathymetry_fills_dtm_nans(self, tmp_path) -> None:
        # Half NaN DTM (sea) + bathymetry of -30 m. The NaN half should
        # come from bathy after the merge.
        dtm_arr = np.full((10, 10), np.nan, dtype=np.float32)
        dtm_arr[:, :5] = 200.0  # land on the left, sea on the right
        bathy_arr = np.full((10, 10), -30.0, dtype=np.float32)
        dtm_path = tmp_path / "dtm.tif"
        bathy_path = tmp_path / "bathy.tif"
        _write_float_geotiff(dtm_path, arr=dtm_arr)
        _write_float_geotiff(bathy_path, arr=bathy_arr)

        merged = terrain_rgb.merge_dtm_bathy(
            self._open(dtm_path), self._open(bathy_path), aoi=self._aoi()
        )
        # We can't assume the exact resampling preserves the half-and-half
        # split, but the merged raster should contain both land + sea values.
        vals = merged.values
        finite = vals[np.isfinite(vals)]
        assert finite.min() < 0  # bathymetry is present
        assert finite.max() > 100  # land is present


# --- _open helpers ----------------------------------------------------


def _make_dtm_zip(tmp_path: Path, *, inner_name: str = "tile/tile.tif") -> Path:
    """Build a zip with one float32 GeoTIFF inside (no DTM data, just shape)."""
    arr = np.full((6, 6), 250.0, dtype=np.float32)
    raw_tif = tmp_path / "raw.tif"
    _write_float_geotiff(raw_tif, arr=arr)
    zip_path = tmp_path / "tile.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.write(raw_tif, arcname=inner_name)
    raw_tif.unlink()
    return zip_path


class TestOpenHelpers:
    def test_open_dtm_reads_from_zip(self, tmp_path: Path) -> None:
        zip_path = _make_dtm_zip(tmp_path, inner_name="x/y.tif")
        spec = terrain_rgb.TerrainRgbSpec(
            dtm_zip=zip_path,
            dtm_inner_filename="x/y.tif",
            bathy_dir=tmp_path,  # unused
            out_path=tmp_path / "out.tif",
        )
        da = terrain_rgb._open_dtm(spec)
        assert da.rio.crs is not None
        assert da.shape[-1] == 6

    def test_open_dtm_raises_when_inner_filename_is_wrong(self, tmp_path: Path) -> None:
        zip_path = _make_dtm_zip(tmp_path, inner_name="real/inner.tif")
        spec = terrain_rgb.TerrainRgbSpec(
            dtm_zip=zip_path,
            dtm_inner_filename="bogus.tif",
            bathy_dir=tmp_path,
            out_path=tmp_path / "out.tif",
        )
        with pytest.raises(FileNotFoundError):
            terrain_rgb._open_dtm(spec)

    def test_open_bathy_picks_the_tif_in_the_dir(self, tmp_path: Path) -> None:
        bathy_dir = tmp_path / "bathy"
        bathy_dir.mkdir()
        _write_float_geotiff(
            bathy_dir / "emodnet.tif",
            arr=np.full((5, 5), -10.0, dtype=np.float32),
        )
        spec = terrain_rgb.TerrainRgbSpec(
            dtm_zip=tmp_path / "dtm.zip",
            dtm_inner_filename="x.tif",
            bathy_dir=bathy_dir,
            out_path=tmp_path / "out.tif",
        )
        da = terrain_rgb._open_bathy(spec)
        assert da.rio.crs is not None

    def test_open_bathy_raises_when_dir_is_empty(self, tmp_path: Path) -> None:
        empty = tmp_path / "empty"
        empty.mkdir()
        spec = terrain_rgb.TerrainRgbSpec(
            dtm_zip=tmp_path / "dtm.zip",
            dtm_inner_filename="x.tif",
            bathy_dir=empty,
            out_path=tmp_path / "out.tif",
        )
        with pytest.raises(FileNotFoundError):
            terrain_rgb._open_bathy(spec)


# --- write_cog --------------------------------------------------------


class TestWriteCog:
    def test_write_cog_emits_a_three_band_raster(self, tmp_path: Path) -> None:
        # Build a small 3-band uint8 DataArray that mimics encode_terrain_rgb's output.
        rgb = np.zeros((3, 8, 8), dtype=np.uint8)
        rgb[0] = 1
        rgb[1] = 134
        rgb[2] = 160
        transform = from_bounds(15.79, 41.48, 16.06, 41.70, 8, 8)
        y_coords = np.linspace(41.70, 41.48, 8)
        x_coords = np.linspace(15.79, 16.06, 8)
        da = xr.DataArray(
            rgb,
            dims=("band", "y", "x"),
            coords={"band": [1, 2, 3], "y": y_coords, "x": x_coords},
        )
        da.rio.write_crs("EPSG:4326", inplace=True)
        da.rio.write_transform(transform, inplace=True)

        out = tmp_path / "terrain.tif"
        terrain_rgb.write_cog(da, out)

        assert out.exists()
        with rasterio.open(out) as ds:
            assert ds.count == 3
            assert ds.dtypes[0] == "uint8"


# --- build_terrain_rgb (end-to-end smoke) ----------------------------


class TestBuildTerrainRgbSmoke:
    def test_end_to_end_writes_a_cog(self, tmp_path: Path) -> None:
        # Tiny DTM zip with land + NaN sea, and a bathy GeoTIFF below.
        dtm_arr = np.full((10, 10), np.nan, dtype=np.float32)
        dtm_arr[:, :5] = 200.0
        raw_tif = tmp_path / "raw.tif"
        _write_float_geotiff(raw_tif, arr=dtm_arr)
        zip_path = tmp_path / "tile.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.write(raw_tif, arcname="t/t.tif")
        raw_tif.unlink()

        bathy_dir = tmp_path / "bathy"
        bathy_dir.mkdir()
        _write_float_geotiff(
            bathy_dir / "b.tif",
            arr=np.full((10, 10), -30.0, dtype=np.float32),
        )

        out_path = tmp_path / "out.tif"
        spec = terrain_rgb.TerrainRgbSpec(
            dtm_zip=zip_path,
            dtm_inner_filename="t/t.tif",
            bathy_dir=bathy_dir,
            out_path=out_path,
            exaggeration=1.0,
        )
        aoi = Polygon(
            [
                (15.80, 41.50),
                (16.05, 41.50),
                (16.05, 41.69),
                (15.80, 41.69),
                (15.80, 41.50),
            ]
        )
        result = terrain_rgb.build_terrain_rgb(spec, aoi=aoi)
        assert result == out_path
        assert out_path.exists()
        with rasterio.open(out_path) as ds:
            assert ds.count == 3
            assert ds.dtypes[0] == "uint8"

    def test_exaggeration_scales_encoded_elevations(self, tmp_path: Path) -> None:
        # Same setup, only the exaggeration changes: the encoded
        # elevations should differ.
        dtm_arr = np.full((6, 6), 100.0, dtype=np.float32)
        raw_tif = tmp_path / "raw.tif"
        _write_float_geotiff(raw_tif, arr=dtm_arr)
        zip_path = tmp_path / "tile.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.write(raw_tif, arcname="t/t.tif")
        raw_tif.unlink()
        bathy_dir = tmp_path / "bathy"
        bathy_dir.mkdir()
        _write_float_geotiff(bathy_dir / "b.tif", arr=np.full((6, 6), -10.0, dtype=np.float32))

        aoi = Polygon(
            [(15.80, 41.50), (16.05, 41.50), (16.05, 41.69), (15.80, 41.69), (15.80, 41.50)]
        )

        def _build(exag: float, name: str) -> Path:
            spec = terrain_rgb.TerrainRgbSpec(
                dtm_zip=zip_path,
                dtm_inner_filename="t/t.tif",
                bathy_dir=bathy_dir,
                out_path=tmp_path / name,
                exaggeration=exag,
            )
            return terrain_rgb.build_terrain_rgb(spec, aoi=aoi)

        flat = _build(1.0, "flat.tif")
        tall = _build(2.0, "tall.tif")
        with rasterio.open(flat) as a, rasterio.open(tall) as b:
            # The encoded elevation for 100 m doubles to 200 m under 2x
            # exaggeration, so at least one byte must differ.
            assert a.read() != pytest.approx(b.read())  # type: ignore[comparison-overlap]


# --- CLI --------------------------------------------------------------


class TestTerrainRgbCli:
    def test_command_is_registered_under_process(self) -> None:
        runner = CliRunner()
        result = runner.invoke(proc_cli.process, ["--help"])
        assert result.exit_code == 0
        assert "terrain-rgb" in result.output

    def test_command_help_advertises_aoi_and_out_options(self) -> None:
        runner = CliRunner()
        result = runner.invoke(proc_cli.process, ["terrain-rgb", "--help"])
        assert result.exit_code == 0
        assert "--aoi" in result.output
        assert "--out" in result.output
        assert "--exaggeration" in result.output
