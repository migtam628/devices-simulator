# Cross-platform executable builds

GitHub Actions packages the Device Simulator Hub for **Windows**, **macOS (Apple Silicon and Intel)**, and **Linux x64**. Downloads are portable archives containing a frozen executable, Python runtime, required Python packages, UI files and printer definitions. You do **not** need to install Python.

## Download the builds
1. Open [Build desktop executables](https://github.com/migtam628/devices-simulator/actions/workflows/build-desktop.yml).
2. Select the most recent **successful** workflow run.
3. At the bottom under **Artifacts**, download the file matching your computer.

| GitHub Actions artifact | Archive / application | Use |
| --- | --- | --- |
| DevicesSimulator-Windows-x64 | ZIP containing `DevicesSimulator/DevicesSimulator.exe` | Extract the **whole** folder and run the EXE inside |
| DevicesSimulator-macOS-arm64 | ZIP containing `DevicesSimulator.app` | Extract and open on an Apple Silicon Mac (M-series) |
| DevicesSimulator-macOS-x64 | ZIP containing `DevicesSimulator.app` | Extract and open on an Intel Mac |
| DevicesSimulator-Linux-x64 | TAR.GZ containing `DevicesSimulator/DevicesSimulator` | Extract and execute on Linux x64 |

Each artifact also includes a **SHA-256 checksum**. GitHub Actions artifacts are retained for 14 days. To rebuild, go to Actions → Build desktop executables → **Run workflow**.

## Linux launch
From the folder containing the downloaded archive:

```bash
mkdir -p ~/Applications
tar -xzf DevicesSimulator-Linux-x64.tar.gz -C ~/Applications
~/Applications/DevicesSimulator/DevicesSimulator
```

The Linux executable opens the hub in the system's **default web browser**, rather than using a bundled GTK/Qt window. Python installation is not needed, but a Linux desktop, default browser and appropriate system libraries are needed.

## Windows / macOS requirements
- Windows uses the machine's **WebView2 runtime** for its native window (may need to be installed).
- macOS uses its Cocoa/WebKit runtime. Choose the right CPU architecture. The app is not notarized or signed with an Apple Developer ID, so macOS may display a Gatekeeper warning; only approve builds you trust.
- These are **portable development applications**, not MSI, DMG, DEB installers, and they are **unsigned**. The Windows ZIP must be extracted with its `_internal` support files intact.

## What GitHub Actions verifies
Each build runs on a runner of the target OS. Its steps:
1. Run the Python test suite.
2. Package the app using PyInstaller.
3. Execute the actual **frozen binary** in `--self-test` mode to ensure bundled UI/PPD resources and PDF-to-JPG processing work.
4. Publish an archive and SHA-256 checksum under GitHub Actions Artifacts.

The self-test is headless; it does not confirm that the UI window renders on a physical desktop. The operating system's **Printers & Scanners** integration is still experimental. An app executable is not a vendor driver; scanner, virtual USB/HID, raw ZPL, and confirmed PrintNode compatibility are separate work.

## Build on your own computer
Use Python 3.12 and run:

```bash
# macOS (and Windows, using python instead of python3):
python3 -m pip install -e '.[desktop,test]' 'pyinstaller>=6.12,<7'
python3 packaging/build.py
python3 packaging/smoke.py

# Linux:
python3 -m pip install -e '.[test]' 'pyinstaller>=6.12,<7'
python3 packaging/build.py
python3 packaging/smoke.py
```

Built archives appear in `release/`.

## System printer registration
The hub includes an experimental **Install in OS** action for Brother and Zebra. It attempts to register IPP printer queues and checks their entries. Native OS permissions and IPP compatibility are still required. See [OS_PRINTERS.md](OS_PRINTERS.md). Captured JPGs are not evidence of real paper printing or shipment fulfillment.

## Rebuilding
Changes to `src/`, `packaging/`, `pyproject.toml` or the workflow on `main` automatically trigger four OS builds. Manual `workflow_dispatch` also works. Only successful platform jobs publish artifacts.
