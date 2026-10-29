# Advanced Studio — architecture and phased delivery

**Status:** v0.13.7 conditional weight/barcode routing with explicit TRUE/FALSE branch decisions.

## Repository review

The previous Studio was a hardcoded four-node illustration with a two-printer demo. The existing Hub has saved profiles, local PDF/JPG capture, test fixtures and fault injection. This implementation extends those instead of rewriting printer services.

## Action plan and implementation status

| Stage | Deliverable | Status |
|---|---|---|
| A | Persistent graph schema, cycle/device validation, safe execution order | Implemented |
| B | Editable canvas, draggable nodes, connections and device bindings | Implemented |
| C | In-app run engine, error propagation, execution logs, JPG links | Implemented |
| D | Port-to-port drag linking, richer node templates, workflow export/import, run replay | Port linking, JSON and replay implemented; richer templates planned |
| E | Managed TCP and POSIX serial reads, conditions/timers and external hooks | TCP/serial and conditional graph routing implemented; timers/hooks planned |
| F | Certified virtual USB/BLE hardware integration and enterprise policies | Requires native development |

## Supported nodes

- Start: deterministic local sample trigger
- Barcode: produces a test string in context; no keyboard or HID output
- Scale: generates a tare-adjusted reading using a saved in-app scale fixture; unstable or overloaded results fail
- TCP Scale: reads a saved, manually activated localhost TCP adapter
- Serial Scale (macOS/Linux): reads a saved, manually activated POSIX PTY adapter; not a native COM/USB device
- Capture: invokes the local printer/scan JPG engine on a saved device; does not use CUPS
- Output: aggregates completed capture jobs for run inspection

Directed edges carry context. Branches are supported. Cycles, unreachable nodes, missing saved device profiles and duplicate edges are rejected. A failure blocks dependent steps; independent branches can complete.

## Using Studio

1. Open Advanced Studio, choose Shipping Station template or Blank workflow.
2. Drag nodes by their headers. Add nodes with the toolbar and configure the selected one in the inspector.
3. Choose Connect from here on a source, then click another node to connect it. Remove connections in the inspector.
4. Save the graph to disk. Edits are revision checked to prevent overwriting another tab's changes.
5. Run locally to generate actual in-app JPG captures. Confirm first.
6. Review step status, errors and JPG links in Run History.

The state file is studio_workflows.json under the Hub state directory (default ~/.devices-simulator/). At most 80 run records are retained. Deleting a workflow does not remove captured JPG files.

## Local API

| Route | Description |
|---|---|
| GET /api/studio/workflows | Returns workflows and recent runs |
| POST /api/studio/workflows/save | Validates and creates/updates a workflow (requires revision for updates) |
| POST /api/studio/workflows/execute | Runs a saved workflow using id |
| POST /api/studio/workflows/delete | Deletes a saved workflow using id |
| POST /api/studio/workflows/export | Authenticated workflow ID to portable JSON document |
| POST /api/studio/workflows/import | Authenticated JSON document and optional device_map; saves NEW workflow |
| POST /api/studio/workflows/replay | Authenticated id + run_id + confirm=true, fresh snapshot execution |
| GET /api/state | Includes Studio snapshot for editor |

All POST requests require the existing local X-Devices-Token header, and the Hub is loopback-only. No arbitrary executable code, file paths or external URLs are allowed as node actions.

## Safety and scope

Limit 40 workflows, 24 nodes, 48 connections per graph. Exactly one Start and at least one Output are mandatory. All nodes must be reachable from Start. Runs only perform local fixture operations; they never claim real physical printing, parcel shipment or customer order fulfillment. Captures may contain sensitive local data.

## Testing

Run: python3 -m pytest -q tests/test_studio_engine.py tests/test_hub_frontend.py

Then run the full test suite. Manually validate drag, selection, save/reopen, connection editing, run reports and JPG opening on macOS and Windows. Automated tests do not replace desktop interaction checks.

## v0.13.0 — External TCP Scale node

The **External TCP Scale** template creates `Start → TCP Scale → Output` using an existing saved Network scale profile. Activate its TCP listener in the Connections page first. The node opens a **real socket** to that *existing*, device-id-bound `127.0.0.1` listener, requests `SI`, reads one bounded ASCII response, and validates a stable positive weight. There is no user-supplied host/port and no automatic adapter activation.

- Response `S S 2.000 kg`: completed; downstream nodes receive `{value: 2, unit: 'kg', status: 'stable'}`.
- Response `S D ...`: fails as unstable.
- Response `S I`: fails as busy/unavailable.
- Response `S +`: fails as over capacity.
- No active listener, closed connection, malformed or oversized reply: fails; downstream nodes are skipped.
- Runtime trace records localhost port, raw reply, execution status and weight. It does **not** assert third-party commercial-app compatibility.

Existing `Scale` nodes still use in-app generated values. Captures continue using the local JPG engine; no CUPS/PrintNode/USB/BLE/remote-network requests are made by Studio.

Local tests: `python3 -m pytest -q tests/test_studio_tcp.py` — covers real managed TCP socket, failure propagation, authorization and device validation.
## v0.13.4 — External Serial Scale node

Use a saved shipping-scale profile with **RS-232 / serial** transport and manually create the virtual serial endpoint in Connections. Then select **External Serial Scale** in Studio, save and run. The node opens that specific active PTY using a new OS file descriptor, sends `SI\r\n`, waits no longer than 2 seconds and reads up to 128 bytes of ASCII. It accepts only a stable, finite, nonnegative weight. History includes the raw reply, PTY path, completed/failed status and weight.

