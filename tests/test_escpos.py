"""ESC/POS 80mm bitmap and Hub capture regression coverage."""
import json
import pytest
from PIL import Image

from lulwa_virtual_printer.engine import capture, detect_format
from lulwa_virtual_printer.escpos_renderer import render_escpos
from lulwa_virtual_printer.hub import HubStore


def test_centered_bold_receipt_renders_real_ink():
    raw=b"\x1b@\x1ba\x01\x1bE\x01HELLO RECEIPT\n\x1ba\x00TOTAL $20.00\n\x1dV\x00"
    receipt=render_escpos(raw)
    assert receipt.width==576
    assert 80 < receipt.height < 500
    assert (0,0,0) in set(receipt.getdata())
    assert receipt.getpixel((0,0))==(255,255,255)


def test_raster_bit_image_rendered_bit_for_bit():
    # GS v 0, normal, 2 bytes per row, 2 rows: black top-left and top-right
    payload=b"\x1b@\x1d\x76\x30\x00\x02\x00\x02\x00"+bytes.fromhex("80010180")
    image=render_escpos(payload)
    assert image.getpixel((8,8))==(0,0,0)
    assert image.getpixel((9,8))==(255,255,255)
    assert image.getpixel((23,8))==(0,0,0)
    assert image.getpixel((8,9))==(255,255,255)
    assert image.getpixel((15,9))==(0,0,0)


def test_text_magnification_changes_receipt_height():
    normal=render_escpos(b"\x1b@TEXT\n")
    large=render_escpos(b"\x1b@\x1d\x21\x11TEXT\n")
    assert large.height>normal.height


@pytest.mark.parametrize("bad",[
    b"hello", b"\x1b@\x1bX", b"\x1b@\x1dX",
    b"\x1b@\x1d\x76\x30\x00\x02\x00\x02\x00\xff",
    b"\x1b@\x1d\x76\x30\x00\xff\xff\xff\xff",
    b"\x1b@\x1ba\x09", b"\x1b@\x1d\x21\xff",
])
def test_unsupported_or_truncated_receipts_fail_closed(bad):
    with pytest.raises(ValueError):
        render_escpos(bad)


def test_page_height_and_input_size_bounds():
    with pytest.raises(ValueError,match="1 MiB"):
        render_escpos(b"\x1b@" + b"A"*(1024*1024))
    with pytest.raises(ValueError,match="too long|exceeds"):
        render_escpos(b"\x1b@" + b"\n"*250)


def test_real_capture_writes_receipt_jpg_and_metadata(tmp_path):
    raw=b"\x1b@RECEIPT EXAMPLE\nTOTAL $5.00\n\x1dV\x00"
    assert detect_format(raw)=="escpos"
    job=capture(raw,"receipt",tmp_path,"receipt QA")
    assert job["status"]=="rendered"
    assert job["format"]=="escpos"
    assert job["images"]==["page-001.jpg"]
    folder=tmp_path/"receipt"
    file=next(folder.glob("*/page-001.jpg"))
    assert file.is_file() and file.stat().st_size>200
    with Image.open(file) as image:
        assert image.width==576
    meta=json.loads((file.parent/"job.json").read_text())
    assert meta["profile"]=="receipt" and meta["status"]=="rendered"


def test_saved_receipt_device_can_generate_sample_without_os_printer(tmp_path):
    store=HubStore(tmp_path/"cfg",tmp_path/"out")
    # Use the same model selection as Create Device in the application.
    from lulwa_virtual_printer.device_catalog import public_catalog
    cat=public_catalog()
    receipt_models=[m for m in cat["models"] if m["category"]=="receipt"]
    assert receipt_models
    model=receipt_models[0]
    device=store.create_device({"preset":"receipt","name":"Receipt QA",
        "model_id":model["id"],"transport":model["transports"][0]})
    result=store.test_device(device["id"])
    assert result["status"]=="rendered"
    assert result["profile"]=="receipt"
    assert store.list_jobs()[0]["id"]==result["id"]
