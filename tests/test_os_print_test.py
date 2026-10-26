import json
import subprocess
import pytest
from lulwa_virtual_printer.os_print_test import verify_print_roundtrip


def test_rejects_unverified_queue(tmp_path, monkeypatch):
    monkeypatch.setattr("lulwa_virtual_printer.os_print_test.platform.system",lambda:"Darwin")
    with pytest.raises(RuntimeError, match="verified"):
        verify_print_roundtrip("brother",tmp_path,registration=lambda _:{"status":"not_installed"})


def test_finds_own_jpg_and_never_claims_physical_output(tmp_path, monkeypatch):
    monkeypatch.setattr("lulwa_virtual_printer.os_print_test.platform.system",lambda:"Linux")
    def send(args, **kwargs):
        title=args[args.index("-t")+1]
        root=tmp_path/"zebra"/title
        root.mkdir(parents=True)
        (root/"page-001.jpg").write_bytes(b"jpg placeholder for status check")
        (root/"job.json").write_text(json.dumps({"title":title,"id":"job-test","status":"rendered","images":["page-001.jpg"],"profile":"zebra"}))
        return subprocess.CompletedProcess(args,0,b"request accepted",b"")
    result=verify_print_roundtrip("zebra",tmp_path,registration=lambda _:{"status":"registered"},runner=send,timeout=0.5)
    assert result["result"]=="os_end_to_end_verified"
    assert result["scope"]=="os_spooler_to_ipp_to_jpg"
    assert result["job_id"]=="job-test"
