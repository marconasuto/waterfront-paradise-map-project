"""Provenance dataclass + atomic sidecar writer.

Every acquisition writes a tiny ``*.provenance.json`` file next to the raw
artifact. The catalog generator (Phase 3 catalog work) consumes these
sidecars to build ``data/catalog.yaml``.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def now_iso_utc() -> str:
    """Return the current UTC instant as an ISO 8601 string with seconds."""
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat()


def sha256_of_file(path: Path) -> str:
    """Compute the SHA-256 of a file's contents."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass(frozen=True)
class Provenance:
    """Acquisition provenance record persisted next to the raw artifact."""

    source_id: str
    publisher: str
    dataset: str
    url: str
    access_method: str
    license: str
    accessed_at: str
    bbox: tuple[float, float, float, float] | None = None
    query: dict[str, Any] = field(default_factory=dict)
    year_data: int | None = None
    sha256: str | None = None
    byte_count: int | None = None
    raw_path: str | None = None


def write_provenance(prov: Provenance, sidecar_path: Path) -> None:
    """Atomically write a ``Provenance`` record as JSON."""
    sidecar_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=sidecar_path.name + ".", dir=sidecar_path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(asdict(prov), f, indent=2, sort_keys=True, ensure_ascii=False)
            f.write("\n")
        os.replace(tmp, sidecar_path)
        os.chmod(sidecar_path, 0o644)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def stamp_provenance(prov: Provenance, raw_path: Path) -> Provenance:
    """Return a copy of ``prov`` with ``sha256`` / ``byte_count`` / ``raw_path`` filled in."""
    return Provenance(
        source_id=prov.source_id,
        publisher=prov.publisher,
        dataset=prov.dataset,
        url=prov.url,
        access_method=prov.access_method,
        license=prov.license,
        accessed_at=prov.accessed_at,
        bbox=prov.bbox,
        query=prov.query,
        year_data=prov.year_data,
        sha256=sha256_of_file(raw_path),
        byte_count=raw_path.stat().st_size,
        raw_path=str(raw_path),
    )
