"""Catalog and in-app scale fixtures; no physical transport claims."""
import http.client
import json
import threading

import pytest

from lulwa_virtual_printer.device_catalog import MODELS, TRANSPORTS, DEFAULT_MODEL, select_model
from lulwa_virtual_printer.hub import PRESETS, HubStore, create_server


def test_every_preset_has_compatible_default_model():
    assert len(MODELS) >= 15
    for key, preset in PRESETS.items():
        model, transport = select_model(key, preset["category"])
        assert model["id"] == DEFAULT_MODEL[key]
        assert transport in model["transports"]
        assert transport in TRANSPORTS


def test_mismatched_category_and_connection_rejected(tmp_path):
    store = HubStore(tmp_path/"cfg", tmp_path/"out")
    for params in (
        {"preset": "scale", "name": "Wrong", "model_id": "zebra-zd421"},
        {"preset": "scale", "name": "Wrong", "model_id": "dymo-m25", "transport": "ble_gatt"},
        {"preset": "zebra", "name": "Wrong", "model_id": "brother-hll2460dw"},
    ):
        with pytest.raises(ValueError):
            store.create_device(params)
    assert store.list_devices() == []


def test_catalog_persists_scale_brand_model_and_usb_profile_only(tmp_path):
    cfg = tmp_path/"cfg"
    store = HubStore(cfg, tmp_path/"out")
    scale = store.create_device({
        "preset":"scale", "name":"Shipping M25",
        "model_id":"dymo-m25", "transport":"usb_hid"
    })
    assert scale["brand"] == "DYMO"
    assert scale["model"] == "M25"
    assert scale["transport"] == "usb_hid"
    assert scale["transport_status"] == "profile_only"
    assert scale["os_status"] == "not_verified"
    assert HubStore(cfg,tmp_path/"out").get_device(scale["id"])["model_id"] == "dymo-m25"


def test_scale_reading_tare_conversions_stability_capacity(tmp_path):
    store = HubStore(tmp_path/"cfg", tmp_path/"out")
    d = store.create_device({"preset":"scale","name":"Scale","model_id":"dymo-m25"})
    read = store.simulate_scale_reading(d["id"],{"gross_kg":2.5,"tare_kg":0.5,"unit":"lb","stable":True})
    assert read["status"] == "stable"
    assert read["weight"] == pytest.approx(4.409, abs=.002)
    assert read["net_kg"] == 2
    assert read["scope"] == "in_app_scale_fixture"
    assert read["transport_status"] == "not_connected"
    unstable = store.simulate_scale_reading(d["id"],{"gross_kg":.5,"unit":"g","stable":False})
    assert unstable["status"] == "unstable"
    assert unstable["weight"] == 500.0
    overloaded = store.simulate_scale_reading(d["id"],{"gross_kg":12,"unit":"kg"})
    assert overloaded["status"] == "over_capacity"
    assert overloaded["stable"] is False
    assert store.get_device(d["id"])["last_measurement"]["status"] == "over_capacity"


def test_invalid_scale_values_and_wrong_category(tmp_path):
    store = HubStore(tmp_path/"cfg", tmp_path/"out")
    s = store.create_device({"preset":"scale","name":"Fixture"})
    p = store.create_device({"preset":"brother","name":"Printer"})
    for values in [
        {"gross_kg":float("nan")},
        {"gross_kg":float("inf")},
        {"gross_kg":-1},
        {"gross_kg":1,"tare_kg":2},
        {"gross_kg":1,"unit":"stones"},
        {"gross_kg":1,"stable":"true"},
    ]:
        with pytest.raises(ValueError):
            store.simulate_scale_reading(s["id"],values)
    with pytest.raises(ValueError):
        store.simulate_scale_reading(p["id"],{"gross_kg":1})


def test_model_can_be_changed_within_category_and_not_cross_category(tmp_path):
    store = HubStore(tmp_path/"cfg",tmp_path/"out")
    d=store.create_device({"preset":"scale","name":"Test bench"})
    updated=store.update_model(d["id"],{"model_id":"ble-weight-standard","transport":"ble_gatt"})
    assert updated["transport"] == "ble_gatt"
    assert updated["brand"] == "Bluetooth SIG"
    assert updated["os_status"] == "not_verified"
    with pytest.raises(ValueError):
        store.update_model(d["id"],{"model_id":"zebra-zd421","transport":"ipp"})


def test_scale_http_endpoint_and_catalog(tmp_path):
    server=create_server(port=0,state_dir=tmp_path/"cfg",output_dir=tmp_path/"out")
    thread=threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    try:
        c=http.client.HTTPConnection("127.0.0.1",server.server_port,timeout=45)
        c.request("GET","/api/catalog")
        res=c.getresponse();cat=json.loads(res.read())
        assert res.status==200
        assert "scale" in {m["category"] for m in cat["models"]}
        assert "ble_gatt" in cat["transports"]
        headers={"Content-Type":"application/json","X-Devices-Token":server.hub_token}
        c.request("POST","/api/devices",json.dumps({"preset":"scale","name":"HTTP scale","model_id":"dymo-m25","transport":"usb_hid"}),headers)
        res=c.getresponse();d=json.loads(res.read())["device"]
        assert res.status==201
        c.request("POST",f'/api/devices/{d["id"]}/scale-reading',json.dumps({"gross_kg":3,"tare_kg":1,"unit":"kg"}),headers)
        res=c.getresponse();val=json.loads(res.read())
        assert res.status==200 and val["reading"]["weight"]==2
        c.request("GET","/api/state")
        state=json.loads(c.getresponse().read())
        assert state["devices"][0]["last_measurement"]["net_kg"]==2
        assert state["catalog"]["default_models"]["scale"]=="generic-scale"
        c.close()
    finally:
        server.shutdown();server.server_close();thread.join(timeout=3)
