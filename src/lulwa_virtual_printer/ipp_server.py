"""Experimental local IPP virtual printers. Not IPP Everywhere certified.

Run: lulwa-ipp --port 8631
Install local OS print queues using the scripts in install/.
The service binds to loopback only to protect sensitive printed content.
"""
from __future__ import annotations
import argparse
import json
import logging
import threading
from collections import deque
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .engine import capture, detect_format
from .ipp import (
    BOOLEAN, ENUM, INTEGER, KEYWORD, LANGUAGE, MIMETYPE,
    NAME, RESOLUTION, TEXT, URI, parse_request, response,
)

LOGGER = logging.getLogger(__name__)
MAX_IPP_SIZE = 25 * 1024 * 1024 + 128 * 1024
STANDARD_FORMATS = frozenset(('application/pdf', 'image/jpeg', 'image/png'))
ZPL_FORMAT = 'application/vnd.zebra-zpl'
RAW_ZPL_FORMAT = 'application/vnd.cups-raw'


def supported_document_formats(key: str) -> list[str]:
    """Advertise only the formats the *selected* virtual printer can render."""
    formats = ['application/pdf', 'image/jpeg', 'image/png']
    if key == 'zebra':
        # Vendor ZPL is experimental; not IPP Everywhere raster compliance.
        formats.append(ZPL_FORMAT)
    return formats


def format_supported(key: str, fmt: str | None) -> bool:
    """Preserve IPP octet-stream autodetection, restrict raw ZPL to Zebra."""
    return (fmt in STANDARD_FORMATS or fmt == 'application/octet-stream'
            or key == 'zebra' and fmt in (ZPL_FORMAT, RAW_ZPL_FORMAT))


def verify_document_format(key: str, fmt: str | None, document: bytes) -> str | None:
    """Reject mismatched MIME/magic and unsupported raw languages before capture."""
    if not format_supported(key, fmt):
        return 'Unsupported document-format: ' + str(fmt)
    if not document:
        return 'Missing document payload'
    try:
        actual = detect_format(document)
    except ValueError:
        return 'Unknown or unsupported document data'
    if actual == 'zpl':
        if key != 'zebra':
            return 'ZPL is supported only on the simulated Zebra queue'
        if fmt not in (ZPL_FORMAT, RAW_ZPL_FORMAT, 'application/octet-stream'):
            return 'ZPL payload does not match declared document-format'
    elif actual in ('pdf', 'image'):
        target = {'pdf': 'application/pdf', 'image': None}[actual]
        if fmt in (ZPL_FORMAT, RAW_ZPL_FORMAT):
            return 'Payload is not a ZPL label'
        if target and fmt not in (target, 'application/octet-stream'):
            return 'PDF payload does not match declared document-format'
        if actual == 'image':
            expected = ('image/png' if document.startswith(b'\x89PNG')
                        else 'image/jpeg')
            if fmt not in (expected, 'application/octet-stream'):
                return 'Image payload does not match declared document-format'
    else:
        return 'Unsupported document data for IPP virtual printer'
    return None

PRINTERS = {
    'brother': ('Lulwa SIM Brother (2 Trays)', 'brother-tray1', 300, 'na_letter_8.5x11in'),
    'brother-tray1': ('Lulwa SIM Brother - Tray 1', 'brother-tray1', 300, 'na_letter_8.5x11in'),
    'brother-tray2': ('Lulwa SIM Brother - Tray 2', 'brother-tray2', 300, 'na_letter_8.5x11in'),
    'zebra': ('Lulwa SIM Zebra 4x6 Label', 'zebra', 203, 'na_index-4x6_4x6in'),
}


