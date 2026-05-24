from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
import respx
from click.testing import CliRunner

from manfredonia_map.acquisition import cli as acq_cli
from manfredonia_map.acquisition import tinitaly


def test_tinitaly_spec_url_pattern():
    spec = tinitaly.TinitalyTileSpec(tile_id="e41005_s10")
    assert spec.url == "https://tinitaly.pi.ingv.it/data/e41005_s10/e41005_s10.zip"
    assert spec.out_filename == "e41005_s10.zip"
    assert spec.source_id == "tinitaly_1_1_e41005_s10"
    assert "TINITALY" in spec.dataset
    assert "e41005_s10" in spec.dataset


def test_acquire_tinitaly_tile_writes_zip_and_provenance(
    tmp_path: Path, respx_mock: respx.Router
) -> None:
    payload = b"PK\x03\x04" + b"y" * 4096
    spec = tinitaly.TinitalyTileSpec(tile_id="e41005_s10")
    respx_mock.get(spec.url).mock(return_value=httpx.Response(200, content=payload))

    out = tmp_path / "tile.zip"
    result = CliRunner().invoke(
        acq_cli.acquire_tinitaly_tile,
        ["e41005_s10", "--out", str(out)],
    )
    assert result.exit_code == 0, result.output
    assert out.read_bytes() == payload

    sidecar = out.with_suffix(out.suffix + ".provenance.json")
    prov = json.loads(sidecar.read_text())
    assert prov["publisher"] == "INGV"
    assert prov["license"] == "CC-BY-4.0"
    assert prov["source_id"] == "tinitaly_1_1_e41005_s10"
    assert prov["byte_count"] == len(payload)
    assert prov["sha256"]


def test_acquire_tinitaly_tile_default_out_under_data_raw(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, respx_mock: respx.Router
) -> None:
    monkeypatch.setattr(acq_cli, "DATA_RAW", tmp_path / "raw")
    spec = tinitaly.TinitalyTileSpec(tile_id="e41005_s10")
    respx_mock.get(spec.url).mock(return_value=httpx.Response(200, content=b"PK\x03\x04"))

    result = CliRunner().invoke(acq_cli.acquire_tinitaly_tile, ["e41005_s10"])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "raw" / "tinitaly" / spec.out_filename).exists()


def test_acquire_tinitaly_tile_propagates_download_error(
    tmp_path: Path, respx_mock: respx.Router
) -> None:
    spec = tinitaly.TinitalyTileSpec(tile_id="zzz_nope")
    respx_mock.get(spec.url).mock(return_value=httpx.Response(404))

    out = tmp_path / "out.zip"
    result = CliRunner().invoke(
        acq_cli.acquire_tinitaly_tile, ["zzz_nope", "--out", str(out)],
    )
    assert result.exit_code != 0
