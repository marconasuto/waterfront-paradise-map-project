from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx
from click.testing import CliRunner

from manfredonia_map.publishing import cli as pub_cli
from manfredonia_map.publishing import manifest as manifest_mod
from manfredonia_map.publishing import uploads_api

# --- low-level client steps -----------------------------------------


def _client(
    *,
    http: httpx.Client | None = None,
    s3_put: uploads_api.S3Putter | None = None,
) -> uploads_api.MapboxUploadsClient:
    return uploads_api.MapboxUploadsClient(
        username="tester",
        secret_token="sk.fake",
        http=http,
        s3_put=s3_put or (lambda **_: None),
        poll_interval_s=0.0,
        poll_timeout_s=10.0,
    )


def test_client_requires_username():
    with pytest.raises(ValueError, match="username"):
        uploads_api.MapboxUploadsClient(username="", secret_token="sk.x")


def test_client_requires_secret_token():
    with pytest.raises(ValueError, match="secret_token"):
        uploads_api.MapboxUploadsClient(username="u", secret_token="")


def test_get_s3_credentials_parses_payload(respx_mock: respx.Router):
    url = "https://api.mapbox.com/uploads/v1/tester/credentials"
    respx_mock.post(url).mock(
        return_value=httpx.Response(
            200,
            json={
                "bucket": "tilestream-uploads",
                "key": "abc/def.mbtiles",
                "url": "http://s3.example/tilestream-uploads/abc/def.mbtiles",
                "accessKeyId": "AKIA",
                "secretAccessKey": "SECRET",
                "sessionToken": "TOKEN",
            },
        ),
    )
    c = _client()
    creds = c.get_s3_credentials()
    assert creds.bucket == "tilestream-uploads"
    assert creds.session_token == "TOKEN"


def test_get_s3_credentials_raises_on_http_error(respx_mock: respx.Router):
    url = "https://api.mapbox.com/uploads/v1/tester/credentials"
    respx_mock.post(url).mock(return_value=httpx.Response(401, json={"message": "bad"}))
    c = _client()
    with pytest.raises(uploads_api.MapboxUploadError, match="HTTP 401"):
        c.get_s3_credentials()


def test_upload_to_s3_delegates_to_s3_put(tmp_path: Path):
    payload = tmp_path / "x.mbtiles"
    payload.write_bytes(b"PK\x03\x04")
    captured: dict[str, Any] = {}

    def _capture(*, file_path: Path, creds: uploads_api.S3Credentials) -> None:
        captured["file_path"] = file_path
        captured["bucket"] = creds.bucket

    c = _client(s3_put=_capture)
    creds = uploads_api.S3Credentials(
        bucket="b",
        key="k",
        url="u",
        access_key_id="a",
        secret_access_key="s",
        session_token="t",
    )
    c.upload_to_s3(payload, creds)
    assert captured["file_path"] == payload
    assert captured["bucket"] == "b"


def test_upload_to_s3_raises_when_file_missing(tmp_path: Path):
    c = _client()
    creds = uploads_api.S3Credentials(
        bucket="b",
        key="k",
        url="u",
        access_key_id="a",
        secret_access_key="s",
        session_token="t",
    )
    with pytest.raises(FileNotFoundError):
        c.upload_to_s3(tmp_path / "missing.bin", creds)


def test_create_upload_sends_expected_body(respx_mock: respx.Router):
    url = "https://api.mapbox.com/uploads/v1/tester"
    route = respx_mock.post(url).mock(return_value=httpx.Response(201, json={"id": "u1"}))
    c = _client()
    result = c.create_upload(
        s3_url="https://s3/tilestream/abc",
        tileset_id="manfredonia-roads-v1",
        name="roads",
    )
    assert result == {"id": "u1"}
    sent_body = json.loads(route.calls.last.request.content)
    assert sent_body == {
        "tileset": "tester.manfredonia-roads-v1",
        "url": "https://s3/tilestream/abc",
        "name": "roads",
    }


def test_create_upload_raises_on_http_error(respx_mock: respx.Router):
    url = "https://api.mapbox.com/uploads/v1/tester"
    respx_mock.post(url).mock(return_value=httpx.Response(400, text="bad request"))
    c = _client()
    with pytest.raises(uploads_api.MapboxUploadError, match="HTTP 400"):
        c.create_upload(s3_url="https://s3/x", tileset_id="t", name="n")


def test_get_upload_status_returns_payload(respx_mock: respx.Router):
    url = "https://api.mapbox.com/uploads/v1/tester/u1"
    respx_mock.get(url).mock(
        return_value=httpx.Response(200, json={"complete": False, "progress": 0.5}),
    )
    c = _client()
    assert c.get_upload_status("u1") == {"complete": False, "progress": 0.5}


