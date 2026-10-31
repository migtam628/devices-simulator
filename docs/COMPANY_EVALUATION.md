# Devices Simulator — Company Evaluation Guide

**Product status:** Early access / experimental
**Delivery:** Portable desktop builds for Windows x64, macOS Apple Silicon/Intel, and Linux x64
**Suggested use:** Local engineering, QA, staging demos, internal proof-of-concept environments

## Who benefits
| Team | Useful pilot | Verification |
|---|---|---|
| QA / automation | Test document generation and printer-error responses | Compare JPGs and inspect job records |
| Fulfillment product | Test 4 × 6 shipping label layout and packing-slip output | Review generated label geometry and PDF source |
| POS / retail engineering | Exercise office printer queues and simulated faults | Capture job logs and confirm host OS routes |
| Sales engineering | Demonstrate software/device workflow before physical deployment | Run a sample in-app workflow, not a real shipment |
| Field and support teams | Reproduce issues with local test profiles | Save redacted diagnostic evidence |

## Capability boundaries

**Implemented locally:** Device profiles; JPG capture from PDF/PNG/JPG and a limited ZPL subset; output gallery; fault simulation; two-device Shipping Station demo; flatbed scanner *fixture*.

**Experimental:** Native local IPP print-queue registration; macOS/Linux CUPS-to-JPG verification; macOS Quartz barcode keyboard simulation (Accessibility permission). These features need validation on each supported host and with each upstream application.

**Not implemented:** Native eSCL/AirScan scanner installation, Windows WIA scanner drivers, true virtual HID/USB devices, complete ZPL/ESC-POS emulation, certified PrintNode integration, code signing, enterprise update/retention management, SSO, central management, warranties or published SLAs.

No simulation result is proof of physical printing or fulfillment. Manufacturer-style profile names do not imply manufacturer support or endorsement.

## Pilot acceptance plan

1. **Use test data only.** Do not print real customer labels into an unreviewed output folder.
2. **Choose supported platform.** Confirm the application opens and the local service starts without a remote dependency.
3. **Test in-app capture.** Import a known PDF and verify the output JPG(s), source file and job metadata.
4. **Test the label profile.** Confirm 4 × 6 document boundaries and verify any ZPL command you depend on is supported.
5. **Simulate failures.** Exercise offline, paper-out, jam, and paused conditions in the application.
6. **Only if necessary, test the OS queue.** Verify the installed printer matches the simulator's loopback IPP URI, then submit a test through the host spooler. Capture a JPG; do not equate successful spooling with successful delivery.
7. **Record incompatibilities.** Include OS/version, device profile, document format and redacted diagnostics in a GitHub issue.

## Security and operational cautions

- Printed content and generated JPGs stay in local files by default. Sensitive customer information may be present in both source files and metadata.
- The simulator IPP server is intended for **loopback use**, not internet-exposed deployment.
- Test output directories need appropriate filesystem permissions; optional preview-first capture retention controls are available in Settings. Review deletions carefully.
- Never use scanned or simulated output to auto-mark real ecommerce orders shipped, printed, paid, or fulfilled.
- A true hardware lab and security review are still required before a production rollout.
- Development builds are unsigned; your endpoint-security policies may block them.

## Commercial licensing and support

**No license has been selected/published in the repository.** Public GitHub availability is not commercial-use permission. Before distributing to a customer or deploying across a company, request licensing clarification from the maintainer. There is no current commitment to paid support, warranty, hosted service, uptime SLAs or enterprise compliance certifications.

For requirements, pilot feedback or a commercial discussion, [open an issue](https://github.com/migtam628/devices-simulator/issues). Avoid including customer documents, serial numbers, internal URLs or secrets in public issues.

## Product materials

- [Product landing page source](index.html)
- [README and quick start](../README.md)
- [Current releases](https://github.com/migtam628/devices-simulator/releases)
- [Issue tracker and feature requests](https://github.com/migtam628/devices-simulator/issues)
- [OS printer guide](OS_PRINTERS.md)
- [Website deployment](WEBSITE_DEPLOY.md)
