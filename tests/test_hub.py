"""State and local HTTP integration tests for Devices Simulator Hub."""
import http.client
import json
import threading
from pathlib import Path

from lulwa_virtual_printer.hub import HubStore, create_server


def test_create_persists_and_rejects_duplicates(tmp_path):
    root = tmp_path / "cfg"
    s = HubStore(root, tmp_path / "out")
    result = s.create_device({"preset": "brother", "name": "Packing Printer", "tray": "tray-2"})
    assert result["lifecycle"] == "draft"
    assert result["os_status"] == "not_verified"
    assert HubStore(root, tmp_path / "out").get_device(result["id"])["tray"] == "tray-2"
    try:
        s.create_device({"preset": "brother", "name": "packing printer"})
        assert False, "Expected duplicate failure"
    except ValueError:
        pass


def test_test_capture_generates_real_jpg_and_history(tmp_path):
    s = HubStore(tmp_path / "cfg", tmp_path / "out")
    brother = s.create_device({"preset": "brother", "name": "Brother", "tray": "tray-2"})
    job = s.test_device(brother["id"])
    assert job["status"] == "rendered"
    assert job["profile"] == "brother-tray2"
    assert (Path(job["directory"]) / "page-001.jpg").is_file()
    assert len(s.list_jobs()) == 1
    assert s.artifact(job["id"], "page-001.jpg") is not None
    assert s.artifact(job["id"], "../../something.jpg") is None
    assert s.get_device(brother["id"])["last_test"]["scope"] == "api_only"


def test_scanner_preview_is_api_only(tmp_path):
    s = HubStore(tmp_path / "cfg", tmp_path / "out")
    scanner = s.create_device({"preset": "scanner", "name": "Scanner"})
    result = s.test_device(scanner["id"])
    assert result["status"] == "rendered"
    assert s.get_device(scanner["id"])["last_test"]["scope"] == "in_app_fixture"
    assert s.get_device(scanner["id"])["os_status"] == "not_verified"


def test_http_token_and_browser_page(tmp_path):
    server = create_server(port=0, state_dir=tmp_path / "cfg", output_dir=tmp_path / "out")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=15)
        conn.request("GET", "/")
        res = conn.getresponse()
        html = res.read().decode()
        assert res.status == 200 and "Device Hub" in html
        assert server.hub_token in html
        conn.request("POST", "/api/devices", json.dumps({"name": "Zebra", "preset": "zebra"}), {"Content-Type": "application/json"})
        res = conn.getresponse()
        assert res.status == 403
        res.read()
        headers = {"Content-Type": "application/json", "X-Devices-Token": server.hub_token}
        conn.request("POST", "/api/devices", json.dumps({"name": "Zebra", "preset": "zebra"}), headers)
        res = conn.getresponse()
        body = json.loads(res.read())
        assert res.status == 201
        device_id = body["device"]["id"]
        conn.request("POST", f"/api/devices/{device_id}/test", "{}", headers)
        res = conn.getresponse()
        body = json.loads(res.read())
        assert res.status == 200 and body["job"]["status"] == "rendered"
        conn.request("GET", "/api/state")
        res = conn.getresponse()
        state = json.loads(res.read())
        assert len(state["devices"]) == 1
        assert len(state["jobs"]) == 1
        assert state["os_install_supported"] is True  # Linux CI supports the experimental install adapter
        conn.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
