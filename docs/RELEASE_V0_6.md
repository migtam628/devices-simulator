# Devices Simulator — v0.6.0 Experimental Release

## Download from GitHub Releases
**Releases:** https://github.com/migtam628/devices-simulator/releases

The GitHub Actions desktop workflow now packages **four portable desktop builds**, verifies their SHA-256 checksums, and publishes a prerelease for the version in `pyproject.toml` only after all four builds pass.

- Windows x64: `DevicesSimulator-Windows-x64.zip`
- macOS Apple Silicon: `DevicesSimulator-macOS-arm64.zip`
- macOS Intel: `DevicesSimulator-macOS-x64.zip`
- Linux x64: `DevicesSimulator-Linux-x64.tar.gz`

GitHub Releases is intended to retain downloads beyond the short Actions artifact window. Each release is versioned. **Never replace an existing tag with a build from a different commit**: bump the project version before shipping future binaries.

## Features implemented in this milestone
- **Brother and Zebra OS print queues**: existing experimental IPP registration with OS queue enumeration. Neither represents a real physical printer.
- **CUPS end-to-end verification**: on macOS/Linux only, the hub can submit a sample through an exact verified local simulator queue and confirm a JPG in the local output folder. A registered queue alone isn't a passed print test.
- **JPG capture**: PDF/JPEG/PNG documents; multi-page files generate separate JPG files. In-app fixtures include Letter, 4×6 labels, and a **flatbed scan preview** (not a native scanner).
- **Limited ZPL II preview**: subset of text, boxes, Code128, paper dimensions and positions. Unsupported commands are recorded as rendering errors rather than silently producing invalid labels. Not full Zebra emulation.
- **Simulated printer faults**: configure offline, paper-out, jam, paused, or normal states from Device Details. Fault tests create failed job records and do not alter an actual OS printer.
- **Studio demo**: select saved Brother and Zebra profiles and run sample packing-slip / label captures to JPG; node drag/drop editing remains planned.
- **Barcode keyboard simulation (macOS)**: replaced the failing legacy IOHIDUserDevice approach with Quartz keyboard-event input; requires macOS Accessibility approval. This does **not** register a real HID/USB device, and a true installed scanner is still planned.

## Using macOS barcode input simulation
1. Run the fresh macOS app from Releases.
2. Open System Integration → Barcode Input Simulator.
3. Click **Enable Keyboard Mode**. macOS may prompt for Accessibility access. If refused, open **System Settings → Privacy & Security → Accessibility**, enable the app/helper if available, then relaunch.
4. Enter a simple barcode in the app and click **Send barcode in 3 seconds**.
5. Focus an empty TextEdit document before the countdown completes.
6. Check the actual typed output. The UI only confirms that keyboard-event dispatch was attempted, not that the focused application processed the input.

**Privacy:** Don't focus a terminal or password field when sending keyboard input. Barcode values are restricted to simple ASCII.

## Known gaps (not in this release)
- Full eSCL/AirScan scanner discovery and Windows WIA driver registration
- True OS virtual HID barcode hardware / signed device driver
- Windows OS print roundtrip verification via Windows spooler
- Full Zebra ZPL and ESC/POS command compatibility
- Studio drag/drop, reusable graph persistence, branching and advanced simulation
- Package signing/notarization, MSI/PKG/DEB installation, autostart daemon, updates
- Verified PrintNode end-to-end interoperability
- Long-term retention controls and production security review

**Never use simulated output as proof of shipment fulfillment or actual physical printing.**
