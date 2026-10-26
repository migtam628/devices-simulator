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

from .engine import capture
from .ipp import (
    BOOLEAN, ENUM, INTEGER, KEYWORD, LANGUAGE, MIMETYPE,
    NAME, RESOLUTION, TEXT, URI, parse_request, response,
)

LOGGER = logging.getLogger(__name__)
MAX_IPP_SIZE = 25 * 1024 * 1024 + 128 * 1024
PRINTERS = {
    'brother': ('Lulwa SIM Brother (2 Trays)', 'brother-tray1', 300, 'na_letter_8.5x11in'),
    'brother-tray1': ('Lulwa SIM Brother - Tray 1', 'brother-tray1', 300, 'na_letter_8.5x11in'),
    'brother-tray2': ('Lulwa SIM Brother - Tray 2', 'brother-tray2', 300, 'na_letter_8.5x11in'),
    'zebra': ('Lulwa SIM Zebra 4x6 Label', 'zebra', 203, 'na_index-4x6_4x6in'),
}

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
        (MIMETYPE, 'document-format-supported', ['application/pdf', 'image/jpeg', 'image/png']),
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
        (KEYWORD, 'job-state-reasons', 'job-aborted-by-system' if job['state'] == 8 else 'none'),
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
        if fmt not in ('application/pdf', 'image/jpeg', 'image/png', 'application/octet-stream'):
            job['state'] = 8
            return 0x040A, 'Unsupported document-format: ' + str(fmt)
        if not document:
            job['state'] = 8
            return 0x0400, 'Missing document payload'
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
        server_version = 'DevicesSimulatorIPP/0.6.1-experimental'

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
                    payload = json.dumps({'events': list(events), 'jobs_seen': len(jobs)}).encode()
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
                length = int(self.headers.get('Content-Length', '-1'))
                if length < 0:
                    return self.send_bytes(b'Content-Length required', 'text/plain', 411)
                if length > MAX_IPP_SIZE:
                    return self.send_bytes(b'Print job too large', 'text/plain', 413)
                payload = self.rfile.read(length)
                request = parse_request(payload)
            except (ValueError, OverflowError) as exc:
                return self.send_bytes(str(exc).encode(), 'text/plain', 400)
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
                if fmt not in ('application/pdf', 'image/jpeg', 'image/png', 'application/octet-stream'):
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
                else:
                    status = 0x0406
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
