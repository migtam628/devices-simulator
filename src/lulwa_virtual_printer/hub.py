"""Local Devices Simulator Hub: truthful device profiles and JPG capture.

Start with: lulwa-hub
This is a local web-based desktop hub, not an OS printer driver.
"""
from __future__ import annotations

import argparse
import base64
import binascii
import json
import logging
import platform
import secrets
import threading
import uuid
import webbrowser
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from .engine import PROFILES, capture

LOG = logging.getLogger(__name__)
MAX_BODY = 35 * 1024 * 1024
MAX_FILE = 25 * 1024 * 1024
CATEGORIES = ("office_printer", "label_printer", "scanner", "barcode", "receipt", "serial")
PRESETS = {
    "brother": {"category": "office_printer", "label": "Brother Dual Tray", "name": "Brother Office Printer", "dpi": 300, "media": "Letter · 8.5 × 11 in", "profiles": ["brother-tray1", "brother-tray2"], "capability": "experimental"},
    "zebra": {"category": "label_printer", "label": "Zebra 4×6 Thermal", "name": "Zebra 4×6 Label Printer", "dpi": 203, "media": "Label · 4 × 6 in", "profiles": ["zebra"], "capability": "experimental"},
    "scanner": {"category": "scanner", "label": "Flatbed Scanner", "name": "Virtual Flatbed Scanner", "dpi": 300, "media": "Letter · 8.5 × 11 in", "profiles": [], "capability": "planned"},
    "barcode": {"category": "barcode", "label": "Barcode Scanner", "name": "Virtual Barcode Scanner", "dpi": None, "media": "HID input", "profiles": [], "capability": "planned"},
    "receipt": {"category": "receipt", "label": "Receipt Printer", "name": "Virtual Receipt Printer", "dpi": 203, "media": "80 mm roll", "profiles": [], "capability": "planned"},
    "serial": {"category": "serial", "label": "Serial / COM Device", "name": "Virtual Serial Device", "dpi": None, "media": "PTY / COM", "profiles": [], "capability": "planned"},
}


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


class HubStore:
    """Atomic-ish local JSON store protected by an in-process lock."""

    def __init__(self, state_dir: Path, output_dir: Path):
        self.state_dir = Path(state_dir).expanduser().resolve()
        self.output_dir = Path(output_dir).expanduser().resolve()
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.state_dir / "devices.json"
        self.lock = threading.RLock()
        if not self.path.exists():
            self._write({"version": 1, "devices": []})

    def _read(self) -> dict:
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _write(self, state: dict):
        tmp = self.path.with_name(f".{self.path.name}.{uuid.uuid4().hex}.tmp")
        try:
            tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
            tmp.replace(self.path)
        finally:
            tmp.unlink(missing_ok=True)

    def list_devices(self) -> list[dict]:
        with self.lock:
            return self._read()["devices"]

    def get_device(self, device_id: str) -> dict | None:
        return next((d for d in self.list_devices() if d["id"] == device_id), None)

    def create_device(self, data: dict) -> dict:
        preset = data.get("preset")
        if preset not in PRESETS:
            raise ValueError("Choose a valid device preset")
        name = str(data.get("name", "")).strip()
        if not 1 <= len(name) <= 64 or any(ord(c) < 32 for c in name):
            raise ValueError("Name must be 1–64 printable characters")
        config = PRESETS[preset]
        with self.lock:
            state = self._read()
            if any(d["name"].casefold() == name.casefold() for d in state["devices"]):
                raise ValueError("Device name already exists")
            obj = {
                "id": str(uuid.uuid4()), "preset": preset, "category": config["category"],
                "name": name, "media": config["media"], "dpi": config["dpi"],
                "tray": data.get("tray") if data.get("tray") in ("tray-1", "tray-2") else "tray-1",
                "output_format": "jpg", "delay_ms": 0,
                "lifecycle": "draft", "os_status": "not_verified",
                "last_test": None, "created_at": timestamp()
            }
            state["devices"].append(obj)
            self._write(state)
            return obj

    def remove_device(self, device_id: str) -> bool:
        with self.lock:
            state = self._read()
            new = [d for d in state["devices"] if d["id"] != device_id]
            if len(new) == len(state["devices"]):
                return False
            state["devices"] = new
            self._write(state)
            return True

    def test_device(self, device_id: str, document: bytes | None = None, title: str = "Sample Test") -> dict:
        import fitz
        device = self.get_device(device_id)
        if not device:
            raise LookupError("Device not found")
        preset = PRESETS[device["preset"]]
        if not preset["profiles"]:
            raise ValueError("This device is a profile preview. No capture backend is implemented yet")
        if document is None:
            label = device["preset"] == "zebra"
            width, height = (288, 432) if label else (612, 792)
            pdf = fitz.open()
            page = pdf.new_page(width=width, height=height)
            page.insert_text((34, 54), "DEVICES SIMULATOR — TEST", fontsize=16)
            page.insert_text((34, 88), device["name"], fontsize=11)
            page.insert_text((34, 111), f"Created {timestamp()[:19]} UTC", fontsize=10)
            page.draw_rect(fitz.Rect(34, 132, width-34, height-38), color=(0.2, 0.43, 0.68), width=1)
            document = pdf.tobytes()
            pdf.close()
        if len(document) > MAX_FILE:
            raise ValueError("File exceeds 25 MB limit")
        profile = "zebra" if device["preset"] == "zebra" else "brother-tray2" if device["tray"] == "tray-2" else "brother-tray1"
        result = capture(document, profile, self.output_dir, title=title, dpi=device["dpi"])
        with self.lock:
            state = self._read()
            for d in state["devices"]:
                if d["id"] == device_id:
                    d["last_test"] = {"status": result["status"], "at": timestamp(), "job_id": result["id"], "scope": "api_only"}
                    break
            self._write(state)
        return result

    def list_jobs(self) -> list[dict]:
        rows = []
        for metadata in self.output_dir.glob("*/*/job.json"):
            try:
                obj = json.loads(metadata.read_text(encoding="utf-8"))
                if not isinstance(obj, dict) or "id" not in obj:
                    continue
                obj["directory"] = str(metadata.parent)
                rows.append(obj)
            except (OSError, ValueError):
                continue
        return sorted(rows, key=lambda x: x.get("created_at", ""), reverse=True)[:200]

    def artifact(self, job_id: str, filename: str) -> Path | None:
        if not filename.startswith("page-") or not filename.endswith(".jpg") or "/" in filename or "\\" in filename:
            return None
        for job in self.list_jobs():
            if job["id"] == job_id and filename in job.get("images", []):
                path = (Path(job["directory"]) / filename).resolve()
                if path.is_relative_to(self.output_dir) and path.is_file():
                    return path
        return None


