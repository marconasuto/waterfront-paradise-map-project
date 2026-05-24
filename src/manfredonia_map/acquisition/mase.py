"""MASE acquisitions (Ministero dell'Ambiente e della Sicurezza Energetica).

For now this covers only the *Rete Natura 2000* national bundle (the
yearly transmission to the European Commission). MASE publishes one
shapefile-bundle zip per year under

``https://download.mase.gov.it/Natura2000/Trasmissione%20CE_<MONTH><YEAR>/``

Two variants exist:

- ``daticartografici`` — bare geometry + minimal attributes (~32 MB).
- ``tuttiicampi`` — all standard-data-form fields included (~32 MB,
  default — richer attribution for downstream styling).

All files are in EPSG:32632 (UTM zone 32 N, WGS84) for nationwide
consistency. License is "non-commercial, cite source" (see
``docs/research/data_sources.md`` §6).

See also: ``OPEN-LICENSE-1`` in ``SPECIFICATIONS.md``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Variant = Literal["daticartografici", "tuttiicampi"]

# The transmission month MASE typically uses ("dicembre" = December).
_DEFAULT_MONTH = "dicembre"


@dataclass(frozen=True)
class MaseNatura2000Spec:
    """Static description of one MASE Natura 2000 bundle release."""

    year: int
    variant: Variant = "tuttiicampi"
    month: str = _DEFAULT_MONTH

    @property
    def url(self) -> str:
        """Return the canonical zip URL for this release."""
        return (
            "https://download.mase.gov.it/Natura2000/"
            f"Trasmissione%20CE_{self.month}{self.year}/"
            f"sic_zps_ita_32_{self.variant}.zip"
        )

    @property
    def out_filename(self) -> str:
        """Suggested filename under ``data/raw/mase_natura2000/``."""
        return f"sic_zps_ita_32_{self.variant}_{self.year}.zip"

    @property
    def source_id(self) -> str:
        """Catalog source identifier for the provenance record."""
        return f"mase_natura2000_{self.year}_{self.variant}"

    @property
    def dataset(self) -> str:
        """Human-readable dataset name for the provenance record."""
        return (
            f"MASE — Rete Natura 2000 (SIC/ZSC/ZPS), trasmissione CE "
            f"{self.month} {self.year} ({self.variant})"
        )
