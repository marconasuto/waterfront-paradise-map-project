"""Promote real perimeters into the AOI builder's mandatory-features set.

The AOI builder (``aoi.cli.build_aoi``) accepts two kinds of mandatory
inputs:

- Buffered points from ``config/mandatory_locations.yaml`` — used as a
  rough fallback when a real perimeter is not yet available.
- Polygon GeoJSONs under ``data/processed/mandatory_for_aoi/`` — taken
  as-is, no buffering needed.

This module lifts already-processed layers (``data/processed/<layer>.geojson``)
into ``data/processed/mandatory_for_aoi/<feature_id>.geojson`` so the
near-coast AOI tightens up around the actual feature outlines instead
of the rough buffered points. Each promotion is a small spec entry in
:data:`PROMOTIONS`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd

from manfredonia_map.paths import DATA_PROCESSED
from manfredonia_map.processing import base


@dataclass(frozen=True)
class MandatoryPromotionSpec:
    """How to extract one named feature from a processed layer."""

    feature_id: str
    layer_id: str
    name_filter_substring: str | None = None
    buffer_m: float = 0.0

    def out_filename(self) -> str:
        """Filename written under ``data/processed/mandatory_for_aoi/``."""
        return f"{self.feature_id}.geojson"


#: Registry of mandatory-feature promotions.
#:
#: Order matters only for log readability — each entry is independent.
#: New entries land here once an upstream layer can replace a buffered
#: point in ``config/mandatory_locations.yaml``.
PROMOTIONS: dict[str, MandatoryPromotionSpec] = {
    "lago_salso": MandatoryPromotionSpec(
        feature_id="lago_salso",
        layer_id="wetlands",
        name_filter_substring="lago salso",
    ),
    "sin_manfredonia": MandatoryPromotionSpec(
        feature_id="sin_manfredonia",
        layer_id="sin_manfredonia",
        # Whole layer — the normalizer already filtered to
        # SITO == "MANFREDONIA".
        name_filter_substring=None,
    ),
    "grotta_scaloria": MandatoryPromotionSpec(
        feature_id="grotta_scaloria",
        layer_id="archeological_areas",
        name_filter_substring="grotta scaloria",
        # OSM stores Grotta Scaloria as a Point; buffer to a small
        # polygon so the AOI builder has something with area to union.
        buffer_m=300.0,
    ),
}


def _filter_by_name(gdf: gpd.GeoDataFrame, needle: str) -> gpd.GeoDataFrame:
    """Case-insensitive substring match on ``name_it``."""
    if "name_it" not in gdf.columns:
        return gdf.iloc[:0]
    names = gdf["name_it"].astype("string").str.lower()
    return gdf[names.str.contains(needle.lower(), na=False)].copy()


def _buffer_metric(gdf: gpd.GeoDataFrame, buffer_m: float) -> gpd.GeoDataFrame:
    """Buffer ``gdf`` by ``buffer_m`` metres (via EPSG:32633 round-trip)."""
    if buffer_m <= 0:
        return gdf
    metric = gdf.to_crs(base.ANALYSIS_CRS).copy()
    metric["geometry"] = metric.geometry.buffer(buffer_m)
    return metric.to_crs(base.STORAGE_CRS)


def promote(
    spec: MandatoryPromotionSpec,
    processed_dir: Path = DATA_PROCESSED,
    out_dir: Path | None = None,
) -> Path:
    """Run one :class:`MandatoryPromotionSpec` and write the polygon GeoJSON.

    Args:
        spec: Promotion spec.
        processed_dir: Directory holding the per-layer processed GeoJSONs.
        out_dir: Destination. Defaults to ``processed_dir/mandatory_for_aoi``.

    Returns:
        The output path.

    Raises:
        FileNotFoundError: When the upstream processed layer is missing.
        ValueError: When no features match the filter.
    """
    src = processed_dir / f"{spec.layer_id}.geojson"
    if not src.exists():
        raise FileNotFoundError(
            f"processed layer not found: {src} — run `mfd-map process vector "
            f"{spec.layer_id}` first."
        )
    gdf = gpd.read_file(src)
    if spec.name_filter_substring is not None:
        gdf = _filter_by_name(gdf, spec.name_filter_substring)
        if gdf.empty:
            raise ValueError(
                f"no features matched name_filter_substring={spec.name_filter_substring!r} in {src}"
            )
    gdf = _buffer_metric(gdf, spec.buffer_m)
    target_dir = out_dir if out_dir is not None else processed_dir / "mandatory_for_aoi"
    out = target_dir / spec.out_filename()
    base.write_layer_geojson(gdf, out)
    return out
