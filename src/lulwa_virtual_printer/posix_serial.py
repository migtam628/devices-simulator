"""Opt-in POSIX pseudo-terminal scale adapter (macOS and Linux only).

Creates a real OS PTY slave path, not USB or Windows COM hardware. Clients can
open the path as a serial port and send S/SI from the MT-SICS-style subset.
"""
from __future__ import annotations

import os
import select
import threading

from .connection_engine import _Adapter, MAX_COMMAND

class _SerialAdapter(_Adapter):
    def __init__(self, store, device_id):
        super().__init__(store, device_id)
        self.master_fd = None
        self.slave_fd = None
        self.slave_path = None
        self.thread = None

    def snapshot(self):
        with self.lock:
            return {"device_id": self.device_id, "running": self.running,
                    "transport": "posix_pty", "protocol": "sics_read_only_subset",
                    "path": self.slave_path, "fault": self.fault,
                    "requests": self.requests, "events": list(self.events),
                    "warning": "POSIX pseudo-terminal only; not a USB or Windows COM port"}

    def serve(self):
        pending = bytearray()
        try:
            while self.running:
                try:
                    readable, _, _ = select.select([self.master_fd], [], [], 0.2)
                    if not readable:
                        continue
                    data = os.read(self.master_fd, 256)
                except (OSError, ValueError):
                    if not self.running:
                        break
                    self.record("serial", "io_error")
                    break
                if not data:
                    continue
                for byte in data:
                    if byte == 10:
                        raw = bytes(pending).rstrip(b"\r")
                        pending.clear()
                        if len(raw) > MAX_COMMAND or len(raw) > 16:
                            self.record("invalid_frame", "rejected")
                            continue
                        try:
                            command = raw.decode("ascii")
                        except UnicodeDecodeError:
                            self.record("invalid_frame", "rejected")
                            continue
                        if not command:
                            continue
                        response = self.response(command)
                        if response is None:
                            # PTYs have no independent client socket to close:
                            # disconnect injection suppresses replies here.
                            continue
                        try:
                            os.write(self.master_fd, response.encode("ascii") + b"\r\n")
                        except OSError:
                            self.record("serial", "write_error")
                            break
                    elif len(pending) < MAX_COMMAND + 1:
                        pending.append(byte)
                    else:
                        # Bound memory and require the next newline to recover.
                        pending = bytearray(b"X" * (MAX_COMMAND + 1))
        finally:
            self.running = False

    def close(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
        for fd in (self.master_fd, self.slave_fd):
            if fd is not None:
                try:
                    os.close(fd)
                except OSError:
                    pass
        self.master_fd = self.slave_fd = None
        self.record("listener", "stopped")


class PosixSerialEngine:
    def __init__(self, store):
        self.store = store
        self.lock = threading.RLock()
        self.adapters = {}

    def snapshot(self):
        with self.lock:
            return [adapter.snapshot() for adapter in self.adapters.values()]

    def start(self, device_id):
        if not hasattr(os, "openpty") or os.name != "posix":
            raise RuntimeError("POSIX serial fixtures are available only on macOS/Linux")
        with self.lock:
            if device_id in self.adapters:
                raise RuntimeError("This serial scale is already active")
            if len(self.adapters) >= 4:
                raise RuntimeError("Maximum active serial fixtures reached")
            device = self.store.get_device(device_id)
            if not device or device.get("category") != "scale" or device.get("transport") != "serial":
                raise ValueError("Select an existing scale model with RS-232 / serial transport")
            import tty
            adapter = _SerialAdapter(self.store, device_id)
            try:
                master, slave = os.openpty()
                adapter.master_fd, adapter.slave_fd = master, slave
                tty.setraw(slave)
                adapter.slave_path = os.ttyname(slave)
                adapter.running = True
                thread = threading.Thread(target=adapter.serve, daemon=True,
                                          name="DevicesSerialScale-" + device_id[:8])
                adapter.thread = thread
                thread.start()
                self.adapters[device_id] = adapter
                adapter.record("listener", "started")
                return adapter.snapshot()
            except Exception:
                adapter.close()
                raise

    def fault(self, device_id, mode):
        if mode not in ("none", "busy", "disconnect") or type(mode) is not str:
            raise ValueError("Invalid serial fault mode")
        with self.lock:
            adapter = self.adapters.get(device_id)
            if not adapter:
                raise LookupError("No active serial scale fixture")
            with adapter.lock:
                adapter.fault = mode
                adapter.record("fault", mode)
            return adapter.snapshot()

    def stop(self, device_id):
        with self.lock:
            adapter = self.adapters.pop(device_id, None)
            if not adapter:
                raise LookupError("No active serial scale fixture")
            adapter.close()
            return adapter.snapshot()

    def stop_all(self):
        with self.lock:
            for key in list(self.adapters):
                self.stop(key)