def read_ipp_http_body(stream, headers, max_bytes=MAX_IPP_SIZE):
    """Read bounded IPP requests in either HTTP Content-Length or chunked form.

    RFC 2910 section 3.5 requires IPP servers to accept HTTP chunked request
    bodies. macOS/CUPS can stream print data without a Content-Length.
    Reject ambiguous framing to avoid persistent-connection request smuggling.
    """
    transfer = headers.get('Transfer-Encoding', '').strip().lower()
    length = headers.get('Content-Length')
    if transfer:
        if transfer != 'chunked' or length is not None:
            raise ValueError('Unsupported or ambiguous HTTP body framing')
        data = bytearray()
        trailer_size = 0
        while True:
            line = stream.readline(128)
            if not line.endswith(b'\r\n'):
                raise ValueError('Invalid HTTP chunk header')
            size_text = line[:-2].split(b';', 1)[0].strip()
            if not size_text or len(size_text) > 16:
                raise ValueError('Invalid HTTP chunk length')
            try:
                size = int(size_text, 16)
            except ValueError as exc:
                raise ValueError('Invalid HTTP chunk length') from exc
            if size > max_bytes - len(data):
                raise OverflowError('Print job exceeds IPP size limit')
            if size == 0:
                while True:
                    trailer = stream.readline(8192)
                    trailer_size += len(trailer)
                    if trailer_size > 8192 or not trailer.endswith(b'\r\n'):
                        raise ValueError('Invalid HTTP chunk trailer')
                    if trailer == b'\r\n':
                        return bytes(data)
            payload = stream.read(size)
            if len(payload) != size or stream.read(2) != b'\r\n':
                raise ValueError('Truncated HTTP chunk')
            data.extend(payload)

    if length is None:
        raise ValueError('Content-Length or chunked Transfer-Encoding required')
    try:
        count = int(length)
    except (ValueError, OverflowError) as exc:
        raise ValueError('Invalid Content-Length') from exc
    if count < 0:
        raise ValueError('Negative Content-Length')
    if count > max_bytes:
        raise OverflowError('Print job exceeds IPP size limit')
    payload = stream.read(count)
    if len(payload) != count:
        raise ValueError('Truncated IPP request body')
    return payload

def printer_attributes(key: str, uri: str):
    name, _, dpi, media = PRINTERS[key]
    entries = [
        (URI, 'printer-uri-supported', uri),
        (NAME, 'printer-name', name),
        (TEXT, 'printer-info', 'Local Lulwa virtual printer: output is saved as JPG'),
        (TEXT, 'printer-location', 'Lulwa Devices Simulator on this computer'),
        (TEXT, 'printer-make-and-model', 'Lulwa Simulator IPP (Experimental)'),
        (KEYWORD, 'uri-authentication-supported', 'none'),
        (KEYWORD, 'uri-security-supported', 'none'),
        (KEYWORD, 'ipp-versions-supported', ['1.1', '2.0']),
        (ENUM, 'operations-supported', [0x0002, 0x0004, 0x0005, 0x0006, 0x0008, 0x0009, 0x000A, 0x000B]),
        (KEYWORD, 'charset-supported', 'utf-8'),
        (LANGUAGE, 'generated-natural-language-supported', 'en-us'),
        (ENUM, 'printer-state', 3),
        (KEYWORD, 'printer-state-reasons', 'none'),
        (BOOLEAN, 'printer-is-accepting-jobs', True),
        (INTEGER, 'queued-job-count', 0),
        (MIMETYPE, 'document-format-supported', supported_document_formats(key)),
        (MIMETYPE, 'document-format-default', 'application/pdf'),
        (KEYWORD, 'media-supported', media),
        (KEYWORD, 'media-ready', media),
        (KEYWORD, 'media-default', media),
        (KEYWORD, 'sides-supported', 'one-sided'),
        (KEYWORD, 'sides-default', 'one-sided'),
        (KEYWORD, 'print-color-mode-supported', ['monochrome', 'color']),
        (KEYWORD, 'print-color-mode-default', 'monochrome' if key != 'zebra' else 'color'),
        (RESOLUTION, 'printer-resolution-supported', (dpi, dpi, 3)),
        (RESOLUTION, 'printer-resolution-default', (dpi, dpi, 3)),
        (KEYWORD, 'job-creation-attributes-supported', ['job-name', 'media', 'copies', 'sides', 'print-color-mode']),
        (INTEGER, 'copies-supported', 1),
        (INTEGER, 'copies-default', 1),
        (BOOLEAN, 'color-supported', True),
    ]
    if key == 'brother':
        entries.extend([
            (KEYWORD, 'media-source-supported', ['tray-1', 'tray-2', 'auto']),
            (KEYWORD, 'media-source-default', 'tray-1'),
        ])
    return entries

