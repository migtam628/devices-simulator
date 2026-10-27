# Devices Simulator v0.12.0 — Read-only scale protocol discovery

Both TCP and POSIX serial scale adapters now implement inquiry responses in addition to weight queries.

- `I0` advertises exactly the implemented read-only commands.
- `I2` returns explicit simulator model / reference capacity; no vendor impersonation.
- `I3` returns a simulator-specific version string.
- `I4` returns an artificial SIM-tagged device identifier.
- Busy/disconnect states and unsupported commands retain explicit diagnostic behavior.
- New real TCP and PTY protocol tests; release README and Connection Engine guide updated.

Not yet supported: complete MT-SICS Level 0, SIR streaming, zero/tare commands, Windows virtual COM, USB/HID, BLE, certified hardware or commercial-app compatibility.