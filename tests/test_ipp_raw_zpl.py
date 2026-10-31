"""Real-socket IPP raw ZPL handling, including Print-Job, Send-Document and failure paths.

This verifies the simulator's loopback IPP transport; it does not certify
PrintNode Client enumeration or native Windows/macOS print queue behavior.
"""
import http.client
import json
import struct
import threading

import fitz
import pytest
from PIL import Image

from lulwa_virtual_printer.ipp import (
    CHARSET, LANGUAGE, URI, NAME, INTEGER, MIMETYPE, attr, parse_request
)
from lulwa_virtual_printer.ipp_server import (
    ZPL_FORMAT, RAW_ZPL_FORMAT, printer_attributes, start_server
)


ZPL = (b"^XA^PW406^LL609^FO20,25^A0N,32,30^FDLULWA SWIM^FS"
       b"^FO20,90^BQN,2,5^FDLA,ORDER-2026-001^FS"
       b"^FO20,220^BY2^BCN,72,Y,N,N^FD2026001^FS^XZ")


def packet(op, uri, *, title="raw-zpl-qa", fmt=None, job_id=None, data=b""):
    body = bytearray(b"\x02\x00" + struct.pack("!HI", op, 77) + b"\x01")
    body += attr(CHARSET, "attributes-charset", "utf-8")
    body += attr(LANGUAGE, "attributes-natural-language", "en-us")
    body += attr(URI, "printer-uri", uri)
    if title is not None:
        body += attr(NAME, "job-name", title)
    if fmt is not None:
        body += attr(MIMETYPE, "document-format", fmt)
    if job_id is not None:
        body += attr(INTEGER, "job-id", job_id)
    return bytes(body) + b"\x03" + data


@pytest.fixture()
def ipp(tmp_path):
    server = start_server(port=0, output=tmp_path)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        yield server.server_port, tmp_path
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=4)


def send(port, printer, op, *, fmt=None, data=b"", title="raw-zpl-qa", job_id=None):
    uri = f"ipp://127.0.0.1:{port}/ipp/{printer}"
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    try:
        conn.request("POST", f"/ipp/{printer}",
                     packet(op, uri, fmt=fmt, data=data, title=title, job_id=job_id),
                     {"Content-Type": "application/ipp"})
        response = conn.getresponse()
        raw = response.read()
        assert response.status == 200
        return raw, parse_request(raw)
    finally:
        conn.close()


def test_zebra_advertises_zpl_but_brother_does_not():
    zebra = next(v for t, n, v in printer_attributes("zebra", "ipp://localhost/ipp/zebra")
                 if n == "document-format-supported")
    brother = next(v for t, n, v in printer_attributes("brother", "ipp://localhost/ipp/brother")
                   if n == "document-format-supported")
    assert ZPL_FORMAT in zebra and ZPL_FORMAT not in brother
    assert RAW_ZPL_FORMAT not in zebra  # CUPS-raw is accepted, not certified/advertised
    assert "application/pdf" in zebra and "image/png" in brother


@pytest.mark.parametrize("format_type", [ZPL_FORMAT, RAW_ZPL_FORMAT, "application/octet-stream"])
def test_real_ipp_print_job_zpl_produces_saved_jpg(ipp, format_type):
    port, folder = ipp
    response, result = send(port, "zebra", 2, fmt=format_type,
                            title="raw label with QR", data=ZPL)
    assert response[2:4] == b"\x00\x00"
    assert result.first("job-state") == 9
    jpgs = list(folder.glob("zebra/*/page-001.jpg"))
    assert len(jpgs) == 1
    meta = json.loads((jpgs[0].parent/"job.json").read_text(encoding="utf-8"))
    assert meta["format"] == "zpl" and meta["status"] == "rendered"
    assert (jpgs[0].parent/"original.zpl").read_bytes() == ZPL
    with Image.open(jpgs[0]) as image:
        assert image.size == (406, 609)
        # JPEG has compression; check dark rendered text/barcodes, not exact RGB.
        assert image.convert("L").getpixel((20, 25)) >= 0
        assert image.convert("L").getextrema()[0] < 100


def test_create_job_send_zpl_document_roundtrip(ipp):
    port, folder = ipp
    create, created = send(port, "zebra", 5, title="two-step-zpl")
    assert create[2:4] == b"\x00\x00"
    job_id = created.first("job-id")
    raw, delivered = send(port, "zebra", 6, job_id=job_id, fmt=ZPL_FORMAT, data=ZPL)
    assert raw[2:4] == b"\x00\x00"
    assert delivered.first("job-state") == 9
    assert len(list(folder.glob("zebra/*/page-001.jpg"))) == 1
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    try:
        conn.request("GET", "/diagnostics")
        diagnostics = json.loads(conn.getresponse().read())
        assert any(evt["operation"] == "0x0006"
                   and evt["document_format"] == ZPL_FORMAT
                   and evt["capture_status"] == "rendered"
                   for evt in diagnostics["events"])
    finally:
        conn.close()


@pytest.mark.parametrize("printer,mime,document", [
    ("brother", ZPL_FORMAT, ZPL),
    ("brother", "application/octet-stream", ZPL),
    ("zebra", "application/pdf", ZPL),
    ("zebra", ZPL_FORMAT, b"%PDF-1.0 hello"),
    ("zebra", "application/octet-stream", b"\x1b@RECEIPT\n"),
    ("zebra", "application/octet-stream", b"\x01\x02\x03"),
    ("zebra", "application/vnd.hp-pcl", ZPL),
])
def test_ipp_rejects_wrong_queue_or_mime_without_jpg(ipp, printer, mime, document):
    port, folder = ipp
    reply, result = send(port, printer, 2, fmt=mime, data=document)
    assert reply[2:4] == b"\x04\x0a", (printer, mime, reply[:4])
    assert result.first("job-state") == 8
    assert not list(folder.glob("*/*/page-*.jpg"))


def test_validate_job_only_accepts_zpl_on_zebra(ipp):
    port, folder = ipp
    ok, _ = send(port, "zebra", 4, fmt=ZPL_FORMAT)
    assert ok[2:4] == b"\x00\x00"
    denied, _ = send(port, "brother", 4, fmt=ZPL_FORMAT)
    assert denied[2:4] == b"\x04\x0a"
    assert not list(folder.glob("*/*/job.json"))


def test_unimplemented_zpl_command_returns_error_and_no_fake_jpg(ipp):
    port, folder = ipp
    invalid = b"^XA^PW406^LL609^FO20,20^B3N,80^FD123^FS^XZ"
    reply, result = send(port, "zebra", 2, fmt=ZPL_FORMAT, data=invalid)
    assert reply[2:4] == b"\x05\x00"
    assert result.first("job-state") == 8
    assert not list(folder.glob("*/*/page-001.jpg"))
    metadata = list(folder.glob("zebra/*/job.json"))
    assert len(metadata) == 1
    assert json.loads(metadata[0].read_text())["status"] == "needs-renderer"


def test_pdf_and_png_regression_on_both_printers(ipp):
    port, folder = ipp
    pdf = fitz.open()
    pdf.new_page(width=80, height=120).insert_text((10, 30), "PDF")
    data = pdf.tobytes()
    pdf.close()
    for printer in ("brother", "zebra"):
        raw, _ = send(port, printer, 2, fmt="application/pdf",
                      data=data, title=f"{printer}-pdf")
        assert raw[2:4] == b"\x00\x00"
    assert list(folder.glob("brother-tray1/*/page-001.jpg"))
    assert list(folder.glob("zebra/*/page-001.jpg"))
