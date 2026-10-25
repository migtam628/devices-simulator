# Devices Simulator — Support Matrix & Implementation Handoff
**Design specification v1.0** · Status: proposed, subject to OS testing

## Purpose
This file is the source of truth for **what the UI may claim** about an installed simulated device. The current repository v0.2 has a document capture engine, an experimental local IPP server and registration scripts. Passing automated protocol tests does **not** demonstrate native Windows, macOS or Linux registration, queue compatibility, driver support or scanner support.

## Capabilities and truthful UI

| Category or capability | Current v0.2 | Target UI label now | Implementation path |
|---|---|---|---|
| PDF/JPG/PNG → JPG files | Local capture engine present; automated tests pass | Available (CLI) | Integrate job metadata in desktop UI |
| Brother virtual office printer | Experimental IPP endpoint; OS enumeration not verified | Experimental | Driverless IPP operations + OS queue check |
| Brother two-tray selection | IPP attributes / tray routing prototype | Experimental | Verify media-source in actual OS job |
| Zebra 4×6 label printer | Experimental IPP profile for PDF/images | Experimental | OS registration + 4×6 media capability and fidelity tests |
| Zebra raw ZPL → JPG | Raw ZPL not rendered | Planned | Local ZPL renderer + pixel output checks |
| OS printer settings integration | Scripts present, not validated on all OSs | Experimental | Platform adapters + explicit privilege + post-install verification |
| System scanner registration | Not implemented | Planned | eSCL/AirScan path for supported systems; WIA work for Windows |
| Virtual barcode HID device | Not implemented | Planned | Privileged platform-specific virtual HID implementation |
| Receipt printer / ESC-POS | Not implemented | Planned | ESC/POS parser + compatible queue/backend |
| Simulated USB identity | Not implemented | Not supported | Separate signed drivers/emulation if needed |
| PrintNode discovery/testing | Not verified | Planned | PrintNode client sees OS-registered printer, complete roundtrip |
| Desktop hub UI | Not implemented | Design approved / Not built | Native shell, pages, wizard, service lifecycle |
| Device Studio visual workflows | Not implemented | Planned | Optional advanced mode |

No “Installed” checkbox should be populated based only on an API request returning HTTP 200, a config file existing, or the installer command exiting 0.

## Device system-registration semantics by platform
| Device class | Windows | macOS | Linux |
|---|---|---|---|
| Office/label printer | IPP printer queue through Windows-supported path; exact behavior verified with native printer enumeration and print test | CUPS/IPP destination; verify with system printer list and test | CUPS/IPP destination; verify with system printer list and test |
| Scanner | Native scanner integration requires OS-compatible architecture; Microsoft WIA driver path is separate from IPP printing | eSCL/AirScan investigation + scanning-app test | eSCL/AirScan/SANE compatibility investigation + scanning-app test |
| Barcode keyboard/HID | Requires native virtual HID transport; not equivalent to text mock | Platform-specific virtual HID facilities; not equivalent to text mock | Platform-specific virtual input/HID transport; not equivalent to text mock |
| Serial/COM | Virtual serial driver may require signed native component | PTY/virtual serial approach (may not appear as USB device) | PTY/virtual tty approach (may not appear as USB device) |

Printing is a protocol/service workflow. A label maker is a printer, not a scanner. Rendering a fake scan in the application is not enough to make a native system scanner appear. Avoid representing ordinary network queue registration as a USB printer driver install.

### OS verification checklist (per install)
1. User sees install permission dialog with intended device name and platform.
2. Local endpoint reports supported functionality and responds to capability query.
3. Platform-specific installer attempts registration.
4. OS printer or scanner enumeration confirms exact name/endpoint.
5. A real system print/scan client submits a sample job to the entry.
6. Captured output file is accessible and dimensions/tray/settings are verified.
7. UI stores `lastVerifiedAt`, `registrationMethod`, `osDeviceId`, `testJobId` and actionable error if any step fails.

The UI can display **OS Registered** only after step 4 and **Test Passed** only after steps 5–6.

