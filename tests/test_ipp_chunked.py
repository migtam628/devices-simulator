"""CUPS/macOS uses HTTP chunked IPP bodies for streaming print jobs.

Exercise real HTTP sockets, both submission workflows and job-state polling,
not only direct renderer calls that bypass the OS print transport.
"""
import http.client
import io
import json
import struct
import threading

import fitz
import pytest

from lulwa_virtual_printer.ipp import attr, parse_request, CHARSET, LANGUAGE, NAME, URI, INTEGER, MIMETYPE
from lulwa_virtual_printer.ipp_server import start_server, read_ipp_http_body


def packet(op, uri, *, job_id=None, title=None, fmt="application/pdf", document=b""):
    body=bytearray(b"\x02\x00"+struct.pack("!HI",op,84)+b"\x01")
    body+=attr(CHARSET,"attributes-charset","utf-8")
    body+=attr(LANGUAGE,"attributes-natural-language","en-us")
    body+=attr(URI,"printer-uri",uri)
    if job_id is not None:
        body+=attr(INTEGER,"job-id",job_id)
    if title is not None:
        body+=attr(NAME,"job-name",title)
    if fmt:
        body+=attr(MIMETYPE,"document-format",fmt)
    body+=b"\x03"+document
    return bytes(body)


def pdf_sample():
    doc=fitz.open()
    doc.new_page(width=288,height=432).insert_text((20,40),"CUPS CHUNKED PRINT TEST")
    payload=doc.tobytes()
    doc.close()
    return payload


def post_chunked(conn, uri, payload):
    conn.putrequest("POST",uri)
    conn.putheader("Content-Type","application/ipp")
    conn.putheader("Transfer-Encoding","chunked")
    conn.endheaders()
    # Deliberately split the IPP header, attributes and actual PDF bytes.
    offsets=[payload[:11],payload[11:52],payload[52:211],payload[211:]]
    for part in offsets:
        if part:
            conn.send(f"{len(part):X};streamed=1\r\n".encode()+part+b"\r\n")
    conn.send(b"0\r\nX-Test-Trailer: done\r\n\r\n")
    result=conn.getresponse()
    return result.status,result.read()


@pytest.mark.parametrize("preset",["zebra","brother"])
def test_real_chunked_print_job_and_status_poll(tmp_path,preset):
    server=start_server(port=0,output=tmp_path)
    worker=threading.Thread(target=server.serve_forever,daemon=True)
    worker.start()
    try:
        uri=f"ipp://127.0.0.1:{server.server_port}/ipp/{preset}"
        connection=http.client.HTTPConnection("127.0.0.1",server.server_port,timeout=10)
        status,raw=post_chunked(connection,f"/ipp/{preset}",
                                packet(2,uri,title="chunked-print",document=pdf_sample()))
        assert status==200 and raw[2:4]==b"\x00\x00"
        jid=parse_request(raw).first("job-id")
        assert isinstance(jid,int) and jid>0

        connection.request("POST",f"/ipp/{preset}",packet(9,uri,job_id=jid),
                           {"Content-Type":"application/ipp"})
        reply=connection.getresponse()
        status_payload=reply.read()
        assert reply.status==200
        assert parse_request(status_payload).first("job-state")==9

        folder="zebra" if preset=="zebra" else "brother-tray1"
        results=list(tmp_path.glob(f"{folder}/*/page-001.jpg"))
        assert len(results)==1 and results[0].stat().st_size>0
        assert json.loads((results[0].parent/"job.json").read_text())["status"]=="rendered"

        connection.request("GET","/diagnostics")
        diag=json.loads(connection.getresponse().read())
        assert "chunked" in diag["supported_http_request_bodies"]
        assert any(e["operation"]=="0x0009" and e["capture_status"]=="state_9"
                   for e in diag["events"])
        assert diag["jobs"][0]["state"]==9
        connection.close()
    finally:
        server.shutdown();server.server_close();worker.join(timeout=3)


def test_chunked_create_job_then_send_document(tmp_path):
    server=start_server(port=0,output=tmp_path)
    worker=threading.Thread(target=server.serve_forever,daemon=True)
    worker.start()
    try:
        uri=f"ipp://127.0.0.1:{server.server_port}/ipp/zebra"
        c=http.client.HTTPConnection("127.0.0.1",server.server_port,timeout=10)
        c.request("POST","/ipp/zebra",packet(5,uri,title="two-step-chunked"),
                  {"Content-Type":"application/ipp"})
        resp=c.getresponse();data=resp.read()
        assert resp.status==200 and data[2:4]==b"\x00\x00"
        jid=parse_request(data).first("job-id")
        status,raw=post_chunked(c,"/ipp/zebra",
            packet(6,uri,job_id=jid,fmt="application/octet-stream",document=pdf_sample()))
        assert status==200 and raw[2:4]==b"\x00\x00"
        assert parse_request(raw).first("job-state")==9
        assert list(tmp_path.glob("zebra/*/page-001.jpg"))
        c.close()
    finally:
        server.shutdown();server.server_close();worker.join(timeout=3)


def test_http_request_length_and_chunked_malformed_rejected():
    data=b"abc"
    assert read_ipp_http_body(io.BytesIO(data),{"Content-Length":"3"})==data
    assert read_ipp_http_body(io.BytesIO(b"3\r\nabc\r\n0\r\n\r\n"),
                              {"Transfer-Encoding":"chunked"})==data
    invalid=[
        (b"",{"Content-Length":"3"}),
        (b"3\r\nabcX\r\n0\r\n\r\n",{"Transfer-Encoding":"chunked"}),
        (b"ZZ\r\n",{"Transfer-Encoding":"chunked"}),
        (b"3\r\nabc\r\n0\r\nBroken\r\n",{"Transfer-Encoding":"chunked"}),
        (b"",{"Transfer-Encoding":"gzip"}),
        (b"",{"Transfer-Encoding":"chunked","Content-Length":"0"}),
    ]
    for raw,headers in invalid:
        with pytest.raises(ValueError):
            read_ipp_http_body(io.BytesIO(raw),headers)
    with pytest.raises(OverflowError):
        read_ipp_http_body(io.BytesIO(b"5\r\n"),{"Transfer-Encoding":"chunked"},max_bytes=4)
    with pytest.raises(OverflowError):
        read_ipp_http_body(io.BytesIO(b""),{"Content-Length":"5"},max_bytes=4)


def test_broken_http_body_reports_safe_diagnostic(tmp_path):
    server=start_server(port=0,output=tmp_path)
    t=threading.Thread(target=server.serve_forever,daemon=True);t.start()
    try:
        c=http.client.HTTPConnection("127.0.0.1",server.server_port,timeout=5)
        c.putrequest("POST","/ipp/zebra")
        c.putheader("Transfer-Encoding","chunked")
        c.putheader("Content-Type","application/ipp")
        c.endheaders()
        c.send(b"ZZ\r\n")
        res=c.getresponse();res.read()
        assert res.status==400
        c.close()
        c=http.client.HTTPConnection("127.0.0.1",server.server_port,timeout=5)
        c.request("GET","/diagnostics")
        diag=json.loads(c.getresponse().read())
        assert any(e["capture_status"]=="http_rejected" for e in diag["events"])
        c.close()
    finally:
        server.shutdown();server.server_close();t.join(timeout=3)
