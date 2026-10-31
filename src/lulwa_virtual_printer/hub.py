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
import math
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
from .retention import retention_preview, retention_cleanup
from .native_printers import get_registration, install_printer, uninstall_printer, service_ready, PORT
from .hid_barcode import MacBarcodeHID
from .mac_scale_hid import MacScaleHID
from .device_catalog import BY_ID
from .os_print_test import print_readiness, verify_print_roundtrip
from .device_catalog import public_catalog, select_model
from .studio_engine import StudioManager
from .connection_engine import ConnectionEngine

LOG = logging.getLogger(__name__)
MAX_BODY = 35 * 1024 * 1024
MAX_FILE = 25 * 1024 * 1024
CATEGORIES = ("office_printer", "label_printer", "scanner", "barcode", "receipt", "serial", "scale", "network_device", "usb_device", "ble_device", "rfid", "sensor")
PRESETS = {
    "brother": {"category": "office_printer", "label": "Brother Dual Tray", "name": "Brother Office Printer", "dpi": 300, "media": "Letter · 8.5 × 11 in", "profiles": ["brother-tray1", "brother-tray2"], "capability": "experimental"},
    "zebra": {"category": "label_printer", "label": "Zebra 4×6 Thermal", "name": "Zebra 4×6 Label Printer", "dpi": 203, "media": "Label · 4 × 6 in", "profiles": ["zebra"], "capability": "experimental"},
    "scanner": {"category": "scanner", "label": "Flatbed Scanner Fixture", "name": "Virtual Flatbed Scan Preview", "dpi": 300, "media": "Letter · 8.5 × 11 in", "profiles": ["scanner"], "capability": "preview_only"},
    "barcode": {"category": "barcode", "label": "Barcode Input Simulator", "name": "Simulated Barcode Input", "dpi": None, "media": "Keyboard events · macOS", "profiles": [], "capability": "experimental"},
    "receipt": {"category": "receipt", "label": "Receipt Printer", "name": "Virtual Receipt Printer", "dpi": 203, "media": "80 mm roll", "profiles": [], "capability": "planned"},
    "serial": {"category": "serial", "label": "Serial / COM Device", "name": "Virtual Serial Device", "dpi": None, "media": "PTY / COM", "profiles": [], "capability": "planned"},
    "scale": {"category": "scale", "label": "Shipping / Postal Scale", "name": "Simulated Shipping Scale", "dpi": None, "media": "Weight · kg / lb", "profiles": [], "capability": "in_app"},
    "network_device": {"category": "network_device", "label": "Network / Ethernet Device", "name": "Network Device Fixture", "dpi": None, "media": "TCP/IP endpoint profile", "profiles": [], "capability": "planned"},
    "usb_device": {"category": "usb_device", "label": "USB Device", "name": "USB Peripheral Fixture", "dpi": None, "media": "USB interface profile", "profiles": [], "capability": "planned"},
    "ble_device": {"category": "ble_device", "label": "BLE Device", "name": "Bluetooth LE Fixture", "dpi": None, "media": "GATT profile", "profiles": [], "capability": "planned"},
    "rfid": {"category": "rfid", "label": "RFID Reader", "name": "RFID Reader Fixture", "dpi": None, "media": "RFID input profile", "profiles": [], "capability": "planned"},
    "sensor": {"category": "sensor", "label": "Sensor / Telemetry", "name": "Sensor Fixture", "dpi": None, "media": "Telemetry profile", "profiles": [], "capability": "planned"},
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
        model, transport = select_model(preset, config["category"], data.get("model_id"), data.get("transport"))
        with self.lock:
            state = self._read()
            if any(d["name"].casefold() == name.casefold() for d in state["devices"]):
                raise ValueError("Device name already exists")
            obj = {
                "id": str(uuid.uuid4()), "preset": preset, "category": config["category"],
                "name": name, "media": config["media"], "dpi": config["dpi"],
                "model_id": model["id"], "brand": model["brand"], "model": model["model"],
                "transport": transport, "transport_status": "profile_only",
                "last_measurement": None,
                "tray": data.get("tray") if data.get("tray") in ("tray-1", "tray-2") else "tray-1",
                "output_format": "jpg", "delay_ms": 0, "fault": "none",
                "lifecycle": "draft", "os_status": "not_verified",
                "last_test": None, "created_at": timestamp()
            }
            state["devices"].append(obj)
            self._write(state)
            return obj


    def update_model(self, device_id: str, data: dict) -> dict:
        """Update fixture metadata only, never OS queues or USB/BLE devices."""
        with self.lock:
            state = self._read()
            for d in state["devices"]:
                if d["id"] == device_id:
                    model, transport = select_model(d["preset"], d["category"],
                                                    data.get("model_id"), data.get("transport"))
                    d.update(model_id=model["id"], brand=model["brand"], model=model["model"],
                             transport=transport, transport_status="profile_only",
                             os_status="not_verified", last_measurement=None)
                    self._write(state)
                    return d
        raise LookupError("Device not found")

    def simulate_scale_reading(self, device_id: str, data: dict) -> dict:
        """A local reading fixture, not real USB, BLE, TCP or certified measurement."""
        with self.lock:
            state = self._read()
            for d in state["devices"]:
                if d["id"] != device_id:
                    continue
                if d["category"] != "scale":
                    raise ValueError("Weight readings are only available on scale profiles")
                model, _ = select_model(d["preset"], d["category"],
                                        d.get("model_id"), d.get("transport"))
                try:
                    gross = float(data.get("gross_kg", 0))
                    tare = float(data.get("tare_kg", 0))
                except (TypeError, ValueError) as exc:
                    raise ValueError("Weight and tare must be numbers") from exc
                if not (math.isfinite(gross) and math.isfinite(tare) and
                        0 <= gross <= 10000 and 0 <= tare <= gross):
                    raise ValueError("Use finite nonnegative kg values; tare must not exceed gross")
                unit = data.get("unit", "kg")
                if unit not in ("kg", "lb", "g", "oz"):
                    raise ValueError("Unsupported scale unit; choose kg, lb, g or oz")
                stable = data.get("stable", True)
                if type(stable) is not bool:
                    raise ValueError("Stable must be a boolean")
                capacity = float(model.get("max_kg", 10000))
                overloaded = gross > capacity
                net = round(gross - tare, 4)
                factor = {"kg": 1.0, "lb": 2.2046226218, "g": 1000.0,
                          "oz": 35.27396195}[unit]
                reading = {
                    "device_id": device_id, "model_id": model["id"],
                    "brand": model["brand"], "model": model["model"],
                    "transport": d["transport"], "transport_status": "not_connected",
                    "scope": "in_app_scale_fixture", "gross_kg": round(gross, 4),
                    "tare_kg": round(tare, 4), "net_kg": net,
                    "weight": round(net * factor, 3), "unit": unit,
                    "stable": stable and not overloaded,
                    "status": "over_capacity" if overloaded else ("stable" if stable else "unstable"),
                    "max_kg": capacity, "at": timestamp()
                }
                d["last_measurement"] = reading
                d["last_test"] = {"status": reading["status"], "at": reading["at"],
                                  "scope": "in_app_scale_fixture"}
                self._write(state)
                return reading
        raise LookupError("Device not found")

    def remove_device(self, device_id: str) -> bool:
        with self.lock:
            state = self._read()
            new = [d for d in state["devices"] if d["id"] != device_id]
            if len(new) == len(state["devices"]):
                return False
            state["devices"] = new
            self._write(state)
            return True


    def configure_device(self, device_id: str, data: dict):
        fault = data.get("fault", "none")
        tray = data.get("tray", "tray-1")
        if fault not in ("none", "offline", "paper_out", "jam", "paused"):
            raise ValueError("Unknown simulated device fault")
        if tray not in ("tray-1", "tray-2"):
            raise ValueError("Unknown Brother paper tray")
        with self.lock:
            state = self._read()
            for d in state["devices"]:
                if d["id"] == device_id:
                    if d["preset"] not in ("brother", "zebra"):
                        raise ValueError("Fault injection only supports printer profiles")
                    d["fault"] = fault
                    if d["preset"] == "brother":
                        d["tray"] = tray
                    self._write(state)
                    return d
        raise LookupError("Device not found")

    def _record_simulated_failure(self, profile: str, title: str, fault: str):
        ident = uuid.uuid4().hex
        directory = self.output_dir / profile / ("simulated-failure-" + ident)
        directory.mkdir(parents=True, exist_ok=False)
        job = {"id": ident, "title": title, "profile": profile,
               "status": "failed", "error": f"Simulated {fault.replace('_', ' ')}",
               "images": [], "format": "simulation", "created_at": timestamp()}
        (directory / "job.json").write_text(json.dumps(job, indent=2), encoding="utf-8")
        return {**job, "directory": str(directory)}

    def run_shipping_demo(self, brother_id: str, zebra_id: str):
        a, b = self.get_device(brother_id), self.get_device(zebra_id)
        if not a or not b or a["preset"] != "brother" or b["preset"] != "zebra":
            raise ValueError("Studio requires saved Brother and Zebra device profiles")
        jobs = [self.test_device(brother_id, title="Studio Packing Slip"),
                self.test_device(zebra_id, title="Studio Shipping Label")]
        return {"status": "completed" if all(x["status"] == "rendered" for x in jobs) else "failed",
                "mode": "local_capture_demo", "jobs": jobs}

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
        profile = ("zebra" if device["preset"] == "zebra" else "scanner"
                   if device["preset"] == "scanner" else
                   "brother-tray2" if device["tray"] == "tray-2" else "brother-tray1")
        fault = device.get("fault", "none")
        result = (self._record_simulated_failure(profile, title, fault) if fault != "none"
                  else capture(document, profile, self.output_dir, title=title, dpi=device["dpi"]))
        with self.lock:
            state = self._read()
            for d in state["devices"]:
                if d["id"] == device_id:
                    d["last_test"] = {"status": result["status"], "at": timestamp(), "job_id": result["id"], "scope": "in_app_fixture" if device["preset"] == "scanner" else "api_only"}
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


def make_handler(store: HubStore, token: str, hid: MacBarcodeHID, scale_hid: MacScaleHID, studio: StudioManager, connections: ConnectionEngine):
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
            if path == "/connections.js":
                file = Path(__file__).with_name("ui") / "connections.js"
                return self.send(200, file.read_bytes(), "application/javascript; charset=utf-8")
            if path in ("/studio.js", "/studio_editor.js", "/studio_debugger.js"):
                file = Path(__file__).with_name("ui") / path.lstrip("/")
                return self.send(200, file.read_bytes(), "application/javascript; charset=utf-8")
            if path in ("/", "/index.html"):
                html = Path(__file__).with_name("ui").joinpath("index.html").read_text(encoding="utf-8")
                html = html.replace("__HUB_TOKEN__", token)
                return self.send(200, html.encode("utf-8"), "text/html; charset=utf-8")
            if path == "/api/state":
                registrations = {p: get_registration(p) for p in ("brother", "zebra")}
                devices = store.list_devices()
                for device in devices:
                    status = registrations.get(device["preset"])
                    if status:
                        device["os_status"] = status["status"]
                return self.send(200, {
                    "devices": devices, "jobs": store.list_jobs(), "registrations": registrations,
                    "ipp_service_ready": service_ready(), "hid": hid.state(),
                    "scale_hid": scale_hid.state(),
                    "presets": PRESETS, "catalog": public_catalog(),
                    "studio": studio.snapshot(), "connections": connections.snapshot(),
                    "platform": platform.system(), "output_dir": str(store.output_dir),
                    "service": "local", "os_install_supported": platform.system() in ("Darwin", "Linux", "Windows"),
                })
            if path == "/api/studio/workflows":
                return self.send(200, studio.snapshot())
            if path == "/api/connections":
                return self.send(200, connections.snapshot())
            if path == "/api/catalog":
                return self.send(200, public_catalog())
            if path == "/api/healthz":
                return self.send(200, {"status": "ok", "engine": "available",
                                       "ipp_service_ready": service_ready()})
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
                # Consume a bounded request body before replying so HTTP/1.1
                # keep-alive cannot interpret leftover JSON as a new request.
                try:
                    rejected_size = int(self.headers.get("Content-Length", "-1"))
                    if 0 <= rejected_size <= MAX_BODY:
                        self.rfile.read(rejected_size)
                    else:
                        self.close_connection = True
                except (ValueError, OverflowError):
                    self.close_connection = True
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
                if path == "/api/system/retention/preview":
                    return self.send(200, {"preview": retention_preview(
                        store.output_dir, payload.get("days"))})
                if path == "/api/system/retention/cleanup":
                    with store.lock:
                        result = retention_cleanup(
                            store.output_dir, payload.get("days"),
                            payload.get("fingerprint"), confirm=payload.get("confirm"))
                    return self.send(200, {"cleanup": result})
                if path == "/api/system/print-readiness":
                    return self.send(200, {"readiness": print_readiness(
                        str(payload.get("preset", "")), store.output_dir)})
                if path == "/api/system/print-test":
                    if payload.get("confirm") is not True:
                        return self.send(400, {"error": "Confirm this OS print test first"})
                    ready = print_readiness(str(payload.get("preset", "")), store.output_dir)
                    if ready["status"] != "ready":
                        reasons = "; ".join(c["detail"] for c in ready["checks"] if not c["ok"])
                        return self.send(409, {"error": "Print path not ready: " + reasons[:600],
                                               "readiness": ready})
                    result = verify_print_roundtrip(str(payload.get("preset", "")), store.output_dir)
                    return self.send(200, {"verification": result})
                if path.startswith("/api/scale-hid/"):
                    device_id = str(payload.get("device_id", ""))
                    device = store.get_device(device_id)
                    if not device or device.get("category") != "scale" or device.get("transport") != "usb_hid":
                        return self.send(400, {"error": "Choose a saved USB HID scale profile"})
                    if device.get("model_id") not in ("dymo-m10", "dymo-m25", "generic-scale"):
                        return self.send(400, {"error": "Current CoreHID preview supports generic POS / DYMO M-series reference profiles"})
                    if path == "/api/scale-hid/start":
                        if payload.get("confirm") is not True:
                            return self.send(400, {"error": "Explicit virtual HID activation confirmation required"})
                        status = scale_hid.start(device_id)
                        # A first zero reading is sent only after helper activation.
                        scale_hid.send(device_id, 0, capacity_kg=BY_ID[device["model_id"]].get("max_kg", 4.5))
                        return self.send(200, {"scale_hid": scale_hid.state()})
                    if path == "/api/scale-hid/stop":
                        if payload.get("confirm") is not True:
                            return self.send(400, {"error": "Confirm virtual HID deactivation"})
                        if scale_hid.device_id != device_id:
                            return self.send(409, {"error": "Selected scale is not active"})
                        return self.send(200, {"scale_hid": scale_hid.stop()})
                    if path == "/api/scale-hid/probe":
                        if scale_hid.device_id != device_id:
                            return self.send(409, {"error": "Activate this scale before checking OS enumeration"})
                        scale_hid.probe()
                        return self.send(200, {"scale_hid": scale_hid.state()})
                    return self.send(404, {"error": "Unknown scale HID action"})
                if path.startswith("/api/connections/"):
                    device_id = payload.get("device_id")
                    if payload.get("confirm") is not True:
                        return self.send(400, {"error": "Explicit localhost listener change confirmation required"})
                    if path == "/api/connections/start":
                        return self.send(200, {"connection": connections.start(device_id, payload.get("port", 0))})
                    if path == "/api/connections/stop":
                        return self.send(200, {"connection": connections.stop(device_id)})
                    if path == "/api/connections/fault":
                        return self.send(200, {"connection": connections.set_fault(device_id, payload.get("fault"))})
                    if path == "/api/connections/probe":
                        return self.send(200, {"probe": connections.probe(device_id)})
                    if path == "/api/connections/serial-start":
                        return self.send(200, {"connection": connections.start_serial(device_id)})
                    if path == "/api/connections/serial-stop":
                        return self.send(200, {"connection": connections.stop_serial(device_id)})
                    if path == "/api/connections/serial-fault":
                        return self.send(200, {"connection": connections.set_serial_fault(device_id, payload.get("fault"))})
                    if path == "/api/connections/serial-probe":
                        return self.send(200, {"probe": connections.probe_serial(device_id)})
                    return self.send(404, {"error": "Unknown connection command"})
                if path == "/api/studio/debug/status":
                    return self.send(200, {"session": studio.live_status()})
                if path == "/api/studio/debug/start":
                    return self.send(200, {"session": studio.live_start(
                        payload.get("id"), payload.get("revision"))})
                if path == "/api/studio/debug/step":
                    return self.send(200, {"result": studio.live_step(
                        payload.get("session_id"), payload.get("expected_step"),
                        payload.get("confirm", False))})
                if path == "/api/studio/debug/cancel":
                    return self.send(200, {"run": studio.live_cancel(payload.get("session_id"))})
                if path == "/api/studio/workflows/inspect":
                    return self.send(200, {"inspection": studio.inspect(
                        payload.get("workflow"), payload.get("checkpoints"))})
                if path == "/api/studio/workflows/save":
                    return self.send(200, {"workflow": studio.save(payload)})
                if path == "/api/studio/workflows/export":
                    return self.send(200, {"document": studio.export_workflow(payload.get("id"))})
                if path == "/api/studio/workflows/import":
                    return self.send(200, {"workflow": studio.import_workflow(
                        payload.get("document"), payload.get("device_map"))})
                if path == "/api/studio/workflows/replay":
                    if payload.get("confirm") is not True:
                        return self.send(400, {"error": "Replay requires explicit confirmation of fresh execution"})
                    return self.send(200, {"run": studio.run(
                        payload.get("id"), replay_run_id=payload.get("run_id"))})
                if path == "/api/studio/workflows/delete":
                    return self.send(200, {"deleted": studio.delete(payload.get("id"))})
                if path == "/api/studio/workflows/execute":
                    return self.send(200, {"run": studio.run(payload.get("id"))})
                if path == "/api/studio/run":
                    result = store.run_shipping_demo(str(payload.get("brother_id","")),
                                                     str(payload.get("zebra_id","")))
                    return self.send(200, {"studio": result})
                if path.startswith("/api/hid/"):
                    if payload.get("confirm") is not True:
                        return self.send(400, {"error": "Confirm keyboard input simulation before starting or sending a scan"})
                    if path == "/api/hid/start":
                        return self.send(200, {"hid": hid.start()})
                    if path == "/api/hid/stop":
                        return self.send(200, {"hid": hid.stop()})
                    if path == "/api/hid/scan":
                        return self.send(200, {"scan": hid.scan(payload.get("barcode", ""), 3.0)})
                    return self.send(404, {"error": "Unknown HID action"})
                if path in ("/api/system/install", "/api/system/uninstall"):
                    if payload.get("confirm") is not True:
                        return self.send(400, {"error": "Explicit OS-change confirmation required"})
                    requested = payload.get("preset")
                    if requested not in ("brother", "zebra"):
                        return self.send(400, {"error": "Only Brother and Zebra printer queues can be modified"})
                    result = (install_printer(requested) if path.endswith("install")
                              and not path.endswith("uninstall") else uninstall_printer(requested))
                    return self.send(200 if result["success"] else 409, {"registration": result,
                                "error": result.get("error", "")})
                parts = path.strip("/").split("/")
                if len(parts) == 4 and parts[:2] == ["api", "devices"] and parts[3] == "model":
                    if any(a["device_id"] == parts[2]
                           for a in connections.snapshot()["listeners"] + connections.snapshot()["serial_listeners"]):
                        return self.send(409, {"error": "Stop active TCP/serial interfaces before changing the scale model"})
                    return self.send(200, {"device": store.update_model(parts[2], payload)})
                if len(parts) == 4 and parts[:2] == ["api", "devices"] and parts[3] == "scale-reading":
                    reading = store.simulate_scale_reading(parts[2], payload)
                    if scale_hid.active() and scale_hid.device_id == parts[2]:
                        # HID input uses tare-adjusted net mass, never gross weight.
                        scale_state = scale_hid.send(
                            parts[2], reading["net_kg"],
                            stable=reading["stable"],
                            capacity_kg=reading["max_kg"])
                        reading["hid_dispatch"] = "sent" if scale_state["running"] else "unavailable"
                        reading["os_enumerated"] = scale_state["external_visible"]
                    return self.send(200, {"reading": reading})
                if len(parts) == 4 and parts[:2] == ["api", "devices"] and parts[3] == "settings":
                    return self.send(200, {"device": store.configure_device(parts[2], payload)})
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
                    if any(a["device_id"] == parts[2] for a in connections.snapshot()["listeners"]):
                        connections.stop(parts[2])
                    if any(a["device_id"] == parts[2] for a in connections.snapshot()["serial_listeners"]):
                        connections.stop_serial(parts[2])
                    removed = store.remove_device(parts[2])
                    return self.send(200 if removed else 404, {"removed": removed})
                return self.send(404, {"error": "Not found"})
            except LookupError as exc:
                return self.send(404, {"error": str(exc)})
            except RuntimeError as exc:
                return self.send(409, {"error": str(exc)})
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
    hid = MacBarcodeHID()
    scale_hid = MacScaleHID()
    connections = ConnectionEngine(store)
    studio = StudioManager(Path(state_dir), store, connections=connections)
    server = ThreadingHTTPServer((host, port), make_handler(store, token, hid, scale_hid, studio, connections))
    server.hub_connections = connections
    server.hub_studio = studio
    server.hub_hid = hid
    server.hub_scale_hid = scale_hid
    server.hub_store = store
    server.hub_token = token
    base_close = server.server_close
    def close_all_services():
        # Ensure no TCP listener remains after HTTP server shutdown, including
        # in tests or third-party embedding that only calls server_close().
        connections.stop_all()
        base_close()
    server.server_close = close_all_services
    return server



def start_attached_ipp(output=None):
    """Start loopback IPP service alongside hub; reuse already running simulator."""
    from .ipp_server import start_server
    try:
        server = start_server(port=PORT, output=output)
    except OSError as exc:
        if service_ready():
            LOG.info("Reusing existing local IPP service on port %s", PORT)
            return None, None
        raise RuntimeError(f"Port {PORT} is occupied; cannot run virtual printer IPP service") from exc
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.2}, daemon=True)
    thread.start()
    return server, thread


def stop_attached_ipp(server, thread):
    if server is not None:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def main():
    parser = argparse.ArgumentParser(description="Devices Simulator local control hub")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--state-dir", type=Path)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    ipp_server, ipp_thread = start_attached_ipp(output=args.output)
    try:
        with create_server(port=args.port, output_dir=args.output, state_dir=args.state_dir) as server:
            url = f"http://127.0.0.1:{server.server_port}/"
            print(f"Devices Simulator Hub: {url}", flush=True)
            print(f"IPP virtual printer service: http://127.0.0.1:{PORT}/healthz", flush=True)
            if not args.no_browser:
                webbrowser.open(url)
            try:
                server.serve_forever(poll_interval=0.2)
            except KeyboardInterrupt:
                pass
            finally:
                server.hub_hid.stop()
                server.hub_scale_hid.stop()
                server.hub_connections.stop_all()
    finally:
        stop_attached_ipp(ipp_server, ipp_thread)


if __name__ == "__main__":
    main()
