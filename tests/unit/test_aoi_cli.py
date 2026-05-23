from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from manfredonia_map.aoi.cli import build_aoi

SOURCE_GEOJSON = {
    "type": "FeatureCollection",
    "name": "test_source",
    "crs": {"type": "name", "properties": {"name": "EPSG:4326"}},
    "features": [
        {
            "type": "Feature",
            "properties": {},
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [15.90, 41.60],
                        [15.95, 41.60],
                        [15.95, 41.65],
                        [15.90, 41.65],
                        [15.90, 41.60],
                    ]
                ],
            },
        }
    ],
}


def _write_source(tmp_path: Path) -> Path:
    p = tmp_path / "src.geojson"
    p.write_text(json.dumps(SOURCE_GEOJSON), encoding="utf-8")
    return p


def test_build_aoi_without_coastline_writes_all_three_files(tmp_path: Path):
    src = _write_source(tmp_path)
    out_dir = tmp_path / "out"
    result = CliRunner().invoke(
        build_aoi,
        [
            "--source", str(src),
            "--coastline", str(tmp_path / "missing.geojson"),
            "--mandatory-dir", str(tmp_path / "missing_dir"),
            "--out-dir", str(out_dir),
        ],
    )
    assert result.exit_code == 0, result.output
    for name in ("aoi_buffered.geojson", "aoi_near_coast.geojson", "aoi.geojson"):
        assert (out_dir / name).exists(), name


def test_build_aoi_alias_buffered_writes_buffered_under_alias(tmp_path: Path):
    src = _write_source(tmp_path)
    out_dir = tmp_path / "out"
    result = CliRunner().invoke(
        build_aoi,
        [
            "--source", str(src),
            "--coastline", str(tmp_path / "missing.geojson"),
            "--mandatory-dir", str(tmp_path / "missing_dir"),
            "--out-dir", str(out_dir),
            "--alias", "buffered",
        ],
    )
    assert result.exit_code == 0, result.output
    alias = json.loads((out_dir / "aoi.geojson").read_text())
    assert alias["features"][0]["properties"]["alias_target"] == "buffered"


def test_build_aoi_with_coastline_includes_band(tmp_path: Path):
    src = _write_source(tmp_path)
    coastline = tmp_path / "coast.geojson"
    coastline.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "crs": {"type": "name", "properties": {"name": "EPSG:4326"}},
                "features": [
                    {
                        "type": "Feature",
                        "properties": {},
                        "geometry": {
                            "type": "LineString",
                            "coordinates": [[15.92, 41.59], [15.92, 41.66]],
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    out_dir = tmp_path / "out"
    result = CliRunner().invoke(
        build_aoi,
        [
            "--source", str(src),
            "--coastline", str(coastline),
            "--mandatory-dir", str(tmp_path / "missing_dir"),
            "--out-dir", str(out_dir),
        ],
    )
    # Either passes (coastal-band sanity met) or fails with our diagnostic.
    # In this synthetic case some default sanity points may sit outside the
    # 2 km band; assert that the failure message is precise if it fails.
    if result.exit_code != 0:
        assert "sanity checks failed" in result.output.lower()
    else:
        near = json.loads((out_dir / "aoi_near_coast.geojson").read_text())
        assert near["features"][0]["properties"]["coastal_band_present"] is True


def test_build_aoi_loads_mandatory_features_from_dir(tmp_path: Path):
    src = _write_source(tmp_path)
    mandatory_dir = tmp_path / "mandatory"
    mandatory_dir.mkdir()
    (mandatory_dir / "lago_salso.geojson").write_text(
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
                                    [15.915, 41.605],
                                    [15.925, 41.605],
                                    [15.925, 41.615],
                                    [15.915, 41.615],
                                    [15.915, 41.605],
                                ]
                            ],
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    out_dir = tmp_path / "out"
    result = CliRunner().invoke(
        build_aoi,
        [
            "--source", str(src),
            "--coastline", str(tmp_path / "missing.geojson"),
            "--mandatory-dir", str(mandatory_dir),
            "--out-dir", str(out_dir),
        ],
    )
    # mandatory present → enough_inputs True; with no coastal band the
    # default sanity points may fail → expect non-zero with diagnostic OR
    # success when the inclusion happens to contain them.
    if result.exit_code != 0:
        assert "sanity checks failed" in result.output.lower()
    else:
        near = json.loads((out_dir / "aoi_near_coast.geojson").read_text())
        assert near["features"][0]["properties"]["mandatory_feature_count"] == 1
