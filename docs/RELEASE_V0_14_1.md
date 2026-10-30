# Devices Simulator v0.14.1 — Experimental Windows OS spooler verification

**What's new**
- Read-only Windows Print Spooler and per-queue online/paused/offline readiness checks via constrained PowerShell queries.
- Optional GDI `PrintDocument` test for exactly verified simulator Brother/Zebra queues, with a single marked page and explicit user confirmation.
- Reuses actual IPP capture tracking to require a tagged, nonempty JPG on disk; a job merely accepted by the Windows spooler is **not** success.
- Windows queue identity probe now queries `Get-PrinterPort` metadata when available but never trusts name-only or localhost-host-only matches.
- System Integration enables OS print verification on Windows only after all readiness checks pass.
- Added mocks for spooler state, safe job generation, one-job provenance, port identity and negative JPG results, plus a Windows-only PowerShell script parser regression.
- Documentation and GitHub Pages version links updated. Linux CUPS end-to-end tests retained.

**Limits**
- These changes do not establish that the Microsoft IPP class driver sends a currently supported format to the experimental renderer.
- Physical Windows printing, PrintNode integration, Windows COM/USB/BLE drivers and signed installers are **not certified**. Actual Windows IPP print-to-JPG success is pending device-side proof.
