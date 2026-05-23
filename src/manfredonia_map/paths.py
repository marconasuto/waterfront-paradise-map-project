"""Repo-relative paths used across the pipeline.

Resolved from this file's location (``src/manfredonia_map/paths.py``).
``REPO_ROOT`` is therefore three ``parents`` up. Importing this module is
side-effect-free; nothing is created on disk.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT: Path = Path(__file__).resolve().parents[2]

CONFIG_DIR: Path = REPO_ROOT / "config"
DATA_DIR: Path = REPO_ROOT / "data"
DATA_RAW: Path = DATA_DIR / "raw"
DATA_INTERIM: Path = DATA_DIR / "interim"
DATA_PROCESSED: Path = DATA_DIR / "processed"
CONTENT_DIR: Path = REPO_ROOT / "content"
DOCS_DIR: Path = REPO_ROOT / "docs"
PLANS_DIR: Path = REPO_ROOT / "plans"

__all__ = [
    "CONFIG_DIR",
    "CONTENT_DIR",
    "DATA_DIR",
    "DATA_INTERIM",
    "DATA_PROCESSED",
    "DATA_RAW",
    "DOCS_DIR",
    "PLANS_DIR",
    "REPO_ROOT",
]
