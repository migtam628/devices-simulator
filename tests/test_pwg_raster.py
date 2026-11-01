"""Real PWG RaS2 PackBits bytes, JPG pixels, and IPP transport regression tests.

Fixture writer is deliberately independent of the application decoder and
writes fields at the CUPS v2 header offsets from the official format spec.
"""
import http.client
import json
import struct
import threading

import pytest
from PIL import Image

from lulwa_virtual_printer.engine import capture, detect_format
from lulwa_virtual_printer.ipp import (
    CHARSET, LANGUAGE, MIMETYPE, NAME, URI, attr, parse_request
)
from lulwa_virtual_printer.ipp_server import printer_attributes, start_server
from lulwa_virtual_printer.pwg_raster import decode_pwg_raster


def pwg_page(width, height, channels, raster, *,
             colorspace=None, bpc=8, bpp=None, stride=None, colors=None, order=0,
             header_string=b"PwgRaster"):
    page = bytearray(1796)
    page[:len(header_string)] = header_string
    def integer(offset, value):
        struct.pack_into(">I", page, offset, value)
    integer(276, 300)
    integer(280, 300)
    integer(372, width)
    integer(376, height)
    integer(384, bpc)
    integer(388, bpp if bpp is not None else channels * 8)
    integer(392, stride if stride is not None else width * channels)
    integer(396, order)
    integer(400, colorspace if colorspace is not None else 18 if channels == 1 else 19)
    integer(420, colors if colors is not None else channels)
    integer(456, 1)
    integer(460, 1)
    return bytes(page) + raster


def gray_fixture():
    # Four sGray pixels, row repetition for the first two rows.
    # Literal run of four pixels: control 257-4=253 (0xFD).
    # Repeated four-pixel black row: control 4-1=3 (0x03).
    raster = bytes([1, 253, 255, 0, 128, 255,
                    0, 3, 0])
    return b"RaS2" + pwg_page(4, 3, 1, raster)


def rgb_fixture():
    # Two 24bit pixels per row, literal-control 0xFF=257-2.
    row1 = bytes([0, 255, 255, 0, 0, 0, 255, 0])
    row2 = bytes([0, 255, 0, 0, 255, 255, 255, 255])
    return b"RaS2" + pwg_page(2, 2, 3, row1 + row2)



def mono_fixture():
    """Packed 1-bit sGray with a padded 9th pixel and repeated scanline."""
    # 9 pixels/row -> 2 bytes. First two rows white,black alternating,
    # with the 9th pixel white (MSB of second byte). Third row is black.
    runs = bytes([1, 255, 0xAA, 0x80, 0, 255, 0, 0])
    return b"RaS2" + pwg_page(9, 3, 1, runs, bpc=1, bpp=1, stride=2)


def test_packed_sgray_1_msb_bit_orientation_padding_and_repeated_rows():
    images = decode_pwg_raster(mono_fixture())
    assert len(images) == 1
    image = images[0]
    assert image.mode == "RGB" and image.size == (9, 3)
    assert image.getpixel((0,0)) == (255,255,255)
    assert image.getpixel((1,0)) == (0,0,0)
    assert image.getpixel((8,0)) == (255,255,255)
    assert image.getpixel((8,1)) == (255,255,255)
    assert image.getpixel((0,2)) == (0,0,0)
    assert image.getpixel((8,2)) == (0,0,0)


def test_1bit_capture_keeps_original_and_jpg(tmp_path):
    result = capture(mono_fixture(), "zebra", tmp_path, title="mono label QA")
    assert result["status"] == "rendered"
    folder = next(tmp_path.glob("zebra/*/job.json")).parent
    assert (folder/"original.pwg").read_bytes() == mono_fixture()
    with Image.open(folder/"page-001.jpg") as jpg:
        assert jpg.size == (9,3)
        assert jpg.convert("L").getpixel((1,1)) < 70


def test_gray_packbits_pixel_and_row_repetition():
    pages = decode_pwg_raster(gray_fixture())
    assert len(pages) == 1
    im = pages[0]
    assert im.mode == "RGB" and im.size == (4, 3)
    assert im.getpixel((0, 0)) == (255, 255, 255)
    assert im.getpixel((1, 0)) == (0, 0, 0)
    assert im.getpixel((2, 0)) == (128, 128, 128)
    assert im.getpixel((2, 1)) == (128, 128, 128)
    assert im.getpixel((3, 2)) == (0, 0, 0)


