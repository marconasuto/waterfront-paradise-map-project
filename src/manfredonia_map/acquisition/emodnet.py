"""EMODnet Bathymetry acquisition via the WCS endpoint.

EMODnet publishes a Web Coverage Service at
``https://ows.emodnet-bathymetry.eu/wcs`` with coverage ``emodnet:mean``
(the DTM 2024 release). Unlike the per-tile zip downloads from the
geoviewer UI, the WCS lets us request a GeoTIFF clipped to our AOI bbox
at any supported resolution — far cleaner for a pipeline.

Native resolution of DTM 2024 is 1/16 arc-minute (≈ 115 m at lat 41°N),
i.e. ``1 / (16 * 60) ≈ 0.001041666 °``. The default below matches.

Output is a single GeoTIFF in EPSG:4326 covering only the AOI; Phase 4
processing re-projects to EPSG:32633 and produces an 8-bit colormapped
COG for Mapbox raster tilesets.

License: CC BY 4.0 (EMODnet Bathymetry consortium).
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlencode

# 1/16 arc-minute in degrees (native EMODnet DTM 2024 resolution).
NATIVE_RES_DEG = 1.0 / (16.0 * 60.0)


@dataclass(frozen=True)
class EmodnetBathymetrySpec:
    """Static spec for one EMODnet Bathymetry WCS GetCoverage request."""

    bbox: tuple[float, float, float, float]  # (west, south, east, north) in EPSG:4326
    res_deg: float = NATIVE_RES_DEG
    coverage: str = "emodnet:mean"
    base_url: str = "https://ows.emodnet-bathymetry.eu/wcs"

    @property
    def url(self) -> str:
        """Compose a WCS 1.0.0 GetCoverage URL for a GeoTIFF."""
        west, south, east, north = self.bbox
        params = {
            "service": "wcs",
            "version": "1.0.0",
            "request": "getcoverage",
            "coverage": self.coverage,
            "crs": "EPSG:4326",
            "bbox": f"{west},{south},{east},{north}",
            "format": "image/tiff",
            "interpolation": "nearest",
            "resx": str(self.res_deg),
            "resy": str(self.res_deg),
        }
        return f"{self.base_url}?{urlencode(params)}"

    @property
    def out_filename(self) -> str:
        """Suggested filename under ``data/raw/emodnet_bathymetry/``."""
        west, south, east, north = self.bbox
        # Use 4-decimal precision in the filename for traceability.
        return (
            f"emodnet_dtm2024_mean_"
            f"w{west:.4f}_s{south:.4f}_e{east:.4f}_n{north:.4f}_"
            f"r{self.res_deg:.6f}.tif"
        )

    @property
    def source_id(self) -> str:
        """Catalog source identifier for the provenance record."""
        return "emodnet_bathymetry_dtm2024_mean"

    @property
    def dataset(self) -> str:
        """Human-readable dataset name for the provenance record."""
        return "EMODnet Bathymetry — Digital Bathymetry DTM 2024 (mean coverage, WCS clip)"
