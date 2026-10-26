"""Verify the actual packaged executable, without displaying a desktop window."""
from __future__ import annotations
import platform
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = "DevicesSimulator"


def main():
    system = platform.system()
    if system == "Windows":
        binary = ROOT / "dist" / APP / (APP + ".exe")
    elif system == "Darwin":
        binary = ROOT / "dist" / (APP + ".app") / "Contents" / "MacOS" / APP
    else:
        binary = ROOT / "dist" / APP / APP
    assert binary.is_file(), f"Packaged executable absent: {binary}"
    report = ROOT / "build" / "frozen-smoke-ok.txt"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.unlink(missing_ok=True)
    p = subprocess.run(
        [str(binary), "--self-test", "--self-test-report", str(report)],
        cwd=ROOT, timeout=100, text=True, capture_output=True,
    )
    if p.stdout:
        print(p.stdout)
    if p.stderr:
        print(p.stderr)
    assert p.returncode == 0, f"Frozen program exited with {p.returncode}"
    assert report.is_file() and report.read_text().startswith("PASS:"), "Frozen smoke test did not finish"
    print(f"Frozen executable smoke test passed on {system}")


if __name__ == "__main__":
    main()
