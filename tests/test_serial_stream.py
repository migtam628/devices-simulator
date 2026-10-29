"""Real POSIX PTY 2Hz stream, bounded lifetime, and opt-out behavior."""
import os
import select
import time

import pytest
from lulwa_virtual_printer.connection_engine import ConnectionEngine
from lulwa_virtual_printer.hub import HubStore
from lulwa_virtual_printer import posix_serial

pytestmark = pytest.mark.skipif(os.name != "posix" or not hasattr(os, "openpty"), reason="POSIX PTY only")


def _line(fd, buffer, timeout=3.0):
    deadline = time.monotonic() + timeout
    while True:
        newline = buffer.find(b"\n")
        if newline >= 0:
            line = bytes(buffer[:newline + 1])
            del buffer[:newline + 1]
            return line
        left = deadline - time.monotonic()
        assert left > 0, "Timed out waiting for PTY stream frame"
        ready, _, _ = select.select([fd], [], [], left)
        assert ready, "PTY did not produce another frame"
        chunk = os.read(fd, 512)
        assert chunk, "Unexpected PTY end of stream"
        buffer.extend(chunk)


def _setup(tmp_path):
    store = HubStore(tmp_path / "cfg", tmp_path / "out")
    device = store.create_device({"preset": "scale", "name": "Live Serial",
                                  "model_id": "generic-scale", "transport": "serial"})
    engine = ConnectionEngine(store)
    connection = engine.start_serial(device["id"])
    return store, device, engine, connection


def test_serial_stream_updates_fault_and_unsubscribe(tmp_path):
    store, device, engine, connection = _setup(tmp_path)
    fd = os.open(connection["path"], os.O_RDWR | os.O_NOCTTY)
    carry = bytearray()
    try:
        os.write(fd, b"SUB\r\n")
        assert _line(fd, carry) == b"SUB OK 500\r\n"
        assert _line(fd, carry) == b"EVT S S 0.000 kg\r\n"
        assert engine.snapshot()["serial_listeners"][0]["streaming"]
        store.simulate_scale_reading(device["id"], {
            "gross_kg": 2.4, "tare_kg": 0.4, "unit": "kg", "stable": True})
        assert any(_line(fd, carry) == b"EVT S S 2.000 kg\r\n" for _ in range(4))
        engine.set_serial_fault(device["id"], "busy")
        assert any(_line(fd, carry) == b"EVT S I\r\n" for _ in range(4))
        engine.set_serial_fault(device["id"], "none")
        os.write(fd, b"UNSUB\r\n")
        assert any(_line(fd, carry) == b"UNSUB OK\r\n" for _ in range(4))
        assert not engine.snapshot()["serial_listeners"][0]["streaming"]
        # Drain previously buffered data; no new periodic reports are sent.
        assert not select.select([fd], [], [], 0.7)[0]
        os.write(fd, b"SI\r\n")
        assert _line(fd, carry) == b"S S 2.000 kg\r\n"
        assert any(e["operation"] == "SUB" and e["result"] == "stopped"
                   for e in engine.snapshot()["serial_listeners"][0]["events"])
    finally:
        os.close(fd)
        engine.stop_all()


def test_serial_stream_expires_and_recovers(monkeypatch, tmp_path):
    monkeypatch.setattr(posix_serial, "SERIAL_STREAM_MAX_SECONDS", 1.05)
    store, device, engine, connection = _setup(tmp_path)
    fd = os.open(connection["path"], os.O_RDWR | os.O_NOCTTY)
    carry = bytearray()
    try:
        os.write(fd, b"SUB\n")
        assert _line(fd, carry) == b"SUB OK 500\r\n"
        events = []
        for _ in range(8):
            frame = _line(fd, carry)
            events.append(frame)
            if frame == b"EVT END LIMIT\r\n":
                break
        assert b"EVT END LIMIT\r\n" in events
        assert 1 <= sum(f.startswith(b"EVT S") for f in events) <= 3
        assert not engine.snapshot()["serial_listeners"][0]["streaming"]
        os.write(fd, b"SI\r\n")
        assert _line(fd, carry) == b"S S 0.000 kg\r\n"
        os.write(fd, b"SUB\r\n")
        assert _line(fd, carry) == b"SUB OK 500\r\n"
        assert _line(fd, carry).startswith(b"EVT S S ")
    finally:
        os.close(fd)
        engine.stop_all()
