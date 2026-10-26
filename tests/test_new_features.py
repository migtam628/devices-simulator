import http.client
import json
import threading

from lulwa_virtual_printer.hub import HubStore, create_server


def test_fault_setting_and_persistence(tmp_path):
    store = HubStore(tmp_path/"settings", tmp_path/"output")
    d = store.create_device({"preset":"brother","name":"Fault Brother"})
    changed = store.configure_device(d["id"], {"fault":"paper_out","tray":"tray-2"})
    assert changed["fault"] == "paper_out"
    assert changed["tray"] == "tray-2"
    fail = store.test_device(d["id"])
    assert fail["status"] == "failed"
    assert fail["images"] == []
    assert "paper out" in fail["error"]
    persisted = HubStore(tmp_path/"settings",tmp_path/"output").get_device(d["id"])
    assert persisted["fault"] == "paper_out"
    assert store.list_jobs()[0]["status"] == "failed"
    store.configure_device(d["id"], {"fault":"none","tray":"tray-1"})
    ok = store.test_device(d["id"])
    assert ok["status"] == "rendered"


def test_studio_workflow_creates_two_jpgs(tmp_path):
    store = HubStore(tmp_path/"settings", tmp_path/"output")
    a = store.create_device({"preset":"brother","name":"Packing"})
    b = store.create_device({"preset":"zebra","name":"Labels"})
    result = store.run_shipping_demo(a["id"],b["id"])
    assert result["status"] == "completed"
    assert len(result["jobs"]) == 2
    assert all(j["images"] == ["page-001.jpg"] for j in result["jobs"])
    assert len(store.list_jobs()) == 2


def test_studio_does_not_accept_other_profiles(tmp_path):
    store = HubStore(tmp_path/"settings",tmp_path/"output")
    a = store.create_device({"preset":"scanner","name":"Flatbed"})
    b = store.create_device({"preset":"zebra","name":"Labels"})
    try:
        store.run_shipping_demo(a["id"],b["id"])
        assert False
    except ValueError as exc:
        assert "Brother and Zebra" in str(exc)


def test_studio_http_local_api(tmp_path):
    server=create_server(port=0,state_dir=tmp_path/"s",output_dir=tmp_path/"o")
    a=server.hub_store.create_device({"preset":"brother","name":"Brother"})
    b=server.hub_store.create_device({"preset":"zebra","name":"Zebra"})
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        c=http.client.HTTPConnection("127.0.0.1",server.server_port,timeout=15)
        headers={"Content-Type":"application/json","X-Devices-Token":server.hub_token}
        c.request("POST","/api/studio/run",json.dumps({"brother_id":a["id"],"zebra_id":b["id"]}),headers)
        result=c.getresponse()
        payload=json.loads(result.read())
        assert result.status==200 and payload["studio"]["status"]=="completed"
        c.close()
    finally:
        server.shutdown();server.server_close();thread.join(timeout=3)
