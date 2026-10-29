"""v0.13.9: gated, serialized, single-step Studio execution."""
import http.client
import json
import threading
import time
from pathlib import Path

import pytest

from lulwa_virtual_printer.hub import HubStore, create_server
from lulwa_virtual_printer.studio_engine import StudioManager, LIVE_TIMEOUT_SECONDS


def setup(tmp_path):
    store = HubStore(tmp_path / "cfg", tmp_path / "out")
    printer = store.create_device({"preset": "brother", "name": "Live Brother"})
    studio = StudioManager(tmp_path / "cfg", store)
    return store, studio, printer


def graph(device_id):
    return {
        "name": "Live JPG QA",
        "nodes": [
            {"id": "start", "type": "start", "config": {}},
            {"id": "barcode", "type": "barcode", "config": {"value": "SKU-1001"}},
            {"id": "capture", "type": "capture", "config": {
                "device_id": device_id, "title": "Manual JPG"}},
            {"id": "output", "type": "output", "config": {}},
        ],
        "edges": [{"source": "start", "target": "barcode"},
                  {"source": "barcode", "target": "capture"},
                  {"source": "capture", "target": "output"}],
    }


def test_live_session_advances_exactly_one_node_with_confirmed_jpg(tmp_path):
    store, studio, printer = setup(tmp_path)
    saved = studio.save(graph(printer["id"]))
    state_before = studio.path.read_bytes()
    session = studio.live_start(saved["id"], saved["revision"])
    assert session["expected_step"] == 0
    assert session["next_node"]["type"] == "start"
    assert not session["steps"]
    assert store.list_jobs() == []
    assert studio.path.read_bytes() == state_before
    with pytest.raises(RuntimeError, match="already active"):
        studio.live_start(saved["id"], saved["revision"])
    assert studio.live_status()["session_id"] == session["session_id"]

    first = studio.live_step(session["session_id"], 0)
    assert first["executed"]["type"] == "start"
    assert first["session"]["expected_step"] == 1
    with pytest.raises(RuntimeError, match="already advanced"):
        studio.live_step(session["session_id"], 0)
    second = studio.live_step(session["session_id"], 1)
    assert second["executed"]["type"] == "barcode"
    assert second["session"]["next_node"]["requires_confirmation"] is True
    with pytest.raises(ValueError, match="confirm explicitly"):
        studio.live_step(session["session_id"], 2)
    assert store.list_jobs() == []
    assert studio.live_status()["expected_step"] == 2

    capture = studio.live_step(session["session_id"], 2, confirm=True)
    assert capture["executed"]["type"] == "capture"
    assert capture["executed"]["status"] == "completed"
    assert len(store.list_jobs()) == 1
    with pytest.raises(RuntimeError, match="already advanced"):
        studio.live_step(session["session_id"], 2, confirm=True)
    assert len(store.list_jobs()) == 1  # duplicate cannot create a second JPG
    done = studio.live_step(session["session_id"], 3)
    assert done["finished"] is True
    assert done["status"] == "completed"
    assert done["run"]["mode"] == "confirmed_manual_step_debugger"
    assert len(done["run"]["steps"]) == 4
    assert studio.live_status() is None
    assert len(studio.snapshot()["runs"]) == 1
    assert studio.snapshot()["runs"][0]["id"] == done["run"]["id"]


def test_session_cancel_keeps_auditable_partial_steps_and_can_restart(tmp_path):
    store, studio, printer = setup(tmp_path)
    saved = studio.save(graph(printer["id"]))
    session = studio.live_start(saved["id"], 1)
    studio.live_step(session["session_id"], 0)
    record = studio.live_cancel(session["session_id"])
    assert record["status"] == "cancelled"
    assert len(record["steps"]) == 1
    assert not store.list_jobs()
    assert studio.live_status() is None
    with pytest.raises(LookupError):
        studio.live_step(session["session_id"], 1)
    next_session = studio.live_start(saved["id"], 1)
    assert next_session["session_id"] != session["session_id"]


def test_live_steps_are_bound_to_exact_revision_and_immutable_snapshot(tmp_path):
    store, studio, printer = setup(tmp_path)
    saved = studio.save(graph(printer["id"]))
    with pytest.raises(RuntimeError, match="revision changed"):
        studio.live_start(saved["id"], 99)
    session = studio.live_start(saved["id"], 1)
    changed = graph(printer["id"])
    changed["nodes"][1]["config"]["value"] = "EDITED"
    studio.save({**changed, "id": saved["id"], "revision": 1})
    studio.live_step(session["session_id"], 0)
    studio.live_step(session["session_id"], 1)
    studio.live_step(session["session_id"], 2, confirm=True)
    result = studio.live_step(session["session_id"], 3)
    assert result["run"]["workflow_revision"] == 1
    assert result["run"]["workflow_snapshot"]["nodes"][1]["config"]["value"] == "SKU-1001"
    assert studio.snapshot()["workflows"][0]["nodes"][1]["config"]["value"] == "EDITED"