## Suggested device and job objects (schema sketch, not implementation)
```json
{
  "device": {
    "id": "uuid",
    "name": "Lulwa SIM Brother",
    "category": "office_printer",
    "profileId": "brother_dual_tray",
    "capabilities": {
      "media": ["na_letter_8.5x11in"],
      "trays": ["tray-1", "tray-2"],
      "dpi": [300],
      "formats": ["application/pdf", "image/png", "image/jpeg"]
    },
    "simulation": {"enabled": true, "health": "running", "faultPreset": null},
    "osRegistration": {
      "platform": "macos",
      "method": "ipp",
      "status": "unverified",
      "osDeviceId": null,
      "lastVerifiedAt": null
    },
    "lastTest": {"outcome": "not_run", "jobId": null, "at": null},
    "output": {"directory": "user-selected folder", "preferredFormat": "jpg"},
    "createdAt": "ISO-8601",
    "updatedAt": "ISO-8601"
  },
  "job": {
    "id": "uuid",
    "deviceId": "uuid",
    "origin": "os_print_dialog",
    "status": "captured",
    "requestedSettings": {"mediaSource": "tray-1", "dpi": 300},
    "actualSettings": {"mediaSource": "tray-1", "dpi": 300},
    "artifacts": ["page-001.jpg"],
    "error": null,
    "createdAt": "ISO-8601"
  }
}
```

**Caution:** `origin`, `status` and exact job fields should be derived from trusted capture/OS events, not arbitrary client-supplied claims.

## Required modular architecture (design boundary)
- Desktop UI layer: shell, shared components, pages and wizard; no elevated commands directly.
- Local daemon/service: device runtimes, queues, job ingestion, rendering, filesystem outputs.
- OS adapters: Windows printer manager, macOS CUPS adapter, Linux CUPS adapter, future scanners and input transports.
- Permission broker: explicit prompted elevation and auditable privileged operations.
- Capability registry: per category × platform × backend × status; drives labels, disabled controls and Help.
- Job/event store: jobs, immutable stage history, artifacts, retries, audit log; secure default retention.
- Studio extension: graph planning/preview over real registered devices, not a separate installation implementation.

## Design-led implementation phases
**Phase A — UI foundation and design verification:** Shared shell, tokens, components, Home, Devices, wizard skeleton, layout previews. No false OS-ready badges.  
**Phase B — Printer vertical slice:** Service lifecycle, Brother profile+tray management, Zebra 4×6, OS install/verify on chosen test system, JPG output, Jobs/Outputs and Diagnostics.  
**Phase C — Cross-platform validation:** Windows/macOS/Linux packaging, permissions, service startup, uninstall, OS printer lists, PrintNode interoperability.  
**Phase D — Expanded devices:** Scanners and HID/serial only after platform support genuinely works.  
**Phase E — Studio:** Graph workspace, node library, inspectable job pipelines, optional enablement.

## Design-implementation acceptance contract
- Cross-platform UI appearance consistent; native permission dialogs honored.
- Add Device wizard is discoverable from Home and Device Library.
- At least Brother and Zebra visually and functionally differentiated.
- Device profile, endpoint state, OS registration and successful test are four separate data concepts.
- No unsupported scanner/HID type is advertised as installed.
- All jobs have verifiable input, result and artifact; images saved in user-selected directory.
- Retention, security, error handling and diagnostic redaction are testable.
- No ecommerce shipping/fulfillment status is modified as a side effect of simulation.
- Studio is disabled by default and never blocks ordinary tasks.

## Standards and documentation used as design references
- OpenPrinting CUPS administration: https://openprinting.github.io/cups/doc/admin.html
- OpenPrinting printer applications and driverless printing: https://openprinting.github.io/cups/drivers.html
- Printer Working Group IPP Everywhere: https://www.pwg.org/ipp/everywhere.html
- Microsoft Add-Printer: https://learn.microsoft.com/powershell/module/printmanagement/add-printer
- Microsoft WIA driver architecture: https://learn.microsoft.com/en-us/windows-hardware/drivers/image/developing-a-wia-scanner-driver

These references describe possible integration architectures. They do not certify this project's current experimental backend or promise compatibility with specific OS releases.
