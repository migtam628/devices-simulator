# Devices Simulator v0.3 — Hub & Wizard

**Implementation stage:** functional local UI and capture engine. Printer/scanner OS installation remains experimental or unsupported.

## What's actually implemented
- Responsive hybrid design shell with Home, Device Library, Create Device Wizard, device details, Jobs, Gallery, Diagnostics, OS Integration, Settings and Studio visual preview.
- Six-step wizard: Category → Profile → Configuration → Behavior → Install in OS (informational only) → Save & Test.
- Persistent local JSON device profiles. Brother two-tray and Zebra 4×6 profiles, with preview-only scanners, barcode, receipt and serial device categories.
- Sample PDFs at Letter (Brother) and 4×6 (Zebra) passed to existing PDF-to-JPG capture engine. Upload local PDF, JPEG or PNG through Device Details.
- Actual JPG output thumbnails and capture job metadata, with local API-only source indication.
- Local loopback HTTP server, unpredictable write token and capped uploads. No cloud account required.
- Optional native desktop window via pywebview. Distribution installers are **not built**; Windows/macOS/Linux GUI runtime compatibility is still to be validated.
- Explicit OS status “not verified” everywhere. Does not mark shipments fulfilled or imply physical printing.

## Run the hub — macOS / Linux
```bash
git clone https://github.com/migtam628/devices-simulator.git
cd devices-simulator
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -e '.[test]'
python3 -m pytest -q
lulwa-hub
```

The hub opens in your browser at `http://127.0.0.1:8765/`. Keep the terminal running. Or use `lulwa-hub --no-browser --port 8765` to launch without automatically opening the browser.

**Optional native window** on macOS and Windows:
```bash
python3 -m pip install -e '.[desktop]'
lulwa-desktop
```

On Linux install a webview backend first (e.g. `python3 -m pip install "pywebview[gtk]"` plus GTK/WebKit system packages appropriate for the distro), then run `lulwa-desktop`. The pywebview project documents per-OS prerequisites: https://pywebview.idepy.com/en/guide/installation

## Run the hub — Windows PowerShell
```powershell
git clone https://github.com/migtam628/devices-simulator.git
cd devices-simulator
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[test,desktop]"
python -m pytest -q
lulwa-desktop
```

If native WebView2 runtime is unavailable, use `lulwa-hub` to open the local browser UI.

## Device test
1. Home → Create Device.
2. Select **Brother Dual Tray** or **Zebra 4×6 Thermal**.
3. Configure the name and (for Brother) default tray.
4. Continue through Behavior and OS Installation info; **Save Device**.
5. Open Device Detail → **Generate Sample** or **Import Document** (PDF/JPG/PNG).
6. In Output Gallery, open the generated JPG.
7. Files are stored under `~/Documents/Lulwa Virtual Printer/<profile>/<title>-<job-id>/`.

## Limitations
- API capture is implemented; system print-dialog installation is not performed from the wizard.
- The older experimental `lulwa-ipp` and CUPS/PowerShell installers are separate.
- Raw ZPL is archived, **not rendered**. Native scanner, barcode HID, serial/COM and receipt printer drivers not implemented.
- Studio is a static visual reference, not a workflow editor.
- OS-native desktop wrapper needs optional dependencies; no signed `.dmg`, `.msi` or `.deb` release installers yet.
- Local generated files can contain personal/customer information; use a protected output folder and secure deletion policy.
- Do not expose the hub beyond loopback; do not use virtual captures to mark orders fulfilled.

## Next implementation phases
1. Verify real OS printer registration against Windows/macOS/Linux and integrate lifecycle/installer/queue enumeration.
2. Make Brother & Zebra capability controls editable and validated, and add raw ZPL local renderer.
3. Device fault injection, retention, editable settings and live diagnostics.
4. Package signed OS installers and autostart service.
5. Scanner device protocol and optional Studio workflow engine.
