"""Verify OS print queue -> local IPP -> real JPG roundtrip.

Only allowed preset queues are addressable. This is NOT a vendor printer
test and is never used to mark an order shipped.
"""
from __future__ import annotations
import json
import platform
from datetime import datetime, timedelta, timezone
from urllib.request import urlopen
import subprocess
import time
import uuid
from pathlib import Path

from .native_printers import PRINTERS, get_registration




def windows_spooler_status(queue: str, *, runner=subprocess.run) -> dict:
    """Read Windows spooler/queue health without submitting or changing jobs.

    queue is a fixed application-owned printer name supplied by PRINTERS.
    Do not expose this helper for arbitrary caller-provided printer names.
    """
    if queue not in {spec[0] for spec in PRINTERS.values()}:
        raise ValueError("Only simulator-owned queue names can be inspected")
    script = (
        "$ErrorActionPreference='Stop';"
        "$s=Get-Service -Name Spooler -ErrorAction Stop;"
        "$p=Get-Printer -Name '" + queue + "' -ErrorAction Stop;"
        "[pscustomobject]@{Spooler=[string]$s.Status;"
        "Status=[string]$p.PrinterStatus;"
        "WorkOffline=[bool]$p.WorkOffline;"
        "PortName=[string]$p.PortName} | ConvertTo-Json -Compress"
    )
    try:
        response = runner(["powershell.exe", "-NoProfile", "-NonInteractive",
                           "-Command", script],
                          capture_output=True, text=True, timeout=8)
        if response.returncode:
            return {"spooler": False, "queue_enabled": False,
                    "detail": str(response.stderr or response.stdout).strip()[:250]
                              or "Windows print management query failed"}
        data = json.loads(response.stdout)
        if not isinstance(data, dict):
            raise ValueError("Windows queue status is not an object")
        spooler = data.get("Spooler") == "Running"
        status = str(data.get("Status", "Unknown"))
        blocked = {"paused", "offline", "error", "notavailable",
                   "paperout", "userintervention", "serverunknown", "dooropen"}
        enabled = spooler and not data.get("WorkOffline", False) and status.lower().replace(" ", "") not in blocked
        return {"spooler": spooler, "queue_enabled": enabled,
                "status": status, "port_name": str(data.get("PortName", ""))[:220],
                "detail": ("Spooler " + str(data.get("Spooler")) +
                           "; printer " + status +
                           ("; WorkOffline=true" if data.get("WorkOffline") else ""))}
    except (OSError, subprocess.TimeoutExpired, ValueError, TypeError) as exc:
        return {"spooler": False, "queue_enabled": False,
                "detail": ("Unable to inspect Windows Spooler: " + str(exc))[:250]}


