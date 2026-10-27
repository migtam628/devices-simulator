"""Opt-in, localhost-only TCP scale adapter.

Supports a deliberately small MT-SICS-style *read-only* subset (S and SI)
for generic/network-capable shipping-scale fixtures. This is not a certified
METTLER TOLEDO BC protocol implementation or an OS USB/COM/BLE device.

No listener starts on import or hub startup; users must explicitly opt in.
"""
from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
import socket
import socketserver
import threading

from .device_catalog import BY_ID

MAX_LISTENERS = 4
MAX_CLIENTS = 8
MAX_COMMAND = 128
FAULTS = frozenset(("none", "busy", "disconnect"))
# The I0 reply advertises only implemented operations, not complete SICS Level 0.
DISCOVERY_COMMANDS = ("I0", "I2", "I3", "I4", "S", "SI")


def utc_now():
    return datetime.now(timezone.utc).isoformat()


class _LocalTCPServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True
    request_queue_size = MAX_CLIENTS


class _ClientHandler(socketserver.StreamRequestHandler):
    def handle(self):
        adapter = self.server.adapter
        if not adapter.slots.acquire(blocking=False):
            adapter.record("capacity", "rejected")
            return
        adapter.connected(1)
        adapter.register_socket(self.request, True)
        try:
            self.request.settimeout(8)
            while adapter.running:
                try:
                    chunk = self.rfile.readline(MAX_COMMAND + 2)
                except (OSError, TimeoutError):
                    break
                if not chunk:
                    break
                if len(chunk) > MAX_COMMAND or not chunk.endswith(b"\n"):
                    adapter.record("invalid_frame", "closed")
                    break
                raw = chunk.strip()
                try:
                    command = raw.decode("ascii")
                except UnicodeDecodeError:
                    adapter.record("invalid_frame", "closed")
                    break
                if not command or len(command) > 16:
                    adapter.record("invalid_frame", "closed")
                    break
                response = adapter.response(command)
                if response is None:
                    break
                try:
                    self.wfile.write(response.encode("ascii") + b"\r\n")
                    self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError, OSError):
                    break
        finally:
            adapter.register_socket(self.request, False)
            adapter.connected(-1)
            adapter.slots.release()


class _Adapter:
    def __init__(self, store, device_id):
        self.store = store
        self.device_id = device_id
        self.slots = threading.BoundedSemaphore(MAX_CLIENTS)
        self.lock = threading.RLock()
        self.events = deque(maxlen=60)
        self.clients = 0
        self.sockets = set()
        self.requests = 0
        self.fault = "none"
        self.running = False
        self.server = None
        self.thread = None

    def record(self, operation, result):
        with self.lock:
            self.events.appendleft({"at": utc_now(), "operation": operation,
                                    "result": result})

    def connected(self, delta):
        with self.lock:
            self.clients += delta
            self.record("client", "connected" if delta > 0 else "disconnected")

    def register_socket(self, sock, connected):
        with self.lock:
            if connected:
                self.sockets.add(sock)
            else:
                self.sockets.discard(sock)

    def disconnect_sockets(self):
        # Close accepted clients during stop instead of leaving them blocked
        # on a stale 8-second read timeout.
        with self.lock:
            sockets = tuple(self.sockets)
        for sock in sockets:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

    def response(self, command):
        with self.lock:
            self.requests += 1
            if self.fault == "disconnect":
                self.record(command if command in DISCOVERY_COMMANDS else "unsupported", "disconnected")
                return None
            if self.fault == "busy":
                self.record(command if command in DISCOVERY_COMMANDS else "unsupported", "busy")
                return f"{command} I" if command in ("I0", "I2", "I3", "I4") else "S I"
        if command not in DISCOVERY_COMMANDS:
            self.record("unsupported", "rejected")
            return "ES"
        device = self.store.get_device(self.device_id)
        if device is None:
            self.record(command, "profile_removed")
            return f"{command} I" if command.startswith("I") else "S I"
        if command == "I0":
            self.record(command, "discovery")
            return "\r\n".join(
                f'I0 {"A" if i == len(DISCOVERY_COMMANDS) - 1 else "B"} 0 "{name}"'
                for i, name in enumerate(DISCOVERY_COMMANDS)
            )
        if command == "I2":
            model = BY_ID.get(device.get("model_id"), {})
            capacity = model.get("max_kg", 0)
            # A simulator-owned identifier, not a manufacturer's USB identity.
            reply = f'I2 A "DEVICES_SIM/{device.get("model_id", "generic-scale")}/{capacity}kg"'
            self.record(command, "identity")
            return reply
        if command == "I3":
            self.record(command, "identity")
            return 'I3 A "DevicesSimulator/0.12/fixture"'
        if command == "I4":
            self.record(command, "identity")
            return f'I4 A "SIM-{self.device_id.replace("-", "")[:12].upper()}"'
        reading = device.get("last_measurement")
        if not reading:
            # No user fixture has been set yet: represent an empty, stable scale.
            reading = {"weight": 0.0, "unit": "kg", "status": "stable"}
        status = reading.get("status", "stable")
        if status == "over_capacity":
            self.record(command, "over_capacity")
            return "S +"
        if status == "unstable" and command == "S":
            self.record(command, "unstable")
            return "S I"
        if status not in ("stable", "unstable"):
            self.record(command, "unavailable")
            return "S I"
        weight = reading.get("weight", 0)
        unit = reading.get("unit", "kg")
        if unit not in ("kg", "g", "lb", "oz") or not isinstance(weight, (float, int)):
            self.record(command, "invalid_fixture")
            return "S I"
        letter = "S" if status == "stable" else "D"
        self.record(command, status)
        return f"S {letter} {weight:.3f} {unit}"

    def snapshot(self):
        with self.lock:
            return {
                "device_id": self.device_id, "host": "127.0.0.1",
                "port": self.server.server_address[1] if self.server else None,
                "protocol": "sics_read_only_subset", "running": self.running,
                "clients": self.clients, "requests": self.requests,
                "fault": self.fault, "events": list(self.events),
                "external_client_verified": any(x["operation"] in ("S", "SI") and
                                                x["result"] in ("stable", "unstable", "over_capacity")
                                                for x in self.events),
            }