def job_attributes(job: dict, printer_uri: str):
    jid = job['job_id']
    return [
        (INTEGER, 'job-id', jid),
        (URI, 'job-uri', f'{printer_uri}/jobs/{jid}'),
        (NAME, 'job-name', job['name']),
        (ENUM, 'job-state', job['state']),
        (KEYWORD, 'job-state-reasons', 'job-aborted-by-system' if job['state'] == 8 else 'job-completed-successfully' if job['state'] == 9 else 'none'),
        (INTEGER, 'job-impressions-completed', len(job.get('images', []))),
    ]

def create_handler(output: str | Path):
    output = Path(output).expanduser().resolve()
    jobs: dict[int, dict] = {}
    events = deque(maxlen=50)
    counter = [0]
    lock = threading.RLock()

    def new_job(name: str) -> dict:
        with lock:
            counter[0] += 1
            jid = counter[0]
            job = {'job_id': jid, 'name': name, 'state': 3, 'images': [], 'directory': ''}
            jobs[jid] = job
            return job

    def record_event(operation: int, status: int, fmt: str | None, job_id=None,
                     capture_status=None, detail=None):
        # Log metadata only; never include printed document or shipping details.
        with lock:
            events.append({'at': datetime.now(timezone.utc).isoformat(),
                           'operation': f'0x{operation:04x}', 'ipp_status': f'0x{status:04x}',
                           'document_format': fmt, 'job_id': job_id,
                           'capture_status': capture_status,
                           'detail': str(detail)[:180] if detail else None})

    def render_into_job(job, document: bytes, key: str, fmt: str | None, request):
        error = verify_document_format(key, fmt, document)
        if error:
            job['state'] = 8
            return (0x0400 if not document else 0x040A), error
        profile = PRINTERS[key][1]
        if key == 'brother' and request.first('media-source', 'tray-1') == 'tray-2':
            profile = 'brother-tray2'
        try:
            result = capture(document, profile, output, job['name'])
            job.update(state=9 if result['status'] == 'rendered' else 8,
                       images=result['images'], directory=result['directory'])
            if job['state'] != 9:
                return 0x0500, result.get('error') or 'Renderer did not produce JPG'
            return 0x0000, None
        except (OSError, ValueError) as exc:
            job['state'] = 8
            LOGGER.warning('IPP capture failed: %s', exc)
            return 0x0500, str(exc)


    class Handler(BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.1'
        server_version = 'DevicesSimulatorIPP/0.8.1-experimental'

        def log_message(self, fmt, *args):
            LOGGER.info('%s %s', self.client_address[0], fmt % args)

        def send_bytes(self, data: bytes, ctype: str, code: int = 200):
            self.send_response(code)
            self.send_header('Content-Type', ctype)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if urlparse(self.path).path == '/diagnostics':
                with lock:
                    payload = json.dumps({
                        'events': list(events),
                        'output_dir': str(output),
                        'jobs_seen': len(jobs),
                        'jobs': [{'job_id': j['job_id'], 'state': j['state'],
                                  'image_count': len(j.get('images', []))}
                                 for j in list(jobs.values())[-15:]],
                        'supported_http_request_bodies': ['content-length', 'chunked']
                    }).encode()
                return self.send_bytes(payload, 'application/json')
            if urlparse(self.path).path == '/healthz':
                data = json.dumps({'status': 'ok', 'printers': list(PRINTERS), 'mode': 'experimental'}).encode()
                return self.send_bytes(data, 'application/json')
            return self.send_bytes(b'Lulwa simulated printer IPP service\n', 'text/plain; charset=utf-8')

        def do_POST(self):
            path = urlparse(self.path).path
            key = path.removeprefix('/ipp/')
            if key not in PRINTERS or path != f'/ipp/{key}':
                return self.send_bytes(b'Unknown printer', 'text/plain', 404)
            try:
                payload = read_ipp_http_body(self.rfile, self.headers)
                request = parse_request(payload)
            except (ValueError, OverflowError) as exc:
                # Reading may have ended before consuming an invalid request;
                # close this HTTP/1.1 connection to avoid framing confusion.
                self.close_connection = True
                status_code = 413 if isinstance(exc, OverflowError) else 400
                record_event(0, status_code, None, capture_status='http_rejected',
                             detail=str(exc))
                LOGGER.warning('IPP HTTP request rejected: %s', exc)
                return self.send_bytes(str(exc).encode(), 'text/plain', status_code)
            host = self.headers.get('Host', f'127.0.0.1:{self.server.server_port}')
            if any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.:-[]' for c in host):
                host = f'127.0.0.1:{self.server.server_port}'
            uri = f'ipp://{host}/ipp/{key}'
            attrs = []
            out = []
            status = 0x0000
            op = request.operation
            if op == 0x000B:
                attrs = printer_attributes(key, uri)
                asked = request.attributes.get('requested-attributes', [])
                if asked and 'all' not in asked and 'printer-description' not in asked and 'printer-defaults' not in asked:
                    attrs = [a for a in attrs if a[1] in asked]
            elif op == 0x0004:
                # Validate-Job: check format without claiming a print occurred.
                fmt = request.first('document-format', 'application/pdf')
                if not format_supported(key, fmt):
                    status = 0x040A
            elif op == 0x0005:
                # Create-Job: client reserves a job ID; document arrives via Send-Document.
                title = str(request.first('job-name', 'IPP print'))[:128]
                job = new_job(title)
                out = job_attributes(job, uri)
                record_event(op, 0, request.first('document-format'), job['job_id'], 'awaiting_document')
            elif op in (0x0002, 0x0006):
                # Print-Job sends bytes with job; Send-Document completes Create-Job.
                fmt = request.first('document-format', 'application/octet-stream')
                if op == 0x0006:
                    try:
                        jid = int(request.first('job-id', 0))
                    except (ValueError, TypeError):
                        jid = 0
                    with lock:
                        job = jobs.get(jid)
                    if not job:
                        status = 0x0406
                        record_event(op, status, fmt, jid, detail='Unknown IPP job ID')
                    elif job['state'] != 3:
                        status = 0x0400
                        record_event(op, status, fmt, jid, detail='IPP job already completed')
                    else:
                        status, detail = render_into_job(job, request.document, key, fmt, request)
                        out = job_attributes(job, uri)
                        record_event(op, status, fmt, jid, 'rendered' if status == 0 else 'failed', detail)
                else:
                    title = str(request.first('job-name', 'IPP print'))[:128]
                    job = new_job(title)
                    status, detail = render_into_job(job, request.document, key, fmt, request)
                    out = job_attributes(job, uri)
                    record_event(op, status, fmt, job['job_id'], 'rendered' if status == 0 else 'failed', detail)
            elif op == 0x0009:
                jid = request.first('job-id')
                with lock:
                    record = jobs.get(jid)
                if record:
                    out = job_attributes(record, uri)
                    record_event(op, 0, None, jid, 'state_' + str(record['state']))
                else:
                    status = 0x0406
                    record_event(op, status, None, jid, detail='Unknown job for status poll')
            elif op == 0x000A:
                # Get-Jobs: provide latest job details as a minimal IPP subset.
                with lock:
                    latest = next(reversed(jobs.values()), None) if jobs else None
                if latest:
                    out = job_attributes(latest, uri)
            elif op == 0x0008:
                status = 0x0405
            else:
                status = 0x0501
                record_event(op, status, None, detail='Unsupported IPP operation')
            return self.send_bytes(response(request, status, printer_attrs=attrs, job_attrs=out), 'application/ipp')
    return Handler

def start_server(host='127.0.0.1', port=8631, output=None):
    if host not in ('localhost', '127.0.0.1', '::1'):
        raise ValueError('For privacy and safety, bind IPP simulator to loopback only')
    output = output or Path.home() / 'Documents' / 'Lulwa Virtual Printer'
    return ThreadingHTTPServer((host, port), create_handler(output))

def main():
    parser = argparse.ArgumentParser(description='Run local experimental IPP printer endpoints')
    parser.add_argument('--host', default='127.0.0.1', choices=['127.0.0.1', 'localhost'])
    parser.add_argument('--port', type=int, default=8631)
    parser.add_argument('--output', default=str(Path.home() / 'Documents' / 'Lulwa Virtual Printer'))
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    with start_server(args.host, args.port, args.output) as server:
        print(f'Running Lulwa IPP: http://127.0.0.1:{server.server_port}/healthz', flush=True)
        try:
            server.serve_forever(poll_interval=0.2)
        except KeyboardInterrupt:
            pass

if __name__ == '__main__':
    main()
