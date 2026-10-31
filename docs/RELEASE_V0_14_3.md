# Devices Simulator v0.14.3 — Private capture retention controls

- Adds read-only retention preview with eligible job count, byte size, batch cap, and stable manifest fingerprint.
- Adds explicitly confirmed manual cleanup under Settings and authenticated Hub endpoints.
- Restricts deletion to known capture profiles and aged job metadata under the configured local output root.
- Refuses symlinked trees, changed manifests, malformed data, unknown paths, missing approval or stale preview fingerprints.
- No background retention daemon, no automatic deletion, and no changes to OS queues or physical devices.
- Adds regression tests for unauthorized and unconfirmed calls, file drift, symlinks, and preservation of recent jobs.
- Updates README, GitHub Pages, company pilot guide and docs.

Limitations: This is local file deletion, not secure erase or compliance certification. Previously recorded Studio history can retain links to deleted JPGs. Still open: verified Windows/macOS native printer integration, PrintNode, HID/USB/BLE, licensed commercial terms and signed installers.
