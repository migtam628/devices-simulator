"""Studio serial nodes use an activated POSIX PTY, not a mock or arbitrary path."""
import http.client
import json
import os
import threading
import time

import pytest

from lulwa_virtual_printer.connection_engine import ConnectionEngine
from lulwa_virtual_printer.hub import HubStore, create_server
from lulwa_virtual_printer.studio_engine import StudioManager, validate_workflow

pytestmark = pytest.mark.skipif(os.name != "posix" or not hasattr(os, "openpty"), reason="POSIX PTY only")


def graph(device_id):
    return {"name": "External Serial Scale QA",
            "nodes": [{"id": "begin", "type": "start", "x": 10, "y": 10, "config": {}},
                      {"id": "weight", "type": "serial_scale", "x": 270, "y": 10,
                       "config": {"device_id": device_id}},
                      {"id": "result", "type": "output", "x": 510, "y": 10, "config": {}}],
            "edges": [{"source": "begin", "target": "weight"},
                      {"source": "weight", "target": "result"}]}


def fixture(tmp_path):
    store = HubStore(tmp_path / "state", tmp_path / "out")
    scale = store.create_device({"preset": "scale", "name": "Serial QA Scale",
                                 "model_id": "generic-scale", "transport": "serial"})
    connections = ConnectionEngine(store)
    studio = StudioManager(tmp_path / "state", store, connections=connections)
    saved = studio.save(graph(scale["id"]))
    return store, scale, connections, studio, saved


def test_studio_serial_real_pty_and_fault_history(tmp_path):
    store, scale, connections, studio, saved = fixture(tmp_path)
    result = studio.run(saved["id"])
    assert result["status"] == "failed"
    assert "Connections first" in result["steps"][1]["detail"]
    assert result["steps"][2]["status"] == "skipped"
    assert result["mode"] == "local_fixture_and_managed_posix_serial"
    try:
        listener = connections.start_serial(scale["id"])
        store.simulate_scale_reading(scale["id"], {
            "gross_kg": 3.5, "tare_kg": .5, "unit": "kg", "stable": True})
        good = studio.run(saved["id"])
        assert good["status"] == "completed"
        assert good["steps"][1]["weight"] == {"value": 3.0, "unit": "kg", "status": "stable"}
        assert "S S 3.000 kg" in good["steps"][1]["detail"]
        assert listener["path"] in good["steps"][1]["detail"]
        assert connections.snapshot()["serial_listeners"][0]["requests"] >= 1
        assert store.list_jobs() == []

        connections.set_serial_fault(scale["id"], "busy")
        busy = studio.run(saved["id"])
        assert busy["status"] == "failed"
        assert "busy" in busy["steps"][1]["detail"].lower()
        connections.set_serial_fault(scale["id"], "none")
        store.simulate_scale_reading(scale["id"], {
            "gross_kg": 1.1, "unit": "kg", "stable": False})
        unstable = studio.run(saved["id"])
        assert unstable["status"] == "failed"
        assert "unstable" in unstable["steps"][1]["detail"].lower()
        store.simulate_scale_reading(scale["id"], {
            "gross_kg": 1.1, "unit": "kg", "stable": True})
        connections.set_serial_fault(scale["id"], "disconnect")
        start = time.monotonic()
        silent = studio.run(saved["id"])
        assert silent["status"] == "failed"
        assert "timed out" in silent["steps"][1]["detail"].lower()
        assert time.monotonic() - start < 4
        assert silent["steps"][2]["status"] == "skipped"

        connections.set_serial_fault(scale["id"], "none")
        assert studio.run(saved["id"])["status"] == "completed"
        connections.stop_serial(scale["id"])
        assert studio.run(saved["id"])["status"] == "failed"
    finally:
        connections.stop_all()


def test_studio_serial_validation_scope_and_missing_listener(tmp_path):
    store, scale, connections, studio, saved = fixture(tmp_path)
    tcp = store.create_device({"preset": "scale", "name": "TCP QA",
                               "model_id": "generic-scale", "transport": "network"})
    usb = store.create_device({"preset": "scale", "name": "USB QA",
                               "model_id": "dymo-m10", "transport": "usb_hid"})
    for identifier in (tcp["id"], usb["id"], "not-found"):
        with pytest.raises(ValueError, match="RS-232 / serial transport"):
            validate_workflow(graph(identifier), store.list_devices())
    assert validate_workflow(graph(scale["id"]), store.list_devices())["order"] == ["begin", "weight", "result"]
    with pytest.raises(RuntimeError, match="Connections first"):
        connections.read_serial_scale(scale["id"])


def test_studio_serial_guard_on_active_subscription(tmp_path):
    store, scale, connections, studio, saved = fixture(tmp_path)
    try:
        listener = connections.start_serial(scale["id"])
        fd = os.open(listener["path"], os.O_RDWR | os.O_NOCTTY)
        try:
            os.write(fd, b"SUB\r\n")
            until = time.monotonic() + 2
            while time.monotonic() < until and not connections.snapshot()["serial_listeners"][0]["streaming"]:
                time.sleep(.02)
            assert connections.snapshot()["serial_listeners"][0]["streaming"]
            run = studio.run(saved["id"])
            assert run["status"] == "failed"
            assert "streaming" in run["steps"][1]["detail"]
            os.write(fd, b"UNSUB\r\n")
            until = time.monotonic() + 2
            while time.monotonic() < until and connections.snapshot()["serial_listeners"][0]["streaming"]:
                time.sleep(.02)
            assert not connections.snapshot()["serial_listeners"][0]["streaming"]
        finally:
            os.close(fd)
    finally:
        connections.stop_all()


def test_studio_serial_authenticated_hub_api(tmp_path):
    server = create_server(port=0, state_dir=tmp_path / "cfg", output_dir=tmp_path / "out")
    scale = server.hub_store.create_device({"preset": "scale", "name": "HTTP serial scale",
                                           "model_id": "generic-scale", "transport": "serial"})
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    client = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=8)
    auth = {"Content-Type": "application/json", "X-Devices-Token": server.hub_token}
    def post(url, data):
        client.request("POST", url, json.dumps(data), auth)
        resp = client.getresponse()
        return resp.status, json.loads(resp.read())
    try:
        status, result = post("/api/studio/workflows/save", graph(scale["id"]))
        assert status == 200
        saved_id = result["workflow"]["id"]
        status, result = post("/api/connections/serial-start", {"device_id": scale["id"], "confirm": True})
        assert status == 200 and result["connection"]["running"]
        status, result = post("/api/studio/workflows/execute", {"id": saved_id})
        assert status == 200 and result["run"]["status"] == "completed"
        assert result["run"]["steps"][1]["weight"] == {"value": 0.0, "unit": "kg", "status": "stable"}
    finally:
        client.close()
        server.shutdown()
        server.server_close()
        worker.join(timeout=4)
