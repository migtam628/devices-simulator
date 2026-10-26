"""macOS virtual HID barcode-scanner controller.

A HID barcode scanner behaves as a keyboard; it is NOT a flatbed scanner and
is NOT shown in macOS Printers & Scanners. Device exists while helper runs.
"""
from __future__ import annotations

import platform
import re
import selectors
import subprocess
import sys
import threading
import time
from pathlib import Path


def helper_binary() -> Path:
    packaged = Path(__file__).resolve().parent / "bin" / "mac_hid_scanner"
    if packaged.is_file():
        return packaged
    # Source checkout: packaging/macos/mac_hid_scanner built with clang.
    return Path(__file__).resolve().parents[2] / "packaging" / "macos" / "mac_hid_scanner"


def validate_barcode(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9._/-]{1,100}", value, re.ASCII):
        raise ValueError("Barcode must have 1–100 ASCII letters, digits, dot, dash, underscore or slash")
    return value


class MacBarcodeHID:
    """One local user-session virtual keyboard; no persistent OS driver."""
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
                "mode": "temporary_virtual_keyboard", "os_verified": False,
                "pending": self._pending, "last_error": self.last_error}

    def start(self):
        with self.lock:
            if self.active():
                return self.state()
            if not self.supported():
                raise RuntimeError("macOS HID barcode helper is unavailable on this platform/build")
            self.last_error = ""
            try:
                self.process = subprocess.Popen(
                    [str(self.binary)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE, text=True, bufsize=1
                )
                selector = selectors.DefaultSelector()
                try:
                    selector.register(self.process.stdout, selectors.EVENT_READ)
                    ready = selector.select(timeout=7)
                    first = self.process.stdout.readline().strip() if ready else ""
                finally:
                    selector.close()
                if first != "READY" or self.process.poll() is not None:
                    raise RuntimeError("Virtual HID did not report READY; check macOS permissions and runtime support")
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
                        proc.wait(timeout=3)
                    except (OSError, subprocess.TimeoutExpired):
                        proc.kill()
                        proc.wait(timeout=3)
                for stream in (proc.stdin, proc.stdout, proc.stderr):
                    if stream:
                        stream.close()
            return self.state()

    def scan(self, text: str, delay: float = 3.0):
        code = validate_barcode(text)
        if not self.active():
            raise RuntimeError("Activate the HID barcode scanner first")
        if not 0 <= delay <= 10:
            raise ValueError("Delay must be 0–10 seconds")
        with self.lock:
            if self._pending:
                raise RuntimeError("A scan is already pending")
            self._pending = True
        def dispatch():
            try:
                time.sleep(delay)
                with self.lock:
                    if not self.active():
                        raise RuntimeError("Virtual HID stopped before barcode scan")
                    self.process.stdin.write("SCAN " + code + "\n")
                    self.process.stdin.flush()
                    # Do not echo captured code into logs/history.
                    self.last_sent_at = time.time()
            except Exception as exc:
                self.last_error = str(exc)
            finally:
                self._pending = False
        threading.Thread(target=dispatch, daemon=True, name="hid-barcode-scan").start()
        return {"queued": True, "delay_seconds": delay, "message": "Focus the target application input field before the scan fires."}