def test_get_upload_status_raises_on_http_error(respx_mock: respx.Router):
    url = "https://api.mapbox.com/uploads/v1/tester/u1"
    respx_mock.get(url).mock(return_value=httpx.Response(404, text="not found"))
    c = _client()
    with pytest.raises(uploads_api.MapboxUploadError, match="HTTP 404"):
        c.get_upload_status("u1")


# --- publish() orchestration ---------------------------------------


def _seed_publish_endpoints(
    respx_mock: respx.Router,
    *,
    statuses: list[dict[str, Any]],
) -> None:
    """Wire credentials + create + status routes for a happy-path publish."""
    respx_mock.post(
        "https://api.mapbox.com/uploads/v1/tester/credentials",
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "bucket": "b",
                "key": "k",
                "url": "https://s3/abc",
                "accessKeyId": "A",
                "secretAccessKey": "S",
                "sessionToken": "T",
            },
        )
    )
    respx_mock.post(
        "https://api.mapbox.com/uploads/v1/tester",
    ).mock(return_value=httpx.Response(201, json={"id": "u1"}))
    status_route = respx_mock.get(
        "https://api.mapbox.com/uploads/v1/tester/u1",
    )
    status_route.side_effect = [httpx.Response(200, json=payload) for payload in statuses]


def test_publish_happy_path_returns_complete_result(tmp_path: Path, respx_mock: respx.Router):
    payload = tmp_path / "roads.mbtiles"
    payload.write_bytes(b"PK\x03\x04")
    s3_calls: list[Path] = []

    _seed_publish_endpoints(
        respx_mock,
        statuses=[
            {"complete": False, "progress": 0.5},
            {"complete": True, "progress": 1.0},
        ],
    )
    c = _client(s3_put=lambda **kw: s3_calls.append(kw["file_path"]))
    result = c.publish(payload, tileset_id="manfredonia-roads-v1", name="roads")
    assert result.complete is True
    assert result.error is None
    assert result.tileset_id == "manfredonia-roads-v1"
    assert s3_calls == [payload]


def test_publish_surface_error_from_status(tmp_path: Path, respx_mock: respx.Router):
    payload = tmp_path / "x.mbtiles"
    payload.write_bytes(b"x")
    _seed_publish_endpoints(
        respx_mock,
        statuses=[
            {"complete": True, "error": "invalid tileset id", "progress": 0.0},
        ],
    )
    c = _client()
    result = c.publish(payload, tileset_id="t", name="x")
    assert result.complete is True
    assert result.error == "invalid tileset id"


def test_publish_times_out_when_never_complete(tmp_path: Path, respx_mock: respx.Router):
    payload = tmp_path / "x.mbtiles"
    payload.write_bytes(b"x")
    _seed_publish_endpoints(
        respx_mock,
        statuses=[{"complete": False, "progress": 0.1}] * 50,
    )
    fake_clock = {"t": 0.0}

    def _sleep(s: float) -> None:
        fake_clock["t"] += s

    def _now() -> float:
        return fake_clock["t"]

    c = uploads_api.MapboxUploadsClient(
        username="tester",
        secret_token="sk.x",
        s3_put=lambda **_: None,
        poll_interval_s=10.0,
        poll_timeout_s=15.0,
    )
    with pytest.raises(uploads_api.MapboxUploadError, match="did not complete"):
        c.publish(
            payload,
            tileset_id="t",
            name="x",
            sleep=_sleep,
            now=_now,
        )


def test_publish_raises_when_file_missing(tmp_path: Path):
    c = _client()
    with pytest.raises(FileNotFoundError):
        c.publish(tmp_path / "nope.bin", tileset_id="t", name="x")


def test_publish_handles_non_numeric_progress(tmp_path: Path, respx_mock: respx.Router):
    payload = tmp_path / "x.bin"
    payload.write_bytes(b"x")
    _seed_publish_endpoints(
        respx_mock,
        statuses=[{"complete": True, "progress": "weird"}],
    )
    c = _client()
    result = c.publish(payload, tileset_id="t", name="x")
    assert result.progress == 0.0


# --- CLI dry-run ----------------------------------------------------


