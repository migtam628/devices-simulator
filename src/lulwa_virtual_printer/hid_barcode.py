"""macOS barcode keyboard INPUT simulator, not a HID device driver.

Quartz CGEvent keyboard input requires macOS Accessibility approval. This
process never appears in Printers & Scanners or as virtual USB hardware.
"""
from __future__ import annotations
import platform
import re
import selectors
import subprocess
import threading
import time
from pathlib import Path


def helper_binary() -> Path:
    bundled = Path(__file__).resolve().parent / "bin" / "mac_hid_scanner"
    if bundled.is_file():
        return bundled
    return Path(__file__).resolve().parents[2] / "packaging" / "macos" / "mac_hid_scanner"


def validate_barcode(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9._/-]{1,100}", value, re.ASCII):
        raise ValueError("Barcode must be 1–100 ASCII letters, digits, dots, dashes, underscores or slashes")
    return value


class MacBarcodeHID:
    """Keeps the existing API name for compatibility; never claims HID registration."""
    def __init__(self, system=None, binary=None):
        self.system = system or platform.system()
        self.binary = Path(binary) if binary else helper_binary()
        self.process = None
        self.lock = threading.RLock()
        self.last_error = ""
        self.last_sent_at = None
        self._pending = False

    def supported(self):
        return self.system == "Darwin" and self.binary.is_file()

    def active(self):
        return self.process is not None and self.process.poll() is None

    def state(self):
        return {"supported": self.supported(), "active": self.active(),
                "mode": "keyboard_event_simulation", "os_verified": False,
                "pending": self._pending, "last_error": self.last_error,
                "last_sent_at": self.last_sent_at}

    def _read_reply(self, timeout=7):
        if not self.process or not self.process.stdout:
            return ""
        selector = selectors.DefaultSelector()
        try:
            selector.register(self.process.stdout, selectors.EVENT_READ)
            if not selector.select(timeout=timeout):
                return ""
            return self.process.stdout.readline().strip()
        finally:
            selector.close()

    def start(self):
        with self.lock:
            if self.active(): return self.state()
            if not self.supported():
                raise RuntimeError("macOS keyboard simulator helper is unavailable on this build")
            self.last_error = ""
            self.process = None
            try:
                self.process = subprocess.Popen([str(self.binary)], stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
                line = self._read_reply()
                if not line.startswith("READY") or self.process.poll() is not None:
                    if "ACCESSIBILITY_PERMISSION_REQUIRED" in line:
                        raise RuntimeError("macOS Accessibility permission required. Open System Settings > Privacy & Security > Accessibility, approve DevicesSimulator or the helper, then relaunch.")
                    detail = line if line.startswith("ERR ") else "Helper did not start; check macOS support"
                    raise RuntimeError(detail)
            except Exception as exc:
                self.last_error = str(exc)
                self.stop()
                raise RuntimeError(self.last_error) from exc
            return self.state()

    def stop(self):
        with self.lock:
            proc = self.process
            self.process = None
            self._pending = False
            if proc is not None:
                if proc.poll() is None:
                    try:
                        proc.stdin.write("QUIT\n")
                        proc.stdin.flush()
                        proc.wait(timeout=2)
                    except (OSError, subprocess.TimeoutExpired):
                        proc.kill()
                        proc.wait(timeout=2)
                for stream in (proc.stdin, proc.stdout, proc.stderr):
                    if stream: stream.close()
            return self.state()

    def scan(self, value: str, delay: float = 3.0):
        barcode = validate_barcode(value)
        if not 0 <= delay <= 10:
            raise ValueError("Delay must be 0–10 seconds")
        with self.lock:
            if not self.active():
                raise RuntimeError("Activate keyboard simulation mode first")
            if self._pending:
                raise RuntimeError("A scan is already pending")
            self._pending = True
        def dispatch():
            try:
                time.sleep(delay)
                with self.lock:
                    if not self.active():
                        raise RuntimeError("Keyboard simulation stopped before scan")
                    self.process.stdin.write("SCAN " + barcode + "\n")
                    self.process.stdin.flush()
                    reply = self._read_reply(timeout=10)
                    if reply != "OK KEYBOARD_EVENTS_SENT":
                        raise RuntimeError(reply if reply.startswith("ERR ") else "No confirmation from keyboard simulator")
                    self.last_sent_at = time.time()
                    self.last_error = ""
            except Exception as exc:
                self.last_error = str(exc)
            finally:
                self._pending = False
        threading.Thread(target=dispatch, daemon=True, name="barcode-keyboard-input").start()
        return {"queued": True, "delay_seconds": delay,
                "message": "Switch focus to the target text field. This is keyboard simulation, not an HID device."}
