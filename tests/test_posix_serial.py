"""macOS/Linux POSIX PTY scale: real serial endpoint, no fake Windows COM."""
import http.client
import json
import os
import select
import threading

import pytest

from lulwa_virtual_printer.connection_engine import ConnectionEngine
from lulwa_virtual_printer.hub import HubStore, create_server

pytestmark=pytest.mark.skipif(os.name!="posix" or not hasattr(os,"openpty"),reason="POSIX PTY only")


def serial_setup(tmp_path):
    store=HubStore(tmp_path/"cfg",tmp_path/"out")
    d=store.create_device({"preset":"scale","name":"Serial Scale",
                           "model_id":"generic-scale","transport":"serial"})
    return store,d


def serial_command(fd,command):
    os.write(fd,command)
    ready,_,_=select.select([fd],[],[],3)
    assert ready,"Expected a serial fixture reply"
    return os.read(fd,128)


def test_real_pty_device_serial_commands_and_weight(tmp_path):
    store,d=serial_setup(tmp_path)
    engine=ConnectionEngine(store)
    try:
        item=engine.start_serial(d["id"])
        assert item["transport"]=="posix_pty"
        assert item["running"] and item["path"].startswith("/dev/")
        probe=engine.serial.probe(d["id"])
        assert probe["passed"] and probe["response_ascii"].startswith("S S 0.000 kg")
        fd=os.open(item["path"],os.O_RDWR|os.O_NOCTTY)
        try:
            assert serial_command(fd,b"SI\r\n")==b"S S 0.000 kg\r\n"
            store.simulate_scale_reading(d["id"],{"gross_kg":3.0,"tare_kg":1.0,"unit":"lb"})
            assert serial_command(fd,b"S\r\n")==b"S S 4.409 lb\r\n"
            store.simulate_scale_reading(d["id"],{"gross_kg":1.1,"unit":"kg","stable":False})
            assert serial_command(fd,b"S\r\n")==b"S I\r\n"
            assert serial_command(fd,b"SI\r\n")==b"S D 1.100 kg\r\n"
            assert serial_command(fd,b"NOTSUPPORTED\r\n")==b"ES\r\n"
            engine.set_serial_fault(d["id"],"busy")
            assert serial_command(fd,b"S\r\n")==b"S I\r\n"
            engine.set_serial_fault(d["id"],"disconnect")
            os.write(fd,b"SI\r\n")
            assert not select.select([fd],[],[],0.35)[0],"PTY fault should suppress responses"
            engine.set_serial_fault(d["id"],"none")
            assert serial_command(fd,b"SI\r\n")==b"S D 1.100 kg\r\n"
        finally:
            os.close(fd)
    finally:
        engine.stop_all()
    assert engine.snapshot()["serial_listeners"]==[]


def test_serial_validation_and_explicit_start(tmp_path):
    store,d=serial_setup(tmp_path)
    usb=store.create_device({"preset":"scale","name":"USB-only","model_id":"dymo-m10","transport":"usb_hid"})
    engine=ConnectionEngine(store)
    assert engine.snapshot()["serial_listeners"]==[]
    assert engine.snapshot()["serial_supported"]
    with pytest.raises(ValueError,match="RS-232"):
        engine.start_serial(usb["id"])
    engine.start_serial(d["id"])
    with pytest.raises(RuntimeError,match="already active"):
        engine.start_serial(d["id"])
    engine.stop_serial(d["id"])
    with pytest.raises(LookupError):
        engine.stop_serial(d["id"])


def test_serial_http_start_fault_stop_and_cleanup(tmp_path):
    server=create_server(port=0,state_dir=tmp_path/"cfg",output_dir=tmp_path/"out")
    device=server.hub_store.create_device({"preset":"scale","name":"API Serial",
                        "model_id":"generic-scale","transport":"serial"})
    thread=threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    conn=http.client.HTTPConnection("127.0.0.1",server.server_port,timeout=6)
    hdr={"Content-Type":"application/json","X-Devices-Token":server.hub_token}
    def call(path,data):
        conn.request("POST",path,json.dumps(data),hdr)
        response=conn.getresponse()
        return response.status,json.loads(response.read())
    try:
        status,_=call("/api/connections/serial-start",{"device_id":device["id"]})
        assert status==400
        status,data=call("/api/connections/serial-start",{"device_id":device["id"],"confirm":True})
        assert status==200 and data["connection"]["running"]
        path=data["connection"]["path"]
        fd=os.open(path,os.O_RDWR|os.O_NOCTTY)
        try:
            assert serial_command(fd,b"SI\r\n")==b"S S 0.000 kg\r\n"
            status,_=call("/api/devices/"+device["id"]+"/model",
                          {"model_id":"generic-scale","transport":"network"})
            assert status==409
            status,_=call("/api/connections/serial-fault",{
                "device_id":device["id"],"fault":"busy","confirm":True})
            assert status==200
            assert serial_command(fd,b"SI\r\n")==b"S I\r\n"
        finally:
            os.close(fd)
        status,_=call("/api/connections/serial-stop",{"device_id":device["id"],"confirm":True})
        assert status==200
        assert not server.hub_connections.snapshot()["serial_listeners"]
        status,data=call("/api/connections/serial-start",{"device_id":device["id"],"confirm":True})
        assert status==200
    finally:
        conn.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=4)
    # Closing the hub must clean up all serial paths.
    assert not server.hub_connections.snapshot()["serial_listeners"]
