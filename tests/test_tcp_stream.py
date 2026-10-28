"""Live 2Hz TCP scale stream: genuine independent socket subscription.

SUB is explicitly a Devices Simulator transport extension, not MT-SICS SIR.
"""
import socket
import time

from lulwa_virtual_printer.connection_engine import ConnectionEngine
from lulwa_virtual_printer.hub import HubStore


def test_bounded_subscription_updates_and_faults(tmp_path):
    store=HubStore(tmp_path/"cfg",tmp_path/"out")
    scale=store.create_device({"preset":"scale","name":"Stream Scale",
                               "model_id":"generic-scale","transport":"network"})
    engine=ConnectionEngine(store)
    try:
        port=engine.start(scale["id"])["port"]
        with socket.create_connection(("127.0.0.1",port),timeout=3) as client:
            client.settimeout(3)
            reader=client.makefile("rb")
            try:
                client.sendall(b"SUB\r\n")
                assert reader.readline()==b"SUB OK 500\r\n"
                assert reader.readline()==b"EVT S S 0.000 kg\r\n"

                store.simulate_scale_reading(scale["id"],{
                    "gross_kg":2.4,"tare_kg":.4,"unit":"kg","stable":True})
                lines=[]
                for _ in range(5):
                    line=reader.readline()
                    lines.append(line)
                    if line==b"EVT S S 2.000 kg\r\n":
                        break
                assert b"EVT S S 2.000 kg\r\n" in lines

                engine.set_fault(scale["id"],"busy")
                assert any(reader.readline()==b"EVT S I\r\n" for _ in range(4))
                engine.set_fault(scale["id"],"none")
                store.simulate_scale_reading(scale["id"],{
                    "gross_kg":1.5,"tare_kg":0,"unit":"kg","stable":False})
                assert any(reader.readline()==b"EVT S D 1.500 kg\r\n" for _ in range(4))
                engine.set_fault(scale["id"],"disconnect")
                assert reader.readline()==b""
            finally:
                reader.close()
        assert any(x["operation"]=="SUB" and x["result"]=="started"
                   for x in engine.snapshot()["listeners"][0]["events"])
    finally:
        engine.stop_all()


def test_stopping_listener_terminates_streaming_client(tmp_path):
    store=HubStore(tmp_path/"cfg",tmp_path/"out")
    scale=store.create_device({"preset":"scale","name":"Stream Shutdown",
                               "model_id":"generic-scale","transport":"network"})
    engine=ConnectionEngine(store)
    try:
        port=engine.start(scale["id"])["port"]
        with socket.create_connection(("127.0.0.1",port),timeout=3) as client:
            client.settimeout(3)
            reader=client.makefile("rb")
            try:
                client.sendall(b"SUB\r\n")
                assert reader.readline()==b"SUB OK 500\r\n"
                assert reader.readline().startswith(b"EVT S S")
                start=time.monotonic()
                engine.stop(scale["id"])
                # Server closes accepted connection without waiting for 8s idle timeout.
                assert reader.readline()==b""
                assert time.monotonic()-start<3
            finally:
                reader.close()
        assert not engine.snapshot()["listeners"]
    finally:
        engine.stop_all()
