# Devices Simulator v0.13.9 — Confirmed live step debugger

- Single shared execution generator for full workflow runs and one-node manual step sessions; consistent branch, failure and capture semantics.
- Token-authenticated `/api/studio/debug/start`, `/status`, `/step`, `/cancel` APIs.
- One volatile Hub session; exact saved workflow revision, random session ID, monotonic 15-minute inactivity timeout.
- Explicit expected-step index prevents duplicate execution and repeat JPG output on request retry.
- Per-node user confirmation for capture/JPG jobs, simulated scale, managed localhost TCP and POSIX serial scale reads.
- Step status, trace, last JPG link, branch choices, recover and cancel controls in Advanced Studio.
- Completed and explicitly cancelled sessions produce bounded run-history records; expiry never silently resumes steps.
- Automated tests cover real JPG captures, invalid IDs/revisions, duplicate calls, expiration, branch parity, HTTP authorization and actual browser confirmation behavior.
- README, architecture guide and GitHub Pages downloads updated.

**Limitations:** This does not add a scheduling daemon, mid-node interrupt, rollback of already-created JPGs, native Windows COM, USB/BLE emulation, certified OS print queue compatibility, or signed installers. Desktop archives remain early access.
