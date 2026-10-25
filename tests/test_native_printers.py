"""OS printer registration must never fake installed status or overwrite other queues."""
import json
import subprocess
from lulwa_virtual_printer.native_printers import (
    PRINTERS, get_registration, install_printer, uninstall_printer,
)

def result(cmd, rc=0, out="", err=""):
    return subprocess.CompletedProcess(cmd, rc, out, err)

def test_mac_install_then_verify():
    actions=[]
    uri=PRINTERS["brother"][2]
    def run(cmd):
        actions.append(cmd)
        if cmd[:2] == ["lpstat", "-v"]:
            if any(x[0]=="lpadmin" for x in actions):
                return result(cmd,out=f"device for Lulwa_SIM_Brother: {uri}\n")
            return result(cmd,1,err="unknown printer")
        if cmd[0] == "lpadmin": return result(cmd)
        raise AssertionError(cmd)
    out=install_printer("brother",system="Darwin",run=run,check_service=lambda:True)
    assert out["status"]=="registered" and out["success"] is True
    assert ["lpadmin","-p","Lulwa_SIM_Brother","-E","-D","Lulwa SIM Brother (2 Trays)","-v",uri,"-m","everywhere"] in actions

def test_no_overwrite_on_colliding_queue():
    def run(cmd):
        return result(cmd,out="device for Lulwa_SIM_Zebra_4x6: ipp://192.0.2.1/other\n")
    out=install_printer("zebra",system="Darwin",run=run,check_service=lambda:True)
    assert out["success"] is False and out["status"]=="conflict"

def test_service_offline_blocks_queue_add():
    def run(cmd):
        if cmd[0]=="lpstat":return result(cmd,1,err="unknown")
        raise AssertionError("lpadmin must not run")
    out=install_printer("zebra",system="Linux",run=run,check_service=lambda:False)
    assert out["success"] is False and "not running" in out["error"]

def test_os_confirmation_rejects_mismatched_uri():
    def run(cmd):
        return result(cmd,out="device for Lulwa_SIM_Brother: ipp://192.0.2.2/printer\n")
    assert get_registration("brother",system="Darwin",run=run)["status"]=="conflict"

def test_mac_uninstall_only_own_queue():
    seen=[]
    uri=PRINTERS["zebra"][2]
    def run(cmd):
        seen.append(cmd)
        if cmd[0]=="lpadmin":return result(cmd)
        if any(s[0]=="lpadmin" for s in seen):
            return result(cmd,1,err="queue missing")
        return result(cmd,out=f"device for Lulwa_SIM_Zebra_4x6: {uri}\n")
    out=uninstall_printer("zebra",system="Darwin",run=run)
    assert out["success"] and out["status"]=="not_installed"
    assert ["lpadmin","-x","Lulwa_SIM_Zebra_4x6"] in seen

def test_windows_install_requires_uri_verification():
    calls=[]
    def run(cmd):
        calls.append(cmd)
        if "Get-Printer " in cmd[-1]:
            if any("Add-Printer" in x[-1] for x in calls):
                return result(cmd,out=json.dumps({"Name":"Lulwa_SIM_Brother","PortName":"WSD-123"}))
            return result(cmd,out="")
        return result(cmd)
    out=install_printer("brother",system="Windows",run=run,check_service=lambda:True)
    assert out["status"]=="unverified" and out["success"] is False

def test_installed_name_does_not_imply_endpoint():
    def run(cmd):
        return result(cmd,out=json.dumps({"Name":"Lulwa_SIM_Zebra_4x6","PortName":"some-other-port"}))
    assert get_registration("zebra",system="Windows",run=run)["status"]=="unverified"

def test_unknown_presets_cannot_install():
    import pytest
    with pytest.raises(ValueError):
        install_printer("scanner",system="Darwin",check_service=lambda:True)


def test_cups_ppd_fallback_when_driverless_rejected():
    uri=PRINTERS["brother"][2]
    calls=[]
    def run(cmd):
        calls.append(cmd)
        if cmd[0]=="lpstat":
            if any(x[0]=="lpadmin" and "-P" in x for x in calls):
                return result(cmd,out=f"device for Lulwa_SIM_Brother: {uri}\n")
            return result(cmd,1,err="not installed")
        if cmd[0]=="lpadmin" and "-m" in cmd:
            return result(cmd,1,err="Unable to create PPD: Printer does not support required IPP attributes or document formats")
        if cmd[0]=="lpadmin" and "-P" in cmd:
            assert cmd[-1].endswith("brother.ppd")
            return result(cmd)
        raise AssertionError(cmd)
    installed=install_printer("brother",system="Darwin",run=run,check_service=lambda:True)
    assert installed["success"] and installed["method"]=="legacy_pdf_ppd"
    assert any("-P" in x for x in calls)


def test_cups_does_not_fallback_on_permission_denied():
    calls=[]
    def run(cmd):
        calls.append(cmd)
        if cmd[0]=="lpstat":return result(cmd,1,err="unknown")
        if cmd[0]=="lpadmin":return result(cmd,1,err="Not authorized")
        raise AssertionError(cmd)
    installed=install_printer("zebra",system="Darwin",run=run,check_service=lambda:True)
    assert not installed["success"]
    assert not any("-P" in x for x in calls)
