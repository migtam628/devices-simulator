"""Retention is opt-in, scoped to existing capture directories and auditable."""
import http.client
import json
import os
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from lulwa_virtual_printer.retention import retention_preview, retention_cleanup
from lulwa_virtual_printer import hub


NOW = datetime(2026, 10, 31, tzinfo=timezone.utc)


def fixture(root, name, days_ago, *, profile="zebra"):
    directory = root / profile / name
    directory.mkdir(parents=True)
    (directory / "job.json").write_text(json.dumps({
        "id": name, "profile": profile,
        "created_at": (NOW - timedelta(days=days_ago)).isoformat(),
        "status": "rendered", "images": ["page-001.jpg"],
    }), encoding="utf-8")
    (directory / "original.pdf").write_bytes(b"%PDF-1.4 /test")
    (directory / "page-001.jpg").write_bytes(b"\xff\xd8\xff sample")
    return directory


def test_preview_does_not_delete_and_cleanup_only_removes_old_capture(tmp_path):
    root = tmp_path / "out"
    old = fixture(root, "old", 130)
    recent = fixture(root, "recent", 12)
    preview = retention_preview(root, 90, now=NOW)
    assert preview["eligible_jobs"] == preview["batch_jobs"] == 1
    assert old.is_dir() and recent.is_dir()
    with pytest.raises(ValueError, match="confirmation"):
        retention_cleanup(root, 90, preview["fingerprint"], now=NOW)
    result = retention_cleanup(root, 90, preview["fingerprint"], confirm=True, now=NOW)
    assert result["deleted_jobs"] == 1 and result["deleted_bytes"] > 0
    assert not old.exists() and recent.is_dir()
    assert list(recent.iterdir())


def test_wrong_fingerprint_and_changed_capture_block_deletion(tmp_path):
    root = tmp_path/"out"
    target = fixture(root, "old", 130)
    preview = retention_preview(root, 90, now=NOW)
    with pytest.raises(RuntimeError, match="changed"):
        retention_cleanup(root, 90, "0"*64, confirm=True, now=NOW)
    (target/"extra.log").write_text("user changed data", encoding="utf-8")
    with pytest.raises(RuntimeError, match="changed"):
        retention_cleanup(root, 90, preview["fingerprint"], confirm=True, now=NOW)
    assert target.is_dir()


def test_invalid_age_and_fingerprint_rejected(tmp_path):
    root = tmp_path/"out"
    fixture(root, "old", 130)
    for age in (None, True, 0, 3651, "90", 1.5, -30):
        with pytest.raises(ValueError, match="days"):
            retention_preview(root, age, now=NOW)
    with pytest.raises(ValueError, match="fingerprint"):
        retention_cleanup(root, 90, "wrong", confirm=True, now=NOW)


def test_unrecognized_profiles_and_invalid_job_metadata_untouched(tmp_path):
    root = tmp_path / "out"
    wrong = fixture(root, "outsider", 200, profile="other")
    malformed = fixture(root, "bad-date", 140)
    raw = json.loads((malformed/"job.json").read_text())
    raw["created_at"] = "broken"
    (malformed/"job.json").write_text(json.dumps(raw), encoding="utf-8")
    preview = retention_preview(root, 90, now=NOW)
    assert preview["batch_jobs"] == 0
    result = retention_cleanup(root, 90, preview["fingerprint"], confirm=True, now=NOW)
    assert result["deleted_jobs"] == 0 and wrong.exists() and malformed.exists()


def test_symlinked_capture_directory_is_never_followed(tmp_path):
    root = tmp_path/"out"
    safe = fixture(root, "old", 130)
    external = tmp_path / "outside"
    external.mkdir()
    (external/"protected.txt").write_text("do not remove", encoding="utf-8")
    try:
        (safe/"jump").symlink_to(external, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("Symlink creation unavailable on runner")
    assert retention_preview(root, 90, now=NOW)["batch_jobs"] == 0
    assert safe.exists() and (external/"protected.txt").exists()


def test_no_automatic_cleanup_and_fingerprint_deterministic(tmp_path):
    root = tmp_path/"out"
    fixture(root, "first", 190)
    one=retention_preview(root, 90, now=NOW)
    two=retention_preview(root, 90, now=NOW)
    assert one["fingerprint"] == two["fingerprint"]
    assert (root/"zebra"/"first").exists()


def test_authenticated_preview_and_explicit_cleanup(tmp_path,monkeypatch):
    server=hub.create_server(port=0,state_dir=tmp_path/"state",output_dir=tmp_path/"jobs")
    worker=threading.Thread(target=server.serve_forever,daemon=True)
    worker.start()
    # This age is relative to a real system, so use a 2020 creation time.
    job_dir=server.hub_store.output_dir/"zebra"/"old"
    job_dir.mkdir(parents=True)
    (job_dir/"job.json").write_text(json.dumps({"id":"old","profile":"zebra",
        "created_at":"2020-01-01T00:00:00+00:00","images":[]}),encoding="utf-8")
    (job_dir/"page-001.jpg").write_bytes(b"jpeg")
    connection=http.client.HTTPConnection("127.0.0.1",server.server_port,timeout=10)
    def post(path,body,auth=True):
        headers={"Content-Type":"application/json"}
        if auth:
            headers["X-Devices-Token"]=server.hub_token
        connection.request("POST",path,json.dumps(body),headers)
        response=connection.getresponse()
        return response.status,json.loads(response.read())
    try:
        route="/api/system/retention/"
        assert post(route+"preview",{"days":30},False)[0]==403
        status,result=post(route+"preview",{"days":30})
        assert status==200 and result["preview"]["batch_jobs"]==1
        token=result["preview"]["fingerprint"]
        status,result=post(route+"cleanup",{"days":30,"fingerprint":token})
        assert status==400
        assert job_dir.exists()
        status,result=post(route+"cleanup",{"days":30,"fingerprint":token,"confirm":True})
        assert status==200 and result["cleanup"]["deleted_jobs"]==1
        assert not job_dir.exists()
    finally:
        connection.close();server.shutdown();server.server_close();worker.join(timeout=4)
