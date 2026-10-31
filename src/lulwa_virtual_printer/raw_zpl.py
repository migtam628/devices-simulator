"""Opt-in, loopback-only RAW TCP ZPL input for local development.

This is NOT an OS-installed printer, a PrintNode-certified port, an actual
Zebra device, or a remotely accessible JetDirect service. It never opens
a listener without explicit API activation and does not auto-start.
"""
from __future__ import annotations

import socket
import socketserver
import threading
from pathlib import Path

from .engine import capture
from .zpl_renderer import MAX_LABEL_BYTES

MAX_LABELS_PER_CONNECTION = 10
DEFAULT_PORT = 9100


class RawZPLListener:
    """Manually activated localhost TCP printing to the Zebra JPG gallery."""

    def __init__(self, output: str | Path):
        self.output = Path(output).expanduser().resolve()
        self._guard = threading.RLock()
        self._server = None
        self._worker = None
        self.accepted = 0
        self.rejected = 0
        self.last_error = None

    def status(self) -> dict:
        with self._guard:
            server = self._server
            return {
                "running": server is not None,
                "host": "127.0.0.1",
                "port": server.server_address[1] if server else None,
                "accepted_labels": self.accepted,
                "rejected_connections_or_labels": self.rejected,
                "last_error": self.last_error,
                "scope": "experimental_loopback_raw_zpl_only",
                "auto_start": False,
                "physical_printer": False,
            }

    def _record(self, *, accepted=False, error=None):
        with self._guard:
            if accepted:
                self.accepted += 1
                self.last_error = None
            else:
                self.rejected += 1
                # Error code only; never store raw customer label data.
                self.last_error = str(error or "invalid_label")[:120]

    def start(self, port: int = DEFAULT_PORT) -> dict:
        if type(port) is not int or not 0 <= port <= 65535:
            raise ValueError("Invalid local raw TCP port")
        with self._guard:
            if self._server is not None:
                raise RuntimeError("Raw ZPL TCP listener is already running")
            owner = self

            class Server(socketserver.ThreadingTCPServer):
                allow_reuse_address = True
                daemon_threads = True
                request_queue_size = 5

            class Handler(socketserver.BaseRequestHandler):
                def handle(self):
                    self.request.settimeout(3)
                    remaining = b""
                    printed = 0
                    while printed < MAX_LABELS_PER_CONNECTION:
                        with owner._guard:
                            if owner._server is None:
                                return
                        try:
                            block = self.request.recv(4096)
                        except socket.timeout:
                            if remaining.strip():
                                owner._record(error="incomplete_label_timeout")
                            return
                        except OSError:
                            return
                        if not block:
                            if remaining.strip():
                                owner._record(error="incomplete_label")
                            return
                        remaining += block
                        if len(remaining) > MAX_LABEL_BYTES + 4096:
                            owner._record(error="zpl_input_size_exceeded")
                            return
                        while b"^XZ" in remaining and printed < MAX_LABELS_PER_CONNECTION:
                            idx = remaining.index(b"^XZ") + 3
                            data, remaining = remaining[:idx].strip(), remaining[idx:]
                            if len(data) > MAX_LABEL_BYTES:
                                owner._record(error="zpl_label_size_exceeded")
                                return
                            if not data.startswith(b"^XA"):
                                owner._record(error="expected_zpl_start")
                                return
                            try:
                                result = capture(data, "zebra", owner.output,
                                                 title="RAW TCP ZPL QA")
                            except (OSError, ValueError):
                                owner._record(error="capture_failed")
                                return
                            if result.get("status") != "rendered" or not result.get("images"):
                                owner._record(error="unsupported_zpl_commands")
                                return
                            owner._record(accepted=True)
                            printed += 1
                        if printed == MAX_LABELS_PER_CONNECTION:
                            if remaining.strip():
                                owner._record(error="zpl_label_batch_limit")
                            return
                    # No commands are sent to real printers; no ACK required.

            try:
                server = Server(("127.0.0.1", port), Handler)
            except OSError as exc:
                raise RuntimeError("Local raw ZPL TCP port is busy or unavailable") from exc
            self._server = server
            worker = threading.Thread(
                target=server.serve_forever,
                kwargs={"poll_interval": 0.1},
                name="devices-raw-zpl-tcp", daemon=True
            )
            self._worker = worker
            worker.start()
            return self.status()

    def stop(self) -> dict:
        with self._guard:
            server, worker = self._server, self._worker
            self._server, self._worker = None, None
        if server is not None:
            server.shutdown()
            server.server_close()
            if worker is not None:
                worker.join(timeout=3)
        return self.status()
