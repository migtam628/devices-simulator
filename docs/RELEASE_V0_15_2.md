# Devices Simulator v0.15.2 — Local raw ZPL TCP label capture

- Adds a manually enabled and locally bound 127.0.0.1:9100 TCP listener for direct RAW ZPL capture.
- Supports up to ten complete ^XA...^XZ labels per connection, each producing persistent original.zpl and a JPG; no real hardware or shipping state changes.
- Restricts incoming input size, timeouts and unrecognized ZPL commands; reports sanitized accepted/rejected counts.
- Adds authenticated Hub start/stop control with explicit confirmation, System Integration status and startup/shutdown lifecycle cleanup.
- Adds real TCP socket tests, malformed stream tests, bounded input tests and API authorization tests.
- README, raw TCP setup docs and GitHub Pages version links updated.

This is not PrintNode certification, Windows/macOS OS printer enumeration, full Zebra ZPL or production network printing. RAW TCP has no per-connection authentication and is intentionally loopback-only and off by default.
