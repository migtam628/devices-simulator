"""Register and verify simulated IPP printer queues in the host operating system.

Only fixed, known queues may be modified; never run user-supplied shell commands.
This module does not install scanner, USB, HID or vendor printer drivers.
"""
from __future__ import annotations

import json
import platform
import re
import subprocess
from dataclasses import dataclass
from urllib.request import urlopen

PORT = 8631
PRINTERS = {
    "brother": ("Lulwa_SIM_Brother", "Lulwa SIM Brother (2 Trays)", f"ipp://127.0.0.1:{PORT}/ipp/brother"),
    "zebra": ("Lulwa_SIM_Zebra_4x6", "Lulwa SIM Zebra 4x6", f"ipp://127.0.0.1:{PORT}/ipp/zebra"),
}


def printer_spec(preset: str):
    if preset not in PRINTERS:
        raise ValueError("Native printer installation only supports Brother and Zebra")
    return PRINTERS[preset]


def run_command(cmd: list[str]):
    try:
        return subprocess.run(cmd, text=True, capture_output=True, timeout=35, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return subprocess.CompletedProcess(cmd, 127, "", str(exc))


def service_ready() -> bool:
    try:
        with urlopen(f"http://127.0.0.1:{PORT}/healthz", timeout=2) as resp:
            info = json.load(resp)
            return resp.status == 200 and "brother" in info.get("printers", []) and "zebra" in info.get("printers", [])
    except (OSError, ValueError, KeyError, TimeoutError):
        return False


def _powershell(code: str, run=run_command):
    return run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", code])


def get_registration(preset: str, system: str | None = None, run=run_command) -> dict:
    name, display, uri = printer_spec(preset)
    system = system or platform.system()
    base = {"preset": preset, "queue": name, "label": display, "uri": uri,
            "status": "unknown", "details": ""}
    if system in ("Darwin", "Linux"):
        result = run(["lpstat", "-v", name])
        if result.returncode != 0:
            base.update(status="not_installed", details=(result.stderr or result.stdout).strip()[:500])
            return base
        # CUPS prints 'device for QUEUE: ipp://...' for exactly the requested queue.
        line = next((s.strip() for s in result.stdout.splitlines() if s.strip().startswith(f"device for {name}:")), "")
        if not line:
            base.update(status="unverified", details="Queue response could not be parsed")
            return base
        found = line.split(":", 1)[1].strip()
        base["actual_uri"] = found
        base["status"] = "registered" if found == uri else "conflict"
        base["details"] = "OS queue found with expected IPP endpoint" if found == uri else "Queue name is already used by another endpoint"
        return base
    if system == "Windows":
        # Presence is confirmed via the native print management API. Windows
        # class-driver port names vary, so endpoint identity is checked separately.
        escaped = name.replace("'", "''")
        script = ("$p=Get-Printer -Name '" + escaped + "' -ErrorAction SilentlyContinue; "
                  "if ($p) { [pscustomobject]@{Name=$p.Name;PortName=$p.PortName} | ConvertTo-Json -Compress }")
        result = _powershell(script, run)
        if result.returncode != 0:
            base.update(status="unknown", details=(result.stderr or result.stdout).strip()[:500])
            return base
        if not result.stdout.strip():
            base.update(status="not_installed", details="No matching Windows printer queue")
            return base
        try:
            found = json.loads(result.stdout)
        except ValueError:
            base.update(status="unverified", details="Unable to parse Windows printer enumeration")
            return base
        if found.get("Name") != name:
            base.update(status="unverified", details="Unexpected Windows printer identity")
            return base
        actual_port = found.get("PortName") or ""
        base["actual_uri"] = actual_port
        if uri in actual_port or uri.replace("ipp://", "http://") in actual_port:
            base.update(status="registered", details="Windows printer and endpoint verified")
        else:
            base.update(status="unverified", details="Printer name detected; IPP endpoint not proven")
        return base
    base.update(status="unsupported", details=f"OS not supported: {system}")
    return base


def install_printer(preset: str, system: str | None = None, run=run_command,
                    check_service=service_ready) -> dict:
    name, display, uri = printer_spec(preset)
    system = system or platform.system()
    previous = get_registration(preset, system=system, run=run)
    if previous["status"] == "registered":
        return {**previous, "success": True, "already_present": True}
    if previous["status"] not in ("not_installed",):
        return {**previous, "success": False, "error": "Printer identity could not be verified; refusing to overwrite existing OS configuration"}
    if not check_service():
        return {**previous, "success": False, "error": "IPP simulator is not running at 127.0.0.1:8631. Start the service before installing."}
    if system in ("Darwin", "Linux"):
        # Driverless queue asks the simulator for its IPP capabilities. No
        # deprecated 'raw' queue or arbitrary PPD is silently installed.
        cmd = ["lpadmin", "-p", name, "-E", "-D", display, "-v", uri, "-m", "everywhere"]
        result = run(cmd)
        if result.returncode:
            msg = (result.stderr or result.stdout).strip()[:1200]
            return {**previous, "success": False, "error": msg or "lpadmin failed",
                    "manual_command": "sudo " + " ".join(subprocess.list2cmdline([word]) if " " in word else word for word in cmd)}
    elif system == "Windows":
        # Fixed code only, no input derived from profile names or custom strings.
        script = ("$ErrorActionPreference='Stop'; Add-Printer -Name '" + name
                  + "' -IppURL '" + uri.replace("ipp://", "http://")
                  + "' -ErrorAction Stop")
        result = _powershell(script, run)
        if result.returncode:
            return {**previous, "success": False, "error": (result.stderr or result.stdout).strip()[:1200] or "Windows printer registration failed"}
    else:
        return {**previous, "success": False, "error": "Unsupported operating system"}
    verified = get_registration(preset, system=system, run=run)
    return {**verified, "success": verified["status"] == "registered",
            "error": "" if verified["status"] == "registered" else "Printer registration attempted, but exact queue and endpoint could not be verified."}


def uninstall_printer(preset: str, system: str | None = None, run=run_command) -> dict:
    name, _, uri = printer_spec(preset)
    system = system or platform.system()
    previous = get_registration(preset, system=system, run=run)
    if previous["status"] == "not_installed":
        return {**previous, "success": True, "already_absent": True}
    if previous["status"] != "registered":
        return {**previous, "success": False, "error": "Cannot remove an OS printer whose endpoint is not verified as ours"}
    if system in ("Darwin", "Linux"):
        result = run(["lpadmin", "-x", name])
    elif system == "Windows":
        result = _powershell(f"$ErrorActionPreference='Stop'; Remove-Printer -Name '{name}' -ErrorAction Stop", run)
    else:
        return {**previous, "success": False, "error": "Unsupported operating system"}
    if result.returncode:
        return {**previous, "success": False, "error": (result.stderr or result.stdout).strip()[:1200] or "Uninstall failed"}
    checked = get_registration(preset, system=system, run=run)
    return {**checked, "success": checked["status"] == "not_installed",
            "error": "" if checked["status"] == "not_installed" else "Queue removal not verified by the operating system"}
