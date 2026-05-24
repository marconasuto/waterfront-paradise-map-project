from __future__ import annotations

import hashlib
from pathlib import Path

import httpx
import pytest
import respx

from manfredonia_map.acquisition import http as acq_http


def test_download_file_streams_to_path_and_returns_sha(
    tmp_path: Path, respx_mock: respx.Router
) -> None:
    payload = b"hello-world\n" * 1000
    url = "https://example.test/file.zip"
    respx_mock.get(url).mock(return_value=httpx.Response(200, content=payload))

    out = tmp_path / "nested" / "file.zip"
    sha = acq_http.download_file(url, out)

    assert out.exists()
    assert out.read_bytes() == payload
    assert sha == hashlib.sha256(payload).hexdigest()
    assert oct(out.stat().st_mode & 0o777) == "0o644"


def test_download_file_verifies_expected_sha(
    tmp_path: Path, respx_mock: respx.Router
) -> None:
    payload = b"x" * 1024
    url = "https://example.test/x.zip"
    respx_mock.get(url).mock(return_value=httpx.Response(200, content=payload))

    expected = hashlib.sha256(payload).hexdigest()
    sha = acq_http.download_file(url, tmp_path / "x.zip", expected_sha256=expected)
    assert sha == expected


def test_download_file_raises_on_sha_mismatch(
    tmp_path: Path, respx_mock: respx.Router
) -> None:
    payload = b"abc"
    url = "https://example.test/y.zip"
    respx_mock.get(url).mock(return_value=httpx.Response(200, content=payload))

    out = tmp_path / "y.zip"
    with pytest.raises(acq_http.DownloadError, match="SHA-256 mismatch"):
        acq_http.download_file(url, out, expected_sha256="0" * 64)

    # The temp file should have been cleaned up after the failure.
    siblings = [p for p in out.parent.iterdir() if p.name.startswith(out.name)]
    assert siblings == []


def test_download_file_raises_on_http_error(
    tmp_path: Path, respx_mock: respx.Router
) -> None:
    url = "https://example.test/missing.zip"
    respx_mock.get(url).mock(return_value=httpx.Response(404))

    with pytest.raises(acq_http.DownloadError, match="HTTP 404"):
        acq_http.download_file(url, tmp_path / "missing.zip")


def test_download_file_passes_custom_headers(
    tmp_path: Path, respx_mock: respx.Router
) -> None:
    url = "https://example.test/hdr.zip"
    route = respx_mock.get(url).mock(return_value=httpx.Response(200, content=b"ok"))
    acq_http.download_file(
        url,
        tmp_path / "hdr.zip",
        headers={"User-Agent": "mfd-map-tests/0.0"},
    )
    request = route.calls.last.request
    assert request.headers["user-agent"] == "mfd-map-tests/0.0"
