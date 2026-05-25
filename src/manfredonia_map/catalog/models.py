"""Pydantic schemas for the data catalog.

These models define the shape of ``data/catalog.yaml`` and double as the
validation contract for ``mfd-map catalog validate``.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

#: Bumped whenever the catalog schema changes incompatibly.
SCHEMA_VERSION = 1


class _StrictModel(BaseModel):
    """Common pydantic config: reject unknown fields, freeze on construction."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class AoiInfo(_StrictModel):
    """Pinned AOI shapes the catalog was generated against."""

    source_path: str
    buffered_path: str
    near_coast_path: str
    alias_path: str
    buffer_m: float
    coastal_band_m: float
    source_sha256: str
    buffered_sha256: str
    near_coast_sha256: str
    alias_sha256: str


class Source(_StrictModel):
    """One raw artifact + its provenance."""

    source_id: str
    publisher: str
    dataset: str
    url: str
    access_method: str
    license: str
    accessed_at: str
    raw_path: str
    sha256: str
    byte_count: int
    bbox: tuple[float, float, float, float] | None = None
    year_data: int | None = None


class VectorLayer(_StrictModel):
    """One processed vector layer (per-layer GeoJSON under ``data/processed/``)."""

    layer_id: str
    type: Literal["vector"] = "vector"
    source_id: str | None
    processed_path: str
    processed_sha256: str
    feature_count: int
    geom_types: list[str] = Field(default_factory=list)
    category: str | None = None
    year_data: int | None = None


class RasterLayer(_StrictModel):
    """One processed raster (8-bit COG under ``data/processed/``)."""

    layer_id: str
    type: Literal["raster"] = "raster"
    source_id: str | None
    processed_path: str
    processed_sha256: str
    width: int
    height: int
    bands: int
    crs: str
    derived_from: str | None = None


class Catalog(_StrictModel):
    """Top-level catalog model."""

    version: int = SCHEMA_VERSION
    generated_at: str
    aoi: AoiInfo
    sources: list[Source]
    vector_layers: list[VectorLayer]
    raster_layers: list[RasterLayer]


__all__ = [
    "SCHEMA_VERSION",
    "AoiInfo",
    "Catalog",
    "RasterLayer",
    "Source",
    "VectorLayer",
]
