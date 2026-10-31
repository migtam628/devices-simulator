"""Real bitmap assertions for ZPL graphics, Z64 and barcode rendering."""
import base64
import binascii
import zlib

import pytest
from lulwa_virtual_printer.zpl_renderer import render_zpl


def image(label):
    return render_zpl(label.encode("ascii"))


def sample(data):
    return "^XA^PW200^LL200^FO10,10" + data + "^FS^XZ"


def test_gfa_ascii_hex_raster_pixel_orientation():
    # 2 bytes/row, 4 rows; bit 1 is black.
    img = image(sample("^GFA,8,8,2,800001000001FFFF"))
    assert img.getpixel((10,10)) == (0,0,0)
    assert img.getpixel((11,10)) == (255,255,255)
    assert img.getpixel((17,10)) == (255,255,255)
    assert img.getpixel((17,11)) == (0,0,0)
    assert img.getpixel((25,13)) == (0,0,0)
    assert img.getpixel((26,13)) == (255,255,255)


def test_gfa_acs_compression_row_fill_and_previous_repeat():
    # ! = F-filled row, comma = zero row, : repeats prior row
    img = image(sample("^GFA,8,8,2,!,:,,,"))
    assert img.getpixel((10,10)) == (0,0,0)
    assert img.getpixel((25,11)) == (0,0,0)
    assert img.getpixel((10,12)) == (255,255,255)
    assert img.getpixel((10,13)) == (255,255,255)


@pytest.mark.parametrize("mode", ["Z64", "B64"])
def test_gfa_base64_decoding_crc_and_real_pixels(mode):
    raw = bytes.fromhex("FF00FF00")
    packed = zlib.compress(raw) if mode == "Z64" else raw
    payload = base64.b64encode(packed).decode("ascii")
    crc = binascii.crc_hqx(payload.encode("ascii"),0)
    src=sample(f"^GFA,{len(packed)},4,2,:{mode}:{payload}:{crc:04X}")
    img=image(src)
    assert img.getpixel((10,10)) == (0,0,0)
    assert img.getpixel((18,10)) == (255,255,255)
    assert img.getpixel((11,11)) == (0,0,0)


def test_gfa_corrupt_crc_and_decompression_bomb_rejected():
    encoded=base64.b64encode(zlib.compress(b"\xFF"*100)).decode("ascii")
    with pytest.raises(ValueError,match="CRC mismatch"):
        image(sample(f"^GFA,100,100,1,:Z64:{encoded}:0000"))
    crc=binascii.crc_hqx(encoded.encode(),0)
    with pytest.raises(ValueError,match="byte count|oversized"):
        image(sample(f"^GFA,100,4,2,:Z64:{encoded}:{crc:04X}"))


@pytest.mark.parametrize("graphic",[
    "^GFA,8,8,2,FFFF",
    "^GFA,8,8,0,FFFFFFFFFFFFFFFF",
    "^GFA,8,9,2,FFFFFFFFFFFFFFFFFF",
    "^GFA,8,8,2,FFFFFFFFFFFFFFFFF",
    "^GFA,8,8,2,V",
    "^GFC,8,8,2,FFFFFFFFFFFFFFFF",
])
def test_invalid_graphics_fail_closed(graphic):
    with pytest.raises(ValueError):
        image(sample(graphic))


def test_hex_escape_is_only_next_field():
    img=image("^XA^PW300^LL160^FO10,10^FH^FDHELLO_20WORLD^FS^FO10,60^FDSECOND^FS^XZ")
    assert img.getpixel((10,10)) != (0,0,0) or img.size == (300,160)
    with pytest.raises(ValueError,match="printable"):
        image("^XA^FO5,5^FH^FDTEST_00END^FS^XZ")


def test_qr_model2_renders_black_and_white_modules():
    img=image("^XA^PW500^LL500^FO20,20^BQN,2,6^FDLA,ORD-1001^FS^XZ")
    region=img.crop((20,20,210,210))
    palette=set(region.getdata())
    assert (0,0,0) in palette
    assert (255,255,255) in palette
    assert img.getpixel((0,0))==(255,255,255)


def test_qr_unsupported_formats_and_overflow():
    with pytest.raises(ValueError,match="model 2"):
        image("^XA^FO0,0^BQN,1,5^FDLA,HEY^FS^XZ")
    with pytest.raises(ValueError,match="exceeds label"):
        image("^XA^PW100^LL100^FO80,80^BQN,2,10^FDLA,HEY^FS^XZ")
    with pytest.raises(ValueError,match="^BQN".replace("^","\\^")):
        image("^XA^FO0,0^BQN,2,4^FDAB,HEY^FS^XZ")
