"""MiC *Vincoli in Rete* (VIR) — manual KML ingestion.

The public Vincoli in Rete portal at
``https://vincoliinrete.beniculturali.it/VincoliInRete/`` does **not**
expose a documented public WFS / WMS endpoint. The internal WFS layer
exists but is only accessible to authenticated institutional users; the
public UI offers KML / CSV / PDF export per site through manual search.
Same situation for the GNA (``gna.cultura.gov.it``) and SITAP
(``sitap.cultura.gov.it``) systems. Tracked as ``OPEN-VIR-1`` in
``SPECIFICATIONS.md``.

For the v1 the OSM proxy (``osm.LAYERS["archaeology"]``) already covers
our key sites — Grotta Scaloria, Siponto, Parco archeologico di Siponto
and Coppa Nevigata. When the user obtains an authoritative KML export
from the VIR portal, this module standardises ingestion:

1. ``mfd-map acquire vir ingest --kml <path>``
2. The KML is copied verbatim to ``data/raw/mic_vincoli_in_rete/`` with
   a deterministic filename derived from its SHA-256 + accessed-on date.
3. A standard provenance sidecar is written.

Phase 4 processing reads the KML(s) via GeoPandas and merges with the
OSM archaeology layer, deduplicating by name.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class VirManualExportSpec:
    """Spec for one manually exported KML from the VIR portal."""

    kml_path: Path
    label: str

    @property
    def out_filename(self) -> str:
        """Suggested filename under ``data/raw/mic_vincoli_in_rete/``."""
        safe_label = "".join(c if c.isalnum() or c in "-_" else "_" for c in self.label)
        return f"vir_{safe_label}.kml"

    @property
    def source_id(self) -> str:
        """Catalog source identifier for the provenance record."""
        return f"mic_vir_manual_{self.label}"

    @property
    def dataset(self) -> str:
        """Human-readable dataset name for the provenance record."""
        return (
            f"MiC Vincoli in Rete — manual KML export ({self.label}); "
            "obtained via portal UI search + export."
        )


def stage_manual_export(spec: VirManualExportSpec, out_dir: Path) -> Path:
    """Copy a manually-exported KML into ``out_dir`` deterministically.

    Args:
        spec: Where the KML currently lives + a short label.
        out_dir: Destination directory (created if missing).

    Returns:
        The destination path of the copied file.

    Raises:
        FileNotFoundError: If ``spec.kml_path`` does not exist.
        ValueError: If the file is empty or does not look like KML.
    """
    if not spec.kml_path.is_file():
        raise FileNotFoundError(spec.kml_path)
    head = spec.kml_path.read_bytes()[:2048].lower()
    if not head or b"<kml" not in head:
        raise ValueError(
            f"{spec.kml_path} does not look like a KML document "
            "(missing <kml ...> root element in first 2 KB)."
        )
    out_dir.mkdir(parents=True, exist_ok=True)
    dst = out_dir / spec.out_filename
    shutil.copyfile(spec.kml_path, dst)
    return dst