def submit_windows_sample(queue: str, marker: str, *, runner=subprocess.run):
    """Opt-in real Windows GDI queue submission (not direct IPP or file capture).

    A PrintDocument sends a *single sample page* to the chosen local queue.
    The OS/IPP driver determines the delivered MIME type; we only report a
    successful roundtrip after finding the matching persisted JPG.
    """
    if queue not in {spec[0] for spec in PRINTERS.values()}:
        raise ValueError("Refusing to print to an unknown Windows printer")
    if not marker.startswith("DS-OS-TEST-") or not marker[11:].isalnum() or len(marker) > 50:
        raise ValueError("Invalid print-test marker")
    script = (
        "$ErrorActionPreference='Stop';"
        "Add-Type -AssemblyName System.Drawing;"
        "$script:DSLabel='" + marker + "';"
        "$d=New-Object System.Drawing.Printing.PrintDocument;"
        "$d.PrinterSettings.PrinterName='" + queue + "';"
        "if(-not $d.PrinterSettings.IsValid){throw 'Simulator printer is invalid'};"
        "$d.DocumentName=$script:DSLabel;"
        "$d.PrintController=New-Object System.Drawing.Printing.StandardPrintController;"
        "$d.add_PrintPage({param($sender,$e)"
        "$font=New-Object System.Drawing.Font('Arial',12);"
        "try{$e.Graphics.DrawString(('DEVICES SIMULATOR OS TEST '+$script:DSLabel),"
        "$font,[System.Drawing.Brushes]::Black,25,50);"
        "$e.HasMorePages=$false}finally{$font.Dispose()}});"
        "try{$d.Print();Write-Output ('Queued '+$script:DSLabel)}"
        "finally{$d.Dispose()}"
    )
    try:
        return runner(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
                      capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError("Windows spooler submission failed: " + str(exc)[:250]) from exc


def print_readiness(preset: str, hub_output: str | Path, *,
                    registration=get_registration, opener=urlopen,
                    runner=subprocess.run, system: str | None = None) -> dict:
    """Read-only check: does the OS queue point at our live, matching output root?

    This does not submit a job, create output directories, or change CUPS.
    Every check has an actionable result to distinguish 'not installed' from
    'CUPS accepted but the JPG is somewhere else'.
    """
    if preset not in PRINTERS:
        raise ValueError("Only the simulated Brother/Zebra queues are supported")
    host = system or platform.system()
    queue, _label, uri = PRINTERS[preset]
    root = Path(hub_output).expanduser().resolve()
    checks = []
    def check(key, okay, detail, action):
        checks.append({"key": key, "ok": bool(okay), "detail": str(detail)[:450],
                       "next_step": None if okay else action})

    if host not in ("Linux", "Darwin", "Windows"):
        check("platform", False, "OS print tests are supported on Windows, macOS and Linux.",
              "Use a supported desktop operating system.")
    else:
        description = ("Windows native GDI spooler sample (experimental)" if host == "Windows"
                       else f"{host} CUPS sample")
        check("platform", True, description, "")

    state = registration(preset)
    found = state.get("status") == "registered"
    check("queue", found,
          state.get("details") or f"Queue {queue} registration status: {state.get('status', 'unknown')}",
          "Start the IPP service, then install the simulator printer queue in System Integration. A conflicting queue name must be resolved manually.")
    # The IPP diagnostics endpoint is deliberately bound to 127.0.0.1.
    observed = None
    try:
        with opener("http://127.0.0.1:8631/diagnostics", timeout=2) as response:
            observed = json.load(response)
        if not isinstance(observed, dict) or not isinstance(observed.get("output_dir"), str):
            observed = None
    except (OSError, ValueError, TimeoutError):
        pass
    check("ipp_service", observed is not None,
          "Local IPP diagnostics responding" if observed else "IPP service is not responding with its output path on port 8631",
          "Start Devices Simulator's IPP service. Confirm another process is not occupying port 8631.")

    ipp_root = (Path(observed["output_dir"]).expanduser().resolve() if observed else None)
    match = ipp_root is not None and ipp_root == root
    check("output_directory", match,
          f"Hub: {root}; IPP: {ipp_root if ipp_root else 'unavailable'}",
          "The Hub and IPP services must use the SAME --output folder. Restart the old IPP process, then launch both services with matching paths.")

    if host in ("Linux", "Darwin") and found:
        try:
            result = runner(["lpstat", "-p", queue, "-l"], capture_output=True,
                            text=True, timeout=5)
            output = ((result.stdout or "") + " " + (result.stderr or "")).strip()
            # CUPS emits 'printer NAME disabled since ...' when queue is stopped.
            enabled = result.returncode == 0 and "disabled" not in output.lower()
            check("queue_enabled", enabled, output[:450] or "CUPS queue status unavailable",
                  "Enable the simulator queue using cupsenable, clear or cancel stalled jobs, then retry the marked OS Print Test.")
        except (OSError, subprocess.TimeoutExpired) as exc:
            check("queue_enabled", False, str(exc),
                  "Confirm CUPS is running and lpstat can query the printer.")
    elif host in ("Linux", "Darwin"):
        check("queue_enabled", False, "No verified queue to query",
              "Install and verify the simulator OS printer queue first.")
    elif host == "Windows" and found:
        health = windows_spooler_status(queue, runner=runner)
        check("spooler", health["spooler"], health["detail"],
              "Start the Windows Print Spooler service; check Windows Services and printing permissions.")
        check("queue_enabled", health["queue_enabled"], health["detail"],
              "Check that the simulator's Windows printer queue is online and not paused/offline.")
    elif host == "Windows":
        check("spooler", False, "No verified simulator queue to inspect",
              "Verify the exact simulator queue and IPP endpoint before sending a test.")
        check("queue_enabled", False, "No verified simulator queue to inspect",
              "Install the simulator Windows IPP printer queue first.")

    return {"preset": preset, "queue": queue, "uri": uri, "platform": host,
            "status": "ready" if all(item["ok"] for item in checks) else "blocked",
            "checks": checks, "hub_output_dir": str(root),
            "ipp_output_dir": str(ipp_root) if ipp_root else None,
            "scope": "read_only_os_print_path"}

def verify_print_roundtrip(preset: str, output: str | Path, *,
                           registration=get_registration, runner=subprocess.run,
                           sleep=time.sleep, timeout=35.0) -> dict:
    if preset not in PRINTERS:
        raise ValueError("Only simulated Brother/Zebra printers can be tested")
    system = platform.system()
    if system not in ("Linux", "Darwin", "Windows"):
        raise RuntimeError("Native OS print roundtrip needs Windows, macOS or Linux")
    state = registration(preset)
    if state.get("status") != "registered":
        raise RuntimeError("OS printer queue and simulator endpoint must be verified before printing")
    name = PRINTERS[preset][0]
    tag = "DS-OS-TEST-" + uuid.uuid4().hex[:12]
    started = datetime.now(timezone.utc)
    if system == "Windows":
        result = submit_windows_sample(name, tag, runner=runner)
    else:
        import fitz
        width, height = (288, 432) if preset == "zebra" else (612, 792)
        pdf = fitz.open()
        page = pdf.new_page(width=width, height=height)
        page.insert_text((25, 60), "DEVICES SIMULATOR - OS TEST", fontsize=14)
        page.insert_text((25, 95), tag, fontsize=11)
        data = pdf.tobytes()
        pdf.close()
        try:
            result = runner(["lp", "-d", name, "-t", tag, "-"],
                            input=data, capture_output=True, timeout=20)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise RuntimeError(f"OS print submission failed: {exc}") from exc
    if result.returncode:
        error = result.stderr.decode("utf-8", "replace") if isinstance(result.stderr, bytes) else str(result.stderr)
        raise RuntimeError(("Windows spooler" if system == "Windows" else "CUPS") +
                           " rejected the print job: " + error[:350])
    output = Path(output).expanduser().resolve()
    deadline = time.monotonic() + timeout
    expected_profiles = ("zebra",) if preset == "zebra" else ("brother-tray1", "brother-tray2")
    last_error = None

    def matches_marker(metadata, folder):
        if metadata.get("title") == tag:
            return True
        # Some CUPS print paths replace the original job-name; verify the actual
        # source PDF's content to match this request, never unrelated new jobs.
        if metadata.get("format") != "pdf":
            return False
        original = folder / metadata.get("original", "original.pdf")
        if not original.is_file():
            return False
        try:
            import fitz
            with fitz.open(original) as doc:
                return any(tag in page.get_text() for page in doc)
        except Exception:
            return False

    while time.monotonic() < deadline:
        for profile in expected_profiles:
            for metadata_path in (output / profile).glob("*/job.json"):
                try:
                    j = json.loads(metadata_path.read_text(encoding="utf-8"))
                    created = (datetime.fromisoformat(j["created_at"].replace("Z", "+00:00"))
                               if j.get("created_at") else
                               datetime.fromtimestamp(metadata_path.stat().st_mtime, tz=timezone.utc))
                    # Some filesystems round modification times to whole seconds.
                    # A unique per-job UUID marker is still required below, so
                    # allow small timestamp quantization without accepting other jobs.
                    if created < started - timedelta(seconds=2):
                        continue
                except (ValueError, OSError, KeyError, TypeError):
                    continue
                if not matches_marker(j, metadata_path.parent):
                    continue
                if j.get("status") != "rendered":
                    last_error = j.get("error") or j.get("status", "not rendered")
                    continue
                images = [metadata_path.parent / item for item in j.get("images", [])]
                if images and all(p.is_file() and p.stat().st_size for p in images):
                    return {"result": "os_end_to_end_verified", "queue": name,
                            "job_id": j["id"], "count": len(images),
                            "profile": j.get("profile"), "scope": "os_spooler_to_ipp_to_jpg",
                            "title": tag}
        sleep(0.4)

    def inspect_queue():
        if system == "Windows":
            return windows_spooler_status(name)["detail"]
        try:
            p = subprocess.run(["lpstat", "-p", name, "-l"], capture_output=True,
                               text=True, timeout=4)
            return (p.stdout or p.stderr).strip()[:300]
        except (OSError, subprocess.TimeoutExpired):
            return "Queue status unavailable"

    def inspect_ipp():
        try:
            with urlopen("http://127.0.0.1:8631/diagnostics", timeout=2) as resp:
                diagnostics = json.load(resp)
            events = diagnostics.get("events", [])
            relevant = [x for x in events if x.get("operation") in
                        ("0x0000", "0x0002", "0x0005", "0x0006", "0x0009")]
            trace = ", ".join(
                f"{x.get('operation')}:{x.get('ipp_status')}:{x.get('capture_status') or '-'}"
                + (":" + str(x.get("detail"))[:70] if x.get("detail") else "")
                for x in relevant[-6:]
            )
            pending = [j.get("job_id") for j in diagnostics.get("jobs", [])
                       if j.get("state") in (3, 4, 5)]
            if pending:
                trace += f" Pending IPP jobs: {pending[-5:]}"
            return trace or "no IPP print requests received"
        except Exception:
            return "IPP diagnostics unavailable"

    hints = [("Windows accepted a GDI spool submission" if system == "Windows"
              else "CUPS accepted the spool request") +
             ", but the simulator could not confirm a JPG."]
    if last_error:
        hints.append("Renderer result: " + str(last_error)[:160])
    hints.append("IPP activity: " + inspect_ipp())
    hints.append(("Windows queue: " if system == "Windows" else "CUPS queue: ") + inspect_queue())
    if system == "Windows":
        hints.append("Windows IPP class drivers may submit document formats this experimental JPG renderer does not accept. Check the latest IPP document_format and capture_status above; queued does not mean rendered.")
    else:
        hints.append("If the printer is stuck, cancel the stalled test job and retry. Do not treat CUPS acceptance as successful output.")
    raise RuntimeError(" ".join(hints))
