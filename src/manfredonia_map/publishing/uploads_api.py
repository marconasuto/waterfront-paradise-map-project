"""Mapbox Uploads API client.

The Uploads API is a uniform path for both vector MBTiles and raster
GeoTIFFs (per ``docs/research/mapbox.md``). It is a three-step dance:

1. Ask Mapbox for **temporary AWS S3 credentials** scoped to a single
   bucket/key (POST ``/uploads/v1/<user>/credentials``).
2. **PUT the file to S3** using those credentials (SigV4 signed; we use
   ``boto3`` since hand-rolling SigV4 is its own project).
3. **POST the upload spec** to Mapbox (``/uploads/v1/<user>``) telling it
   which S3 URL to ingest and which tileset id to publish to.

Then poll ``GET /uploads/v1/<user>/<upload_id>`` until ``complete`` is
true (or ``error`` is set).

The MTS path is preferred for richer recipes / re-tile control; the
Uploads path is simpler and fits our v1 fine since we already have
deterministic local MBTiles + 8-bit COGs from Phase 5a.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import httpx

logger = logging.getLogger(__name__)

#: Mapbox API host (no trailing slash).
MAPBOX_HOST = "https://api.mapbox.com"

#: Polling cadence + ceiling for the upload status check (per call).
_POLL_INTERVAL_S = 5.0
_POLL_TIMEOUT_S = 30 * 60.0  # 30 min — generous; small layers finish in seconds

#: Any HTTP status at this threshold or above is treated as an API error.
_HTTP_ERROR_STATUS = 400


class MapboxUploadError(RuntimeError):
    """Mapbox Uploads API returned an error or timed out."""


@dataclass(frozen=True)
class S3Credentials:
    """Temporary AWS credentials returned by Mapbox for a single upload."""

    bucket: str
    key: str
    url: str
    access_key_id: str
    secret_access_key: str
    session_token: str


@dataclass(frozen=True)
class UploadResult:
    """Outcome of one Uploads API call."""

    upload_id: str
    tileset_id: str
    name: str
    complete: bool
    error: str | None
    progress: float


class S3Putter(Protocol):
    """Test seam — anything that knows how to PUT bytes to an S3 key."""

    def __call__(self, *, file_path: Path, creds: S3Credentials) -> None:
        """Upload ``file_path`` to ``creds.bucket``/``creds.key``."""


def _default_s3_put(*, file_path: Path, creds: S3Credentials) -> None:
    """Default ``S3Putter`` using ``boto3``."""
    import boto3  # noqa: PLC0415  # heavy; only import at runtime

    s3 = boto3.client(
        "s3",
        aws_access_key_id=creds.access_key_id,
        aws_secret_access_key=creds.secret_access_key,
        aws_session_token=creds.session_token,
    )
    with file_path.open("rb") as f:
        s3.upload_fileobj(f, creds.bucket, creds.key)


class MapboxUploadsClient:
    """Thin Uploads API wrapper. Inject ``http`` and ``s3_put`` for tests."""

    def __init__(
        self,
        *,
        username: str,
        secret_token: str,
        http: httpx.Client | None = None,
        s3_put: S3Putter = _default_s3_put,
        poll_interval_s: float = _POLL_INTERVAL_S,
        poll_timeout_s: float = _POLL_TIMEOUT_S,
        host: str = MAPBOX_HOST,
    ) -> None:
        """Construct the client; validate that username + secret_token are set."""
        if not username:
            raise ValueError("username is required (set MAPBOX_USERNAME in .env)")
        if not secret_token:
            raise ValueError("secret_token is required (set MAPBOX_SECRET_TOKEN in .env)")
        self.username = username
        self.secret_token = secret_token
        self.http = http or httpx.Client(
            timeout=120.0,
            headers={"User-Agent": "manfredonia-map/0.0.1 (publishing pipeline)"},
        )
        self.s3_put = s3_put
        self.poll_interval_s = poll_interval_s
        self.poll_timeout_s = poll_timeout_s
        self.host = host.rstrip("/")

    # --- low-level steps ----------------------------------------------

    def get_s3_credentials(self) -> S3Credentials:
        """Step 1 — ask Mapbox for temp S3 credentials."""
        resp = self.http.post(
            f"{self.host}/uploads/v1/{self.username}/credentials",
            params={"access_token": self.secret_token},
        )
        if resp.status_code >= _HTTP_ERROR_STATUS:
            raise MapboxUploadError(
                f"credentials request failed: HTTP {resp.status_code} {resp.text!r}"
            )
        payload = resp.json()
        return S3Credentials(
            bucket=payload["bucket"],
            key=payload["key"],
            url=payload["url"],
            access_key_id=payload["accessKeyId"],
            secret_access_key=payload["secretAccessKey"],
            session_token=payload["sessionToken"],
        )

    def upload_to_s3(self, file_path: Path, creds: S3Credentials) -> None:
        """Step 2 — PUT the file to the Mapbox-controlled S3 bucket."""
        if not file_path.is_file():
            raise FileNotFoundError(file_path)
        self.s3_put(file_path=file_path, creds=creds)

    def create_upload(self, *, s3_url: str, tileset_id: str, name: str) -> dict[str, Any]:
        """Step 3 — tell Mapbox which S3 URL to ingest and where to publish."""
        body = {
            "tileset": f"{self.username}.{tileset_id}",
            "url": s3_url,
            "name": name,
        }
        resp = self.http.post(
            f"{self.host}/uploads/v1/{self.username}",
            params={"access_token": self.secret_token},
            json=body,
        )
        if resp.status_code >= _HTTP_ERROR_STATUS:
            raise MapboxUploadError(f"upload create failed: HTTP {resp.status_code} {resp.text!r}")
        return resp.json()

    def get_upload_status(self, upload_id: str) -> dict[str, Any]:
        """Poll for the current state of an in-progress upload."""
        resp = self.http.get(
            f"{self.host}/uploads/v1/{self.username}/{upload_id}",
            params={"access_token": self.secret_token},
        )
        if resp.status_code >= _HTTP_ERROR_STATUS:
            raise MapboxUploadError(f"status request failed: HTTP {resp.status_code} {resp.text!r}")
        return resp.json()

    # --- orchestration ------------------------------------------------

    def publish(
        self,
        file_path: Path,
        *,
        tileset_id: str,
        name: str,
        sleep: Any = time.sleep,
        now: Any = time.monotonic,
    ) -> UploadResult:
        """Run the full upload + poll dance for one file."""
        if not file_path.is_file():
            raise FileNotFoundError(file_path)
        logger.info("Mapbox upload: %s → %s.%s", file_path.name, self.username, tileset_id)
        creds = self.get_s3_credentials()
        self.upload_to_s3(file_path, creds)
        created = self.create_upload(s3_url=creds.url, tileset_id=tileset_id, name=name)
        upload_id = str(created["id"])
        return self._poll_until_done(upload_id, tileset_id, name, sleep=sleep, now=now)

    def _poll_until_done(
        self,
        upload_id: str,
        tileset_id: str,
        name: str,
        *,
        sleep: Any,
        now: Any,
    ) -> UploadResult:
        """Poll status until ``complete`` or ``error``; return the final state."""
        deadline = now() + self.poll_timeout_s
        while True:
            status = self.get_upload_status(upload_id)
            complete = bool(status.get("complete"))
            error_msg = status.get("error")
            progress_raw = status.get("progress", 0.0)
            try:
                progress = float(progress_raw)
            except (TypeError, ValueError):
                progress = 0.0
            if complete or error_msg:
                return UploadResult(
                    upload_id=upload_id,
                    tileset_id=tileset_id,
                    name=name,
                    complete=complete,
                    error=str(error_msg) if error_msg else None,
                    progress=progress,
                )
            if now() >= deadline:
                raise MapboxUploadError(
                    f"upload {upload_id} did not complete within "
                    f"{self.poll_timeout_s:.0f}s (last progress={progress})"
                )
            sleep(self.poll_interval_s)
