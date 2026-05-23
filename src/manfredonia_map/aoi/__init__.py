"""AOI builder.

Produces the two project AOI shapes described in ``SPECIFICATIONS.md`` §3:

- ``aoi_buffered`` — source polygon expanded by 1 km in both directions.
- ``aoi_near_coast`` — ``aoi_buffered`` intersected with the union of the
  coastal band and the mandatory features.

All geometric math runs in the analysis CRS (EPSG:32633, UTM 33N) so buffer
distances are true metres; results are re-projected to EPSG:4326 (storage
CRS) before serialization.
"""

from manfredonia_map.aoi import builder, io, sanity

__all__ = ["builder", "io", "sanity"]
