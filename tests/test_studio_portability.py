"""Portable Studio workflows and explicit snapshot replay security regressions."""
import copy
import http.client
import json
import shutil
import subprocess
import threading
from pathlib import Path

import pytest

from lulwa_virtual_printer.hub import HubStore, create_server
from lulwa_virtual_printer.studio_engine import StudioManager


def barcode_flow(value="SKU-001"):
    return {
        "name": "Portable Barcode QA",
        "nodes": [
            {"id": "start", "type": "start", "config": {}},
            {"id": "barcode", "type": "barcode", "config": {"value": value}},
            {"id": "output", "type": "output", "config": {}}
        ],
        "edges": [{"source": "start", "target": "barcode"},
                  {"source": "barcode", "target": "output"}],
    }


def device_flow(device_id):
    return {
        "name": "Portable Shipping QA",
        "nodes": [
            {"id": "start", "type": "start", "config": {}},
            {"id": "scale", "type": "scale", "config": {"device_id": device_id,
                "gross_kg": 2.5, "tare_kg": .5, "unit": "kg", "stable": True}},
            {"id": "output", "type": "output", "config": {}},
        ],
        "edges": [{"source": "start", "target": "scale"},
                  {"source": "scale", "target": "output"}],
    }


def test_export_import_creates_new_graph_without_metadata(tmp_path):
    store = HubStore(tmp_path / "cfg", tmp_path / "out")
    studio = StudioManager(tmp_path / "cfg", store)
    original = studio.save(barcode_flow())
    run = studio.run(original["id"])
    document = studio.export_workflow(original["id"])
    assert document["format"] == "devices-simulator-studio"
    assert document["version"] == 1
    assert set(document) == {"format", "version", "workflow"}
    assert set(document["workflow"]) == {"name", "nodes", "edges"}
    assert "id" not in document["workflow"] and "runs" not in document
    assert run["id"] not in json.dumps(document)

    imported = studio.import_workflow(document)
    assert imported["id"] != original["id"]
    assert imported["revision"] == 1
    assert imported["nodes"] == original["nodes"]
    assert imported["edges"] == original["edges"]
    assert studio.run(imported["id"])["status"] == "completed"
    assert len(studio.snapshot()["workflows"]) == 2


def test_import_device_mapping_and_invalid_document_atomic(tmp_path):
    store = HubStore(tmp_path / "cfg", tmp_path / "out")
    studio = StudioManager(tmp_path / "cfg", store)
    old = store.create_device({"preset": "scale", "name": "Old Scale"})
    new = store.create_device({"preset": "scale", "name": "New Scale"})
    source = studio.save(device_flow(old["id"]))
    document = studio.export_workflow(source["id"])
    store.remove_device(old["id"])
    before = len(studio.snapshot()["workflows"])
    with pytest.raises(ValueError, match="existing scale"):
        studio.import_workflow(document)
    copy_ = studio.import_workflow(document, {old["id"]: new["id"]})
    assert copy_["nodes"][1]["config"]["device_id"] == new["id"]
    assert studio.run(copy_["id"])["status"] == "completed"

    bad_versions = [
        {**document, "version": True},
        {**document, "version": 999},
        {**document, "format": "untrusted"},
        {**document, "workflow": {**document["workflow"], "nodes": [{"id": "fake", "type": "shell"}]}},
    ]
    for bad in bad_versions:
        with pytest.raises(ValueError):
            studio.import_workflow(bad)
    with pytest.raises(ValueError, match="64 KB"):
        studio.import_workflow({**document, "junk": "x"*70000})
    with pytest.raises(ValueError, match="Device mapping"):
        studio.import_workflow(document, ["unsafe"])
    assert len(studio.snapshot()["workflows"]) == before+1


