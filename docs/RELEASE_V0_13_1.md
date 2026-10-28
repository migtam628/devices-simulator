# v0.13.1 — Continuous TCP scale sample stream

- New `SUB` command to opt into 2 Hz scale reports on a managed loopback TCP socket.
- Simulator-specific `SUB OK 500` acknowledgement and repeated `EVT ...` lines.
- Dynamic scale changes, busy/overload/unstable faults reflected in successive output frames.
- Disconnect and listener stop end streaming and release client sessions.
- Real multi-frame TCP socket and teardown regression tests.
- Documentation, README and release downloads updated.

Not MT-SICS `SIR`; not a serial push adapter, hardware USB/BLE/COM device, commercial software compatibility guarantee or deferred CUPS repair.