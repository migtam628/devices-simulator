# v0.10.0 — Universal Connection Engine

Devices Simulator now hosts an opt-in localhost TCP scale that a separate local program can connect to. This is a test fixture, not installed physical hardware.

- New Connections screen: start/stop listener, choose port, update weight, inject faults, inspect command logs.
- Real 127.0.0.1 TCP socket for MT-SICS-style read-only S and SI requests.
- Stable/unstable, tare-adjusted values, overload, busy and disconnect fault states.
- Real TCP roundtrip self-test; does not prove compatibility with an external shipping app.
- Limits: maximum 4 active endpoints, 8 concurrent clients per listener, bounded commands and idle timeout.
- Authenticated Hub API; no automatic listeners on startup, explicit activation and shutdown cleanup.
- New integration tests, README, protocol guide and updated release links.

Not included: native USB/COM/BLE devices, full manufacturer protocol support, LAN exposure or remote management.

See [Connection Engine setup guide](CONNECTION_ENGINE.md).