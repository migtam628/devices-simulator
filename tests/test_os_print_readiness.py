"""v0.14.0 local print-path readiness diagnostics never execute a print job."""
import http.client
import io
import json
import subprocess
import threading

import pytest

from lulwa_virtual_printer import hub
from lulwa_virtual_printer.os_print_test import print_readiness


class FakeHTTP:
    def __init__(self, payload):
        self.data = io.BytesIO(json.dumps(payload).encode("utf-8"))
    def __enter__(self):
        return self.data
    def __exit__(self, *args):
        self.data.close()


def local_runner(command, **kwargs):
    assert command[:2] == ["lpstat", "-p"], command
    assert kwargs["timeout"] <= 5
    return subprocess.CompletedProcess(command, 0, "printer Lulwa_SIM_Zebra_4x6 is idle. enabled since Thu", "")


def registered(_preset):
    return {"status": "registered", "details": "Queue has expected IPP endpoint"}


def test_success_when_queue_listener_and_output_root_all_agree(tmp_path):
    calls = []
    def open_mock(url, timeout):
        assert url == "http://127.0.0.1:8631/diagnostics" and timeout <= 2
        calls.append("probe")
        return FakeHTTP({"output_dir": str(tmp_path)})
    report = print_readiness("zebra", tmp_path, registration=registered,
                             opener=open_mock, runner=local_runner, system="Linux")
    assert report["status"] == "ready"
    assert report["scope"] == "read_only_os_print_path"
    assert all(c["ok"] for c in report["checks"])
    assert report["hub_output_dir"] == report["ipp_output_dir"] == str(tmp_path)
    assert calls == ["probe"]
    assert list(tmp_path.iterdir()) == []  # no JPG, no state file


def test_stale_ipp_service_using_wrong_output_folder_is_blocked(tmp_path):
    report = print_readiness(
        "zebra", tmp_path, registration=registered, runner=local_runner,
        opener=lambda _url, timeout: FakeHTTP({"output_dir": str(tmp_path/"other")}),
        system="Darwin")
    assert report["status"] == "blocked"
    bad = {c["key"]: c for c in report["checks"] if not c["ok"]}
    assert set(bad) == {"output_directory"}
    assert "SAME --output" in bad["output_directory"]["next_step"]


def test_missing_ipp_diagnostics_reports_listener_and_output_block(tmp_path):
    def missing(*args, **kwargs):
        raise ConnectionRefusedError("IPP not listening")
    report = print_readiness("brother", tmp_path,
        registration=registered, opener=missing, runner=local_runner, system="Linux")
    bad = {c["key"] for c in report["checks"] if not c["ok"]}
    assert bad == {"ipp_service", "output_directory"}


def test_disabled_queue_fails_even_if_listener_and_output_match(tmp_path):
    def disabled(command, **kwargs):
        return subprocess.CompletedProcess(command, 0, "printer Lulwa_SIM_Zebra_4x6 disabled since today", "")
    report = print_readiness("zebra", tmp_path, registration=registered,
        opener=lambda _url, timeout: FakeHTTP({"output_dir": str(tmp_path)}),
        runner=disabled, system="Linux")
    assert report["status"] == "blocked"
    assert {x["key"] for x in report["checks"] if not x["ok"]} == {"queue_enabled"}


def test_unverified_queue_no_shell_mutation_or_print_submission(tmp_path):
    commands = []
    def runner(command, **kwargs):
        commands.append(command)
        raise AssertionError("No lpstat calls without verified printer")
    report = print_readiness("zebra", tmp_path,
        registration=lambda _: {"status": "conflict", "details": "Other printer owns this queue"},
        opener=lambda _url, timeout: FakeHTTP({"output_dir": str(tmp_path)}),
        runner=runner, system="Linux")
    assert report["status"] == "blocked"
    assert "queue" in {x["key"] for x in report["checks"] if not x["ok"]}
    assert commands == []


def test_windows_unverified_queue_does_not_claim_working_os_spooler(tmp_path):
    report = print_readiness("zebra", tmp_path,
        registration=lambda _name: {"status": "unverified", "details": "IPP URL not verified"},
        opener=lambda _url, timeout: FakeHTTP({"output_dir": str(tmp_path)}),
        runner=lambda *_a, **_k: pytest.fail("Unverified Windows queue must never submit or probe"),
        system="Windows")
    assert report["status"] == "blocked"
    assert "queue" in {x["key"] for x in report["checks"] if not x["ok"]}


def test_invalid_printer_name_rejected_before_any_probe(tmp_path):
    with pytest.raises(ValueError, match="Brother/Zebra"):
        print_readiness("../printer", tmp_path, registration=lambda _: pytest.fail("not called"))


def test_authenticated_hub_readiness_and_failed_preflight_never_dispatch_lp(tmp_path, monkeypatch):
    calls = []
    def readiness(preset, output):
        calls.append((preset, output))
        return {"status": "blocked", "checks": [{"key":"output_directory","ok":False,
                 "detail":"Hub and IPP output folders differ","next_step":"restart"}]}
    monkeypatch.setattr(hub, "print_readiness", readiness)
    monkeypatch.setattr(hub, "verify_print_roundtrip", lambda *_args: pytest.fail("must not print"))
    server = hub.create_server(port=0, state_dir=tmp_path/"state", output_dir=tmp_path/"jobs")
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=10)
    def request(path, authorized=True):
        h = {"Content-Type":"application/json"}
        if authorized:
            h["X-Devices-Token"] = server.hub_token
        conn.request("POST",path,json.dumps({"preset":"zebra","confirm":True}),h)
        response = conn.getresponse()
        return response.status, json.loads(response.read())
    try:
        assert request("/api/system/print-readiness", False)[0] == 403
        code, result = request("/api/system/print-readiness")
        assert code == 200 and result["readiness"]["status"] == "blocked"
        code, result = request("/api/system/print-test")
        assert code == 409 and "output folders differ" in result["error"]
        assert len(calls) == 2
        assert server.hub_store.list_jobs() == []
    finally:
        conn.close()
        server.shutdown()
        server.server_close()
        worker.join(timeout=4)
