import http.client
import json
import threading
import pytest
from lulwa_virtual_printer import hub


def test_system_install_requires_explicit_confirmation(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(hub, "install_printer", lambda name: calls.append(name) or {"success":True,"status":"registered"})
    monkeypatch.setattr(hub, "get_registration", lambda name: {"status":"not_installed","queue":name})
    monkeypatch.setattr(hub, "service_ready", lambda: True)
    server=hub.create_server(port=0,state_dir=tmp_path/"config",output_dir=tmp_path/"out")
    worker=threading.Thread(target=server.serve_forever,daemon=True)
    worker.start()
    try:
        client=http.client.HTTPConnection("127.0.0.1",server.server_port,timeout=10)
        headers={"Content-Type":"application/json","X-Devices-Token":server.hub_token}
        for body,status in [
            ({"preset":"brother"},400),
            ({"preset":"scanner","confirm":True},400),
            ({"preset":"brother","confirm":True},200),
        ]:
            client.request("POST","/api/system/install",json.dumps(body),headers)
            reply=client.getresponse()
            assert reply.status==status, reply.read()
            reply.read()
        assert calls == ["brother"]
        client.close()
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=3)


def test_system_install_invalid_token_is_rejected(tmp_path, monkeypatch):
    calls=[]
    monkeypatch.setattr(hub, "install_printer", lambda name: calls.append(name))
    server=hub.create_server(port=0,state_dir=tmp_path/"config",output_dir=tmp_path/"out")
    worker=threading.Thread(target=server.serve_forever,daemon=True)
    worker.start()
    try:
        client=http.client.HTTPConnection("127.0.0.1",server.server_port,timeout=10)
        client.request("POST","/api/system/install",'{"preset":"brother","confirm":true}',{"Content-Type":"application/json"})
        response=client.getresponse()
        assert response.status==403
        response.read()
        assert calls==[]
        client.close()
    finally:
        server.shutdown();server.server_close();worker.join(timeout=3)
