"""Advanced Studio calls a real managed TCP scale socket, never arbitrary hosts."""
import http.client
import json
import threading

import pytest

from lulwa_virtual_printer.connection_engine import ConnectionEngine
from lulwa_virtual_printer.hub import HubStore, create_server
from lulwa_virtual_printer.studio_engine import StudioManager, validate_workflow


def network_flow(device_id):
    return {
        "name": "External TCP Scale QA",
        "nodes": [
            {"id": "begin", "type": "start", "x": 20, "y": 120, "config": {}},
            {"id": "weight", "type": "tcp_scale", "x": 270, "y": 120,
             "config": {"device_id": device_id}},
            {"id": "result", "type": "output", "x": 550, "y": 120, "config": {}},
        ],
        "edges": [{"source": "begin", "target": "weight"},
                  {"source": "weight", "target": "result"}],
    }


def fixture(tmp_path):
    store = HubStore(tmp_path / "state", tmp_path / "out")
    scale = store.create_device({"preset": "scale", "name": "Warehouse TCP scale",
                                 "model_id": "generic-scale", "transport": "network"})
    return store, scale


def test_studio_real_socket_weight_and_failure_history(tmp_path):
    store, dev = fixture(tmp_path)
    manager = ConnectionEngine(store)
    studio = StudioManager(tmp_path / "state", store, connections=manager)
    saved = studio.save(network_flow(dev["id"]))
    first = studio.run(saved["id"])
    assert first["status"] == "failed"
    assert first["steps"][1]["status"] == "failed"
    assert "Start this scale" in first["steps"][1]["detail"]
    assert first["steps"][2]["status"] == "skipped"
    assert first["mode"] == "local_fixture_and_managed_tcp"

    try:
        listener = manager.start(dev["id"])  # actual TCP socket
        store.simulate_scale_reading(dev["id"], {
            "gross_kg": 3, "tare_kg": 1, "unit": "kg", "stable": True})
        good = studio.run(saved["id"])
        assert good["status"] == "completed"
        step = good["steps"][1]
        assert step["type"] == "tcp_scale"
        assert step["weight"] == {"value": 2.0, "unit": "kg", "status": "stable"}
        assert f"localhost:{listener['port']}" in step["detail"]
        assert manager.snapshot()["listeners"][0]["requests"] >= 1
        assert len(store.list_jobs()) == 0

        manager.set_fault(dev["id"], "busy")
        failed = studio.run(saved["id"])
        assert failed["status"] == "failed"
        assert "busy" in failed["steps"][1]["detail"].lower()
        assert failed["steps"][2]["status"] == "skipped"

        manager.set_fault(dev["id"], "none")
        store.simulate_scale_reading(dev["id"], {
            "gross_kg": 1.4, "tare_kg": 0, "unit": "kg", "stable": False})
        unstable = studio.run(saved["id"])
        assert unstable["status"] == "failed"
        assert "unstable" in unstable["steps"][1]["detail"].lower()

        manager.set_fault(dev["id"], "disconnect")
        disconnected = studio.run(saved["id"])
        assert disconnected["status"] == "failed"
        assert "disconnected" in disconnected["steps"][1]["detail"].lower()

    finally:
        manager.stop_all()


def test_studio_rejects_nonnetwork_or_unknown_devices(tmp_path):
    store, dev = fixture(tmp_path)
    usb = store.create_device({"preset": "scale", "name": "USB DYMO",
                               "model_id": "dymo-m10", "transport": "usb_hid"})
    for device_id in (usb["id"], "unknown"):
        with pytest.raises(ValueError, match="Network transport"):
            validate_workflow(network_flow(device_id), store.list_devices())
    assert validate_workflow(network_flow(dev["id"]), store.list_devices())["order"] == ["begin", "weight", "result"]


def test_studio_managed_tcp_api_run(tmp_path):
    server = create_server(port=0, state_dir=tmp_path / "cfg", output_dir=tmp_path / "out")
    dev = server.hub_store.create_device({"preset": "scale", "name": "QA network",
                                          "model_id": "generic-scale", "transport": "network"})
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=10)
    auth = {"Content-Type": "application/json", "X-Devices-Token": server.hub_token}
    def post(url, payload):
        conn.request("POST", url, json.dumps(payload), auth)
        resp = conn.getresponse()
        return resp.status, json.loads(resp.read())
    try:
        status, result = post("/api/studio/workflows/save", network_flow(dev["id"]))
        assert status == 200
        flow_id = result["workflow"]["id"]
        status, result = post("/api/connections/start", {"device_id": dev["id"], "confirm": True})
        assert status == 200 and result["connection"]["running"]
        status, result = post("/api/studio/workflows/execute", {"id": flow_id})
        assert status == 200 and result["run"]["status"] == "completed"
        assert result["run"]["steps"][1]["weight"]["value"] == 0.0
    finally:
        conn.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