def test_replay_snapshot_is_immutable_and_creates_fresh_run(tmp_path):
    store = HubStore(tmp_path / "cfg", tmp_path / "out")
    studio = StudioManager(tmp_path / "cfg", store)
    saved = studio.save(barcode_flow("ORIGINAL"))
    first = studio.run(saved["id"])
    assert first["status"] == "completed"
    assert first["workflow_revision"] == 1
    assert first["workflow_snapshot"]["nodes"][1]["config"]["value"] == "ORIGINAL"

    updated = studio.save({**saved, **barcode_flow("EDITED")})
    assert updated["revision"] == 2
    normal = studio.run(saved["id"])
    assert normal["workflow_snapshot"]["nodes"][1]["config"]["value"] == "EDITED"
    replayed = studio.run(saved["id"], replay_run_id=first["id"])
    assert replayed["id"] not in (first["id"], normal["id"])
    assert replayed["replayed_from"] == first["id"]
    assert replayed["workflow_revision"] == 1
    assert replayed["workflow_snapshot"]["nodes"][1]["config"]["value"] == "ORIGINAL"
    assert studio.snapshot()["workflows"][0]["nodes"][1]["config"]["value"] == "EDITED"
    assert studio.snapshot()["runs"][0]["id"] == replayed["id"]
    assert studio.run(saved["id"], replay_run_id=replayed["id"])["status"] == "completed"
    with pytest.raises(LookupError):
        studio.run(saved["id"], replay_run_id="no-such-run")

    # Old history is explicitly non-replayable instead of silently executing
    # the current edited graph.
    with studio.lock:
        db = studio._read()
        db["runs"][0].pop("workflow_snapshot")
        legacy_id = db["runs"][0]["id"]
        studio._write(db)
    with pytest.raises(ValueError, match="no snapshot"):
        studio.run(saved["id"], replay_run_id=legacy_id)


def test_replay_renders_new_capture_not_old_image(tmp_path):
    store = HubStore(tmp_path / "cfg", tmp_path / "out")
    printer = store.create_device({"preset": "brother", "name": "Replay Brother"})
    flow = {
        "name": "Replay JPG",
        "nodes": [{"id": "start", "type": "start", "config": {}},
                  {"id": "capture", "type": "capture", "config": {
                      "device_id": printer["id"], "title": "Sample Packing Slip"}},
                  {"id": "output", "type": "output", "config": {}}],
        "edges": [{"source": "start", "target": "capture"},
                  {"source": "capture", "target": "output"}]
    }
    studio = StudioManager(tmp_path / "cfg", store)
    saved = studio.save(flow)
    original = studio.run(saved["id"])
    replay = studio.run(saved["id"], replay_run_id=original["id"])
    assert original["status"] == replay["status"] == "completed"
    assert replay["steps"][1]["job_id"] != original["steps"][1]["job_id"]
    assert len(store.list_jobs()) == 2


def test_authenticated_http_import_export_and_replay_confirmation(tmp_path):
    server = create_server(port=0, state_dir=tmp_path / "cfg", output_dir=tmp_path / "out")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=12)
    auth = {"X-Devices-Token": server.hub_token, "Content-Type": "application/json"}
    def call(path, data, authenticated=True):
        conn.request("POST", path, json.dumps(data), auth if authenticated else {"Content-Type": "application/json"})
        resp = conn.getresponse()
        return resp.status, json.loads(resp.read())
    try:
        status, _ = call("/api/studio/workflows/import", {"document": {}}, False)
        assert status == 403
        status, saved = call("/api/studio/workflows/save", barcode_flow())
        assert status == 200
        workflow_id = saved["workflow"]["id"]
        status, exported = call("/api/studio/workflows/export", {"id": workflow_id})
        assert status == 200
        status, imported = call("/api/studio/workflows/import", {"document": exported["document"]})
        assert status == 200 and imported["workflow"]["id"] != workflow_id
        status, current = call("/api/studio/workflows/execute", {"id": workflow_id})
        assert status == 200 and current["run"]["status"] == "completed"
        before = len(server.hub_studio.snapshot()["runs"])
        status, denied = call("/api/studio/workflows/replay", {
            "id": workflow_id, "run_id": current["run"]["id"]})
        assert status == 400
        assert len(server.hub_studio.snapshot()["runs"]) == before
        status, replay = call("/api/studio/workflows/replay", {
            "id": workflow_id, "run_id": current["run"]["id"], "confirm": True})
        assert status == 200
        assert replay["run"]["replayed_from"] == current["run"]["id"]
        assert len(server.hub_studio.snapshot()["runs"]) == before+1
        status, other = call("/api/studio/workflows/replay", {
            "id": imported["workflow"]["id"], "run_id": current["run"]["id"], "confirm": True})
        assert status == 404
    finally:
        conn.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def test_studio_browser_syntax_and_controls():
    source = Path(__file__).resolve().parents[1] / "src/lulwa_virtual_printer/ui/studio.js"
    text = source.read_text(encoding="utf-8")
    for token in ("flow-import-apply", "flow-export", "flow-replay:", "flow-map-", "flow-import-file"):
        assert token in text
    if shutil.which("node"):
        result = subprocess.run(["node", "--check", str(source)], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
