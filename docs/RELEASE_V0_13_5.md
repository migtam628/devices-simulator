# Devices Simulator v0.13.5 — Portable Advanced Studio workflows

**New:**
- Authenticated workflow JSON export with a strict format/version and portable DAG only.
- JSON import up to 64 KB with explicit local device remapping, complete graph validation and creation as a new saved workflow.
- Run-history snapshot replay: the graph attempted by a prior run is stored; replays require confirmation and perform a fresh, independently traced run.
- Studio import/export controls, mapping screen and replay buttons.
- README, technical docs, landing-page downloads, and HTTP/validation/graph snapshot/JPG regression tests.

**Boundaries:** Existing run records without graph snapshots cannot replay. Replays can generate additional JPG artifacts, use current local fixture readings, and contact only previously activated managed localhost scale endpoints. Not a deterministic restoration of past output, native driver, USB/BLE device, Windows COM emulator or third-party hardware certification.

Portable desktop builds are early access, unsigned and subject to operating-system checks.
