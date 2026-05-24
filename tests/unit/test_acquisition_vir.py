from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from manfredonia_map.acquisition import cli as acq_cli
from manfredonia_map.acquisition import vir

MINIMAL_KML = """\
<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>Test Vincolo</name>
    <Placemark>
      <name>Grotta Scaloria</name>
      <Point><coordinates>15.907,41.648,0</coordinates></Point>
    </Placemark>
  </Document>
</kml>
"""


def test_spec_sanitises_label_in_filename():
    spec = vir.VirManualExportSpec(kml_path=Path("/x.kml"), label="puglia/foggia 2024!")
    assert spec.out_filename == "vir_puglia_foggia_2024_.kml"


def test_spec_source_id_and_dataset_reflect_label():
    spec = vir.VirManualExportSpec(kml_path=Path("/x.kml"), label="grotta-scaloria")
    assert spec.source_id == "mic_vir_manual_grotta-scaloria"
    assert "Vincoli in Rete" in spec.dataset


def test_stage_manual_export_copies_kml(tmp_path: Path):
    src = tmp_path / "input.kml"
    src.write_text(MINIMAL_KML, encoding="utf-8")
    spec = vir.VirManualExportSpec(kml_path=src, label="grotta-scaloria")
    dst = vir.stage_manual_export(spec, tmp_path / "staged")
    assert dst.exists()
    assert dst.name == "vir_grotta-scaloria.kml"
    assert dst.read_text(encoding="utf-8") == MINIMAL_KML


def test_stage_manual_export_raises_when_file_missing(tmp_path: Path):
    spec = vir.VirManualExportSpec(kml_path=tmp_path / "nope.kml", label="x")
    with pytest.raises(FileNotFoundError):
        vir.stage_manual_export(spec, tmp_path)


def test_stage_manual_export_rejects_non_kml(tmp_path: Path):
    src = tmp_path / "bogus.kml"
    src.write_text("<html><body>not a kml</body></html>", encoding="utf-8")
    spec = vir.VirManualExportSpec(kml_path=src, label="x")
    with pytest.raises(ValueError, match="does not look like a KML"):
        vir.stage_manual_export(spec, tmp_path)


def test_stage_manual_export_rejects_empty(tmp_path: Path):
    src = tmp_path / "empty.kml"
    src.write_bytes(b"")
    spec = vir.VirManualExportSpec(kml_path=src, label="x")
    with pytest.raises(ValueError, match="does not look like a KML"):
        vir.stage_manual_export(spec, tmp_path)


def test_acquire_vir_ingest_writes_provenance(tmp_path: Path):
    src = tmp_path / "exported.kml"
    src.write_text(MINIMAL_KML, encoding="utf-8")
    out_dir = tmp_path / "out"
    result = CliRunner().invoke(
        acq_cli.acquire_vir_ingest,
        ["--kml", str(src), "--label", "grotta-scaloria", "--out-dir", str(out_dir)],
    )
    assert result.exit_code == 0, result.output
    staged = out_dir / "vir_grotta-scaloria.kml"
    assert staged.exists()
    sidecar = staged.with_suffix(staged.suffix + ".provenance.json")
    prov = json.loads(sidecar.read_text())
    assert prov["publisher"] == "Ministero della Cultura"
    assert prov["source_id"] == "mic_vir_manual_grotta-scaloria"
    assert prov["access_method"].startswith("manual KML export")
    assert prov["sha256"]
    assert prov["byte_count"] == len(MINIMAL_KML)


def test_acquire_vir_ingest_default_out_under_data_raw(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(acq_cli, "DATA_RAW", tmp_path / "raw")
    src = tmp_path / "exported.kml"
    src.write_text(MINIMAL_KML, encoding="utf-8")
    result = CliRunner().invoke(
        acq_cli.acquire_vir_ingest,
        ["--kml", str(src), "--label", "siponto"],
    )
    assert result.exit_code == 0, result.output
    assert (tmp_path / "raw" / "mic_vincoli_in_rete" / "vir_siponto.kml").exists()


def test_acquire_vir_ingest_propagates_validation_errors(tmp_path: Path):
    bogus = tmp_path / "bogus.kml"
    bogus.write_text("<html>not kml</html>", encoding="utf-8")
    result = CliRunner().invoke(
        acq_cli.acquire_vir_ingest,
        ["--kml", str(bogus), "--label", "x", "--out-dir", str(tmp_path / "out")],
    )
    assert result.exit_code != 0