def make_handler(store: HubStore, token: str):
    class Handler(BaseHTTPRequestHandler):
        server_version = "DevicesHub/0.3"
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt, *args):
            LOG.info("%s %s", self.client_address[0], fmt % args)

        def send(self, code, body, mime="application/json"):
            data = json.dumps(body, ensure_ascii=False).encode("utf-8") if mime == "application/json" else body
            self.send_response(code)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            path = unquote(urlparse(self.path).path)
            if path in ("/", "/index.html"):
                html = Path(__file__).with_name("ui").joinpath("index.html").read_text(encoding="utf-8")
                html = html.replace("__HUB_TOKEN__", token)
                return self.send(200, html.encode("utf-8"), "text/html; charset=utf-8")
            if path == "/api/state":
                return self.send(200, {
                    "devices": store.list_devices(), "jobs": store.list_jobs(),
                    "presets": PRESETS, "platform": platform.system(), "output_dir": str(store.output_dir),
                    "service": "local", "os_install_supported": False,
                })
            if path == "/api/healthz":
                return self.send(200, {"status": "ok", "engine": "available", "os_registration": "not_verified"})
            if path.startswith("/api/artifacts/"):
                parts = path.split("/")
                if len(parts) != 5:
                    return self.send(404, {"error": "Artifact not found"})
                file = store.artifact(parts[3], parts[4])
                if file is None:
                    return self.send(404, {"error": "Artifact not found"})
                return self.send(200, file.read_bytes(), "image/jpeg")
            return self.send(404, {"error": "Not found"})

        def do_POST(self):
            if self.headers.get("X-Devices-Token") != token:
                return self.send(403, {"error": "Local access token required"})
            try:
                size = int(self.headers.get("Content-Length", "-1"))
                if size < 0 or size > MAX_BODY:
                    return self.send(413, {"error": "Invalid or oversized request"})
                payload = json.loads(self.rfile.read(size))
                if not isinstance(payload, dict):
                    raise ValueError("Expected JSON object")
                path = urlparse(self.path).path
                if path == "/api/devices":
                    return self.send(201, {"device": store.create_device(payload)})
                parts = path.strip("/").split("/")
                if len(parts) == 4 and parts[:2] == ["api", "devices"] and parts[3] == "test":
                    document = None
                    if "file_base64" in payload:
                        try:
                            document = base64.b64decode(payload["file_base64"], validate=True)
                        except (binascii.Error, TypeError):
                            raise ValueError("Invalid base64 file")
                    title = str(payload.get("title", "Sample Test"))[:80]
                    result = store.test_device(parts[2], document, title)
                    return self.send(200, {"job": result})
                if len(parts) == 3 and parts[:2] == ["api", "devices"] and parts[2]:
                    if payload.get("action") != "remove_profile":
                        raise ValueError("Only profile removal is supported; OS uninstall is not implemented")
                    removed = store.remove_device(parts[2])
                    return self.send(200 if removed else 404, {"removed": removed})
                return self.send(404, {"error": "Not found"})
            except LookupError as exc:
                return self.send(404, {"error": str(exc)})
            except (ValueError, TypeError, UnicodeError) as exc:
                return self.send(400, {"error": str(exc)})
            except OSError:
                LOG.exception("Hub storage error")
                return self.send(500, {"error": "Local storage error; check folder permissions"})

    return Handler


def create_server(host="127.0.0.1", port=8765, state_dir=None, output_dir=None):
    if host not in ("127.0.0.1", "localhost"):
        raise ValueError("The desktop hub must be restricted to loopback")
    state_dir = state_dir or Path.home() / ".devices-simulator"
    output_dir = output_dir or Path.home() / "Documents" / "Lulwa Virtual Printer"
    store = HubStore(Path(state_dir), Path(output_dir))
    token = secrets.token_urlsafe(32)
    server = ThreadingHTTPServer((host, port), make_handler(store, token))
    server.hub_store = store
    server.hub_token = token
    return server


def main():
    parser = argparse.ArgumentParser(description="Devices Simulator local control hub")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--state-dir", type=Path)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    with create_server(port=args.port, output_dir=args.output, state_dir=args.state_dir) as server:
        url = f"http://127.0.0.1:{server.server_port}/"
        print(f"Devices Simulator Hub: {url}", flush=True)
        print("Local-only hub. Native OS printer installation is NOT yet implemented in this UI.", flush=True)
        if not args.no_browser:
            webbrowser.open(url)
        try:
            server.serve_forever(poll_interval=0.2)
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
