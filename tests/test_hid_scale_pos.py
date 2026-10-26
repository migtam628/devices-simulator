import http.client,json,struct,threading
import pytest
from lulwa_virtual_printer.hid_scale_pos import REPORT_DESCRIPTOR,STATUS,UNITS,encode_weight_report,decode_weight_report
from lulwa_virtual_printer.mac_scale_hid import MacScaleHID
from lulwa_virtual_printer.hub import create_server

def test_report_descriptor_and_values():
    assert REPORT_DESCRIPTOR[:6]==bytes([0x05,0x8d,0x09,0x20,0xa1,0x01])
    assert bytes([0x85,0x03]) in REPORT_DESCRIPTOR
    report=encode_weight_report(1.234)
    assert report==struct.pack("<BBBBH",3,4,2,0,1234)
    assert decode_weight_report(report)["weight_g"]==1234
    assert encode_weight_report(0)[1]==STATUS["zero"]
    assert encode_weight_report(1,stable=False)[1]==STATUS["unstable"]
    assert encode_weight_report(6,capacity_kg=4.5)[1]==STATUS["over_capacity"]
    for args in ({"net_kg":float("nan")},{"net_kg":-1},{"net_kg":1,"stable":"yes"},
                 {"net_kg":1,"capacity_kg":float("inf")}):
        with pytest.raises(ValueError):encode_weight_report(**args)

def test_no_mac_helper_no_false_connection(tmp_path):
    m=MacScaleHID(system="Linux",binary=tmp_path/"not-here")
    assert not m.state()["running"] and not m.state()["external_visible"]
    with pytest.raises(RuntimeError,match="unavailable"):m.start("scale-1")
    with pytest.raises(RuntimeError,match="Activate"):m.send("scale-1",1.0)

def test_http_consent_for_scale_virtual_hid(tmp_path):
    server=create_server(port=0,state_dir=tmp_path/"state",output_dir=tmp_path/"out")
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        conn=http.client.HTTPConnection("127.0.0.1",server.server_port,timeout=10)
        token={"X-Devices-Token":server.hub_token,"Content-Type":"application/json"}
        conn.request("POST","/api/devices",json.dumps({"preset":"scale","name":"M10","model_id":"dymo-m10","transport":"usb_hid"}),token)
        response=conn.getresponse();device=json.loads(response.read())["device"]
        assert response.status==201
        conn.request("POST","/api/scale-hid/start",json.dumps({"device_id":device["id"]}),token)
        response=conn.getresponse();response.read();assert response.status==400
        conn.request("POST","/api/scale-hid/start",json.dumps({"device_id":device["id"],"confirm":True}))
        response=conn.getresponse();response.read();assert response.status==403
        conn.request("GET","/api/state")
        response=conn.getresponse();state=json.loads(response.read())
        assert not state["scale_hid"]["running"] and not state["scale_hid"]["external_visible"]
        conn.close()
    finally:
        server.hub_scale_hid.stop()
        server.shutdown();server.server_close();thread.join(timeout=3)
