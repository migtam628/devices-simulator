"""Windows OS-print queue diagnostics and opt-in GDI submission safety tests.

Most tests are deliberately mocked: CI cannot establish live IPP driver
compatibility on a user's Windows machine.
"""
import base64
import io
import json
import platform
import shutil
import subprocess

import pytest

from lulwa_virtual_printer.native_printers import get_registration, PRINTERS
from lulwa_virtual_printer.os_print_test import (
    print_readiness, submit_windows_sample, verify_print_roundtrip,
    windows_spooler_status,
)


class Response:
    def __init__(self, data):
        self.data = io.BytesIO(json.dumps(data).encode("utf-8"))
    def __enter__(self):
        return self.data
    def __exit__(self, *a):
        self.data.close()


def windows_runner(health=None, calls=None, code=0):
    def runner(command, **kwargs):
        if calls is not None:
            calls.append((command, kwargs))
        assert command[0] == "powershell.exe"
        assert "-NoProfile" in command and "-NonInteractive" in command
        return subprocess.CompletedProcess(
            command, code,
            json.dumps(health or {"Spooler": "Running", "Status": "Normal",
                                  "WorkOffline": False, "PortName": "http://127.0.0.1:8631/ipp/zebra"}),
            "failure" if code else "")
    return runner


def test_windows_spooler_status_read_only_and_bounded():
    calls=[]
    result=windows_spooler_status("Lulwa_SIM_Zebra_4x6",runner=windows_runner(calls=calls))
    assert result["spooler"] and result["queue_enabled"]
    assert "Get-Service -Name Spooler" in calls[0][0][-1]
    assert "Get-Printer -Name 'Lulwa_SIM_Zebra_4x6'" in calls[0][0][-1]
    assert "Set-Printer" not in calls[0][0][-1]
    assert "Add-Printer" not in calls[0][0][-1]
    assert calls[0][1]["timeout"]==8


@pytest.mark.parametrize("health",[
    {"Spooler":"Stopped","Status":"Normal","WorkOffline":False},
    {"Spooler":"Running","Status":"Offline","WorkOffline":False},
    {"Spooler":"Running","Status":"Paused","WorkOffline":False},
    {"Spooler":"Running","Status":"Normal","WorkOffline":True},
    {"Spooler":"Running","Status":"PaperOut","WorkOffline":False},
])
def test_windows_spooler_disabled_paused_or_offline(health):
    x=windows_spooler_status("Lulwa_SIM_Brother",runner=windows_runner(health))
    assert not x["queue_enabled"]


def test_windows_spooler_command_rejection_and_invalid_name():
    x=windows_spooler_status("Lulwa_SIM_Brother",runner=windows_runner(code=1))
    assert not x["spooler"] and not x["queue_enabled"]
    with pytest.raises(ValueError, match="simulator-owned"):
        windows_spooler_status("Some Physical Printer")


def test_win_readiness_checks_queue_spooler_folder_without_printing(tmp_path):
    cmds=[]
    report=print_readiness("zebra",tmp_path,system="Windows",
        registration=lambda _id:{"status":"registered","details":"Verified local IPP URL"},
        opener=lambda _url,timeout:Response({"output_dir":str(tmp_path)}),
        runner=windows_runner(calls=cmds))
    assert report["status"]=="ready"
    assert {x["key"] for x in report["checks"]} >= {"platform","queue","ipp_service","output_directory","spooler","queue_enabled"}
    assert not any("PrintDocument" in c[0][-1] for c in cmds)
    assert list(tmp_path.iterdir())==[]


def test_windows_readiness_rejects_stopped_spooler(tmp_path):
    status={"Spooler":"Stopped","Status":"Normal","WorkOffline":False}
    r=print_readiness("zebra",tmp_path,system="Windows",
        registration=lambda _id:{"status":"registered"},
        opener=lambda _url,timeout:Response({"output_dir":str(tmp_path)}),
        runner=windows_runner(status))
    assert r["status"]=="blocked"
    assert "spooler" in {c["key"] for c in r["checks"] if not c["ok"]}


def test_windows_queue_port_url_requires_exact_simulator_identity():
    uri=PRINTERS["zebra"][2]
    def run(command):
        assert "Get-PrinterPort" in command[-1]
        return subprocess.CompletedProcess(command,0,
            json.dumps({"Name":"Lulwa_SIM_Zebra_4x6","PortName":"IPP_PORT_XYZ",
                        "Description":"Virtual IPP at " + uri}),"")
    assert get_registration("zebra",system="Windows",run=run)["status"]=="registered"
    def wrong(command):
        return subprocess.CompletedProcess(command,0,
            json.dumps({"Name":"Lulwa_SIM_Zebra_4x6","PortName":"IPP_PORT_XYZ",
                        "PrinterHostAddress":"127.0.0.1"}),"")
    assert get_registration("zebra",system="Windows",run=wrong)["status"]=="unverified"


