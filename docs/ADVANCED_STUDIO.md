# Advanced Studio — architecture and phased delivery

**Status:** v0.9.0 local-first workflow editor and execution foundation.

## Repository review

The previous Studio was a hardcoded four-node illustration with a two-printer demo. The existing Hub has saved profiles, local PDF/JPG capture, test fixtures and fault injection. This implementation extends those instead of rewriting printer services.

## Action plan and implementation status

| Stage | Deliverable | Status |
|---|---|---|
| A | Persistent graph schema, cycle/device validation, safe execution order | Implemented |
| B | Editable canvas, draggable nodes, connections and device bindings | Implemented |
| C | In-app run engine, error propagation, execution logs, JPG links | Implemented |
| D | Port-to-port drag linking, richer node templates, workflow export/import, run replay | Next |
| E | TCP/serial transport adapters, conditions, timers and external software hooks | Planned |
| F | Certified virtual USB/BLE hardware integration and enterprise policies | Requires native development |

## Supported nodes

- Start: deterministic local sample trigger
- Barcode: produces a test string in context; no keyboard or HID output
- Scale: generates a tare-adjusted reading using a saved in-app scale fixture; unstable or overloaded results fail
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
| GET /api/state | Includes Studio snapshot for editor |

All POST requests require the existing local X-Devices-Token header, and the Hub is loopback-only. No arbitrary executable code, file paths or external URLs are allowed as node actions.

## Safety and scope

Limit 40 workflows, 24 nodes, 48 connections per graph. Exactly one Start and at least one Output are mandatory. All nodes must be reachable from Start. Runs only perform local fixture operations; they never claim real physical printing, parcel shipment or customer order fulfillment. Captures may contain sensitive local data.

## Testing

Run: python3 -m pytest -q tests/test_studio_engine.py tests/test_hub_frontend.py

Then run the full test suite. Manually validate drag, selection, save/reopen, connection editing, run reports and JPG opening on macOS and Windows. Automated tests do not replace desktop interaction checks.
