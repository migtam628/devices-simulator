"""Advanced Studio conditional graph routing regression tests."""
import copy
import http.client
import json
import threading

import pytest
from lulwa_virtual_printer.hub import HubStore, create_server
from lulwa_virtual_printer.studio_engine import StudioManager, validate_workflow


def graph(scale_id, threshold=1.25, barcode=False):
    input_node = ({"id": "input", "type": "barcode", "config": {"value": "SKU-1001"}}
                  if barcode else {"id": "input", "type": "scale", "config": {
                      "device_id": scale_id, "gross_kg": 2, "tare_kg": 0, "unit": "kg", "stable": True}})
    config = ({"field": "barcode", "operator": "contains", "value": "SKU"} if barcode
              else {"field": "weight", "operator": "gte", "value": threshold})
    return {
        "name": "Conditional QA",
        "nodes": [{"id": "start", "type": "start", "config": {}}, input_node,
                  {"id": "condition", "type": "condition", "config": config},
                  {"id": "yes", "type": "output", "config": {}},
                  {"id": "no", "type": "output", "config": {}}],
        "edges": [{"source": "start", "target": "input"},
                  {"source": "input", "target": "condition"},
                  {"source": "condition", "target": "yes", "branch": "true"},
                  {"source": "condition", "target": "no", "branch": "false"}],
    }


def fixture(tmp_path):
    store = HubStore(tmp_path / "cfg", tmp_path / "out")
    scale = store.create_device({"preset": "scale", "name": "Routing Scale"})
    return store, scale, StudioManager(tmp_path / "cfg", store)


@pytest.mark.parametrize("threshold,decision", [(1.25, True), (3.0, False)])
def test_selects_one_weight_route_without_failing_other(tmp_path, threshold, decision):
    store, scale, studio = fixture(tmp_path)
    saved = studio.save(graph(scale["id"], threshold))
    result = studio.run(saved["id"])
    assert result["status"] == "completed"
    steps = {step["node_id"]: step for step in result["steps"]}
    assert steps["condition"]["decision"] is decision
    assert steps["condition"]["selected_branch"] == ("true" if decision else "false")
    assert steps["yes" if decision else "no"]["status"] == "completed"
    assert steps["no" if decision else "yes"]["status"] == "inactive"
    assert store.list_jobs() == []


def test_barcode_import_export_and_replay_preserve_branch_semantics(tmp_path):
    _, scale, studio = fixture(tmp_path)
    saved = studio.save(graph(scale["id"], barcode=True))
    first = studio.run(saved["id"])
    assert first["steps"][2]["decision"] is True
    doc = studio.export_workflow(saved["id"])
    assert sorted(edge["branch"] for edge in doc["workflow"]["edges"] if "branch" in edge) == ["false", "true"]
    imported = studio.import_workflow(doc)
    assert studio.run(imported["id"])["status"] == "completed"
    changed = graph(scale["id"], barcode=True)
    changed["nodes"][2]["config"] = {"field": "barcode", "operator": "equals", "value": "OTHER"}
    updated = studio.save({**changed, "id": saved["id"], "revision": 1})
    assert updated["revision"] == 2
    assert studio.run(saved["id"])["steps"][2]["decision"] is False
    replay = studio.run(saved["id"], replay_run_id=first["id"])
    assert replay["replayed_from"] == first["id"]
    assert replay["steps"][2]["decision"] is True


