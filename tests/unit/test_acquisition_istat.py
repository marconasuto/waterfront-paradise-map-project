from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
import respx
from click.testing import CliRunner

from manfredonia_map.acquisition import cli as acq_cli
from manfredonia_map.acquisition import istat


def test_istat_spec_generalized_url_for_2024():
    spec = istat.IstatBoundariesSpec(year=2024, generalized=True)
    assert spec.url == (
        "https://www.istat.it/storage/cartografia/confini_amministrativi/"
        "generalizzati/2024/Limiti01012024_g.zip"
    )
    assert spec.out_filename == "Limiti01012024_g.zip"
    assert spec.source_id == "istat_limiti_2024_generalized"
    assert "1 gennaio 2024" in spec.dataset


def test_istat_spec_detailed_url_for_2024():
    spec = istat.IstatBoundariesSpec(year=2024, generalized=False)
    assert spec.url == (
        "https://www.istat.it/storage/cartografia/confini_amministrativi/"
        "non_generalizzati/2024/Limiti01012024.zip"
    )
    assert spec.out_filename == "Limiti01012024.zip"
    assert spec.source_id == "istat_limiti_2024_detailed"


def test_istat_spec_year_variants_pattern():
    spec = istat.IstatBoundariesSpec(year=2023, generalized=True)
    assert spec.out_filename == "Limiti01012023_g.zip"
    assert "2023" in spec.url


def test_acquire_istat_boundaries_writes_zip_and_provenance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    respx_mock: respx.Router,
) -> None:
    payload = b"PK\x03\x04" + b"x" * 4096  # zip magic + filler
    spec = istat.IstatBoundariesSpec(year=2024, generalized=True)
    respx_mock.get(spec.url).mock(return_value=httpx.Response(200, content=payload))

    out = tmp_path / "istat_admin" / spec.out_filename
    result = CliRunner().invoke(
        acq_cli.acquire_istat_boundaries,
        ["--year", "2024", "--generalized", "--out", str(out)],
    )
    assert result.exit_code == 0, result.output
    assert out.exists()
    assert out.read_bytes() == payload

    sidecar = out.with_suffix(out.suffix + ".provenance.json")
    assert sidecar.exists()
    prov = json.loads(sidecar.read_text())
    assert prov["publisher"] == "ISTAT"
    assert prov["license"] == "CC-BY-3.0"
    assert prov["year_data"] == 2024
    assert prov["source_id"] == "istat_limiti_2024_generalized"
    assert prov["byte_count"] == len(payload)
    assert prov["sha256"]


def test_acquire_istat_boundaries_default_out_lands_under_data_raw(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    respx_mock: respx.Router,
) -> None:
    monkeypatch.setattr(acq_cli, "DATA_RAW", tmp_path / "raw")
    spec = istat.IstatBoundariesSpec(year=2024, generalized=True)
    respx_mock.get(spec.url).mock(return_value=httpx.Response(200, content=b"PK\x03\x04"))

    result = CliRunner().invoke(acq_cli.acquire_istat_boundaries, [])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "raw" / "istat_admin" / spec.out_filename).exists()


def test_acquire_istat_boundaries_detailed_flag_picks_other_url(
    tmp_path: Path,
    respx_mock: respx.Router,
) -> None:
    spec = istat.IstatBoundariesSpec(year=2024, generalized=False)
    respx_mock.get(spec.url).mock(return_value=httpx.Response(200, content=b"PK\x03\x04"))

    out = tmp_path / "detailed.zip"
    result = CliRunner().invoke(
        acq_cli.acquire_istat_boundaries,
        ["--detailed", "--out", str(out)],
    )
    assert result.exit_code == 0, result.output
    assert out.exists()
