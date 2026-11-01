# Devices Simulator v0.16.2 — Verified macOS application printer lifecycle

- Strengthens the macOS-15 CUPS acceptance test to invoke application-owned `native_printers.install_printer` and `uninstall_printer`, not duplicate CLI implementation.
- Verifies the exact simulator URI after installation and a unique OS print job that creates a real JPG.
- Tests automatic fallback from unavailable IPP Everywhere PPD generation to a bundled PDF pass-through PPD and records the method.
- Refuses to report success if the printer identity cannot be verified or if queue cleanup fails.
- Does not change existing real-printer queues and applies elevated permissions only in the isolated macOS CI runner.
- Updates README, landing page, and OS diagnostics documentation.

The v0.16.1 1-bit PWG rendering remains included. This is not a general driverless IPP Everywhere or real hardware certification, and Windows/PrintNode native integration remains unverified.
