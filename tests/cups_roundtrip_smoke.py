"""Actual Linux CUPS -> simulator IPP -> JPG smoke test for GitHub Actions.

Invoked explicitly by the dedicated CI CUPS job (not ordinary pytest).
No physical printers and no remote network endpoints are used.
"""
from __future__ import annotations

import json
import subprocess
import tempfile
import threading
import traceback
from pathlib import Path
from urllib.request import urlopen

from lulwa_virtual_printer.ipp_server import start_server
from lulwa_virtual_printer.native_printers import PRINTERS
from lulwa_virtual_printer.os_print_test import verify_print_roundtrip


def checked(*args):
    print("+", " ".join(args), flush=True)
    result = subprocess.run(args, text=True, capture_output=True, timeout=35)
    print(result.stdout, result.stderr, flush=True)
    if result.returncode:
        raise RuntimeError(f"Command failed with exit {result.returncode}: {args!r}")
    return result


def main():
    with tempfile.TemporaryDirectory(prefix="devices-cups-") as directory:
        output = Path(directory) / "output"
        server = start_server(port=8631, output=output)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            for preset in ("zebra", "brother"):
                name, _, uri = PRINTERS[preset]
                try:
                    checked("sudo", "lpadmin", "-p", name, "-E", "-v", uri, "-m", "everywhere")
                    checked("lpstat", "-v", name)
                    report = verify_print_roundtrip(preset, output, timeout=40)
                    assert report["result"] == "os_end_to_end_verified"
                    job_dir = next(output.glob(report["profile"] + "/*/job.json"))
                    metadata = json.loads(job_dir.read_text(encoding="utf-8"))
                    assert metadata["status"] == "rendered", metadata
                    print("PASS:", preset, report, flush=True)
                finally:
                    subprocess.run(["sudo", "lpadmin", "-x", name], check=False, timeout=15)
        except Exception:
            traceback.print_exc()
            try:
                with urlopen("http://127.0.0.1:8631/diagnostics", timeout=3) as response:
                    print("IPP DIAGNOSTICS:", response.read().decode("utf-8"), flush=True)
            except Exception as e:
                print("IPP diagnostic endpoint failed:", repr(e), flush=True)
            for cmd in (["lpstat", "-t"], ["sudo", "tail", "-n", "100", "/var/log/cups/error_log"]):
                try:
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=6)
                    print("DIAG", cmd, result.stdout[-5000:], result.stderr[-1000:], flush=True)
                except Exception as e:
                    print("DIAG failed", str(e))
            raise
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=4)


if __name__ == "__main__":
    main()