def test_srgb_chunky_channels_and_multpage():
    single = rgb_fixture()
    pages = decode_pwg_raster(single)
    assert len(pages) == 1 and pages[0].size == (2, 2)
    assert pages[0].getpixel((0, 0)) == (255, 0, 0)
    assert pages[0].getpixel((1, 0)) == (0, 255, 0)
    assert pages[0].getpixel((0, 1)) == (0, 0, 255)
    assert pages[0].getpixel((1, 1)) == (255, 255, 255)
    combo = single + gray_fixture()[4:]
    multi = decode_pwg_raster(combo)
    assert len(multi) == 2 and multi[1].getpixel((2, 1)) == (128, 128, 128)


def test_in_app_capture_persists_source_all_page_jpg(tmp_path):
    data = rgb_fixture() + gray_fixture()[4:]
    assert detect_format(data) == "pwg-raster"
    result = capture(data, "brother-tray1", tmp_path, title="pwg QA")
    assert result["format"] == "pwg-raster"
    assert result["status"] == "rendered"
    assert result["images"] == ["page-001.jpg", "page-002.jpg"]
    folder = next(tmp_path.glob("brother-tray1/*/job.json")).parent
    assert (folder / "original.pwg").read_bytes() == data
    for page in result["images"]:
        assert (folder/page).stat().st_size > 250
    assert json.loads((folder/"job.json").read_text())["status"] == "rendered"


@pytest.mark.parametrize("broken,needle", [
    (b"RaS2", "contains no pages"),
    (b"RaS2X", "Truncated"),
    (b"RaS2" + pwg_page(4, 3, 1, b""), "Truncated"),
    (b"RaS2" + pwg_page(4, 3, 1, bytes([3, 3, 0])), "repeat exceeds"),
    (b"RaS2" + pwg_page(4, 3, 1, bytes([0, 4, 0])), "run exceeds"),
    (b"RaS2" + pwg_page(4, 3, 1, bytes([0, 128])), "0x80"),
    (b"RaS2" + pwg_page(4, 3, 1, bytes([0, 253, 255])), "Truncated"),
    (b"RaS2" + pwg_page(4, 3, 1, bytes([0, 0])), "Truncated"),
    (b"RaS2" + pwg_page(0, 3, 1, b""), "dimensions"),
    (b"RaS2" + pwg_page(8000, 8000, 1, b""), "pixel limit"),
    (b"RaS2" + pwg_page(4, 3, 1, b"", colorspace=3), "formats"),
    (b"RaS2" + pwg_page(4, 3, 1, b"", order=2), "packing"),
    (b"RaS2" + pwg_page(4, 3, 1, b"", colors=3), "packing"),
    (b"RaS2" + pwg_page(4, 3, 1, b"", bpp=1), "formats"),
    (b"RaS2" + pwg_page(9, 3, 1, b"", bpc=1, bpp=1, stride=9), "packing"),
    (b"RaS2" + pwg_page(9, 3, 1, b"", bpc=1, bpp=8, stride=9), "formats"),
    (b"RaS2" + pwg_page(9, 3, 1, bytes([1,255,0xAA,0x80,2,0]), bpc=1, bpp=1, stride=2), "repeat exceeds"),
    (b"RaS2" + pwg_page(9, 3, 1, bytes([0,253,0xAA,0x80,0x00]), bpc=1, bpp=1, stride=2), "run exceeds"),
    (b"RaS2" + pwg_page(4, 3, 1, b"", stride=2), "packing"),
    (gray_fixture() + b"trailing", "Truncated"),
    (b"2SaR" + gray_fixture()[4:], "RaS2"),
])
def test_corrupt_pwg_fails_closed(broken, needle):
    with pytest.raises(ValueError, match=needle):
        decode_pwg_raster(broken)


def test_rejects_page_count_over_limit():
    data = b"RaS2" + (pwg_page(1, 1, 1, bytes([0, 0, 255])) * 13)
    with pytest.raises(ValueError, match="page count"):
        decode_pwg_raster(data)


