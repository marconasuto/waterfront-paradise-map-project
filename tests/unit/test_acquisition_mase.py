from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
import respx
from click.testing import CliRunner

from manfredonia_map.acquisition import cli as acq_cli
from manfredonia_map.acquisition import mase


def test_mase_natura2000_spec_default_url_for_2025():
    spec = mase.MaseNatura2000Spec(year=2025)
    assert spec.url == (
        "https://download.mase.gov.it/Natura2000/Trasmissione%20CE_dicembre2025/"
        "sic_zps_ita_32_tuttiicampi.zip"
    )
    assert spec.out_filename == "sic_zps_ita_32_tuttiicampi_2025.zip"
    assert spec.source_id == "mase_natura2000_2025_tuttiicampi"
    assert "Natura 2000" in spec.dataset
    assert "2025" in spec.dataset


def test_mase_natura2000_spec_variant_daticartografici():
    spec = mase.MaseNatura2000Spec(year=2024, variant="daticartografici")
    assert spec.url.endswith("sic_zps_ita_32_daticartografici.zip")
    assert "Trasmissione%20CE_dicembre2024" in spec.url
    assert spec.source_id == "mase_natura2000_2024_daticartografici"


def test_acquire_mase_natura2000_writes_zip_and_provenance(
    tmp_path: Path, respx_mock: respx.Router
) -> None:
    payload = b"PK\x03\x04" + b"x" * 8192
    spec = mase.MaseNatura2000Spec(year=2025)
    respx_mock.get(spec.url).mock(return_value=httpx.Response(200, content=payload))

    out = tmp_path / "natura.zip"
    result = CliRunner().invoke(
        acq_cli.acquire_mase_natura2000,
        ["--year", "2025", "--variant", "tuttiicampi", "--out", str(out)],
    )
    assert result.exit_code == 0, result.output
    assert out.exists()
    assert out.read_bytes() == payload

    sidecar = out.with_suffix(out.suffix + ".provenance.json")
    prov = json.loads(sidecar.read_text())
    assert prov["publisher"] == "MASE"
    assert prov["license"] == "non-commercial, cite source"
    assert prov["source_id"] == "mase_natura2000_2025_tuttiicampi"
    assert prov["year_data"] == 2025
    assert prov["byte_count"] == len(payload)
    assert prov["sha256"]


def test_acquire_mase_natura2000_default_out_under_data_raw(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, respx_mock: respx.Router
) -> None:
    monkeypatch.setattr(acq_cli, "DATA_RAW", tmp_path / "raw")
    spec = mase.MaseNatura2000Spec(year=2025)
    respx_mock.get(spec.url).mock(return_value=httpx.Response(200, content=b"PK\x03\x04"))

    result = CliRunner().invoke(acq_cli.acquire_mase_natura2000, [])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "raw" / "mase_natura2000" / spec.out_filename).exists()


def test_acquire_mase_natura2000_variant_flag_picks_other_url(
    tmp_path: Path, respx_mock: respx.Router
) -> None:
    spec = mase.MaseNatura2000Spec(year=2025, variant="daticartografici")
    respx_mock.get(spec.url).mock(return_value=httpx.Response(200, content=b"PK\x03\x04"))

    out = tmp_path / "carto.zip"
    result = CliRunner().invoke(
        acq_cli.acquire_mase_natura2000,
        ["--variant", "daticartografici", "--out", str(out)],
    )
    assert result.exit_code == 0, result.output
    assert out.exists()
