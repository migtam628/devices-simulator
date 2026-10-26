"""Opt-in macOS CoreHID generic POS scale manager.

CoreHID requires Apple HID virtual-device entitlement/signing. The unsigned
portable app should report the entitlement problem, not a fake connection.
No USB port, DYMO vendor identity, or native device is simulated on other OSes.
"""
from __future__ import annotations
import platform
import selectors
import subprocess
import threading
from pathlib import Path
from .hid_scale_pos import encode_weight_report


def helper_binary() -> Path:
    bundled=Path(__file__).resolve().parent/"bin"/"mac_scale_corehid"
    if bundled.is_file():
        return bundled
    return Path(__file__).resolve().parents[2]/"packaging"/"macos"/"mac_scale_corehid"


class MacScaleHID:
    def __init__(self,system=None,binary=None,run=subprocess.run):
        self.system=system or platform.system()
        self.binary=Path(binary) if binary else helper_binary()
        self.run=run
        self.proc=None
        self.device_id=None
        self.lock=threading.RLock()
        self.last_error=""
        self.last_report_hex=None
        self.external_visible=False

    def supported(self):
        return self.system=="Darwin" and self.binary.is_file()

    def active(self):
        return self.proc is not None and self.proc.poll() is None

    def state(self):
        with self.lock:
            return {"available":self.supported(),"running":self.active(),
                    "device_id":self.device_id,"last_error":self.last_error,
                    "external_visible":self.external_visible,
                    "last_report_hex":self.last_report_hex,
                    "mode":"generic_pos_hid_experimental",
                    "warning":"CoreHID requires an approved Apple entitlement. This is NOT an official DYMO USB device."}

    def _receive(self,seconds=6):
        if not self.proc or not self.proc.stdout:return ""
        poll=selectors.DefaultSelector()
        try:
            poll.register(self.proc.stdout,selectors.EVENT_READ)
            if not poll.select(seconds):return ""
            return self.proc.stdout.readline().strip()
        finally:
            poll.close()

    def probe(self):
        """Require another OS process to enumerate our device by product string."""
        if not self.active():
            self.external_visible=False
            return False
        try:
            check=self.run(["hidutil","list"],capture_output=True,text=True,timeout=6)
            self.external_visible=(check.returncode==0 and
                                   "Devices Simulator POS Scale" in check.stdout)
        except (OSError,subprocess.TimeoutExpired):
            self.external_visible=False
        return self.external_visible

    def start(self,device_id):
        with self.lock:
            if self.active():
                if self.device_id!=device_id:
                    raise RuntimeError("Deactivate the current POS scale first")
                self.probe()
                return self.state()
            if not self.supported():
                raise RuntimeError("macOS CoreHID scale helper unavailable (macOS 15+ and compiled binary required)")
            self.device_id=None
            self.external_visible=False
            self.last_error=""
            try:
                self.proc=subprocess.Popen(
                    [str(self.binary)],stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                    text=True,bufsize=1)
                reply=self._receive()
                if not reply.startswith("READY "):
                    if reply.startswith("ERR HID_CREATION_FAILED"):
                        raise RuntimeError("macOS refused virtual HID creation. Apple CoreHID entitlement/code signing is required; standard GitHub binaries cannot install this device.")
                    raise RuntimeError(reply if reply.startswith("ERR ") else "CoreHID helper did not report READY")
                self.device_id=device_id
                self.probe()
                return self.state()
            except Exception as exc:
                error=str(exc)
                self.stop()
                self.last_error=error
                raise RuntimeError(error) from exc

    def send(self,device_id,net_kg,stable=True,capacity_kg=4.5):
        with self.lock:
            if not self.active() or self.device_id!=device_id:
                raise RuntimeError("Activate the scale's CoreHID helper before sending HID reports")
            data=encode_weight_report(net_kg,stable=stable,capacity_kg=capacity_kg)
            self.proc.stdin.write("REPORT "+data.hex().upper()+"\n")
            self.proc.stdin.flush()
            reply=self._receive()
            if reply!="OK REPORT_SENT":
                self.last_error=reply or "Timed out sending HID report"
                raise RuntimeError(self.last_error)
            self.last_report_hex=data.hex().upper()
            self.probe()
            return self.state()

    def stop(self):
        with self.lock:
            p=self.proc
            self.proc=None
            self.device_id=None
            self.external_visible=False
            if p:
                if p.poll() is None:
                    try:
                        p.stdin.write("QUIT\n")
                        p.stdin.flush()
                        p.wait(timeout=2)
                    except (OSError,subprocess.TimeoutExpired):
                        p.kill();p.wait(timeout=3)
                for stream in (p.stdin,p.stdout,p.stderr):
                    if stream:stream.close()
            return self.state()
