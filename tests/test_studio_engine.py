"""Advanced Studio v1: persistent DAGs, local execution, failure trace and API."""
import copy
import http.client
import json
import threading
from pathlib import Path

import pytest

from lulwa_virtual_printer.hub import HubStore, create_server
from lulwa_virtual_printer.studio_engine import StudioManager, validate_workflow


def fixtures(store):
    return (
        store.create_device({"preset": "brother", "name": "Studio Brother"}),
        store.create_device({"preset": "zebra", "name": "Studio Zebra"}),
        store.create_device({"preset": "scale", "name": "Studio Scale"}),
    )


def graph(brother, zebra, scale):
    nodes = [
        {"id": "start", "type": "start", "x": 20, "y": 30, "config": {}},
        {"id": "barcode", "type": "barcode", "x": 250, "y": 30, "config": {"value": "ITEM-001"}},
        {"id": "scale", "type": "scale", "x": 470, "y": 30, "config": {
            "device_id": scale["id"], "gross_kg": 2.5, "tare_kg": .5,
            "unit": "lb", "stable": True}},
        {"id": "pack", "type": "capture", "x": 700, "y": 20, "config": {
            "device_id": brother["id"], "title": "Studio Packing Slip"}},
        {"id": "label", "type": "capture", "x": 700, "y": 180, "config": {
            "device_id": zebra["id"], "title": "Studio Label"}},
        {"id": "finish", "type": "output", "x": 970, "y": 60, "config": {}},
    ]
    edge_pairs = [("start", "barcode"), ("barcode", "scale"), ("scale", "pack"),
                  ("scale", "label"), ("pack", "finish"), ("label", "finish")]
    return {"name": "Warehouse Sample", "nodes": nodes,
            "edges": [{"source": a, "target": b} for a, b in edge_pairs]}


def test_studio_saved_persisted_and_two_real_jpg_jobs(tmp_path):
    root = tmp_path / "cfg"
    store = HubStore(root, tmp_path / "out")
    a, b, c = fixtures(store)
    studio = StudioManager(root, store)
    flow = studio.save(graph(a, b, c))
    assert flow["revision"] == 1
    assert len(flow["order"]) == 6
    assert StudioManager(root, store).snapshot()["workflows"][0]["id"] == flow["id"]
    run = studio.run(flow["id"])
    assert run["status"] == "completed"
    assert run["mode"] == "local_fixture_only"
    assert len(run["steps"]) == 6
    assert all(s["status"] == "completed" for s in run["steps"])
    assert len(store.list_jobs()) == 2
    for job in store.list_jobs():
        assert job["status"] == "rendered"
        assert (Path(job["directory"]) / "page-001.jpg").is_file()
    assert store.get_device(c["id"])["last_measurement"]["weight"] == pytest.approx(4.409, abs=.002)
    assert StudioManager(root, store).snapshot()["runs"][0]["id"] == run["id"]


def test_fault_injection_blocks_output_but_keeps_other_path(tmp_path):
    store = HubStore(tmp_path/"cfg", tmp_path/"out")
    a, b, c = fixtures(store)
    flow = graph(a, b, c)
    studio = StudioManager(tmp_path/"cfg", store)
    saved = studio.save(flow)
    store.configure_device(a["id"], {"fault": "paper_out"})
    run = studio.run(saved["id"])
    assert run["status"] == "failed"
    steps = {step["node_id"]: step for step in run["steps"]}
    assert steps["pack"]["status"] == "failed"
    assert steps["label"]["status"] == "completed"
    assert steps["finish"]["status"] == "skipped"
    assert "paper out" in steps["pack"]["detail"]
    assert len(store.list_jobs()) == 2  # failed Brother job + successful Zebra JPG


