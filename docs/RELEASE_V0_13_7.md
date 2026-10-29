# Devices Simulator v0.13.7 — Advanced Studio conditional routing

- **Condition** nodes compare stable upstream scale weight or barcode fixture strings with validated operators and values.
- Explicit TRUE and FALSE connection ports and two ready-to-edit workflow templates.
- Only the selected branch executes. Unselected nodes are marked `inactive` (not errors); joining branches can continue on a valid active path.
- Condition decision and selected branch recorded in run history, with separate inactive-node diagnostics.
- Export/import and confirmed replay preserve condition edges, configuration and revision snapshot history.
- Regression coverage includes positive/negative routes, inactive printer capture, branch joins, invalid input, HTTP API and actual frontend JavaScript runtime.
- README, Studio architecture notes and website release links updated.

**Boundaries:** No generic scripts or webhooks, device auto-activation, hardware-level emulation, Windows virtual COM, USB/BLE drivers, or physical print-stack certification. Desktop binaries are unsigned experimental builds.
