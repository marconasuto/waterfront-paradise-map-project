"""ISPRA national hydrography acquisitions via the `hy` WFS workspace.

ISPRA publishes the *Reticolo Idrografico Nazionale 1:250.000* (and its
companion datasets — primary basins, secondary basins, basin authorities,
network points) through a GeoServer WFS at

``https://sdi.isprambiente.it/geoserver/hy/wfs``

The pipeline issues an OGC WFS 2.0.0 ``GetFeature`` request with our AOI
bbox and ``application/json`` output, landing a small GeoJSON per layer
directly under ``data/raw/ispra_hydrography/``. License: CC-BY-4.0
(ISPRA).

Underground / aquifer data — the *Carta Idrogeologica d'Italia 1:500.000*
(CII500K, 2025) — is published by ISPRA's Geological Survey on a
different infrastructure (``portalesgi.isprambiente.it``); its
programmatic endpoint is not yet wired up in this module (tracked as
``OPEN-CII500K-1`` in ``SPECIFICATIONS.md``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlencode

#: WFS layers in the ISPRA `hy` workspace that the pipeline knows about.
#: All four are AOI-bbox friendly (small feature counts at our scale).
HydroLayer = Literal[
    "reticolo_idrografico",
    "bacini_principali",
    "bacini_secondari",
    "autorita_bacino",
]
LAYERS: tuple[HydroLayer, ...] = (
    "reticolo_idrografico",
    "bacini_principali",
    "bacini_secondari",
    "autorita_bacino",
)


@dataclass(frozen=True)
class IspraHydrographySpec:
    """Spec for one ISPRA hydrography WFS GetFeature request."""

    layer: HydroLayer
    bbox: tuple[float, float, float, float]  # (west, south, east, north) in EPSG:4326
    base_url: str = "https://sdi.isprambiente.it/geoserver/hy/wfs"

    @property
    def url(self) -> str:
        """Compose a WFS 2.0.0 GetFeature URL returning GeoJSON."""
        west, south, east, north = self.bbox
        params = {
            "service": "WFS",
            "version": "2.0.0",
            "request": "GetFeature",
            "typeNames": f"hy:{self.layer}",
            "srsName": "EPSG:4326",
            "bbox": f"{west},{south},{east},{north},EPSG:4326",
            "outputFormat": "application/json",
        }
        return f"{self.base_url}?{urlencode(params)}"

    @property
    def out_filename(self) -> str:
        """Suggested filename under ``data/raw/ispra_hydrography/``."""
        return f"hy_{self.layer}_aoi.geojson"

    @property
    def source_id(self) -> str:
        """Catalog source identifier for the provenance record."""
        return f"ispra_hy_{self.layer}"

    @property
    def dataset(self) -> str:
        """Human-readable dataset name for the provenance record."""
        return (
            f"ISPRA — {self.layer.replace('_', ' ')} "
            "(Reticolo Idrografico Nazionale 1:250.000, AOI bbox clip via WFS)"
        )