def test_cyclic_or_disconnected_or_unsafe_graph_rejected(tmp_path):
    store = HubStore(tmp_path/"cfg", tmp_path/"out")
    a, b, c = fixtures(store)
    base = graph(a, b, c)
    broken = []
    cyclic = copy.deepcopy(base)
    cyclic["edges"].append({"source": "finish", "target": "barcode"})
    broken.append(cyclic)
    duplicate = copy.deepcopy(base)
    duplicate["edges"].append(duplicate["edges"][0])
    broken.append(duplicate)
    disconnected = copy.deepcopy(base)
    disconnected["edges"] = [{"source":"start","target":"finish"}]
    broken.append(disconnected)
    unknown_model = copy.deepcopy(base)
    unknown_model["nodes"][2]["config"]["device_id"] = "nonexistent"
    broken.append(unknown_model)
    unsafe = copy.deepcopy(base)
    unsafe["nodes"][1]["config"]["value"] = "\nSYSTEM INPUT"
    broken.append(unsafe)
    for flow in broken:
        with pytest.raises(ValueError):
            validate_workflow(flow, store.list_devices())


def test_revision_conflicts_duplicate_and_delete(tmp_path):
    store = HubStore(tmp_path/"cfg", tmp_path/"out")
    a, b, c = fixtures(store)
    studio = StudioManager(tmp_path/"cfg", store)
    original = studio.save(graph(a, b, c))
    updated = studio.save({**original, "name": "Warehouse Revised"})
    assert updated["revision"] == 2
    with pytest.raises(RuntimeError, match="changed"):
        studio.save({**original, "name": "Stale Update"})
    duplicate = {k:v for k,v in original.items() if k not in ("id","revision","updated_at","created_at")}
    created = studio.save(duplicate)
    assert created["id"] != original["id"]
    assert studio.delete(original["id"])
    with pytest.raises(LookupError):
        studio.run(original["id"])
    assert len(studio.snapshot()["workflows"]) == 1


def test_deleted_device_creates_validation_failure_record(tmp_path):
    store = HubStore(tmp_path/"cfg", tmp_path/"out")
    a,b,c=fixtures(store)
    studio=StudioManager(tmp_path/"cfg",store)
    saved=studio.save(graph(a,b,c))
    assert store.remove_device(c["id"])
    run=studio.run(saved["id"])
    assert run["status"]=="failed"
    assert run["steps"][0]["node_id"]=="validation"
    assert not store.list_jobs()


def test_http_workflows_token_persistence_and_browser_js(tmp_path):
    server=create_server(port=0,state_dir=tmp_path/"cfg",output_dir=tmp_path/"out")
    a,b,c=fixtures(server.hub_store)
    worker=threading.Thread(target=server.serve_forever,daemon=True)
    worker.start()
    try:
        conn=http.client.HTTPConnection("127.0.0.1",server.server_port,timeout=25)
        payload=json.dumps(graph(a,b,c))
        conn.request("GET","/studio.js")
        response=conn.getresponse()
        script=response.read().decode()
        assert response.status==200 and "function studioPage" in script
        conn.request("POST","/api/studio/workflows/save",payload,{"Content-Type":"application/json"})
        response=conn.getresponse();response.read()
        assert response.status==403
        headers={"Content-Type":"application/json","X-Devices-Token":server.hub_token}
        conn.request("POST","/api/studio/workflows/save",payload,headers)
        response=conn.getresponse()
        saved=json.loads(response.read())["workflow"]
        assert response.status==200 and saved["revision"]==1
        conn.request("POST","/api/studio/workflows/execute",json.dumps({"id":saved["id"]}),headers)
        response=conn.getresponse()
        result=json.loads(response.read())["run"]
        assert response.status==200 and result["status"]=="completed"
        conn.request("GET","/api/state")
        response=conn.getresponse()
        body=json.loads(response.read())
        assert body["studio"]["runs"][0]["id"]==result["id"]
        conn.request("GET","/api/studio/workflows")
        response=conn.getresponse()
        assert json.loads(response.read())["workflows"][0]["id"]==saved["id"]
        conn.close()
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=2)
