"""Real localhost socket tests for the opt-in experimental Zebra RAW TCP receiver."""
import http.client
import json
import socket
import threading
import time

import pytest
from PIL import Image

from lulwa_virtual_printer.raw_zpl import RawZPLListener
from lulwa_virtual_printer import hub


LABEL = (b"^XA^PW406^LL609^FO20,20^A0N,34,32^FDRAW TCP ZPL^FS"
         b"^FO20,100^BQN,2,5^FDLA,ORDER-2026^FS^XZ")


def wait_for(predicate, timeout=3):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        if predicate():
            return
        time.sleep(0.02)
    raise AssertionError("RAW TCP socket did not complete expected processing")


def send(port, data):
    with socket.create_connection(("127.0.0.1", port), timeout=2) as sock:
        sock.sendall(data)
        sock.shutdown(socket.SHUT_WR)


def test_opt_in_tcp_starts_off_by_default_and_saves_real_jpg(tmp_path):
    listener=RawZPLListener(tmp_path)
    assert not listener.status()["running"] and listener.status()["auto_start"] is False
    assert list(tmp_path.iterdir()) == []
    active=listener.start(port=0)
    try:
        assert active["running"] and active["host"] == "127.0.0.1"
        assert active["scope"] == "experimental_loopback_raw_zpl_only"
        send(active["port"], LABEL)
        wait_for(lambda: listener.status()["accepted_labels"]==1)
        files=list(tmp_path.glob("zebra/*/page-001.jpg"))
        assert len(files)==1
        assert files[0].stat().st_size>1000
        metadata=json.loads((files[0].parent/"job.json").read_text())
        assert metadata["format"] == "zpl" and metadata["status"] == "rendered"
        assert (files[0].parent/"original.zpl").read_bytes() == LABEL
        with Image.open(files[0]) as im:
            assert im.size==(406,609)
    finally:
        stopped=listener.stop()
        assert not stopped["running"]


def test_multiple_labels_one_tcp_connection_persist_separately(tmp_path):
    listener=RawZPLListener(tmp_path)
    port=listener.start(port=0)["port"]
    try:
        send(port,LABEL+b"\r\n"+LABEL)
        wait_for(lambda: listener.status()["accepted_labels"] == 2)
        assert len(list(tmp_path.glob("zebra/*/job.json")))==2
        assert len(list(tmp_path.glob("zebra/*/page-001.jpg")))==2
    finally:
        listener.stop()


@pytest.mark.parametrize("payload,error",[
    (b"NOT ZPL^XZ","expected_zpl_start"),
    (b"^XA^PW406^LL609^FO10,10^B3N,80^FDABC^FS^XZ","unsupported_zpl_commands"),
    (b"^XA^PW406^LL609^FDHALF","incomplete_label"),
    (b"BAD DATA","incomplete_label"),
    (b"^XA"+b"B"*1100000,"zpl_input_size_exceeded"),
])
def test_bad_raw_input_never_creates_jpg(tmp_path,payload,error):
    listener=RawZPLListener(tmp_path)
    port=listener.start(port=0)["port"]
    try:
        try:
            send(port,payload)
        except (ConnectionResetError,BrokenPipeError):
            pass  # oversized input is rejected while client still writes
        wait_for(lambda: listener.status()["rejected_connections_or_labels"]>=1)
        assert listener.status()["last_error"] == error
        assert not list(tmp_path.glob("zebra/*/page-001.jpg"))
    finally:
        listener.stop()


def test_occupied_port_fails_without_starting_second_listener(tmp_path):
    first=RawZPLListener(tmp_path)
    second=RawZPLListener(tmp_path)
    port=first.start(port=0)["port"]
    try:
        with pytest.raises(RuntimeError,match="busy"):
            second.start(port=port)
        assert second.status()["running"] is False
        with pytest.raises(RuntimeError,match="already running"):
            first.start(port=0)
        with pytest.raises(ValueError,match="port"):
            second.start(port="9100")
        with pytest.raises(ValueError,match="port"):
            second.start(port=-1)
    finally:
        first.stop()
        second.stop()


def test_hub_requires_token_and_explicit_confirmation(tmp_path,monkeypatch):
    # Use an ephemeral TCP port in CI rather than occupying production port 9100.
    original_start=RawZPLListener.start
    monkeypatch.setattr(RawZPLListener,"start",lambda self,port=9100: original_start(self,port=0))
    srv=hub.create_server(port=0,state_dir=tmp_path/"state",output_dir=tmp_path/"out")
    t=threading.Thread(target=srv.serve_forever,daemon=True)
    t.start()
    conn=http.client.HTTPConnection("127.0.0.1",srv.server_port,timeout=10)
    def post(path,body,auth=True):
        headers={"Content-Type":"application/json"}
        if auth:
            headers["X-Devices-Token"]=srv.hub_token
        conn.request("POST",path,json.dumps(body),headers)
        reply=conn.getresponse()
        return reply.status,json.loads(reply.read())
    try:
        assert not srv.hub_raw_zpl.status()["running"]
        assert post("/api/system/raw-zpl/start",{"confirm":True},False)[0]==403
        assert post("/api/system/raw-zpl/start",{"confirm":False})[0]==400
        assert not srv.hub_raw_zpl.status()["running"]
        code,response=post("/api/system/raw-zpl/start",{"confirm":True})
        assert code==200 and response["raw_zpl"]["running"] is True
        listen_port=response["raw_zpl"]["port"]
        send(listen_port,LABEL)
        wait_for(lambda: srv.hub_raw_zpl.status()["accepted_labels"]==1)
        conn.request("GET","/api/state")
        report=json.loads(conn.getresponse().read())
        assert report["raw_zpl"]["accepted_labels"]==1
        assert report["raw_zpl"]["host"]=="127.0.0.1"
        assert post("/api/system/raw-zpl/stop",{"confirm":True},False)[0]==403
        code,response=post("/api/system/raw-zpl/stop",{"confirm":True})
        assert code==200 and not response["raw_zpl"]["running"]
        assert list((tmp_path/"out").glob("zebra/*/page-001.jpg"))
    finally:
        conn.close();srv.shutdown();srv.server_close();t.join(timeout=3)
        assert not srv.hub_raw_zpl.status()["running"]


def test_dashboard_has_explicit_raw_tcp_control():
    path=hub.Path(hub.__file__).with_name("ui")/"index.html"
    html=path.read_text(encoding="utf-8")
    assert "Start local ZPL TCP" in html
    assert "Stop ZPL TCP listener" in html
    assert "raw-zpl-start" in html and "raw-zpl-stop" in html
    assert "/api/system/raw-zpl/" in html