Unstable (`S D`), busy (`S I`), overcapacity (`S +`), missing listener, malformed reply and timeout fail the step; downstream nodes are skipped. Streams started using `SUB` must be stopped with `UNSUB` before running Studio. A PTY is **shared** and cannot guarantee exclusive access against other processes. Studio rejects the simulator's active subscription state but cannot prevent external tools from also opening the PTY. Runs do not start a serial listener, accept a custom path, activate physical hardware, or use Windows COM.

Tests: `python3 -m pytest -q tests/test_studio_serial.py tests/test_studio_tcp.py` (POSIX PTY tests skip on Windows). Manually verify the UI on both macOS architectures before calling the feature platform-certified.

## v0.13.5 — portable workflow exchange and snapshot replay

- In the Studio library choose **Import JSON** and select a portable `devices-simulator-studio` schema v1 file (max 64 KB). The device-binding screen lists referenced source device IDs and compatible saved local profiles. Confirm mappings to create a **new** workflow; validation rejects missing/unsupported node types, invalid DAGs, bad transports, or missing device profiles. Import cannot overwrite local workflow IDs or inject run-history metadata.
- Save a workflow, then choose **Export JSON**. The downloaded `.studio.json` contains only `format`, `version` and `workflow` (name/nodes/edges). No local run history, authentication tokens, captured JPGs, revision or workflow ID are exported.
- After a run, Run History offers **Replay snapshot**. Explicitly confirm a **new execution** of the *old saved graph*, even if the currently editable workflow has changed. Results and JPGs are generated afresh. Active TCP/PTY adapters must still be started manually; replay does not restore previous scale measurements or files. Run history records snapshot, revision and replay source run ID. Old history without a snapshot cannot be replayed.
- APIs `POST /api/studio/workflows/export`, `/import`, `/replay` all require Hub authorization. Replay additionally requires `confirm: true` and a valid run belonging to the selected saved workflow. Only 80 recent runs remain available for replay. No custom external URLs or arbitrary scripts.
- Backend format and run history changes are backward-compatible; old runs remain readable but cannot be replayed.

Tests: `python3 -m pytest -q tests/test_studio_portability.py`; run the full suite and inspect the import/download UI manually before production use.

## v0.13.6 — Advanced Workflow Editor

**Canvas and links:** Every eligible node has visible, accessible input/output port buttons. Drag from an output port to an input port to create a directed edge. Alternatively, click an output and choose a destination on the canvas, or use the selected node's inspector destination dropdown plus **Add connection**. Links fail visibly if they would create a cycle, duplicate an edge, link into Start or out of Output, link a node to itself, or exceed 48 edges. This is a client-side convenience check: the existing backend still validates reachability and topology when saving. Live paths follow nodes during dragging.

**Editing history:** Undo/redo buttons and Ctrl/Cmd+Z, Ctrl/Cmd+Shift+Z, Ctrl+Y keyboard shortcuts apply outside text-edit controls. Up to 40 snapshots are retained per opened draft; redo is cleared by a new edit. Edits include node additions/removal, changes to connections, positioning, name and inspector settings after sync. The workflow's saved ID and revision are preserved across undo/redo, and opening a different workflow or template resets editing history. Ordinary native undo remains available while typing into inputs.

**Run diagnostics:** Run History provides **Inspect run** for saved graph snapshots. For a matching current draft, node borders indicate completed, failed or skipped states; the inspector shows counts, selected-step details and recorded errors. If the draft differs from the historical graph, the tool deliberately suppresses node coloring and tells the user why. Inspection does not replay or execute anything, and no printer/scale traffic occurs.

**Testing:** `python3 -m pytest -q tests/test_studio_editor.py` uses the actual Studio JavaScript in a Node VM for graph linking, history restoration, limit checks, port markup and run diagnostics; it also checks local HTTP asset serving. Run the full suite, then manually exercise pointer interactions, keyboard alternatives, dark mode and touch devices on Windows/macOS/Linux. UI tests are not physical-device compatibility certification.

**Deferred:** Branch conditions, breakpoints, arbitrary external software hooks, signed installers, OS-native USB/BLE/Windows COM and end-to-end CUPS/PrintNode field verification remain separate tasks.

## v0.13.7 — Conditional routing, branch diagnostics and templates

- Add a **Condition** node after a **Scale**, **TCP Scale**, **Serial Scale** or **Barcode** input. Configure either `weight` `gte` / `lt` against a numeric threshold (using the upstream reading's unit) or `barcode` `equals` / `contains` against a printable text fixture. No code evaluation, user-defined file paths or external URL inputs.
- Every Condition requires **exactly two distinct outgoing edges**: `branch: "true"` and `branch: "false"`. Other node types cannot set a branch label. Missing/duplicate labels, cycles and invalid comparisons fail backend validation. The new **Weight Routing** and **Barcode Routing** templates demonstrate both paths. Branch ports are separate and labeled T/F, and inspector-based linking supports keyboard users.
- The engine evaluates the condition once from the upstream workflow context; the selected branch is activated. Unselected branch nodes become `inactive`, not `failed`, so workflows may complete with intentionally unused branches. At a merge node, a successful active path can proceed when the other path is inactive. An actual failed or blocked upstream step still makes the dependent step `skipped` and marks the run failed. The engine does not dispatch inactive capture jobs.
- Run History stores each condition's `decision` and `selected_branch`, while inactive steps have a separate status. The inspector counts inactive nodes. Portable JSON export/import and explicit snapshot replay retain branch labels and validate them on load.
- **Testing:** `python3 -m pytest -q tests/test_studio_conditions.py tests/test_studio_conditional_ui.py` plus the full suite. Desktop UI manual checks are still needed, especially drag/touch interactions and OS-specific executable behavior.

**Not included:** generic scripting, timed conditions, webhook triggers, multi-condition expression builders, OS-native drivers, real physical printer operation, or certified scale protocol compatibility.
