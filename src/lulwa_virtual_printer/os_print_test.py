"""Verify OS print queue -> local IPP -> real JPG roundtrip.

Only allowed preset queues are addressable. This is NOT a vendor printer
test and is never used to mark an order shipped.
"""
from __future__ import annotations
import json
import platform
import subprocess
import time
import uuid
from pathlib import Path

from .native_printers import PRINTERS, get_registration


def verify_print_roundtrip(preset: str, output: str | Path, *,
                           registration=get_registration, runner=subprocess.run,
                           sleep=time.sleep, timeout=12.0) -> dict:
    if preset not in PRINTERS:
        raise ValueError("Only simulated Brother/Zebra printers can be tested")
    system = platform.system()
    if system not in ("Linux", "Darwin"):
        raise RuntimeError("Native OS print roundtrip currently requires macOS/Linux CUPS lp")
    state = registration(preset)
    if state.get("status") != "registered":
        raise RuntimeError("OS printer queue and simulator endpoint must be verified before printing")
    import fitz
    name = PRINTERS[preset][0]
    tag = "DS-OS-TEST-" + uuid.uuid4().hex[:12]
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
        raise RuntimeError("CUPS rejected the print job: " + error[:350])
    output = Path(output).expanduser().resolve()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        for p in output.glob("*/*/job.json"):
            try:
                j = json.loads(p.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                continue
            if j.get("title") == tag and j.get("status") == "rendered" and j.get("images"):
                images = [p.parent / image for image in j["images"]]
                if all(x.is_file() for x in images):
                    return {"result": "os_end_to_end_verified", "queue": name,
                            "job_id": j["id"], "count": len(images), "profile": j.get("profile"),
                            "scope": "os_print_dialog_path", "title": tag}
        sleep(0.4)
    raise RuntimeError("CUPS accepted the job, but no JPG arrived from the simulator. Check output folder, IPP document format and printer queue.")
