from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import pytest
from click.testing import CliRunner
from shapely.geometry import LineString

from manfredonia_map.acquisition import cli as acq_cli


def _write_aoi(tmp_path: Path) -> Path:
    p = tmp_path / "aoi_buffered.geojson"
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
    return p


def test_acquire_coastline_writes_geojson_and_provenance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = gpd.GeoDataFrame(
        geometry=[
            LineString([(15.92, 41.55), (15.93, 41.60), (15.94, 41.65)]),
        ],
        crs="EPSG:4326",
    )
    monkeypatch.setattr(
        acq_cli.osm,
        "fetch_coastline",
        lambda bbox, fetcher=None: fake,
    )

    aoi = _write_aoi(tmp_path)
    out = tmp_path / "raw" / "coastline" / "coastline.geojson"
    result = CliRunner().invoke(
        acq_cli.acquire_coastline,
        ["--aoi", str(aoi), "--out", str(out)],
    )
    assert result.exit_code == 0, result.output
    assert out.exists()

    sidecar = out.with_suffix(".provenance.json")
    assert sidecar.exists()
    prov = json.loads(sidecar.read_text())
    assert prov["source_id"] == "osm_coastline"
    assert prov["license"] == "ODbL-1.0"
    assert prov["bbox"] == [15.8, 41.49, 16.05, 41.69]
    assert prov["sha256"]
    assert prov["byte_count"] > 0


def test_acquire_coastline_fails_loud_when_zero_features(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        acq_cli.osm,
        "fetch_coastline",
        lambda bbox, fetcher=None: gpd.GeoDataFrame(geometry=[], crs="EPSG:4326"),
    )

    aoi = _write_aoi(tmp_path)
    out = tmp_path / "raw" / "coastline" / "coastline.geojson"
    result = CliRunner().invoke(
        acq_cli.acquire_coastline,
        ["--aoi", str(aoi), "--out", str(out)],
    )
    assert result.exit_code != 0
    assert "0 coastline features" in result.output.lower()