def test_expired_session_stops_without_automatic_resumption(tmp_path):
    store, studio, printer = setup(tmp_path)
    saved = studio.save(graph(printer["id"]))
    session = studio.live_start(saved["id"], 1)
    studio._live["last_used"] = time.monotonic() - LIVE_TIMEOUT_SECONDS - 1
    assert studio.live_status() is None
    with pytest.raises(LookupError):
        studio.live_step(session["session_id"], 0)
    assert studio.snapshot()["runs"] == []
    assert store.list_jobs() == []


def test_invalid_session_ids_and_expected_step_rejected(tmp_path):
    _, studio, printer = setup(tmp_path)
    saved = studio.save(graph(printer["id"]))
    session = studio.live_start(saved["id"], 1)
    for step in (-1, True, "0", None):
        with pytest.raises(ValueError):
            studio.live_step(session["session_id"], step)
    for ident in (None, 1, "bad id"):
        with pytest.raises(ValueError):
            studio.live_step(ident, 0)
    with pytest.raises(LookupError):
        studio.live_step("wrong", 0)
    with pytest.raises(LookupError):
        studio.live_cancel("wrong")
    assert studio.live_status()["expected_step"] == 0


def test_session_steps_share_normal_executor_for_condition_routing(tmp_path):
    store, studio, printer = setup(tmp_path)
    # No extra adapters needed: compare barcode against a stable literal.
    plan = {
        "name": "Live conditions",
        "nodes": [
            {"id": "start", "type": "start", "config": {}},
            {"id": "barcode", "type": "barcode", "config": {"value": "SKU"}},
            {"id": "condition", "type": "condition", "config": {
                "field": "barcode", "operator": "contains", "value": "SKU"}},
            {"id": "yes", "type": "output", "config": {}},
            {"id": "no", "type": "output", "config": {}},
        ],
        "edges": [
            {"source": "start", "target": "barcode"},
            {"source": "barcode", "target": "condition"},
            {"source": "condition", "target": "yes", "branch": "true"},
            {"source": "condition", "target": "no", "branch": "false"},
        ],
    }
    saved = studio.save(plan)
    expected = studio.run(saved["id"])
    session = studio.live_start(saved["id"], 1)
    while session:
        result = studio.live_step(session["session_id"], session["expected_step"],
                                  confirm=bool(session["next_node"]["requires_confirmation"]))
        session = result["session"]
    actual = result["run"]
    assert [(x["node_id"], x["status"], x.get("decision"))
            for x in actual["steps"]] == [
               (x["node_id"], x["status"], x.get("decision")) for x in expected["steps"]]
    assert actual["status"] == expected["status"] == "completed"


def test_live_debug_http_requires_local_token_and_prevents_repeat(tmp_path):
    server = create_server(port=0, state_dir=tmp_path / "cfg", output_dir=tmp_path / "out")
    printer = server.hub_store.create_device({"preset": "brother", "name": "HTTP Manual Printer"})
    saved = server.hub_studio.save(graph(printer["id"]))
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=10)

    def post(path, payload, authorized=True):
        headers = {"Content-Type": "application/json"}
        if authorized:
            headers["X-Devices-Token"] = server.hub_token
        conn.request("POST", path, json.dumps(payload), headers)
        response = conn.getresponse()
        return response.status, json.loads(response.read())

    try:
        code, _ = post("/api/studio/debug/start", {"id": saved["id"], "revision": 1}, False)
        assert code == 403
        code, start = post("/api/studio/debug/start", {"id": saved["id"], "revision": 1})
        assert code == 200
        sid = start["session"]["session_id"]
        code, _ = post("/api/studio/debug/status", {})
        assert code == 200
        code, first = post("/api/studio/debug/step",
                           {"session_id": sid, "expected_step": 0})
        assert code == 200 and first["result"]["executed"]["type"] == "start"
        code, _ = post("/api/studio/debug/step",
                       {"session_id": sid, "expected_step": 0})
        assert code == 409
        code, cancelled = post("/api/studio/debug/cancel", {"session_id": sid})
        assert code == 200 and cancelled["run"]["status"] == "cancelled"
        assert not server.hub_store.list_jobs()
    finally:
        conn.close()
        server.shutdown()
        server.server_close()
        worker.join(timeout=4)
