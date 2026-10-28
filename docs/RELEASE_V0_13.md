# Devices Simulator v0.13.0 — Advanced Studio managed TCP

- New **External TCP Scale** graph node and template, with device-profile selection.
- Studio reads through real localhost TCP socket via the Connection Engine, not through direct fixture access.
- Strict device ID binding prevents arbitrary host/port networking; listener must be activated explicitly.
- Stable SICS-style SI replies propagate measured weight to downstream nodes.
- Busy, unstable, overloaded, missing listener or disconnect results fail clearly and skip dependent steps.
- New integration tests exercise live socket, run history, HTTP API and failure modes.
- README, Studio guide, Connection Engine guide, site downloads updated.

Does not implement USB, BLE, Windows COM, real barcode HID or CUPS repair.