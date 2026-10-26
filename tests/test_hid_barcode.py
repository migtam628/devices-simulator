import http.client
import json
import threading
import pytest
from lulwa_virtual_printer import hub
from lulwa_virtual_printer.hid_barcode import MacBarcodeHID, validate_barcode

@pytest.mark.parametrize("code", ["LULWA1001", "0123456789", "SKU-A_1/TEST.3"])
def test_valid_codes(code):
    assert validate_barcode(code) == code

@pytest.mark.parametrize("code", ["", "A"*101, "BAD\nQUIT", "has spaces", "é", "SKU:123"])
def test_invalid_codes(code):
    with pytest.raises(ValueError):
        validate_barcode(code)

def test_unsupported_host(tmp_path):
    device = MacBarcodeHID(system="Linux", binary=tmp_path/"missing")
    assert not device.supported() and not device.active()
    assert not device.state()["os_verified"]
    with pytest.raises(RuntimeError, match="unavailable"):
        device.start()

def test_hid_requires_local_confirmation(tmp_path, monkeypatch):
    calls=[]
    class FakeHID:
        def state(self): return {"supported":True, "active":False, "os_verified":False}
        def scan(self, barcode, delay):
            calls.append((barcode,delay))
            return {"queued":True}
        def stop(self):return self.state()
        def start(self):return self.state()
    monkeypatch.setattr(hub, "MacBarcodeHID", lambda: FakeHID())
    server=hub.create_server(port=0,state_dir=tmp_path/"cfg",output_dir=tmp_path/"out")
    thread=threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    try:
        client=http.client.HTTPConnection("127.0.0.1",server.server_port,timeout=10)
        headers={"Content-Type":"application/json","X-Devices-Token":server.hub_token}
        for payload,expected in [({"barcode":"LULWA1001"},400),
                                 ({"confirm":True,"barcode":"LULWA1001"},200)]:
            client.request("POST","/api/hid/scan",json.dumps(payload),headers)
            response=client.getresponse()
            assert response.status==expected
            response.read()
        assert calls==[("LULWA1001",3.0)]
        client.request("GET","/api/state")
        response=client.getresponse()
        assert json.loads(response.read())["hid"]["supported"] is True
        client.close()
    finally:
        server.shutdown();server.server_close();thread.join(timeout=3)