def test_gdi_sample_is_opt_in_and_target_is_fixed():
    commands=[]
    marker="DS-OS-TEST-deadbeef1234"
    output=submit_windows_sample("Lulwa_SIM_Brother",marker,runner=windows_runner(calls=commands))
    assert output.returncode==0
    script=commands[0][0][-1]
    assert "System.Drawing.Printing.PrintDocument" in script
    assert "StandardPrintController" in script
    assert "$d.DocumentName=$script:DSLabel" in script
    assert marker in script
    assert "Lulwa_SIM_Brother" in script
    assert commands[0][1]["timeout"]==20
    for bad in ("Physical LaserJet","Lulwa_SIM_Brother';Remove-Printer"):
        with pytest.raises(ValueError):
            submit_windows_sample(bad,marker,runner=windows_runner(calls=commands))
    with pytest.raises(ValueError):
        submit_windows_sample("Lulwa_SIM_Brother","wrong;something",runner=windows_runner(calls=commands))
    assert len(commands)==1


def test_gdi_print_is_not_a_false_positive_without_jpg(tmp_path,monkeypatch):
    monkeypatch.setattr("lulwa_virtual_printer.os_print_test.platform.system",lambda:"Windows")
    calls=[]
    def runner(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command,0,"Queued", "")
    # No matching JPG: a successful native spooler call is not success.
    monkeypatch.setattr("lulwa_virtual_printer.os_print_test.urlopen",
                        lambda *a,**kw: (_ for _ in ()).throw(ConnectionRefusedError()))
    with pytest.raises(RuntimeError, match="could not confirm a JPG"):
        verify_print_roundtrip("zebra",tmp_path,
            registration=lambda _id:{"status":"registered"},
            runner=runner,sleep=lambda _:None,timeout=0)
    assert len(calls)==1 and "PrintDocument" in calls[0][-1]
    assert not list(tmp_path.glob("*/*/job.json"))


def test_gdi_print_positive_requires_matching_created_jpg(tmp_path,monkeypatch):
    monkeypatch.setattr("lulwa_virtual_printer.os_print_test.platform.system",lambda:"Windows")
    def runner(command, **kwargs):
        script=command[-1]
        import re
        match=re.search(r"DS-OS-TEST-[a-f0-9]{12}",script)
        assert match is not None
        tag=match.group()
        folder=tmp_path/"zebra"/tag
        folder.mkdir(parents=True)
        (folder/"page-001.jpg").write_bytes(b"test jpg bytes")
        # Simulate filesystem timestamp rounding by replacing the mtime
        # with the previous whole second. The UUID marker still proves identity.
        metadata=folder/"job.json"
        metadata.write_text(json.dumps({
            "id":"captured-from-windows","title":tag,"profile":"zebra",
            "status":"rendered","images":["page-001.jpg"]}),encoding="utf-8")
        import os,time
        t=int(time.time())
        os.utime(metadata,(t,t))
        return subprocess.CompletedProcess(command,0,"Queued","")
    result=verify_print_roundtrip("zebra",tmp_path,
        registration=lambda _id:{"status":"registered"},
        runner=runner,timeout=1.5,sleep=lambda _:None)
    assert result["result"]=="os_end_to_end_verified"
    assert result["job_id"]=="captured-from-windows"
    assert result["scope"]=="os_spooler_to_ipp_to_jpg"


@pytest.mark.skipif(platform.system()!="Windows",reason="PowerShell parser only on Windows runner")
def test_native_windows_powershell_script_syntax():
    commands=[]
    submit_windows_sample("Lulwa_SIM_Zebra_4x6","DS-OS-TEST-deadbeef1234",
                          runner=windows_runner(calls=commands))
    script=commands[0][0][-1]
    encoded=base64.b64encode(script.encode("utf-16le")).decode("ascii")
    parse=("$source=[Text.Encoding]::Unicode.GetString([Convert]::FromBase64String('"+
        encoded+"'));$tokens=$null;$errors=$null;"
        "[System.Management.Automation.Language.Parser]::ParseInput($source,[ref]$tokens,[ref]$errors)|Out-Null;"
        "if($errors.Count -gt 0){$errors|Out-String|Write-Error;exit 1}")
    p=subprocess.run(["powershell.exe","-NoProfile","-NonInteractive","-Command",parse],
                     capture_output=True,timeout=20)
    assert p.returncode==0,p.stderr.decode("utf-8","replace")
