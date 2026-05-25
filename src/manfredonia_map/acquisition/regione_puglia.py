"""Regione Puglia open data (dati.puglia.it / CKAN).

CKAN is a generic open-data catalog framework; each dataset has stable
``/dataset/<id>/resource/<id>/download/<filename>`` URLs. We treat each
dataset as one ``RegionePugliaSpec`` so the acquisition pattern matches
the rest of the pipeline (ISTAT, MASE, EMODnet, …).

Currently wired:

- ``sin`` — *Siti di Interesse Nazionale (SIN)* for Puglia (all 4 SINs:
  Bari, Brindisi, Manfredonia, Taranto) as one shapefile bundle.
  Published by InnovaPuglia (Servizio Territorio e Ambiente). License
  CC-BY-4.0. Last updated 2025-08-04.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

DatasetId = Literal["sin"]


@dataclass(frozen=True)
class RegionePugliaSpec:
    """Static spec for one Regione Puglia / CKAN dataset."""

    dataset_id: DatasetId

    @property
    def url(self) -> str:
        """Return the direct download URL for this dataset."""
        if self.dataset_id == "sin":
            # Dataset 70c4d257…, resource 7263c82e… — verified 2026-05-25.
            return (
                "https://dati.puglia.it/ckan/dataset/"
                "70c4d257-d87e-4533-9e18-b9515b469b5b/resource/"
                "7263c82e-de36-43b9-98f1-0e84cf78f5a3/download/sin.zip"
            )
        raise ValueError(f"unknown dataset_id={self.dataset_id!r}")  # pragma: no cover

    @property
    def out_filename(self) -> str:
        """Suggested filename under ``data/raw/<source_id>/``."""
        if self.dataset_id == "sin":
            return "sin_puglia.zip"
        raise ValueError(f"unknown dataset_id={self.dataset_id!r}")  # pragma: no cover

    @property
    def source_id(self) -> str:
        """Catalog source identifier for the provenance record."""
        return f"regione_puglia_{self.dataset_id}"

    @property
    def publisher(self) -> str:
        """Provenance ``publisher`` field — required by CC-BY-4.0 attribution."""
        return "Regione Puglia / InnovaPuglia (Servizio Territorio e Ambiente)"

    @property
    def dataset(self) -> str:
        """Human-readable dataset name for the provenance record."""
        if self.dataset_id == "sin":
            return (
                "Regione Puglia — Siti di Interesse Nazionale (SIN), "
                "shapefile bundle including Bari / Brindisi / Manfredonia / Taranto"
            )
        raise ValueError(f"unknown dataset_id={self.dataset_id!r}")  # pragma: no cover
