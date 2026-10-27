# v0.11.0 — POSIX serial scale adapter

Adds opt-in, real POSIX pseudo-terminal paths for external scale-client testing on macOS/Linux.

- Create/close a virtual serial endpoint for a saved scale model with RS-232 / COM transport.
- Use ASCII S/SI read-only commands with current in-app weight, tare and units.
- Test unstable/over-capacity and busy/silent-response states.
- New serial controls, path display and diagnostic logs in the Connections page.
- The Hub closes created PTYs on shutdown; adapters never auto-start.
- Real PTY integration tests on supported CI operating systems.

Windows COM emulation, physical USB device identity, BLE GATT and complete MT-SICS implementation remain separate milestones.

See [Connection Engine technical guide](CONNECTION_ENGINE.md).