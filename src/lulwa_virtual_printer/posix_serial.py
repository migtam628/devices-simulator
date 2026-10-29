"""Opt-in POSIX pseudo-terminal scale adapter (macOS and Linux only).

Creates a real OS PTY slave path, not USB or Windows COM hardware. Clients can
open the path as a serial port and send S/SI from the MT-SICS-style subset.
"""
from __future__ import annotations

import os
import select
import threading
import time

# A short-lived simulator-only protocol; NOT MT-SICS SIR.
SERIAL_STREAM_INTERVAL = 0.5
SERIAL_STREAM_MAX_SECONDS = 30.0
SERIAL_STREAM_MAX_EVENTS = 60

from .connection_engine import _Adapter, MAX_COMMAND

class _SerialAdapter(_Adapter):
    def __init__(self, store, device_id):
        super().__init__(store, device_id)
        self.master_fd = None
        self.slave_fd = None
        self.slave_path = None
        self.thread = None
        self.streaming = False
        self.stream_next = 0.0
        self.stream_deadline = 0.0
        self.stream_events = 0

    def snapshot(self):
        with self.lock:
            return {"device_id": self.device_id, "running": self.running,
                    "transport": "posix_pty", "protocol": "sics_read_only_subset",
                    "path": self.slave_path, "fault": self.fault,
                    "requests": self.requests, "events": list(self.events),
                    "streaming": self.streaming, "stream_events": self.stream_events,
                    "warning": "POSIX pseudo-terminal only; not a USB or Windows COM port"}

    def _write_line(self, response):
        # Never let an unread PTY indefinitely block the adapter's worker.
        packet = response.encode("ascii") + b"\r\n"
        try:
            if os.write(self.master_fd, packet) == len(packet):
                return True
        except (OSError, BlockingIOError):
            pass
        self.record("serial", "write_backpressure")
        return False

    def _end_stream(self, reason, signal=False):
        with self.lock:
            self.streaming = False
            self.record("SUB", reason)
        if signal:
            self._write_line("EVT END LIMIT")

    def _tick_stream(self):
        if not self.streaming:
            return
        now = time.monotonic()
        if now < self.stream_next:
            return
        if now >= self.stream_deadline or self.stream_events >= SERIAL_STREAM_MAX_EVENTS:
            self._end_stream("expired", signal=True)
            return
        reply = self.response("SI")
        if reply is None:
            self._end_stream("disconnected")
            return
        if not self._write_line("EVT " + reply):
            self._end_stream("backpressure")
            return
        with self.lock:
            self.stream_events += 1
            self.stream_next = now + SERIAL_STREAM_INTERVAL

    def serve(self):
        pending = bytearray()
        try:
            while self.running:
                # A single thread owns both serial responses and timed events:
                # command replies cannot be interleaved at the byte level.
                delay = 0.2
                if self.streaming:
                    delay = min(delay, max(0.0, self.stream_next - time.monotonic()))
                try:
                    readable, _, _ = select.select([self.master_fd], [], [], delay)
                    data = os.read(self.master_fd, 256) if readable else b""
                except BlockingIOError:
                    data = b""
                except (OSError, ValueError):
                    if not self.running:
                        break
                    self.record("serial", "io_error")
                    break
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
                        if command == "SUB":
                            # PTY has no per-client identity. SUB controls a
                            # shared, bounded stream; UNSUB stops it explicitly.
                            if self._write_line("SUB OK 500"):
                                now = time.monotonic()
                                with self.lock:
                                    self.streaming = True
                                    self.stream_next = now
                                    self.stream_deadline = now + SERIAL_STREAM_MAX_SECONDS
                                    self.stream_events = 0
                                    self.record("SUB", "started")
                            continue
                        if command == "UNSUB":
                            if self.streaming:
                                self._end_stream("stopped")
                            self._write_line("UNSUB OK")
                            continue
                        response = self.response(command)
                        if response is None:
                            # PTYs have no independent client socket to close:
                            # disconnect injection suppresses replies here.
                            continue
                        self._write_line(response)
                    elif len(pending) < MAX_COMMAND + 1:
                        pending.append(byte)
                    else:
                        # Bound memory and require the next newline to recover.
                        pending = bytearray(b"X" * (MAX_COMMAND + 1))
                self._tick_stream()
        finally:
            with self.lock:
                self.streaming = False
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
                os.set_blocking(master, False)
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

    def probe(self, device_id):
        """Open a second OS file descriptor for a real PTY roundtrip."""
        with self.lock:
            adapter = self.adapters.get(device_id)
            if not adapter or not adapter.running:
                raise LookupError("No active serial scale fixture")
            path = adapter.slave_path
        try:
            fd = os.open(path, os.O_RDWR | os.O_NOCTTY)
            try:
                os.write(fd, b"SI\r\n")
                readable, _, _ = select.select([fd], [], [], 1.5)
                reply = os.read(fd, 128) if readable else b""
            finally:
                os.close(fd)
        except OSError as exc:
            raise RuntimeError("Local PTY test failed: " + type(exc).__name__) from exc
        passed = reply.startswith((b"S S ", b"S D ", b"S +\r\n", b"S I\r\n"))
        return {"device_id": device_id, "test": "local_pty_si",
                "path": path, "passed": passed,
                "response_ascii": reply.decode("ascii", "replace")[:100],
                "note": "A local PTY probe is not proof of third-party software compatibility"}

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
