"""Mapbox configuration loaded from ``.env`` via pydantic-settings.

The pipeline expects three values, all settable as environment variables
(loaded from the gitignored ``.env`` at the repo root by default):

- ``MAPBOX_SECRET_TOKEN`` (``sk.*``) — pipeline-side token with the
  ``TILESETS:*`` / ``UPLOADS:*`` / ``STYLES:WRITE/LIST`` scopes
  (see ``SPECIFICATIONS.md`` §10 token strategy).
- ``MAPBOX_PUBLIC_TOKEN`` (``pk.*``) — used by the web app only; the
  pipeline doesn't strictly need it but it's stored alongside for
  symmetry.
- ``MAPBOX_USERNAME`` — the account that owns the tokens / tilesets.

This module only *reads* the settings; it never writes them back. The
``.env`` file remains the single editable surface (rotate the secret
token via ``open -e .env``).
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from manfredonia_map.paths import REPO_ROOT


class MapboxSettings(BaseSettings):
    """Mapbox account + token settings, sourced from the environment."""

    secret_token: str = Field(default="", alias="MAPBOX_SECRET_TOKEN")
    public_token: str = Field(default="", alias="MAPBOX_PUBLIC_TOKEN")
    username: str = Field(default="", alias="MAPBOX_USERNAME")

    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    def require_username(self) -> str:
        """Return the username or raise a clear error if unset."""
        if not self.username:
            raise RuntimeError("MAPBOX_USERNAME is not set. Add it to .env (see .env.example).")
        return self.username

    def require_secret_token(self) -> str:
        """Return the secret token or raise a clear error if unset."""
        if not self.secret_token:
            raise RuntimeError("MAPBOX_SECRET_TOKEN is not set. Add it to .env (see .env.example).")
        return self.secret_token


def load_from_env_file(env_file: Path | None = None) -> MapboxSettings:
    """Load :class:`MapboxSettings` from a specific ``.env`` file."""
    if env_file is None:
        return MapboxSettings()
    return MapboxSettings(_env_file=str(env_file))  # type: ignore[call-arg]
