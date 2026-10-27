"""Real-socket read-only MT-SICS discovery and simulator identity checks."""
import os
import select
import socket

import pytest

from lulwa_virtual_printer.connection_engine import ConnectionEngine, DISCOVERY_COMMANDS
from lulwa_virtual_printer.hub import HubStore


def _scale(tmp_path, transport):
    store=HubStore(tmp_path/"state",tmp_path/"output")
    scale=store.create_device({"preset":"scale","name":"Discovery Scale",
                               "model_id":"generic-scale","transport":transport})
    return store,scale


def _query_tcp(sock, command):
    sock.sendall(command.encode("ascii")+b"\r\n")
    output=[]
    sock_file=sock.makefile("rb")
    try:
        while True:
            line=sock_file.readline()
            if not line:
                raise AssertionError("Socket closed before completed reply")
            output.append(line.decode("ascii").strip())
            if command != "I0" or line.startswith(b"I0 A "):
                return output
    finally:
        # Close the file wrapper without closing the underlying test socket.
        sock_file.close()


def test_tcp_discovery_inventory_identity_and_sessions(tmp_path):
    store,scale=_scale(tmp_path,"network")
    engine=ConnectionEngine(store)
    port=engine.start(scale["id"])["port"]
    try:
        with socket.create_connection(("127.0.0.1",port),timeout=3) as conn:
            conn.settimeout(3)
            # Use one connection and read the actual multi-line I0 response.
            with conn.makefile("rb") as reader:
                conn.sendall(b"I0\r\n")
                found=[]
                while True:
                    row=reader.readline().decode("ascii").strip()
                    found.append(row)
                    if row.startswith("I0 A "):
                        break
                assert len(found)==len(DISCOVERY_COMMANDS)
                assert found[0]=='I0 B 0 "I0"'
                assert found[-1]=='I0 A 0 "SI"'
                assert all(f'"{c}"' in found[i] for i,c in enumerate(DISCOVERY_COMMANDS))
                assert not any('"SIR"' in row or '"T"' in row or '"Z"' in row for row in found)
                for cmd in ("I2","I3","I4","S"):
                    conn.sendall((cmd+"\r\n").encode("ascii"))
                    reply=reader.readline().decode("ascii").strip()
                    if cmd=="I2":
                        assert reply=='I2 A "DEVICES_SIM/generic-scale/50kg"'
                    elif cmd=="I3":
                        assert reply=='I3 A "DevicesSimulator/0.12/fixture"'
                    elif cmd=="I4":
                        assert reply.startswith('I4 A "SIM-') and reply.endswith('"')
                        assert scale["id"].replace("-","")[:12].upper() in reply
                    else:
                        assert reply=="S S 0.000 kg"
                conn.sendall(b"I1\r\n")
                assert reader.readline()==b"ES\r\n"
        state=engine.snapshot()["listeners"][0]
        assert any(x["operation"]=="I0" and x["result"]=="discovery" for x in state["events"])
    finally:
        engine.stop_all()


def test_busy_identity_replies_with_command_specific_unavailable(tmp_path):
    store,scale=_scale(tmp_path,"network")
    engine=ConnectionEngine(store)
    try:
        port=engine.start(scale["id"])["port"]
        engine.set_fault(scale["id"],"busy")
        with socket.create_connection(("127.0.0.1",port),timeout=3) as conn:
            conn.settimeout(3)
            with conn.makefile("rb") as reader:
                conn.sendall(b"I2\r\n")
                assert reader.readline()==b"I2 I\r\n"
                conn.sendall(b"SI\r\n")
                assert reader.readline()==b"S I\r\n"
        engine.set_fault(scale["id"],"none")
        assert engine.probe(scale["id"])["passed"]
    finally:
        engine.stop_all()


@pytest.mark.skipif(os.name!="posix" or not hasattr(os,"openpty"),reason="POSIX serial only")
def test_serial_inquiry_uses_same_protocol_responder(tmp_path):
    store,scale=_scale(tmp_path,"serial")
    engine=ConnectionEngine(store)
    try:
        serial=engine.start_serial(scale["id"])
        fd=os.open(serial["path"],os.O_RDWR|os.O_NOCTTY)
        try:
            os.write(fd,b"I2\r\n")
            readable,_,_=select.select([fd],[],[],3)
            assert readable
            assert os.read(fd,128)==b'I2 A "DEVICES_SIM/generic-scale/50kg"\r\n'
            os.write(fd,b"I4\r\n")
            readable,_,_=select.select([fd],[],[],3)
            assert readable
            assert os.read(fd,128).startswith(b'I4 A "SIM-')
        finally:
            os.close(fd)
    finally:
        engine.stop_all()
