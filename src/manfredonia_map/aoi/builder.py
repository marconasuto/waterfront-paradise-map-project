"""Pure-function AOI builder.

Buffer and clip operations always re-project into ``ANALYSIS_CRS`` (UTM
33N, EPSG:32633) so distances are measured in metres, then back into
``STORAGE_CRS`` (WGS 84, EPSG:4326) before returning. The functions in
this module are deterministic for the same input geometry: identical
shapely versions + identical input bytes → identical output bytes.
"""

from __future__ import annotations

from collections.abc import Iterable

import geopandas as gpd
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

ANALYSIS_CRS = "EPSG:32633"
STORAGE_CRS = "EPSG:4326"


def _reproject(geom: BaseGeometry, src_crs: str, dst_crs: str) -> BaseGeometry:
    """Re-project a single geometry between two CRSs via a 1-row GeoSeries."""
    series = gpd.GeoSeries([geom], crs=src_crs).to_crs(dst_crs)
    return series.iloc[0]


def build_buffered_aoi(
    source: BaseGeometry, source_crs: str, buffer_m: float
) -> BaseGeometry:
    """Expand a source polygon by ``buffer_m`` metres on every side.

    Args:
        source: Source polygon geometry.
        source_crs: CRS of ``source`` as a string parseable by pyproj.
        buffer_m: Buffer distance in metres (computed in the analysis CRS).

    Returns:
        A geometry in EPSG:4326.
    """
    metric = _reproject(source, source_crs, ANALYSIS_CRS)
    return _reproject(metric.buffer(buffer_m), ANALYSIS_CRS, STORAGE_CRS)


def build_coastal_band(
    coastline: BaseGeometry | None,
    coastline_crs: str | None,
    band_m: float,
) -> BaseGeometry | None:
    """Build a band of ``band_m`` metres on both sides of a coastline.

    Args:
        coastline: Coastline geometry (LineString / MultiLineString /
            anything ``shapely`` can ``buffer``). May be ``None`` when
            the coastline has not been acquired yet.
        coastline_crs: CRS of ``coastline``.
        band_m: Half-width of the band in metres.

    Returns:
        The buffer polygon in EPSG:4326, or ``None`` if ``coastline`` is
        ``None``.
    """
    if coastline is None:
        return None
    if coastline_crs is None:
        raise ValueError("coastline_crs must be supplied when coastline is not None")
    metric = _reproject(coastline, coastline_crs, ANALYSIS_CRS)
    return _reproject(metric.buffer(band_m), ANALYSIS_CRS, STORAGE_CRS)


def build_near_coast_aoi(
    aoi_buffered: BaseGeometry,
    coastal_band: BaseGeometry | None,
    mandatory_features: Iterable[BaseGeometry],
) -> BaseGeometry:
    """Intersect ``aoi_buffered`` with the union of band and mandatory features.

    When neither the coastal band nor any mandatory feature is available
    (e.g., acquisition has not run yet), the function falls back to
    returning ``aoi_buffered`` unchanged. The caller is expected to log
    a warning in that case so the downstream pipeline is aware that
    near-coast guarantees are not yet enforced.

    Args:
        aoi_buffered: The buffered AOI (EPSG:4326).
        coastal_band: Coastal band geometry (EPSG:4326) or ``None``.
        mandatory_features: Geometries (EPSG:4326) that must be included
            regardless of the coastal band — e.g., the SIN perimeter,
            Lago Salso, Oasi Laguna del Re, wetlands, Grotta Scaloria
            buffer.

    Returns:
        A geometry in EPSG:4326.
    """
    inclusions = [
        g for g in (coastal_band, *list(mandatory_features)) if g is not None and not g.is_empty
    ]
    if not inclusions:
        return aoi_buffered
    return aoi_buffered.intersection(unary_union(inclusions))
