"""Sanity checks the AOI builder enforces on the near-coast shape.

Coordinates are approximate; the SIN, Lago Salso, Oasi Laguna del Re, and
Grotta Scaloria points will be refined once the actual perimeters are
acquired (Phase 3). Acqua di Cristo coordinates come from publicly
available sources (see ``docs/research/data_sources.md`` §12).
"""

from __future__ import annotations

from dataclasses import dataclass

from shapely.geometry import Point
from shapely.geometry.base import BaseGeometry


@dataclass(frozen=True)
class SanityCheck:
    """A single inside/outside assertion on the AOI."""

    name: str
    lon: float
    lat: float
    must_be_inside: bool = True

    def point(self) -> Point:
        """Return the check's location as a shapely Point in EPSG:4326."""
        return Point(self.lon, self.lat)


DEFAULT_CHECKS: tuple[SanityCheck, ...] = (
    SanityCheck("lago_salso_centroid", lon=15.92, lat=41.610),
    SanityCheck("oasi_laguna_del_re_centroid", lon=15.96, lat=41.590),
    SanityCheck("acqua_di_cristo", lon=15.9238, lat=41.6307),
    SanityCheck("sin_manfredonia_centroid", lon=15.940, lat=41.590),
    SanityCheck("grotta_scaloria", lon=15.907, lat=41.648),
)


def run_checks(
    near_coast: BaseGeometry,
    checks: tuple[SanityCheck, ...] = DEFAULT_CHECKS,
) -> dict[str, bool]:
    """Evaluate each sanity check against ``near_coast``.

    Args:
        near_coast: The AOI geometry to test (EPSG:4326).
        checks: Override the default list of checks (used in tests).

    Returns:
        A dict mapping the check name to its boolean outcome (``True`` if
        the assertion holds).
    """
    return {
        check.name: near_coast.contains(check.point()) == check.must_be_inside
        for check in checks
    }
