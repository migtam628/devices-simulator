# Devices Simulator v0.13.6 — Advanced Workflow Editor

- **Visual graph linking:** clickable and draggable output/input ports. Directed edges are checked for duplicates, self-links, illegal Start/Output directions, cycles and connection limit before being drawn.
- **Keyboard-accessible alternative:** Inspector destination selector and Connect from here, plus clickable ports for users not dragging.
- **Undo and redo:** 40 editable-graph snapshots, restoring node positions, edges and settings without overwriting saved workflow revision IDs.
- **Live wiring:** lines track nodes as they are dragged, with an in-progress connection preview.
- **Run diagnostics:** inspected historical traces color matching graph nodes by completion/failed/skipped; suppress misleading highlighting when graph revisions differ.
- **Regression tests:** Node runtime graph tests and local JavaScript HTTP asset tests; existing device, TCP, PTY and capture tests retained.
- **Docs:** README, technical roadmap, release notes and website download links updated.

**Boundaries:** Only Studio editing and trace display changed. This is not support for physical USB, BLE, Windows COM, real OS scanner installation, or certified manufacturer printer/scale protocols. Desktop bundles are unsigned early-access builds.
