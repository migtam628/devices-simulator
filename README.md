# Devices Simulator — Lulwa Virtual Printer v0.1

Prototype virtual-printer capture engine for testing Lulwa Swim fulfillment documents. Supports Brother Tray 1, Brother Tray 2, and Zebra 4x6 profiles. Converts incoming PDF, JPG or PNG documents into saved JPG files. Raw ZPL is **archived but not rendered**.

> **Current state:** This is a working document-to-JPG capture engine and an experimental CUPS backend, **not** a production-ready cross-platform virtual printer installer. Windows OS printer installation, robust macOS/Linux system queue installation, ZPL rendering, desktop GUI, and PrintNode integration are pending. The project's test suite exercises engine behavior, not OS printer registration.

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

## Printer profiles

| Profile | Purpose | Default DPI |
| --- | --- | --- |
| `brother-tray1` | Letter packing slip | 300 |
| `brother-tray2` | Letter invoice / forms | 300 |
| `zebra` | 4x6 label | 203 |

These are **capture profiles** and do not automatically appear in an operating system's Print dialog. Image input retains its source dimensions; the profile name alone does not resize output. For PDF input the document page size and DPI determine JPG dimensions.

## Experimental CUPS backend (Linux / macOS)

`install/cups-backend` and `install/install-cups.sh` demonstrate a CUPS device backend and three separate queues. `lpadmin -m raw` is deprecated and unsupported on some CUPS/macOS releases. Do not use the installer on a production computer. CUPS must be able to invoke the Python interpreter with this package and its dependencies installed; the output folder must be writable by the CUPS service. These prerequisites are **not automatically configured**. This installer currently does not provide a complete secure, supported driverless IPP service.

## Limitations and safety

- PDF and raster images are rendered to JPG. PostScript is rejected until converted to PDF.
- Raw Zebra ZPL is saved as `original.zpl` with `needs-renderer` status; no JPG is generated yet.
- Jobs are limited to 25 MiB source data and 100 PDF pages.
- Treat output as sensitive customer data: protect saved labels and packing slips with OS permissions and appropriate retention. Do not expose the backend to untrusted networks.
- PrintNode does not integrate automatically with the capture CLI; genuine OS-installed printers are required to be recognized by PrintNode.
- Rendering/capture success **must not** mark a shipment fulfilled.

## Next milestones

1. Install genuine OS-discoverable virtual queues on Windows, macOS, and Linux with documented uninstall.
2. Local PDF and ZPL rendering, accurate 4x6 page boundaries and DPI handling.
3. Desktop UI for print history, previews, simulated printer states and error injection.
4. PrintNode end-to-end compatibility and testing with Lulwa Swim admin.

## Tests

```bash
python3 -m pip install -e '.[test]'
python3 -m pytest -q
```
