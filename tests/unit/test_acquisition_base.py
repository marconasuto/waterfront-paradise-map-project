from __future__ import annotations

import hashlib
import json
from pathlib import Path

from manfredonia_map.acquisition import base


def test_now_iso_utc_is_offset_aware():
    s = base.now_iso_utc()
    # ISO 8601 with a UTC offset suffix
    assert s.endswith("+00:00")
    # No microseconds in the canonical form
    assert "." not in s.split("+")[0]


def test_sha256_of_file_matches_hashlib(tmp_path: Path):
    p = tmp_path / "x.bin"
    payload = b"hello world\n"
    p.write_bytes(payload)
    assert base.sha256_of_file(p) == hashlib.sha256(payload).hexdigest()


def test_stamp_provenance_fills_hash_size_and_path(tmp_path: Path):
    p = tmp_path / "raw.bin"
    p.write_bytes(b"abc")
    prov = base.Provenance(
        source_id="x",
        publisher="x",
        dataset="x",
        url="x",
        access_method="x",
        license="x",
        accessed_at="2026-05-23T00:00:00+00:00",
    )
    stamped = base.stamp_provenance(prov, p)
    assert stamped.byte_count == 3
    assert stamped.sha256 == hashlib.sha256(b"abc").hexdigest()
    assert stamped.raw_path == str(p)


def test_write_provenance_writes_json_and_sets_mode(tmp_path: Path):
    sidecar = tmp_path / "x.provenance.json"
    prov = base.Provenance(
        source_id="x",
        publisher="x",
        dataset="x",
        url="x",
        access_method="x",
        license="x",
        accessed_at="2026-05-23T00:00:00+00:00",
        bbox=(1.0, 2.0, 3.0, 4.0),
        query={"k": "v"},
    )
    base.write_provenance(prov, sidecar)
    data = json.loads(sidecar.read_text())
    assert data["source_id"] == "x"
    assert data["bbox"] == [1.0, 2.0, 3.0, 4.0]
    assert data["query"] == {"k": "v"}
    mode = oct(sidecar.stat().st_mode & 0o777)
    assert mode == "0o644"
