# Devices Simulator — v0.6.0 Device Hub Pro

Prototype operating-system IPP print queues and virtual-printer capture engine for testing Lulwa Swim fulfillment documents. Supports Brother Tray 1, Brother Tray 2, and Zebra 4x6 profiles. Converts incoming PDF, JPG or PNG documents into saved JPG files. A limited ZPL-II subset (text, boxes and Code128) can be rendered; unsupported commands are archived with explicit errors.

> **Current state:** Local IPP printer endpoints and cross-platform system queue registration scripts are included. IPP protocol tests pass, but real Windows/macOS/Linux installation and print-dialog support are **unverified and experimental**. Not IPP Everywhere, Mopria, or AirPrint certified. Scanner device installation, PWG Raster, ZPL rendering and PrintNode integration are not implemented. A local hub GUI exists, with experimental operating-system printer registration.

## macOS barcode keyboard input (Accessibility, experimental)

The earlier virtual-HID helper failed on some modern macOS versions. The v0.6 helper uses Quartz keyboard events with user-approved Accessibility permission. **No true HID/USB scanner is installed.** [Details](docs/RELEASE_V0_6.md).

## Download executables from GitHub Releases

The project now builds portable **Windows EXE**, **macOS .app (Apple Silicon and Intel)**, and **Linux x64** executable archives. No Python installation is required on the end user's machine.

**[Download the latest GitHub release](https://github.com/migtam628/devices-simulator/releases)** · [v0.6 features and known gaps](docs/RELEASE_V0_6.md) · [Build instructions](docs/DESKTOP_BUILDS.md)

**Note:** These are unsigned development builds. Linux opens a local browser UI. Native OS printer registration is still experimental; executable packaging alone does not install a guaranteed-working OS printer or scanner.

## New in v0.4 — Native printer installation

See [Hub Quick Start](docs/HUB_QUICKSTART.md) for Windows, macOS and Linux setup, native-window option, wizard use and limitations.

Launch the local browser hub after installation with `lulwa-hub`. Optional desktop shell: `lulwa-desktop` after installing `.[desktop]`.

## Quick start (Windows / macOS / Linux)

Python 3.10+ is required:

```bash
# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e '.[test]'
lulwa-print --profile brother-tray1 --title packing-slip sample.pdf
lulwa-print --profile brother-tray2 --title invoice sample.pdf
lulwa-print --profile zebra --title shipping-label label.pdf
python3 -m pytest -q
```

On Windows PowerShell, use `py -3 -m venv .venv`, then `.venv\Scripts\Activate.ps1` and `python -m pip install -e ".[test]"` (inside the activated virtual environment).

Default output: `~/Documents/Lulwa Virtual Printer/<profile>/<title>-<job-id>/`. Each successful capture contains `page-001.jpg` (and subsequent pages), the original file, and `job.json`.

## System printer registration (experimental)

Start the simulator in one terminal:

```bash
lulwa-ipp --port 8631
```

Then in another terminal, while the service remains running:

- **macOS/Linux with CUPS:** `bash install/install-macos-linux.sh`
- **Windows 11 PowerShell:** `.\\install\\install-windows.ps1`

The scripts attempt to add **Lulwa SIM Brother (2 Trays)** and **Lulwa SIM Zebra 4x6 Label** to the OS printer list. Whether installation actually succeeds depends on IPP client compatibility: this prototype does not yet fully support IPP Everywhere or PWG Raster. See [OS printer guide](docs/OS_PRINTERS.md) for setup, limitations and uninstall.

## Printer profiles

| Profile | Purpose | Default DPI |
| --- | --- | --- |
| `brother-tray1` | Letter packing slip | 300 |
| `brother-tray2` | Letter invoice / forms | 300 |
| `zebra` | 4x6 label | 203 |

These are **capture profiles** that may now be registered as local OS printer queues through the experimental IPP server. Image input retains its source dimensions; the profile name alone does not resize output. For PDF input the document page size and DPI determine JPG dimensions.

## Legacy CUPS backend (Linux / macOS — deprecated experiment)

`install/cups-backend` and `install/install-cups.sh` demonstrate a CUPS device backend and three separate queues. `lpadmin -m raw` is deprecated and unsupported on some CUPS/macOS releases. Do not use the installer on a production computer. CUPS must be able to invoke the Python interpreter with this package and its dependencies installed; the output folder must be writable by the CUPS service. These prerequisites are **not automatically configured**. This installer currently does not provide a complete secure, supported driverless IPP service.

## Limitations and safety

- PDF and raster images are rendered to JPG. PostScript is rejected until converted to PDF.
- ZPL is locally rendered for supported commands. Unsupported ZPL is saved as `original.zpl` with `needs-renderer` status.
- Jobs are limited to 25 MiB source data and 100 PDF pages.
- Treat output as sensitive customer data: protect saved labels and packing slips with OS permissions and appropriate retention. Do not expose the backend to untrusted networks.
- PrintNode does not integrate automatically with the capture CLI; genuine OS-installed printers are required to be recognized by PrintNode.
- Rendering/capture success **must not** mark a shipment fulfilled.

## Next milestones

1. Validate OS-visible IPP printer installation on Windows/macOS/Linux; implement missing IPP capabilities and PWG Raster.
2. Local PDF and ZPL rendering, accurate 4x6 page boundaries and DPI handling.
3. Desktop UI for print history, previews, simulated printer states and error injection.
4. PrintNode end-to-end compatibility and testing with Lulwa Swim admin.
5. Native scanner support requires a separate eSCL/AirScan and Windows-compatible scanner implementation.

## Tests

```bash
python3 -m pip install -e '.[test]'
python3 -m pytest -q
```