def _seed_manifest_file(tmp_path: Path) -> Path:
    entries = [
        manifest_mod.ManifestEntry(
            layer_id="coastline",
            layer_type="vector",
            source_id="osm_coastline",
            mapbox_tileset_id="manfredonia-coastline-v1",
            mapbox_tileset_url="mapbox://tileset/tester.manfredonia-coastline-v1",
            input_path=str(tmp_path / "coastline.mbtiles"),
            input_sha256="0" * 64,
            description="d",
            attribution="a",
            mapbox_studio_url="https://studio.mapbox.com/x",
        ),
        manifest_mod.ManifestEntry(
            layer_id="dtm",
            layer_type="raster",
            source_id="t",
            mapbox_tileset_id="manfredonia-dtm-v1",
            mapbox_tileset_url="mapbox://tileset/tester.manfredonia-dtm-v1",
            input_path=str(tmp_path / "dtm.tif"),
            input_sha256="0" * 64,
            description="d",
            attribution="a",
            mapbox_studio_url="https://studio.mapbox.com/y",
        ),
    ]
    (tmp_path / "coastline.mbtiles").write_bytes(b"PK\x03\x04")
    (tmp_path / "dtm.tif").write_bytes(b"II*\x00")
    out = tmp_path / "manifest.yaml"
    manifest_mod.write(entries, out)
    return out


def test_cli_publish_upload_dry_run_makes_no_api_calls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("MAPBOX_USERNAME", "tester")
    monkeypatch.setenv("MAPBOX_SECRET_TOKEN", "sk.x")
    manifest_path = _seed_manifest_file(tmp_path)

    def _boom(*args: object, **kwargs: object) -> None:
        raise AssertionError("no HTTP calls should be made in dry-run mode")

    monkeypatch.setattr(httpx, "Client", _boom)

    result = CliRunner().invoke(
        pub_cli.publish_upload,
        ["--manifest", str(manifest_path)],  # default is --dry-run
    )
    assert result.exit_code == 0, result.output
    assert "DRY RUN" in result.output
    assert "coastline" in result.output
    assert "dtm" in result.output


def test_cli_publish_upload_only_and_skip_filters(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MAPBOX_USERNAME", "tester")
    monkeypatch.setenv("MAPBOX_SECRET_TOKEN", "sk.x")
    manifest_path = _seed_manifest_file(tmp_path)

    result = CliRunner().invoke(
        pub_cli.publish_upload,
        ["--manifest", str(manifest_path), "--only", "coastline"],
    )
    assert result.exit_code == 0, result.output
    assert "coastline" in result.output
    assert "dtm" not in result.output

    result = CliRunner().invoke(
        pub_cli.publish_upload,
        ["--manifest", str(manifest_path), "--skip", "coastline", "--skip", "dtm"],
    )
    assert result.exit_code == 0, result.output
    assert "nothing to upload" in result.output


def test_cli_publish_upload_no_dry_run_invokes_client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("MAPBOX_USERNAME", "tester")
    monkeypatch.setenv("MAPBOX_SECRET_TOKEN", "sk.x")
    manifest_path = _seed_manifest_file(tmp_path)

    publish_calls: list[dict[str, Any]] = []

    class _FakeClient:
        def __init__(self, **_kwargs: object) -> None: ...
        def publish(
            self,
            file_path: Path,
            *,
            tileset_id: str,
            name: str,
            **_: object,
        ) -> uploads_api.UploadResult:
            publish_calls.append(
                {"file_path": file_path, "tileset_id": tileset_id, "name": name},
            )
            return uploads_api.UploadResult(
                upload_id="u",
                tileset_id=tileset_id,
                name=name,
                complete=True,
                error=None,
                progress=1.0,
            )

    monkeypatch.setattr(pub_cli.uploads_mod, "MapboxUploadsClient", _FakeClient)

    result = CliRunner().invoke(
        pub_cli.publish_upload,
        ["--manifest", str(manifest_path), "--no-dry-run"],
    )
    assert result.exit_code == 0, result.output
    assert len(publish_calls) == 2
    assert "uploaded 2/2 successfully" in result.output


def test_cli_publish_upload_reports_failures(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MAPBOX_USERNAME", "tester")
    monkeypatch.setenv("MAPBOX_SECRET_TOKEN", "sk.x")
    manifest_path = _seed_manifest_file(tmp_path)

    class _BoomClient:
        def __init__(self, **_kwargs: object) -> None: ...
        def publish(
            self,
            file_path: Path,
            *,
            tileset_id: str,
            name: str,
            **_: object,
        ) -> uploads_api.UploadResult:
            raise uploads_api.MapboxUploadError("kaboom")

    monkeypatch.setattr(pub_cli.uploads_mod, "MapboxUploadsClient", _BoomClient)
    result = CliRunner().invoke(
        pub_cli.publish_upload,
        ["--manifest", str(manifest_path), "--no-dry-run"],
    )
    assert result.exit_code != 0
    assert "uploads failed for" in result.output
