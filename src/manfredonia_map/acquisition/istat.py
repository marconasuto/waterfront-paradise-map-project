"""ISTAT *Confini delle unità amministrative a fini statistici* acquisition.

ISTAT publishes administrative boundaries (regioni / province / comuni)
as a single zipped shapefile bundle per year. Two resolutions exist:
*generalizzato* (~3 MB, suffix ``_g``) and *non generalizzato* (~70 MB).
URL pattern (verified for 2024):
``https://www.istat.it/storage/cartografia/confini_amministrativi/{quality}/{year}/Limiti{date}{suffix}.zip``

Phase 3 stores the zip verbatim under ``data/raw/istat_admin/``; Phase 4
processing reads via ``zip://`` GeoPandas paths and filters to Manfredonia
and Monte Sant'Angelo. License: CC BY 3.0 (ISTAT terms).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IstatBoundariesSpec:
    """Static spec for one ISTAT confini release."""

    year: int
    generalized: bool

    @property
    def url(self) -> str:
        """Return the download URL for this year + resolution."""
        date = f"01{1:02d}{self.year}"  # "01012024" pattern
        if self.generalized:
            return (
                "https://www.istat.it/storage/cartografia/confini_amministrativi/"
                f"generalizzati/{self.year}/Limiti{date}_g.zip"
            )
        return (
            "https://www.istat.it/storage/cartografia/confini_amministrativi/"
            f"non_generalizzati/{self.year}/Limiti{date}.zip"
        )

    @property
    def out_filename(self) -> str:
        """Suggested filename under ``data/raw/istat_admin/``."""
        date = f"01{1:02d}{self.year}"
        suffix = "_g" if self.generalized else ""
        return f"Limiti{date}{suffix}.zip"

    @property
    def source_id(self) -> str:
        """Catalog source identifier for the provenance record."""
        suffix = "generalized" if self.generalized else "detailed"
        return f"istat_limiti_{self.year}_{suffix}"

    @property
    def dataset(self) -> str:
        """Human-readable dataset name for the provenance record."""
        suffix = "generalizzati" if self.generalized else "non generalizzati"
        return f"ISTAT — Confini amministrativi al 1 gennaio {self.year} ({suffix})"
