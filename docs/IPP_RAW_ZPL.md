# Zebra raw ZPL → local IPP → JPG (v0.15.1)

This milestone lets a **direct IPP client** submit a ZPL label to the simulator
and receive a real local JPG preview. The service listens only on
`127.0.0.1:8631`, not on public interfaces.

## Supported local endpoints

| Endpoint | Supported document formats |
|---|---|
| `ipp://127.0.0.1:8631/ipp/zebra` | PDF, PNG, JPEG; **raw ZPL** |
| `ipp://127.0.0.1:8631/ipp/brother` | PDF, PNG, JPEG; **no raw ZPL** |
| `ipp://127.0.0.1:8631/ipp/brother-tray1` | PDF, PNG, JPEG |
| `ipp://127.0.0.1:8631/ipp/brother-tray2` | PDF, PNG, JPEG |

Specify `document-format: application/vnd.zebra-zpl` for raw ZPL to Zebra.
The Zebra queue also accepts the `application/octet-stream` auto-detect
format and `application/vnd.cups-raw` for compatibility, but `cups-raw`
is **not advertised** as a generally supported format. A matching MIME and
real `^XA … ^XZ` ZPL body are both required. The renderer supports only
its documented subset; unsupported ZPL commands fail without an output JPG.

The IPP request can be `Print-Job` (one-step) or `Create-Job` followed by
`Send-Document`. The server reports job completion only when its capture
engine has produced a JPG. The local Gallery receives an `original.zpl`
and `page-001.jpg` under the `zebra` output profile, plus job.json.

## Test and inspect

1. Start the desktop application with the attached loopback IPP service.
2. Submit a test ZPL through an IPP client that supports vendor document
   formats. Use **only the simulator Zebra endpoint**, not a physical printer.
3. Inspect `http://127.0.0.1:8631/diagnostics` for the IPP job's
   `document_format`, `ipp_status`, and `capture_status`.
4. Verify `zebra/<job-folder>/original.zpl`, `page-001.jpg`, and job.json.
5. Never report success merely because a Windows/macOS queue accepted a job.

Tests `tests/test_ipp_raw_zpl.py` send actual HTTP IPP request bodies via
loopback sockets, including two-step printing, MIME mismatch, invalid ZPL,
PDF regressions and preserved source bytes.

## PrintNode distinction

PrintNode describes raw printing as commands sent in a printer-native
language (e.g. ZPL). The **PrintNode Client** may use OS-specific driver
or spooler facilities rather than a direct IPP request with the ZPL MIME
type. This milestone validates **the simulator's IPP endpoint only**.
It does not establish that the PrintNode Client discovers the queue or
preserves raw ZPL bytes through a particular Windows/macOS printer driver.

**Out of scope:** real printer shipping output, supported EPL, certified ZPL
barcode scannability, IPP Everywhere, PWG Raster/Apple URF and native driver
installation.

References: [PrintNode raw printing](https://www.printnode.com/en/docs/what-is-raw-printing),
[Printer Working Group IPP guide](https://www.pwg.org/ipp/ippguide.html).
