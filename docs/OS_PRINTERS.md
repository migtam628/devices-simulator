# Install OS-visible simulated printers — experimental v0.8.1

The IPP server presents virtual print devices to operating-system printer
settings. It does **not** currently install a scanner or native USB device.
The server has not been certified or validated with Windows/macOS/Linux
installation in real environments, and some OS clients may refuse to install.

## 1. Start the local print service

macOS / Linux:

```bash
git clone https://github.com/migtam628/devices-simulator.git
cd devices-simulator
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e '.[test]'
lulwa-ipp --port 8631
```

Windows PowerShell:

```powershell
git clone https://github.com/migtam628/devices-simulator.git
cd devices-simulator
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[test]"
lulwa-ipp --port 8631
```

Keep the service running. It listens on loopback `127.0.0.1:8631` only.
Check http://127.0.0.1:8631/healthz locally.

## 2. Register printers in OS settings

**macOS/Linux:** In another terminal while the service is running:

```bash
bash install/install-macos-linux.sh
lpstat -p
```

The script registers `Lulwa_SIM_Brother` and `Lulwa_SIM_Zebra_4x6` via
`lpadmin -m everywhere`. Administrative rights and a functioning CUPS
service may be required. If the CUPS setup fails, save the exact error:
this IPP server is not yet fully IPP Everywhere compliant.

**Windows 11:** In another PowerShell window:

```powershell
.\install\install-windows.ps1
Get-Printer | Where-Object Name -Match 'Lulwa'
```

If automated installation fails, open Settings > Bluetooth & devices >
Printers & scanners > Add device > Add manually > Add a printer using an
IP address/hostname. Select **IPP Device** and supply one endpoint:

- `http://127.0.0.1:8631/ipp/brother`
- `http://127.0.0.1:8631/ipp/zebra`

These are IPP devices, **not** physical USB devices or signed Windows drivers.
Some Windows builds or the Microsoft IPP Class Driver may refuse to negotiate.
Do not claim installation succeeded unless the device appears in `Get-Printer`.

## 3. Print and inspect the JPG

Once registered, choose the simulated printer in any application's Print
dialog and print a PDF test page. Accepted document formats: PDF, JPEG,
PNG. The engine writes the original, `job.json` and `page-001.jpg`
under `~/Documents/Lulwa Virtual Printer/` in the user's environment.

Brother primary endpoint advertises `tray-1` and `tray-2`, but a
specific OS print dialog may omit tray selection. Optional explicit
queue endpoints are `/ipp/brother-tray1` and `/ipp/brother-tray2`.
Zebra advertises 4×6 media at 203 DPI.

Unimplemented document formats: PWG Raster, URF, PostScript, raw ZPL.
These can prevent OS printing despite registration.

## 4. Remove printers

macOS/Linux: `bash install/uninstall-macos-linux.sh`

Windows: List first with `Get-Printer`, then use
`Remove-Printer -Name '<exact printer name>'` only for matching Lulwa queues.
Stop `lulwa-ipp` to stop the service. No autostart installer exists yet.

## Scanner support (not implemented)

Native scanners require eSCL/AirScan and/or platform-specific Windows
scanner discovery and transport. Naming an IPP printer “scanner” does
not register it as an OS scanner. Thermal label makers are printers.

## Security and technical limitations

- Localhost-only, no authentication and no LAN discovery.
- The simulator must remain running or OS print jobs cannot be delivered.
- The partial IPP protocol implementation is *not* IPP Everywhere certified.
- Carrier documents can contain PII: protect JPG output and limit retention.
- An accepted captured job does not mean an actual order was fulfilled.

## macOS print jobs stuck waiting

See [CUPS Print → JPG troubleshooting](CUPS_JPG_TROUBLESHOOTING.md). v0.8.1 supports bounded HTTP chunked IPP request bodies and records IPP job-state diagnostics. An installed queue does not guarantee a completed print.
