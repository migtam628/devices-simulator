# Devices Simulator v0.14.0 — OS Print-to-JPG reliability

- Added an actual Linux **CUPS lpadmin + lp** end-to-end CI job for Brother and Zebra queues, including real JPG disk verification after OS spooler submission.
- Added read-only authenticated `/api/system/print-readiness` to identify queue registration failure, missing IPP service, IPP/Hub output-directory mismatch, and disabled/failed CUPS queues before printing.
- Added **Check print path** and contextual failure instructions in System Integration, with an explicit ready state before Verify OS Print → JPG.
- IPP diagnostics now reveal the resolved output directory so a stale or separate IPP process cannot silently masquerade as the Hub's capture folder.
- Added readiness tests for mismatched output roots, offline/disabled queues, unsupported OS, token authorization and side-effect-free blocked requests.
- README, release notes, website links and troubleshooting guide updated.

**Verified:** Ubuntu Linux CUPS-to-IPP-to-JPG path for both profiles. **Not verified:** actual macOS or Windows end-user printing, physical drivers, PrintNode or USB/BLE integration. These are early-access unsigned binaries.
