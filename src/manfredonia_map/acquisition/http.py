"""Generic HTTPS file downloader used by source-specific acquisitions.

Streams the body to disk so we never load multi-MB / multi-GB payloads
into memory. Retries on transient errors with exponential backoff
(``tenacity``). Verifies the optional ``expected_sha256`` after writing.

Tests use ``respx`` to mock httpx — no real network ever happens in unit
tests (``tests/conftest.py`` also blocks ``socket.socket`` unless the
test is marked ``@pytest.mark.network``).
"""

from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

_HTTP_ERROR_THRESHOLD = 400


class DownloadError(RuntimeError):
    """Raised when a download cannot be completed (after retries)."""


@retry(
    retry=retry_if_exception_type(
        (httpx.TransportError, httpx.HTTPStatusError, DownloadError)
    ),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=30),
    reraise=True,
)
def download_file(
    url: str,
    out_path: Path,
    *,
    expected_sha256: str | None = None,
    timeout_s: float = 120.0,
    chunk_size: int = 65536,
    headers: dict[str, str] | None = None,
    verify_ssl: bool = True,
) -> str:
    """Download ``url`` to ``out_path`` atomically; return the SHA-256.

    The download is written to a sibling temp file first, then renamed
    via :func:`os.replace` so an interrupted download never leaves a
    half-written ``out_path``. SHA-256 is computed while streaming.

    Args:
        url: Source URL.
        out_path: Destination path. Parent directories are created.
        expected_sha256: If supplied, the download is verified against
            this digest; mismatch raises :class:`DownloadError`.
        timeout_s: Per-request timeout in seconds.
        chunk_size: Stream chunk size in bytes.
        headers: Optional request headers (e.g. a ``User-Agent``).
        verify_ssl: Set to ``False`` to skip TLS certificate
            verification. Required for a handful of academic infra
            (e.g. ``tinitaly.pi.ingv.it`` ships a self-signed cert
            chain Python's default CA bundle does not trust). Always
            pair with an ``expected_sha256`` when used in CI.

    Returns:
        The hex SHA-256 of the downloaded bytes.

    Raises:
        DownloadError: On non-2xx status or SHA mismatch.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    fd, tmp = tempfile.mkstemp(prefix=out_path.name + ".", dir=out_path.parent)
    try:
        with os.fdopen(fd, "wb") as f, httpx.stream(
            "GET",
            url,
            timeout=timeout_s,
            follow_redirects=True,
            headers=headers,
            verify=verify_ssl,
        ) as resp:
            if resp.status_code >= _HTTP_ERROR_THRESHOLD:
                # Drain the body so connections can be re-used.
                resp.read()
                raise DownloadError(f"HTTP {resp.status_code} for {url}")
            for chunk in resp.iter_bytes(chunk_size):
                digest.update(chunk)
                f.write(chunk)
        sha = digest.hexdigest()
        if expected_sha256 is not None and sha != expected_sha256:
            raise DownloadError(
                f"SHA-256 mismatch for {url}: expected {expected_sha256}, got {sha}"
            )
        os.replace(tmp, out_path)
        os.chmod(out_path, 0o644)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return sha
