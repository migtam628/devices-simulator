# Universal Connection Engine — milestone 1

## Goal and implementation status

Connect **external local applications** to Devices Simulator through a genuine TCP socket, not merely an in-app fixture. Version 1 of the engine implements a controlled, portable and bounded TCP *scale* adapter. It is not hardware enumeration and does not claim full vendor compatibility.

Implementation:
- \`src/lulwa_virtual_printer/connection_engine.py\`: lifecycle manager and localhost-only TCP scale adapter
- \`src/lulwa_virtual_printer/hub.py\`: local authenticated start/stop/fault APIs
- \`tests/test_connection_engine.py\`: real TCP socket integration tests and negative cases
- `src/lulwa_virtual_printer/ui/connections.js`: live Connections screen, listener controls, fault injection and socket self-test
- Process shutdown stops all owned adapters; adapters do **not** auto-start when the app reopens

## Action plan / milestones

| Phase | Deliverable | Status |
|---|---|---|
| 1 | Local TCP transport, streaming socket commands and explicit lifecycle | Implemented in source |
| 2 | Link existing weight fixtures, simulated errors, telemetry and API control | Implemented in source |
| 3 | Device Hub Connections page, real TCP client self-test, API integration | Implemented |
| 4 | Model-specific MT-SICS coverage, protocol contracts, scripts and replay | Planned |
| 5 | Cross-platform serial / PTY / Windows COM adapters | Planned |
| 6 | BLE GATT peripherals and USB HID drivers per OS | Platform-specific, not implemented |
| 7 | Studio connection nodes, security hardening, managed deployment | Planned |

## Supported model and protocol scope

Only shipping scale **profiles saved with Network transport** can host a TCP endpoint. E.g., create **Generic → Shipping Scale Fixture**, then select **Network TCP/IP**. A METTLER TOLEDO BC *reference* profile can be configured as Network as well, but **this endpoint is a deliberately limited generic MT-SICS-style subset**. It is **not** a drop-in BC emulator.

Implemented line-based ASCII requests (send CRLF, LF also accepted):
- \`SI\`: send immediate weight. Stable: \`S S 1.250 kg\\r\\n\`; unstable: \`S D 1.250 kg\\r\\n\`.
- \`S\`: send stable weight. Unstable readings yield \`S I\\r\\n\` (not ready).
- Overcapacity: \`S +\\r\\n\` for both.
- Unsupported commands: \`ES\\r\\n\` (subset error).
- No current reading: zero weight.
- Busy injection: \`S I\\r\\n\`; disconnect injection: TCP connection closes.

The line framing and response convention follow the publicly documented MT-SICS stable/immediate weight commands. This subset does **not** implement the full MT-SICS level 0/1/2 commands, asynchronous streaming, hardware zero/tare commands, serial baud settings or manufacturer-specific status registers.

Reference: [METTLER TOLEDO IND221/IND226 SICS command list](https://www.mt.com/dam/mt_ext_files/Editorial/Generic/8/IND221_IND226_User_Manual_Editorial-Generic_1177682892834_files/ind221_ind226_usermanual72182839e.pdf) and [MT-SICS Reference Manual](https://www.mt.com/mt_ext_files/Editorial/Generic/1/PL-S_SICS_0x0002467000027246000b531d_files/b-s-al-pl-sics-e-11780447.pdf).

## Local Hub API

All POST operations require \`X-Devices-Token\`, already held in the local app. These cannot be called unauthenticated from a normal webpage:

| Route | Request fields | Behavior |
|---|---|---|
| GET /api/connections | none | Current listeners and per-listener diagnostic history |
| POST /api/connections/start | device_id, port=0, confirm=true | Bind an explicit loopback TCP listener, return chosen port |
| POST /api/connections/fault | device_id, fault=none/busy/disconnect, confirm=true | Simulate protocol errors and lost connections |
| POST /api/connections/stop | device_id, confirm=true | Stop a previously started listener |
| POST /api/connections/probe | device_id, confirm=true | Real TCP roundtrip from separate socket; not third-party compatibility proof |
| POST /api/devices/{id}/scale-reading | gross_kg, tare_kg, unit, stable | Update the saved local weight fixture read by TCP |
| GET /api/state | none | Includes \`connections\` snapshot for Hub UI |

The Connections page supports port assignment, live weight changes and recent command events. The connection payload never accepts a custom host/IP address. Ports must be 0 (OS chooses ephemeral) or 1024–65535. Maximum four scale listeners, eight simultaneous clients per listener; each command is bounded and idle connections time out.

### Verifying without any real scale

After creating a Network-connected scale profile and starting it through the app, use its displayed TCP port (for example 12500). In a separate terminal:

\`\`\`bash
python3 - <<'PY'
import socket
with socket.create_connection(("127.0.0.1", 12500), timeout=3) as conn:
    conn.settimeout(3)
    conn.sendall(b"SI\r\n")
    print(repr(conn.recv(128)))
PY
\`\`\`

The expected reply for an unset scale is \`b'S S 0.000 kg\\r\\n'\`. Change the scale weight in the Hub and rerun to see an updated value. Then select Busy or Disconnect to verify your client application’s error handling.

**Security:** The service listens on loopback only, but any program running on the same machine can access its TCP test endpoint. Never store credentials or use real customer data in scale command payloads. The TCP port does not expose the Hub's privileged management routes; management operations still require the Hub's session token. No LAN exposure, remote device discovery or auto-starting transports are implemented.

## Next

An opt-in serial adapter can reuse the same command handler and diagnostics; Windows virtual COM requires a driver, while Linux/macOS PTY adapters can be implemented without pretending to be USB HID. BLE advertising and virtual USB hardware are separate OS-specific milestones.
