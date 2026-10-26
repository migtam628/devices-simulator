"""Curated, extensible device model catalog.

Transport entries describe real-world model capabilities, NOT interfaces
installed by Devices Simulator. Vendor IDs and protocol framing are not
emulated merely because a model appears in this list.
"""
from __future__ import annotations

TRANSPORTS = {
    "local": {"label": "In-app fixture", "implemented": True},
    "usb_hid": {"label": "USB HID", "implemented": False},
    "usb_serial": {"label": "USB serial / CDC", "implemented": False},
    "usb_vendor": {"label": "USB vendor-specific", "implemented": False},
    "ble_gatt": {"label": "Bluetooth LE / GATT", "implemented": False},
    "bluetooth_serial": {"label": "Bluetooth Classic / serial", "implemented": False},
    "serial": {"label": "RS-232 / COM", "implemented": False},
    "network": {"label": "Ethernet / Wi-Fi (TCP/IP)", "implemented": False},
    "ipp": {"label": "IPP print queue (experimental)", "implemented": True},
}
# Category is distinct from transport; a device may expose many transports.
# max_kg is a profile guardrail for in-app scale fixtures, not metrological certification.
MODELS = [
    {"id": "generic-office", "category": "office_printer", "brand": "Generic", "model": "Dual-Tray Office Printer", "transports": ["ipp", "network", "usb_vendor"], "note": "Two-tray document capture fixture; generic behavior"},
    {"id": "brother-hll2460dw", "category": "office_printer", "brand": "Brother", "model": "HL-L2460DW", "transports": ["ipp", "network", "usb_vendor"], "note": "Reference profile only; this real model has one 250-sheet main tray, not two native trays", "source": "https://www.brother-usa.com/p/laser-printers/HLL2460DW"},
    {"id": "generic-label", "category": "label_printer", "brand": "Generic", "model": "4 × 6 Thermal Label", "transports": ["ipp", "network", "usb_vendor"], "note": "Generic 4×6 capture, limited ZPL subset"},
    {"id": "zebra-zd421", "category": "label_printer", "brand": "Zebra", "model": "ZD421", "transports": ["ipp", "usb_vendor", "network", "ble_gatt", "serial"], "note": "BLE is generally for setup/light transfer; optional hardware interfaces depend on configuration", "source": "https://www.zebra.com/us/en/products/printers/desktop/zd400-series/zd421.html"},
    {"id": "brother-ql1110nwb", "category": "label_printer", "brand": "Brother", "model": "QL-1110NWB", "transports": ["usb_vendor", "network", "bluetooth_serial"], "note": "4-inch label width; Brother command language is not emulated", "source": "https://www.brother-usa.com/p/desktop-label-printers/QL1110NWB"},
    {"id": "generic-scale", "category": "scale", "brand": "Generic", "model": "Shipping Scale Fixture", "transports": ["local", "usb_hid", "usb_serial", "serial", "network", "ble_gatt"], "max_kg": 50, "note": "Working in-app weight fixture; external transports are planned"},
    {"id": "dymo-m10", "category": "scale", "brand": "DYMO", "model": "M10", "transports": ["usb_hid"], "max_kg": 4.5, "note": "USB HID postal scale; no USB descriptor impersonation", "source": "https://download.dymo.com/UserManuals/digitalscales/W008021_USBPostalScales_NA.pdf"},
    {"id": "dymo-m25", "category": "scale", "brand": "DYMO", "model": "M25", "transports": ["usb_hid"], "max_kg": 11, "note": "USB HID postal scale; no USB descriptor impersonation", "source": "https://download.dymo.com/UserManuals/digitalscales/W008021_USBPostalScales_NA.pdf"},
    {"id": "mettler-bc", "category": "scale", "brand": "METTLER TOLEDO", "model": "BC Shipping Scale", "transports": ["serial", "usb_serial", "network", "bluetooth_serial"], "max_kg": 35, "note": "MT-SICS style serial transport; model capacity/configuration varies; external command replies not implemented", "source": "https://www.mt.com/dam/ind/IND_PDF/30126862_R02_BC_Scale_SM_EN.pdf"},
    {"id": "ble-weight-standard", "category": "scale", "brand": "Bluetooth SIG", "model": "Generic GATT Weight Scale (WSS)", "transports": ["ble_gatt"], "max_kg": 150, "note": "Service 0x181D / Weight Measurement 0x2A9D; health-scale standard, not automatically a shipping scale", "source": "https://www.bluetooth.com/wp-content/uploads/Files/Specification/HTML/WSS_v1.0.1/out/en/index-en.html"},
    {"id": "generic-scan", "category": "scanner", "brand": "Generic", "model": "Document Scanner Fixture", "transports": ["local", "network", "usb_vendor"], "note": "In-app scan preview only; native eSCL/WIA not yet supported"},
    {"id": "generic-barcode", "category": "barcode", "brand": "Generic", "model": "Barcode Keyboard Wedge", "transports": ["local", "usb_hid", "ble_gatt"], "note": "macOS keyboard events only; no installed HID device"},
    {"id": "zebra-ds2208", "category": "barcode", "brand": "Zebra", "model": "DS2208", "transports": ["usb_hid", "serial"], "note": "Model reference; USB HID and serial emulation are not implemented", "source": "https://www.zebra.com/ap/en/support-downloads/scanners/general-purpose-scanners/ds2200-series.html"},
    {"id": "generic-receipt", "category": "receipt", "brand": "Generic", "model": "80 mm Receipt Printer", "transports": ["usb_vendor", "network", "serial"], "note": "Device profile only; ESC/POS simulation planned"},
    {"id": "epson-t88vii", "category": "receipt", "brand": "Epson", "model": "OmniLink TM-T88VII", "transports": ["usb_vendor", "network", "serial"], "note": "USB/Ethernet common; exact optional interfaces vary; ESC/POS not yet implemented", "source": "https://mediaserver.goepson.com/ImConvServlet/imconv/93938a326f949a1b2bc0a47bb18db8b1518999dd/original?assetDescr=OmniLink_TM-T88VII_Specification_Sheet_CPD-61180R1.pdf"},
    {"id": "generic-serial", "category": "serial", "brand": "Generic", "model": "Serial/COM Peripheral", "transports": ["serial", "usb_serial", "bluetooth_serial", "network"], "note": "Profile only; no PTY/COM device created"},
    {"id": "generic-network", "category": "network_device", "brand": "Generic", "model": "Network/TCP Peripheral", "transports": ["network"], "note": "Profile only; no TCP listener or network discovery"},
    {"id": "generic-usb", "category": "usb_device", "brand": "Generic", "model": "USB HID Peripheral", "transports": ["usb_hid", "usb_vendor"], "note": "Profile only; no USB enumeration or driver"},
    {"id": "generic-ble", "category": "ble_device", "brand": "Generic", "model": "BLE GATT Peripheral", "transports": ["ble_gatt"], "note": "Profile only; no BLE advertising or GATT server"},
    {"id": "generic-rfid", "category": "rfid", "brand": "Generic", "model": "RFID Reader", "transports": ["usb_hid", "usb_serial", "network", "ble_gatt"], "note": "Profile only; no RFID protocol reader"},
    {"id": "generic-sensor", "category": "sensor", "brand": "Generic", "model": "Telemetry Sensor", "transports": ["ble_gatt", "network", "serial"], "note": "Profile only; no transport adapter"},
]
BY_ID = {item["id"]: item for item in MODELS}
DEFAULT_MODEL = {
    "brother": "generic-office", "zebra": "generic-label",
    "scanner": "generic-scan", "barcode": "generic-barcode",
    "receipt": "generic-receipt", "serial": "generic-serial",
    "scale": "generic-scale", "network_device": "generic-network",
    "usb_device": "generic-usb", "ble_device": "generic-ble",
    "rfid": "generic-rfid", "sensor": "generic-sensor",
}

def select_model(preset: str, category: str, model_id=None, transport=None) -> tuple[dict, str]:
    chosen = model_id if model_id is not None else DEFAULT_MODEL[preset]
    model = BY_ID.get(chosen)
    if model is None or model["category"] != category:
        raise ValueError("Brand/model is not valid for the selected device category")
    selected = transport or model["transports"][0]
    if selected not in model["transports"] or selected not in TRANSPORTS:
        raise ValueError("Connection type is unsupported for this model")
    return model, selected

def public_catalog() -> dict:
    return {"models": MODELS, "transports": TRANSPORTS, "default_models": DEFAULT_MODEL}
