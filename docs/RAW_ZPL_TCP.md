# Local RAW TCP ZPL label capture — v0.15.2

This experimental feature accepts **ZPL on the local computer only** and
renders a JPG in the existing Zebra Gallery. Unlike the IPP service, this
uses a simple raw TCP stream; unlike a real Zebra printer, it does not
operate physical hardware, announce a USB printer, or answer a printer
status protocol.

## Enable and test

1. Start Devices Simulator.
2. Open **System Integration → Local RAW ZPL TCP port**.
3. Choose **Start local ZPL TCP** and confirm. The Hub binds a socket to
   `127.0.0.1:9100`. The listener does not auto-start on restart.
4. In another local process, connect to that address and send **test ZPL**.
5. Inspect **Gallery / Jobs** for `original.zpl`, `job.json`, and
   `page-001.jpg` under the `zebra` output folder.
6. Stop the listener in the interface when finished.

Example Python **on the same computer** (never use a real shipping order):

```python
import socket
sample = (b"^XA^PW406^LL609"
          b"^FO20,30^A0N,32,32^FDLOCAL TEST LABEL^FS"
          b"^FO20,120^BQN,2,5^FDLA,QA-0001^FS^XZ")
with socket.create_connection(("127.0.0.1", 9100), timeout=3) as stream:
    stream.sendall(sample)
```

This intentionally uses the ordinary raw-port behavior: there is **no
acknowledgement** over TCP, so inspect JPG and job.json for actual
completion. The listener can accept at most 10 complete labels per
connection and up to 1 MiB of input per label. Malformed and incomplete
labels are rejected without claiming a print occurred. Timeouts bound
stalled connections; accepted/rejected counts and a content-free last
error appear in System Integration.

## Security and operating constraints

- The Hub token and explicit confirmation protect **activation and stop**.
- The raw socket has **no protocol authentication**, like traditional
  Port 9100 printing. Therefore, it binds exclusively to 127.0.0.1 and
  is off by default. Do **not** port-forward, reverse-proxy, or expose
  it to untrusted network peers.
- Captured content stays on disk and can contain PII. Use test data only
  and review capture retention in Settings.
- Raw TCP labels go **directly to the simulator's JPG renderer**, not to
  physical Brother/Zebra printers and not to a shipment service.
- PrintNode Client may use operating-system queues; it has NOT been
  verified against this raw listener. This is not a PrintNode API or
  native printer discovery endpoint.
- Unsupported ZPL commands fail rather than render an incorrect label.
- Closing the Hub closes the listener even after abnormal client jobs.

The regression suite sends real TCP streams, including two labels on one
connection, missing delimiters, oversize payloads, malformed commands,
port conflicts, login-token authorization of start/stop, and shutdown
teardown.

References:
- [PrintNode's raw printing concept](https://www.printnode.com/en/docs/what-is-raw-printing)
- [Zebra's ZPL programming guide](https://www.zebra.com/us/en/support-downloads/printer-software/zpl.html)