def test_rejects_cumulative_decode_bomb_before_allocating():
    page = pwg_page(3500, 3000, 3, b"")
    data = b"RaS2" + page
    # A single page would be <128 MB; the missing pixel data must be detected.
    with pytest.raises(ValueError, match="Truncated"):
        decode_pwg_raster(data)


def ipp_packet(op, uri, data=b"", fmt=None, title="pwg-raster-print"):
    out = bytearray(b"\x02\x00" + struct.pack("!HI", op, 26) + b"\x01")
    out += attr(CHARSET, "attributes-charset", "utf-8")
    out += attr(LANGUAGE, "attributes-natural-language", "en-us")
    out += attr(URI, "printer-uri", uri)
    out += attr(NAME, "job-name", title)
    if fmt is not None:
        out += attr(MIMETYPE, "document-format", fmt)
    return bytes(out) + b"\x03" + data


@pytest.fixture
def server(tmp_path):
    srv = start_server(port=0, output=tmp_path)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        yield srv.server_port, tmp_path
    finally:
        srv.shutdown()
        srv.server_close()
        t.join(timeout=3)


def ipp_request(port, printer, op, data=b"", fmt=None):
    uri=f"ipp://127.0.0.1:{port}/ipp/{printer}"
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    try:
        connection.request("POST", f"/ipp/{printer}",
                           ipp_packet(op, uri, data, fmt),
                           {"Content-Type": "application/ipp"})
        reply = connection.getresponse()
        raw = reply.read()
        assert reply.status == 200
        return raw, parse_request(raw)
    finally:
        connection.close()


@pytest.mark.parametrize("queue", ["zebra", "brother"])
@pytest.mark.parametrize("fixture", [gray_fixture, mono_fixture])
def test_real_ipp_pwg_print_job_to_jpg(server, queue, fixture):
    port, folder = server
    attrs = next(value for _, name, value in printer_attributes(queue, "ipp://here")
                 if name == "document-format-supported")
    assert "image/pwg-raster" in attrs
    types = next(value for _, name, value in printer_attributes(queue, "ipp://here")
                 if name == "pwg-raster-document-type-supported")
    assert "sgray_1" in types
    raw, status=ipp_request(port, queue, 4, fmt="image/pwg-raster")
    assert raw[2:4] == b"\x00\x00"  # Validate-Job
    raw, result=ipp_request(port, queue, 2, fixture(), fmt="image/pwg-raster")
    assert raw[2:4] == b"\x00\x00"
    assert result.first("job-state") == 9
    profile = "zebra" if queue == "zebra" else "brother-tray1"
    file=next(folder.glob(profile+"/*/page-001.jpg"))
    assert file.stat().st_size>200
    assert (file.parent/"original.pwg").read_bytes()==fixture()
    assert json.loads((file.parent/"job.json").read_text())["status"]=="rendered"


def test_real_ipp_multi_page_pwg_to_multiple_jpgs(server):
    port, folder=server
    raw, result=ipp_request(
        port,"brother",2,rgb_fixture()+gray_fixture()[4:],"image/pwg-raster")
    assert raw[2:4] == b"\x00\x00" and result.first("job-state")==9
    assert len(list(folder.glob("brother-tray1/*/page-*.jpg")))==2


@pytest.mark.parametrize("fmt,body", [
    ("application/pdf", gray_fixture()),
    ("image/pwg-raster", b"%PDF-1.1\n"),
    ("application/vnd.zebra-zpl", gray_fixture()),
    ("image/pwg-raster", b"^XA^FDNO^FS^XZ"),
])
def test_ipp_format_mismatch_rejected_without_fake_jpg(server, fmt, body):
    port, folder=server
    raw,result=ipp_request(port,"zebra",2,body,fmt)
    assert raw[2:4] == b"\x04\x0a"
    assert result.first("job-state") == 8
    assert not list(folder.glob("*/*/page-001.jpg"))


def test_ipp_invalid_pwg_returns_error_without_output(server):
    port, folder=server
    raw,result=ipp_request(port,"zebra",2,gray_fixture()[:-5],"image/pwg-raster")
    assert raw[2:4] == b"\x05\x00"
    assert result.first("job-state") == 8
    meta=next(folder.glob("zebra/*/job.json"))
    assert json.loads(meta.read_text())["status"] == "needs-renderer"
    assert not list(folder.glob("zebra/*/page-001.jpg"))
