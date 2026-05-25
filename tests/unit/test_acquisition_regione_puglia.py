from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
import respx
from click.testing import CliRunner

from manfredonia_map.acquisition import cli as acq_cli
from manfredonia_map.acquisition import regione_puglia


def test_spec_sin_url_and_metadata():
    spec = regione_puglia.RegionePugliaSpec(dataset_id="sin")
    assert spec.url == (
        "https://dati.puglia.it/ckan/dataset/"
        "70c4d257-d87e-4533-9e18-b9515b469b5b/resource/"
        "7263c82e-de36-43b9-98f1-0e84cf78f5a3/download/sin.zip"
    )
    assert spec.out_filename == "sin_puglia.zip"
    assert spec.source_id == "regione_puglia_sin"
    assert "InnovaPuglia" in spec.publisher
    assert "Siti di Interesse Nazionale" in spec.dataset


def test_acquire_sin_writes_zip_and_provenance(
    tmp_path: Path, respx_mock: respx.Router
) -> None:
    payload = b"PK\x03\x04" + b"x" * 8192
    spec = regione_puglia.RegionePugliaSpec(dataset_id="sin")
    respx_mock.get(spec.url).mock(return_value=httpx.Response(200, content=payload))

    out = tmp_path / "out.zip"
    result = CliRunner().invoke(
        acq_cli.acquire_regione_puglia_dataset,
        ["sin", "--out", str(out)],
    )
    assert result.exit_code == 0, result.output
    assert out.read_bytes() == payload

    sidecar = out.with_suffix(out.suffix + ".provenance.json")
    prov = json.loads(sidecar.read_text())
    assert prov["source_id"] == "regione_puglia_sin"
    assert prov["license"] == "CC-BY-4.0"
    assert prov["publisher"].startswith("Regione Puglia")
    assert prov["access_method"] == "HTTPS (CKAN open data)"
    assert prov["sha256"]
    assert prov["byte_count"] == len(payload)


def test_acquire_sin_default_out_under_data_raw(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, respx_mock: respx.Router
) -> None:
    monkeypatch.setattr(acq_cli, "DATA_RAW", tmp_path / "raw")
    spec = regione_puglia.RegionePugliaSpec(dataset_id="sin")
    respx_mock.get(spec.url).mock(return_value=httpx.Response(200, content=b"PK\x03\x04"))

    result = CliRunner().invoke(acq_cli.acquire_regione_puglia_dataset, ["sin"])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "raw" / spec.source_id / spec.out_filename).exists()