def test_branch_join_and_inactive_capture_do_not_create_jobs(tmp_path):
    store, scale, studio = fixture(tmp_path)
    printer = store.create_device({"preset": "brother", "name": "Shipping Printer"})
    g = graph(scale["id"], 1.0)
    g["nodes"] = g["nodes"][:3] + [
        {"id": "capture", "type": "capture", "config": {"device_id": printer["id"], "title": "True Branch"}},
        {"id": "false_path", "type": "barcode", "config": {"value": "FALSE"}},
        {"id": "join", "type": "output", "config": {}}]
    g["edges"] = g["edges"][:2] + [
        {"source": "condition", "target": "capture", "branch": "true"},
        {"source": "condition", "target": "false_path", "branch": "false"},
        {"source": "capture", "target": "join"},
        {"source": "false_path", "target": "join"}]
    saved = studio.save(g)
    first = studio.run(saved["id"])
    steps = {s["node_id"]: s for s in first["steps"]}
    assert first["status"] == "completed"
    assert steps["capture"]["status"] == "completed"
    assert steps["false_path"]["status"] == "inactive"
    assert steps["join"]["status"] == "completed"
    assert len(store.list_jobs()) == 1

    changed = copy.deepcopy(g)
    changed["nodes"][2]["config"]["value"] = 5
    saved = studio.save({**changed, "id": saved["id"], "revision": 1})
    second = studio.run(saved["id"])
    steps = {s["node_id"]: s for s in second["steps"]}
    assert second["status"] == "completed"
    assert steps["capture"]["status"] == "inactive"
    assert steps["false_path"]["status"] == "completed"
    assert steps["join"]["status"] == "completed"
    assert len(store.list_jobs()) == 1


def test_missing_upstream_condition_value_fails_and_blocks_dependents(tmp_path):
    _, scale, studio = fixture(tmp_path)
    g = graph(scale["id"])
    g["nodes"] = [n for n in g["nodes"] if n["id"] != "input"]
    g["edges"] = [{"source": "start", "target": "condition"}] + g["edges"][2:]
    saved = studio.save(g)
    run = studio.run(saved["id"])
    assert run["status"] == "failed"
    steps = {s["node_id"]: s for s in run["steps"]}
    assert "requires an upstream stable scale" in steps["condition"]["detail"]
    assert steps["yes"]["status"] == steps["no"]["status"] == "skipped"


@pytest.mark.parametrize("mutation,reason", [
    ("missing_branch_label", "must specify branch"),
    ("bad_branch", "must specify branch"),
    ("duplicate_branch", "exactly one true and one false"),
    ("missing_false", "exactly one true and one false"),
    ("branch_on_start", "Only Condition"),
    ("wrong_field", "field must be weight or barcode"),
    ("wrong_operator", "numeric"),
    ("invalid_barcode", "printable"),
])
def test_rejects_invalid_condition_schema(tmp_path, mutation, reason):
    store, scale, _ = fixture(tmp_path)
    g = graph(scale["id"])
    if mutation == "missing_branch_label":
        del g["edges"][2]["branch"]
    elif mutation == "bad_branch":
        g["edges"][2]["branch"] = "unsafe"
    elif mutation == "duplicate_branch":
        g["edges"][3]["branch"] = "true"
    elif mutation == "missing_false":
        g["edges"].pop()
    elif mutation == "branch_on_start":
        g["edges"][0]["branch"] = "true"
    elif mutation == "wrong_field":
        g["nodes"][2]["config"]["field"] = "script"
    elif mutation == "wrong_operator":
        g["nodes"][2]["config"]["operator"] = "eval"
    elif mutation == "invalid_barcode":
        g["nodes"][2]["config"] = {"field": "barcode", "operator": "contains", "value": "\n"}
    with pytest.raises(ValueError, match=reason):
        validate_workflow(g, store.list_devices())


def test_auth_api_exposes_selected_branch_without_new_endpoints(tmp_path):
    server = create_server(port=0, state_dir=tmp_path / "cfg", output_dir=tmp_path / "out")
    scale = server.hub_store.create_device({"preset": "scale", "name": "HTTP Routing Scale"})
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    client = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=10)
    auth = {"X-Devices-Token": server.hub_token, "Content-Type": "application/json"}
    def post(path, data):
        client.request("POST", path, json.dumps(data), auth)
        response = client.getresponse()
        return response.status, json.loads(response.read())
    try:
        status, saved = post("/api/studio/workflows/save", graph(scale["id"]))
        assert status == 200
        status, result = post("/api/studio/workflows/execute", {"id": saved["workflow"]["id"]})
        assert status == 200
        assert result["run"]["status"] == "completed"
        assert result["run"]["steps"][2]["selected_branch"] == "true"
        assert {s["status"] for s in result["run"]["steps"]} == {"completed", "inactive"}
    finally:
        client.close()
        server.shutdown()
        server.server_close()
        worker.join(timeout=3)
