"""Real TCP sockets / SICS subset, lifecycle and API authorization regression."""
import http.client
import json
import socket
import threading
import time

import pytest

from lulwa_virtual_printer.connection_engine import ConnectionEngine, MAX_COMMAND
from lulwa_virtual_printer.hub import HubStore, create_server


def scale_fixture(tmp_path):
    store=HubStore(tmp_path/"cfg",tmp_path/"out")
    device=store.create_device({"preset":"scale","name":"Network Shipping Scale",
                                "model_id":"generic-scale","transport":"network"})
    return store,device


def command(port, cmd, timeout=2):
    with socket.create_connection(("127.0.0.1",port),timeout=timeout) as sock:
        sock.settimeout(timeout)
        sock.sendall(cmd)
        return sock.recv(128)


def test_real_loopback_tcp_scale_protocol_and_live_weight(tmp_path):
    store,dev=scale_fixture(tmp_path)
    manager=ConnectionEngine(store)
    try:
        item=manager.start(dev["id"],0)
        assert item["host"]=="127.0.0.1" and item["running"]
        assert item["protocol"]=="sics_read_only_subset"
        port=item["port"]
        assert command(port,b"SI\r\n")==b"S S 0.000 kg\r\n"
        store.simulate_scale_reading(dev["id"],{"gross_kg":2.5,"tare_kg":.5,"unit":"lb"})
        assert command(port,b"S\r\n")==b"S S 4.409 lb\r\n"
        store.simulate_scale_reading(dev["id"],{"gross_kg":1.5,"unit":"kg","stable":False})
        assert command(port,b"S\r\n")==b"S I\r\n"
        assert command(port,b"SI\r\n")==b"S D 1.500 kg\r\n"
        store.simulate_scale_reading(dev["id"],{"gross_kg":75,"unit":"kg","stable":True})
        assert command(port,b"SI\r\n")==b"S +\r\n"
        assert command(port,b"UNSUPPORTED\r\n")==b"ES\r\n"
        snapshot=manager.snapshot()
        assert snapshot["scope"]=="localhost_only"
        assert snapshot["listeners"][0]["requests"]>=6
        assert snapshot["listeners"][0]["external_client_verified"]
        assert snapshot["listeners"][0]["events"][0]["operation"]=="unsupported"
    finally:
        manager.stop_all()
    with pytest.raises(OSError):
        command(port,b"SI\r\n")


def test_faults_session_handling_and_lifecycle(tmp_path):
    store,dev=scale_fixture(tmp_path)
    manager=ConnectionEngine(store)
    try:
        port=manager.start(dev["id"],0)["port"]
        with pytest.raises(RuntimeError,match="already listening"):
            manager.start(dev["id"])
        manager.set_fault(dev["id"],"busy")
        assert command(port,b"SI\r\n")==b"S I\r\n"
        manager.set_fault(dev["id"],"disconnect")
        assert command(port,b"SI\r\n")==b""
        manager.set_fault(dev["id"],"none")
        assert command(port,b"S\n")==b"S S 0.000 kg\r\n"
        with pytest.raises(ValueError):
            manager.set_fault(dev["id"],"remote_code")
        assert command(port,b"X"*(MAX_COMMAND+2)+b"\n")==b""
        assert command(port,b"\xff\n")==b""
    finally:
        manager.stop_all()


def test_only_network_scales_allowed_loopback_port_and_no_autostart(tmp_path):
    store=HubStore(tmp_path/"cfg",tmp_path/"out")
    usb=store.create_device({"preset":"scale","name":"DYMO Scale","model_id":"dymo-m10","transport":"usb_hid"})
    printer=store.create_device({"preset":"zebra","name":"Label Printer"})
    store,network=store,store.create_device({"preset":"scale","name":"Network Scale","model_id":"generic-scale","transport":"network"})
    engine=ConnectionEngine(store)
    assert engine.snapshot()["listeners"]==[]
    with pytest.raises(ValueError,match="Network"):
        engine.start(usb["id"])
    with pytest.raises(ValueError,match="shipping-scale"):
        engine.start(printer["id"])
    for port in (-1,80,65536,True,"9123"):
        with pytest.raises(ValueError):
            engine.start(network["id"],port)
    item=engine.start(network["id"],0)
    try:
        with pytest.raises(RuntimeError,match="already"):
            engine.start(network["id"])
        with pytest.raises(LookupError):
            engine.stop("missing")
    finally:
        engine.stop_all()
    assert not engine.snapshot()["listeners"]
    # No background server is restored when the manager is recreated.
    assert ConnectionEngine(store).snapshot()["listeners"]==[]


def test_tcp_hub_api_authorization_and_profile_removal(tmp_path):
    server=create_server(port=0,state_dir=tmp_path/"cfg",output_dir=tmp_path/"out")
    dev=server.hub_store.create_device({"preset":"scale","name":"API Network Scale",
         "model_id":"generic-scale","transport":"network"})
    worker=threading.Thread(target=server.serve_forever,daemon=True)
    worker.start()
    con=http.client.HTTPConnection("127.0.0.1",server.server_port,timeout=5)
    hdr={"Content-Type":"application/json","X-Devices-Token":server.hub_token}
    try:
        def post(path,data,authorized=True):
            con.request("POST",path,json.dumps(data),headers=hdr if authorized else {"Content-Type":"application/json"})
            r=con.getresponse()
            return r.status,json.loads(r.read())
        status,_=post("/api/connections/start",{"device_id":dev["id"],"port":0,"confirm":True},False)
        assert status==403
        status,_=post("/api/connections/start",{"device_id":dev["id"],"port":0})
        assert status==400
        status,resp=post("/api/connections/start",{"device_id":dev["id"],"port":0,"confirm":True})
        assert status==200 and resp["connection"]["running"]
        port=resp["connection"]["port"]
        assert command(port,b"SI\r\n")==b"S S 0.000 kg\r\n"
        con.request("GET","/api/connections")
        r=con.getresponse()
        live=json.loads(r.read())
        assert r.status==200 and live["listeners"][0]["port"]==port
        status,_=post("/api/devices/"+dev["id"]+"/model",{"model_id":"generic-scale","transport":"usb_hid"})
        assert status==409
        status,_=post("/api/connections/fault",{"device_id":dev["id"],"fault":"busy","confirm":True})
        assert status==200
        assert command(port,b"S\r\n")==b"S I\r\n"
        status,_=post("/api/devices/"+dev["id"],{"action":"remove_profile"})
        assert status==200
        assert server.hub_connections.snapshot()["listeners"]==[]
    finally:
        con.close()
        server.hub_connections.stop_all()
        server.shutdown()
        server.server_close()
        worker.join(timeout=4)
