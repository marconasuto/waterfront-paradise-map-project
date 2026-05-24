from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
import respx
from click.testing import CliRunner

from manfredonia_map.acquisition import cli as acq_cli
from manfredonia_map.acquisition import emodnet


def test_emodnet_spec_url_contains_expected_params():
    bbox = (15.80, 41.49, 16.05, 41.69)
    spec = emodnet.EmodnetBathymetrySpec(bbox=bbox)
    parsed = urlparse(spec.url)
    assert parsed.netloc == "ows.emodnet-bathymetry.eu"
    params = {k: v[0] for k, v in parse_qs(parsed.query).items()}
    assert params["service"] == "wcs"
    assert params["version"] == "1.0.0"
    assert params["request"] == "getcoverage"
    assert params["coverage"] == "emodnet:mean"
    assert params["crs"] == "EPSG:4326"
    assert params["bbox"] == "15.8,41.49,16.05,41.69"
    assert params["format"] == "image/tiff"
    assert float(params["resx"]) == pytest.approx(emodnet.NATIVE_RES_DEG)
    assert float(params["resy"]) == pytest.approx(emodnet.NATIVE_RES_DEG)


def test_emodnet_spec_filename_encodes_bbox_and_res():
    bbox = (15.80, 41.49, 16.05, 41.69)
    spec = emodnet.EmodnetBathymetrySpec(bbox=bbox, res_deg=0.001)
    assert spec.out_filename.startswith("emodnet_dtm2024_mean_")
    assert "w15.8000" in spec.out_filename
    assert "s41.4900" in spec.out_filename
    assert "e16.0500" in spec.out_filename
    assert "n41.6900" in spec.out_filename
    assert "r0.001000" in spec.out_filename
    assert spec.out_filename.endswith(".tif")


def test_emodnet_spec_source_id_and_dataset_are_stable():
    spec = emodnet.EmodnetBathymetrySpec(bbox=(0, 0, 1, 1))
    assert spec.source_id == "emodnet_bathymetry_dtm2024_mean"
    assert "EMODnet" in spec.dataset
    assert "2024" in spec.dataset


def test_acquire_emodnet_bathymetry_writes_geotiff_and_provenance(
    tmp_path: Path, respx_mock: respx.Router
) -> None:
    aoi = tmp_path / "aoi.geojson"
    aoi.write_text(
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
                                    [15.80, 41.49],
                                    [16.05, 41.49],
                                    [16.05, 41.69],
                                    [15.80, 41.69],
                                    [15.80, 41.49],
                                ]
                            ],
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    # Build the expected URL using the spec (so the test matches the impl)
    bbox = (15.8, 41.49, 16.05, 41.69)
    expected_url = emodnet.EmodnetBathymetrySpec(bbox=bbox).url
    payload = b"II*\x00" + b"x" * 4096  # TIFF little-endian magic + filler
    respx_mock.get(expected_url).mock(return_value=httpx.Response(200, content=payload))

    out = tmp_path / "out.tif"
    result = CliRunner().invoke(
        acq_cli.acquire_emodnet_bathymetry,
        ["--aoi", str(aoi), "--out", str(out)],
    )
    assert result.exit_code == 0, result.output
    assert out.read_bytes() == payload

    sidecar = out.with_suffix(out.suffix + ".provenance.json")
    prov = json.loads(sidecar.read_text())
    assert prov["publisher"] == "EMODnet Bathymetry Consortium"
    assert prov["license"] == "CC-BY-4.0"
    assert prov["source_id"] == "emodnet_bathymetry_dtm2024_mean"
    assert prov["bbox"] == [15.8, 41.49, 16.05, 41.69]
    assert prov["query"]["coverage"] == "emodnet:mean"
    assert prov["year_data"] == 2024


def test_acquire_emodnet_bathymetry_default_out_under_data_raw(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, respx_mock: respx.Router
) -> None:
    monkeypatch.setattr(acq_cli, "DATA_RAW", tmp_path / "raw")
    aoi = tmp_path / "aoi.geojson"
    aoi.write_text(
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
                                [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0], [0.0, 0.0]]
                            ],
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    bbox = (0.0, 0.0, 1.0, 1.0)
    spec = emodnet.EmodnetBathymetrySpec(bbox=bbox)
    respx_mock.get(spec.url).mock(return_value=httpx.Response(200, content=b"II*\x00"))

    result = CliRunner().invoke(acq_cli.acquire_emodnet_bathymetry, ["--aoi", str(aoi)])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "raw" / "emodnet_bathymetry" / spec.out_filename).exists()
