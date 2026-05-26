from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
import respx
from click.testing import CliRunner

from manfredonia_map.acquisition import cli as acq_cli
from manfredonia_map.acquisition import ispra


def test_ispra_spec_url_has_expected_params():
    bbox = (15.79, 41.49, 16.06, 41.69)
    spec = ispra.IspraHydrographySpec(layer="reticolo_idrografico", bbox=bbox)
    parsed = urlparse(spec.url)
    assert parsed.netloc == "sdi.isprambiente.it"
    params = {k: v[0] for k, v in parse_qs(parsed.query).items()}
    assert params["service"] == "WFS"
    assert params["version"] == "2.0.0"
    assert params["request"] == "GetFeature"
    assert params["typeNames"] == "hy:reticolo_idrografico"
    assert params["srsName"] == "EPSG:4326"
    assert params["bbox"] == "15.79,41.49,16.06,41.69,EPSG:4326"
    assert params["outputFormat"] == "application/json"


def test_ispra_spec_filename_and_ids():
    bbox = (0.0, 0.0, 1.0, 1.0)
    spec = ispra.IspraHydrographySpec(layer="bacini_principali", bbox=bbox)
    assert spec.out_filename == "hy_bacini_principali_aoi.geojson"
    assert spec.source_id == "ispra_hy_bacini_principali"
    assert "bacini principali" in spec.dataset


def test_ispra_layers_tuple_contains_expected():
    assert "reticolo_idrografico" in ispra.LAYERS
    assert "bacini_principali" in ispra.LAYERS
    assert "bacini_secondari" in ispra.LAYERS
    assert "autorita_bacino" in ispra.LAYERS


def _aoi_4326(tmp_path: Path) -> Path:
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
                                    [15.79, 41.49],
                                    [16.06, 41.49],
                                    [16.06, 41.69],
                                    [15.79, 41.69],
                                    [15.79, 41.49],
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


_GEOJSON_FIXTURE = json.dumps(
    {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"nome": "Cervaro", "tipo": "TORRENTE"},
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[15.85, 41.5], [15.92, 41.6]],
                },
            }
        ],
    }
).encode("utf-8")


def test_acquire_ispra_hydrography_writes_geojson_and_provenance(
    tmp_path: Path, respx_mock: respx.Router
) -> None:
    aoi = _aoi_4326(tmp_path)
    bbox = (15.79, 41.49, 16.06, 41.69)
    spec = ispra.IspraHydrographySpec(layer="reticolo_idrografico", bbox=bbox)
    respx_mock.get(spec.url).mock(return_value=httpx.Response(200, content=_GEOJSON_FIXTURE))

    out = tmp_path / "out.geojson"
    result = CliRunner().invoke(
        acq_cli.acquire_ispra_hydrography,
        ["reticolo_idrografico", "--aoi", str(aoi), "--out", str(out)],
    )
    assert result.exit_code == 0, result.output
    assert out.read_bytes() == _GEOJSON_FIXTURE

    prov = json.loads(out.with_suffix(".provenance.json").read_text())
    assert prov["publisher"] == "ISPRA"
    assert prov["license"] == "CC-BY-4.0"
    assert prov["source_id"] == "ispra_hy_reticolo_idrografico"
    assert prov["access_method"] == "WFS 2.0.0 GetFeature"
    assert prov["bbox"] == [15.79, 41.49, 16.06, 41.69]


def test_acquire_ispra_hydrography_default_out_under_data_raw(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, respx_mock: respx.Router
) -> None:
    monkeypatch.setattr(acq_cli, "DATA_RAW", tmp_path / "raw")
    aoi = _aoi_4326(tmp_path)
    bbox = (15.79, 41.49, 16.06, 41.69)
    spec = ispra.IspraHydrographySpec(layer="bacini_principali", bbox=bbox)
    respx_mock.get(spec.url).mock(return_value=httpx.Response(200, content=_GEOJSON_FIXTURE))

    result = CliRunner().invoke(
        acq_cli.acquire_ispra_hydrography,
        ["bacini_principali", "--aoi", str(aoi)],
    )
    assert result.exit_code == 0, result.output
    expected = tmp_path / "raw" / "ispra_hydrography" / spec.out_filename
    assert expected.exists()


def test_acquire_ispra_hydrography_all_runs_each_layer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, respx_mock: respx.Router
) -> None:
    monkeypatch.setattr(acq_cli, "DATA_RAW", tmp_path / "raw")
    aoi = _aoi_4326(tmp_path)
    bbox = (15.79, 41.49, 16.06, 41.69)
    for layer in ispra.LAYERS:
        spec = ispra.IspraHydrographySpec(layer=layer, bbox=bbox)
        respx_mock.get(spec.url).mock(return_value=httpx.Response(200, content=_GEOJSON_FIXTURE))

    result = CliRunner().invoke(
        acq_cli.acquire_ispra_hydrography_all,
        ["--aoi", str(aoi)],
    )
    assert result.exit_code == 0, result.output
    for layer in ispra.LAYERS:
        assert (tmp_path / "raw" / "ispra_hydrography" / f"hy_{layer}_aoi.geojson").exists()


def test_acquire_ispra_hydrography_all_collects_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, respx_mock: respx.Router
) -> None:
    monkeypatch.setattr(acq_cli, "DATA_RAW", tmp_path / "raw")
    aoi = _aoi_4326(tmp_path)
    bbox = (15.79, 41.49, 16.06, 41.69)
    # All but one succeed; "autorita_bacino" 404s and bubbles up to the
    # summary at the end.
    for layer in ispra.LAYERS:
        spec = ispra.IspraHydrographySpec(layer=layer, bbox=bbox)
        if layer == "autorita_bacino":
            respx_mock.get(spec.url).mock(return_value=httpx.Response(404))
        else:
            respx_mock.get(spec.url).mock(
                return_value=httpx.Response(200, content=_GEOJSON_FIXTURE)
            )

    result = CliRunner().invoke(
        acq_cli.acquire_ispra_hydrography_all,
        ["--aoi", str(aoi)],
    )
    assert result.exit_code != 0
    assert "autorita_bacino" in result.output


def test_acquire_ispra_hydrography_all_honours_skip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, respx_mock: respx.Router
) -> None:
    monkeypatch.setattr(acq_cli, "DATA_RAW", tmp_path / "raw")
    aoi = _aoi_4326(tmp_path)
    bbox = (15.79, 41.49, 16.06, 41.69)
    only = "reticolo_idrografico"
    spec = ispra.IspraHydrographySpec(layer=only, bbox=bbox)
    respx_mock.get(spec.url).mock(return_value=httpx.Response(200, content=_GEOJSON_FIXTURE))

    skip_args: list[str] = []
    for layer in ispra.LAYERS:
        if layer != only:
            skip_args.extend(["--skip", layer])
    result = CliRunner().invoke(
        acq_cli.acquire_ispra_hydrography_all,
        ["--aoi", str(aoi), *skip_args],
    )
    assert result.exit_code == 0, result.output
    out_dir = tmp_path / "raw" / "ispra_hydrography"
    assert sorted(p.name for p in out_dir.iterdir() if p.suffix == ".geojson") == [
        f"hy_{only}_aoi.geojson"
    ]
