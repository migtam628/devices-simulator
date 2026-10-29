# Devices Simulator v0.13.8 — Read-only Advanced Studio debugger

**Added**
- Authenticated `POST /api/studio/workflows/inspect` for deterministic, validated *unsaved* execution plans without side effects.
- Per-node order, incoming/outgoing edges, condition routing metadata, local-write/capture risk flags and active-adapter warnings.
- UI **Inspect plan**, step-by-step walkthrough, direct step selection, canvas highlight, and optional review checkpoints.
- Stale-plan detection: a draft edit invalidates the last inspection; no misleading highlights.
- Regression tests for no jobs, no device reads/state writes, invalid inputs, authorization, and actual browser-JavaScript stepper behavior.
- Updated README, Advanced Studio documentation, version links and release notes.

**Safety and limitations**
- Inspection **does not run** workflows, start hardware adapters, produce JPGs, or write run records.
- Checkpoints are inspection markers only; there is **no live execution pause/resume** in this release.
- Actual Run locally and Replay operations have their separate explicit confirmations.
- Not a native virtual COM/USB/BLE driver or certified OS printing integration. Desktop bundles remain unsigned early-access builds.
