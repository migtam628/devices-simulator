import http.client
import json
import struct
import threading

import fitz
import pytest
from lulwa_virtual_printer.ipp import attr, parse_request, response, CHARSET, LANGUAGE, URI, NAME, MIMETYPE, KEYWORD
from lulwa_virtual_printer.ipp_server import start_server


def make_request(op: int, url: str, data: bytes = b'', fmt: str = 'application/pdf', source: str | None = None):
    out = bytearray(b'\x02\x00' + struct.pack('!HI', op, 7) + b'\x01')
    out += attr(CHARSET, 'attributes-charset', 'utf-8')
    out += attr(LANGUAGE, 'attributes-natural-language', 'en-us')
    out += attr(URI, 'printer-uri', url)
    if op == 2:
        out += attr(NAME, 'job-name', 'test-order')
        out += attr(MIMETYPE, 'document-format', fmt)
        if source:
            out += b'\x02' + attr(KEYWORD, 'media-source', source)
    out += b'\x03' + data
    return bytes(out)


def test_wire_parser_and_response():
    request = parse_request(make_request(11, 'ipp://localhost/ipp/zebra'))
    assert request.operation == 11
    assert request.first('printer-uri') == 'ipp://localhost/ipp/zebra'
    output = response(request, 0)
    assert output[:4] == b'\x02\x00\x00\x00'


def test_reject_missing_ipp_delimiter():
    with pytest.raises(ValueError, match='delimiter'):
        parse_request(b'\x02\x00' + struct.pack('!HI', 11, 1) + b'\x01')


def test_real_http_ipp_capture(tmp_path):
    server = start_server(port=0, output=tmp_path)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_port
        uri = f'ipp://127.0.0.1:{port}/ipp/brother'
        connection = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
        connection.request('POST', '/ipp/brother', make_request(11, uri), {'Content-Type': 'application/ipp'})
        reply = connection.getresponse()
        payload = reply.read()
        assert reply.status == 200
        assert b'Lulwa SIM Brother' in payload
        assert b'tray-1' in payload
        assert b'tray-2' in payload
        doc = fitz.open()
        doc.new_page(width=72, height=72)
        pdf = doc.tobytes()
        connection.request('POST', '/ipp/brother', make_request(2, uri, pdf, source='tray-2'), {'Content-Type': 'application/ipp'})
        reply = connection.getresponse()
        payload = reply.read()
        assert reply.status == 200
        assert payload[:4] == b'\x02\x00\x00\x00'
        jobs = list(tmp_path.glob('brother-tray2/*/page-001.jpg'))
        assert len(jobs) == 1
        status = json.loads((jobs[0].parent/'job.json').read_text())
        assert status['profile'] == 'brother-tray2'
        connection.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_no_external_network_listeners():
    with pytest.raises(ValueError, match='loopback'):
        start_server(host='0.0.0.0')