class ConnectionEngine:
    """Owns at most four explicitly started localhost listeners.

    Network endpoints are ephemeral and never auto-restored on launch.
    """
    def __init__(self, store):
        self.store = store
        self.lock = threading.RLock()
        self.adapters = {}
        # Imported lazily to keep POSIX-specific tty behavior off Windows.
        from .posix_serial import PosixSerialEngine
        self.serial = PosixSerialEngine(store)

    def snapshot(self):
        with self.lock:
            return {"listeners": [a.snapshot() for a in self.adapters.values()],
                    "serial_listeners": self.serial.snapshot(),
                    "serial_supported": __import__("os").name == "posix",
                    "supported": ["tcp_scale_sics_read_only", "posix_pty_scale_sics_read_only"],
                    "scope": "localhost_only", "max_listeners": MAX_LISTENERS}

    def start(self, device_id, port=0):
        if type(device_id) is not str:
            raise ValueError("Select an existing scale profile")
        if type(port) is not int or (port != 0 and not 1024 <= port <= 65535):
            raise ValueError("Port must be 0 (automatic) or 1024–65535")
        with self.lock:
            if device_id in self.adapters:
                raise RuntimeError("This scale is already listening")
            if len(self.adapters) >= MAX_LISTENERS:
                raise RuntimeError("Maximum simultaneous TCP listeners reached")
            device = self.store.get_device(device_id)
            if not device or device.get("category") != "scale":
                raise ValueError("An existing shipping-scale fixture is required")
            if device.get("transport") != "network":
                raise ValueError("Choose a scale model that supports network and save Network transport")
            # The model-catalog API already validates which physical models
            # declare network transport. Never imitate proprietary commands.
            adapter = _Adapter(self.store, device_id)
            try:
                server = _LocalTCPServer(("127.0.0.1", port), _ClientHandler)
            except OSError as exc:
                raise RuntimeError("Cannot bind localhost TCP port (already in use or unavailable)") from exc
            try:
                server.adapter = adapter
                adapter.server = server
                adapter.running = True
                thread = threading.Thread(target=server.serve_forever,
                                          name="DevicesTCPScale-" + device_id[:8],
                                          kwargs={"poll_interval": 0.1}, daemon=True)
                thread.start()
                adapter.thread = thread
                self.adapters[device_id] = adapter
                adapter.record("listener", "started")
                return adapter.snapshot()
            except Exception:
                adapter.running = False
                server.server_close()
                raise

    def probe(self, device_id):
        """Run a REAL TCP client self-test; not proof of 3rd-party compatibility."""
        with self.lock:
            adapter = self.adapters.get(device_id)
            if adapter is None:
                raise LookupError("No active TCP listener for this device")
            port = adapter.server.server_address[1]
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=2) as client:
                client.settimeout(2)
                client.sendall(b"SI\r\n")
                reply = client.recv(128)
        except OSError as exc:
            raise RuntimeError("TCP loopback probe failed: " + type(exc).__name__) from exc
        # A valid SICS-style response is expected for a healthy scale.
        passed = reply.startswith((b"S S ", b"S D ", b"S +\r\n", b"S I\r\n"))
        return {"device_id": device_id, "port": port, "test": "local_tcp_si",
                "passed": passed, "response_ascii": reply.decode("ascii", "replace")[:100],
                "note": "A loopback probe is not a verified third-party integration"}

    def set_fault(self, device_id, fault):
        if fault not in FAULTS or type(fault) is not str:
            raise ValueError("Fault must be none, busy or disconnect")
        with self.lock:
            adapter = self.adapters.get(device_id)
            if adapter is None:
                raise LookupError("No active TCP listener for this device")
            with adapter.lock:
                adapter.fault = fault
                adapter.record("fault", fault)
            return adapter.snapshot()

    def stop(self, device_id):
        with self.lock:
            adapter = self.adapters.pop(device_id, None)
            if adapter is None:
                raise LookupError("No active TCP listener for this device")
            adapter.running = False
            adapter.record("listener", "stopping")
            adapter.disconnect_sockets()
            adapter.server.shutdown()
            adapter.server.server_close()
            adapter.thread.join(timeout=3)
            return adapter.snapshot()

    def start_serial(self, device_id):
        return self.serial.start(device_id)

    def probe_serial(self, device_id):
        return self.serial.probe(device_id)

    def stop_serial(self, device_id):
        return self.serial.stop(device_id)

    def set_serial_fault(self, device_id, mode):
        return self.serial.fault(device_id, mode)

    def stop_all(self):
        with self.lock:
            for device_id in list(self.adapters):
                self.stop(device_id)
            self.serial.stop_all()
