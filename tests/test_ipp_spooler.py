"""Real HTTP IPP two-stage printing, no OS printer required for protocol coverage."""
import http.client
import json
import struct
import threading

import fitz
from lulwa_virtual_printer.ipp import (
    attr, parse_request, CHARSET, LANGUAGE, URI, NAME, INTEGER, MIMETYPE
)
from lulwa_virtual_printer.ipp_server import start_server


def packet(operation, uri, *, data=b"", job_id=None, title=None, fmt=None):
    out = bytearray(b"\x02\x00" + struct.pack("!HI", operation, 42) + b"\x01")
    out += attr(CHARSET, "attributes-charset", "utf-8")
    out += attr(LANGUAGE, "attributes-natural-language", "en-us")
    out += attr(URI, "printer-uri", uri)
    if title:
        out += attr(NAME, "job-name", title)
    if job_id is not None:
        out += attr(INTEGER, "job-id", job_id)
    if fmt:
        out += attr(MIMETYPE, "document-format", fmt)
    return bytes(out) + b"\x03" + data


def test_create_job_then_send_document_produces_jpg(tmp_path):
    server = start_server(port=0, output=tmp_path)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        uri = f"ipp://127.0.0.1:{server.server_port}/ipp/zebra"
        conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=10)
        conn.request("POST", "/ipp/zebra", packet(0x0005, uri, title="two-step-shipping"),
                     {"Content-Type": "application/ipp"})
        response = conn.getresponse()
        raw = response.read()
        assert response.status == 200
        assert raw[2:4] == b"\x00\x00", raw
        job_id = parse_request(raw).first("job-id")
        assert job_id is not None
        document = fitz.open()
        document.new_page(width=288, height=432).insert_text((20, 60), "TWO STEP IPP")
        pdf = document.tobytes()
        document.close()
        # Some CUPS clients send application/octet-stream; engine checks magic.
        conn.request("POST", "/ipp/zebra", packet(0x0006, uri, job_id=job_id,
                     fmt="application/octet-stream", data=pdf),
                     {"Content-Type": "application/ipp"})
        response = conn.getresponse()
        raw = response.read()
        assert raw[2:4] == b"\x00\x00", raw
        assert list(tmp_path.glob("zebra/*/page-001.jpg"))
        jobs = list(tmp_path.glob("zebra/*/job.json"))
        assert json.loads(jobs[0].read_text())["title"] == "two-step-shipping"
        conn.request("GET", "/diagnostics")
        response = conn.getresponse()
        diagnostic = json.loads(response.read())
        assert any(e["operation"] == "0x0006" and e["capture_status"] == "rendered"
                   for e in diagnostic["events"])
        conn.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_send_document_unknown_id_returns_ipp_error(tmp_path):
    server = start_server(port=0, output=tmp_path)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        uri = f"ipp://127.0.0.1:{server.server_port}/ipp/brother"
        conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=10)
        conn.request("POST", "/ipp/brother", packet(0x0006, uri, job_id=987, data=b"%PDF-"),
                     {"Content-Type": "application/ipp"})
        res = conn.getresponse()
        raw = res.read()
        assert raw[2:4] == b"\x04\x06"
        assert not list(tmp_path.glob("*/*/job.json"))
        conn.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
