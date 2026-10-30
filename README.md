<div align="center">

<img src="docs/assets/product-hero.svg" alt="Illustrated Devices Simulator dashboard with office printer, thermal label printer and captured output" width="100%">

# Devices Simulator

**A local-first device workflow lab for teams building software that prints, labels, and scans.**

Test output, reproduce printer failures, and inspect captured JPGs without needing a full hardware lab for every test.

[**Download for Windows, macOS & Linux**](https://github.com/migtam628/devices-simulator/releases) · [Product page source](docs/index.html) · [Company evaluation](docs/COMPANY_EVALUATION.md) · [Support & feedback](https://github.com/migtam628/devices-simulator/issues)

![Desktop builds](https://github.com/migtam628/devices-simulator/actions/workflows/build-desktop.yml/badge.svg)
![Early access](https://img.shields.io/badge/status-early%20access-167789)
![Platform](https://img.shields.io/badge/Windows%20%7C%20macOS%20%7C%20Linux-desktop-18394f)

<sub>This hero is an illustration, not a live application screenshot or proof of native OS device installation.</sub>

</div>

---

## Meet your hardware-independent testing workspace

Software teams building commerce, shipping, POS and internal operations systems face an awkward dependency: testing device workflows usually means maintaining real printers and scanners everywhere.

**Devices Simulator** helps developers, QA teams, and solution engineers create repeatable *local* testing scenarios for office printing, shipping labels, scanner fixtures, and barcode input. It makes generated output visible and simulated failures reproducible.

<div align="center"><img src="docs/assets/workflow.svg" alt="Illustrated workflow: input document, device simulation, JPG capture, visual QA review" width="100%"></div>

> **Early-access software:** The simulator accelerates testing. It does **not** prove physical printing, shipping fulfillment, native scanner installation, or certification by a hardware vendor.

### Feature overview

| Capability | Current support | Detail |
|---|---|---|
| Office printer simulation | **In-app + experimental OS queues** | Brother-style profiles, Letter media, two-tray settings |
| 4 × 6 thermal label simulation | **In-app + experimental OS queues** | Zebra-style label captures and partial ZPL II |
| Local document capture | **Available** | PDF, JPG, PNG and supported ZPL to JPG files |
| Printer fault testing | **Available** | Normal, offline, paper-out, jam and paused |
| Jobs, Gallery and Diagnostics | **Available** | Source documents, output files, metadata and trace information |
| CUPS end-to-end verification | **Experimental — macOS/Linux** | Confirm OS spooler → local IPP → JPG, not just a queued job |
| Flatbed scanner preview | **In-app fixture only** | Not an installed OS scanner |
| macOS barcode entry | **Experimental keyboard simulation** | Accessibility-based input, not a true HID or USB device |
| Studio shipping-station demo | **Available demo** | Capture sample Brother packing slip + Zebra label |
| WIA/eSCL scanner, true HID, ESC/POS, PrintNode certification | **Not implemented / unverified** | Tracked as future work |

<div align="center"><img src="docs/assets/device-preview.svg" alt="Illustration showing simulated Brother-style dual trays and a Zebra-style 4 × 6 label" width="94%"></div>

## Device catalog: scales, BLE, USB & network peripherals

Devices Simulator now supports saved manufacturer/model/transport profiles across office and label printers, shipping scales, barcode scanners, document scanners, receipt printers, serial devices, BLE devices, USB peripherals, network devices, RFID readers and sensors.

In **Create Device**, pick a category → brand → model → connection. Each catalog profile only offers transports appropriate to that reference model. You can change a saved profile in **My Devices**.

**Shipping scale test bench (v0.7):** Generate local weight readings with gross weight, tare, kg/lb/g/oz output, stable/unstable state and over-capacity behavior. This is a *working in-app fixture*, not an installed DYMO/METTLER TOLEDO USB or Bluetooth device. USB, BLE and network selections are saved configurations until their adapters are implemented.

Read the **[Device catalog and transport architecture](docs/DEVICE_CATALOG_PROTOCOLS.md)** for researched models, official manufacturer sources and the native transport roadmap.

## Experimental macOS virtual HID POS scale (v0.8)

The app now includes an opt-in native **CoreHID** prototype for a generic POS shipping scale on macOS 15+. It encodes USB-IF scale reports and provides Activate, Send weight, Check OS enumeration and Deactivate controls.

**Apple's HID virtual-device entitlement is required.** Ordinary unsigned Releases do not have approved entitlements. An attempted activation can fail with a precise diagnostic; the app must not show a connected device unless the OS accepts it. Even if it enumerates, this is NOT a DYMO M10 USB identity/VID/PID clone.

See the [macOS CoreHID scale development and test guide](docs/MACOS_COREHID_SCALE.md). Other OS HID drivers remain planned.
## Advanced Studio — editable workflow engine (v0.9.0)

Studio now has a visual workflow editor, a saved workflow library, configurable nodes and connections, drag positioning, revision protection and run history. A Shipping Station template can route sample barcode data through an optional scale fixture into Brother/Zebra captures, then an output report.

**Supported:** Start → Barcode Data → Scale Reading → Printer/Scanner Capture → Output. All runs use **in-app local fixtures**, not OS printer queues. Failed steps block their downstream dependencies while independent branches can still complete. View local JPG captures in the run log.

**Not yet supported:** External USB/BLE/network data streams, live remote devices, background triggers, arbitrary scripts, OS printing, or automatic order fulfillment.

[Advanced Studio technical architecture and roadmap](docs/ADVANCED_STUDIO.md)

## Universal Connection Engine — TCP milestone (main branch)

External software connectivity first became available in v0.10.0, with additional POSIX serial endpoints in v0.11.0: an **opt-in loopback TCP server** for shipping-scale fixtures. Another local application can open a socket, send a line-delimited \`SI\` (immediate) or \`S\` (stable) command, and read back a tare-adjusted scale value using a limited MT-SICS-style response. It supports simulated unstable, overload, busy and disconnect states, plus connection telemetry.

**This is not** a registered USB/HID device, a serial/COM driver, a BLE peripheral, or a certified METTLER TOLEDO BC emulation. TCP listens only on \`127.0.0.1\`, never starts automatically, and requires explicit activation in the **Connections** dashboard (or authenticated Hub API). The scale reference profile must have **Network** selected.

See the [Connection Engine guide](docs/CONNECTION_ENGINE.md) for the exact API, socket examples, security and troubleshooting. Windows/macOS/Linux runtime verification is tracked separately from Python socket tests.

## Virtual serial scale ports — macOS and Linux (v0.11.0)

Alongside the TCP adapter, Devices Simulator now supports an **opt-in POSIX pseudo-terminal (PTY)** for serial-compatible scale testing on macOS and Linux. In the **Connections** page, configure a network-capable scale for TCP or a serial-capable scale for RS-232 / COM and activate the matching adapter.

Another local program can open the generated `/dev/...` PTY path, send ASCII `S` or `SI`, and receive the same weight fixture values as the TCP adapter. Busy and silent-response faults are supported. This is **not a physical RS-232 port, USB CDC device, or Windows COM driver**. Windows serial emulation requires separate native work.

See the [Connection Engine Guide](docs/CONNECTION_ENGINE.md) for PTY testing commands, platform boundaries and examples.
## Connection reliability updates — v0.11.1

The Connection Engine now closes existing TCP client sockets when a listener is stopped, rather than leaving those sessions waiting for their idle timeout. POSIX serial fixtures now include **Test serial roundtrip**, which opens the generated PTY from a separate file descriptor and checks the actual response.

These are **local transport tests**. Neither TCP nor PTY self-tests certify external software compatibility, and the serial PTY is not Windows COM or USB hardware.
## Protocol discovery for third-party scale clients — v0.12.0

External applications can now query **what the simulator actually supports** over TCP and POSIX serial, instead of assuming an entire manufacturer protocol is available. Implemented inquiry commands: `I0` (advertises only supported commands), `I2` (generic simulator identity and capacity), `I3` (simulator software identity) and `I4` (simulated serial ID). Existing `S` and `SI` weight commands remain supported.

The replies identify the endpoint as `DEVICES_SIM` or `DevicesSimulator` and never claim real METTLER TOLEDO hardware. `SIR`, zero/tare commands, Windows COM, USB/HID, and BLE are **not yet implemented**. Discovery is designed to fail visibly for software needing unsupported commands rather than pretending compatibility.

See [Connection Engine protocol and socket test guide](docs/CONNECTION_ENGINE.md).
## v0.13.0 — Advanced Studio + real TCP scale integration

Advanced Studio now includes an **External TCP Scale** node and template. Unlike the in-app Scale node, this one opens an actual TCP socket to a previously activated **localhost-only** scale endpoint in the Connections screen, sends a read-only `SI` command and consumes the returned measurement. It records the response in workflow history, fails clearly on missing listeners, busy/unstable/overload/disconnect states, and skips dependent steps.

The node **never** starts a listener itself, accepts a custom host or port, reaches LAN/internet devices, changes a physical scale, or resolves the deferred CUPS issue. Only saved Network scale profiles and explicitly activated local listeners are eligible. Existing workflows continue using local fixtures unchanged.

See [Advanced Studio guide](docs/ADVANCED_STUDIO.md) and [Connection Engine guide](docs/CONNECTION_ENGINE.md).
## v0.13.1 — Live TCP scale subscriptions

External clients can subscribe to **live 2 Hz weight reports** over an existing localhost scale listener using the simulator-specific `SUB` command. The server returns `SUB OK 500` followed by `EVT S S 2.000 kg`-style readings approximately every 500 ms. The client ends its subscription by closing the socket; stopping the listener also closes active client connections.

**Important:** `SUB`/`EVT` is a **Devices Simulator extension**, not an implementation of METTLER TOLEDO `SIR` or an official product protocol. It works only on the TCP adapter in this milestone; POSIX serial remains request/response. Streaming requires manually activating the listener and does not broadcast to the LAN.
## v0.13.2 — Windows test reliability

Cross-platform automated checks now allow more realistic startup and HTTP response time on heavily loaded Windows CI runners. Node.js syntax checks and local Hub socket tests still assert their results; this change does not alter production TCP, serial or Studio behavior. The functional milestones remain **v0.13.0** (Studio-to-TCP workflow) and **v0.13.1** (opt-in 2Hz TCP weight stream).
## v0.13.3 — bounded POSIX serial live-weight subscriptions

macOS/Linux virtual serial scale ports now support a **simulator-specific `SUB` / `UNSUB` stream** alongside their existing read-only `S`, `SI` and discovery commands. `SUB` acknowledges `SUB OK 500`, then emits `EVT S S ...` readings at up to 2 Hz. `UNSUB` stops the stream. Each subscription expires automatically after 30 seconds or 60 events, whichever comes first, and sends `EVT END LIMIT` when possible. Reissue `SUB` to begin another bounded session.

Unlike TCP, a POSIX pseudo-terminal is a **shared serial path**, not a per-client socket: multiple open applications could see the same stream, and the emulator cannot reliably detect individual client disconnects. Streaming never begins automatically and a non-reading client cannot block the worker indefinitely. This is not MT-SICS `SIR`, USB HID, Bluetooth, or Windows COM hardware. See the [Connection Engine guide](docs/CONNECTION_ENGINE.md).

## v0.13.4 — Advanced Studio managed serial scale reads

Advanced Studio now has an **External Serial Scale** template and a **Serial Scale** workflow node on macOS/Linux. Create a saved RS-232/serial scale profile, manually activate its virtual serial (PTY) endpoint in **Connections**, then open the template, save and run. Studio opens the existing OS PTY and reads one bounded `SI` response, recording the raw reply and weight in workflow history. Missing listeners, busy/unstable/overload states and timeouts fail cleanly, skipping downstream steps.

A POSIX PTY is **shared**: stop any `SUB` stream using `UNSUB` before running the workflow and avoid simultaneous clients. No Windows COM driver, physical USB/BLE device, arbitrary serial paths or OS print jobs are created by this milestone. Existing TCP and local fixture workflows remain unchanged. See [Advanced Studio](docs/ADVANCED_STUDIO.md).

## v0.13.5 — portable Advanced Studio workflows and snapshot replay

**Export JSON** saves a portable workflow graph without local run history, customer artifacts, output images, or persistence identifiers. **Import JSON** reads a `devices-simulator-studio` v1 document (64 KB maximum), prompts for explicit bindings from the imported device IDs to saved compatible local profiles, validates the graph, and creates a **new workflow** without overwriting existing work. Neither importing nor exporting activates connections or prints.

Run History now offers **Replay snapshot** for runs created by v0.13.5 and later. Replay re-executes the **saved original graph** using current local fixtures/active adapters. This is a **new run**, potentially producing new JPG files; it is *not* a deterministic restoration of prior weight readings or rendered output. Replay requires explicit confirmation. Older history records without snapshots cannot be replayed. These actions remain authenticated and local-only. See [Advanced Studio](docs/ADVANCED_STUDIO.md).

## v0.13.6 — visual Advanced Studio editor and run diagnostics

The Advanced Studio canvas now provides **real clickable connection ports**. Drag an output port to another node's input port, or connect using the inspector's keyboard-accessible destination selector. New links are checked immediately for duplicates, self-links, illegal Start/Output directions, graph cycles and the 48-edge limit; final validation still happens on the backend before saving.

**Undo / Redo** tracks up to 40 graph edits (nodes, connections, moved positions, workflow name and inspector changes), while preserving the saved workflow's ID/revision. Keyboard shortcuts: Ctrl/Cmd+Z and Ctrl/Cmd+Shift+Z or Ctrl+Y outside text inputs. The canvas updates connection paths as nodes move.

Run History's **Inspect run** button highlights completed, failed and skipped nodes on an *unchanged* graph and shows failure reasons in the inspector. When the current draft differs from the saved historical snapshot, highlighting is disabled to prevent misleading diagnostics. These enhancements affect the UI only: no new OS device drivers, arbitrary network access, printer queue routing or automatic device activation are introduced.

See [Advanced Studio technical guide](docs/ADVANCED_STUDIO.md). Platform builds remain experimental and require interactive testing.

## v0.13.7 — Advanced Studio conditional routing

Advanced Studio now supports a **Condition** node with **TRUE** and **FALSE** outputs. A condition checks either an upstream scale reading (at least / less than a threshold in that reading's current unit) or a barcode string (equals / contains). Both outputs must connect to distinct downstream nodes. A selected route runs normally; the unselected route is explicitly marked **inactive**, not failed. When branches converge, a valid active route can continue through the join; errors on active upstream branches still block their dependents.

Use **Weight Routing** or **Barcode Routing** in Studio to create a ready-to-edit example. Configure a Condition in its inspector, link via labeled T/F ports or the keyboard-friendly branch selector, then save and run. Run diagnostics show branch decisions and inactive steps; run replay/export/import preserve the conditional graph.

The server still validates the DAG: missing or duplicate branch labels, invalid values, cycles, and unsupported node actions are rejected. Conditions never start TCP/serial adapters, print to physical devices, execute scripts, or bypass local-only restrictions. For tests and known limitations see [Advanced Studio](docs/ADVANCED_STUDIO.md).

## v0.13.8 — Read-only workflow debugger and execution preflight

Advanced Studio adds an **Inspect plan** button that validates a draft workflow without saving it or performing a device operation. The local authenticated preflight API returns the real topological order, dependencies and conditional links, and identifies actions that **would** generate JPGs, update local fixtures, or read an already-active TCP/PTY adapter if the workflow were executed. It does **not** activate listeners, create jobs, poll scales, write run records, or modify saved workflows.

The inspection panel provides **Previous/Next step**, direct step selection, canvas highlighting and optional **review checkpoints**. These are **not** live breakpoints: stepping through the plan never performs any operation. If you edit the graph after inspecting, the prior plan is marked stale and highlighting is suppressed until you inspect again. The original Run locally and Replay actions continue to require their own explicit confirmations.

New endpoint: authenticated `POST /api/studio/workflows/inspect` with `{"workflow": {name, nodes, edges}, "checkpoints": ["node_id"]}`, returning `{"inspection": ...}` as a read-only result. The same backend validation applies to unsaved, imported, and saved graphs. This is a safe preflight debugger, **not** pausable/resumable live execution. See [Advanced Studio](docs/ADVANCED_STUDIO.md).

## v0.13.9 — Confirmed live step-by-step workflow debugger

Advanced Studio now provides **Start paused session**, **Execute next step**, **Recover active session**, and **Cancel session** alongside the read-only Inspect plan tool. Each button action executes **at most one node** in the exact saved graph revision. Starting a session does not execute anything. The only execution trigger is an explicit authenticated Step request with the precise expected step index; retries cannot repeat prior JPG captures.

**Safety boundaries:** Printer capture, simulated scale reads, real managed localhost TCP scale reads, and POSIX PTY scale reads each require a separate user confirmation before execution. Inactive condition routes do not create JPG jobs. Paused sessions are **in-memory only**, expire after 15 minutes without requests, are limited to one active Hub session, and never resume automatically. Restarting the app discards paused state; already-produced JPG artifacts cannot be undone. An explicit Cancel records partial steps in Run History.

**How to use:** Open Advanced Studio, save a valid graph, select Start paused session, then use Execute next step one node at a time. Confirm local-effects steps individually. Use Recover active session to rejoin a still-live session after reloading the page; Cancel session stops any remaining nodes. Run History records finished and cancelled debug runs. Existing Inspect plan remains strictly read-only.

**API:** token-authenticated `POST /api/studio/debug/start`, `/status`, `/step`, and `/cancel`. For detailed limitations and test procedures see [Advanced Studio](docs/ADVANCED_STUDIO.md).

## v0.14.0 — OS Print-to-JPG reliability and fault diagnosis

**Real Linux CUPS end-to-end verification is now part of CI.** On Ubuntu 22.04, the workflow installs and starts the actual CUPS scheduler, registers the simulator's Brother and Zebra IPP Everywhere printer queues with `lpadmin`, prints unique marked PDFs using `lp`, then confirms that **each job produced a non-empty JPG on disk**. This tests the real OS spooler → IPP → rendering path rather than only the in-app capture API. Linux CI passed on both queues. **macOS and Windows print-dialog compatibility remain unverified on actual user computers.**

**Find why JPGs are missing:** Open **System Integration → Check print path** for the Brother or Zebra queue. This read-only diagnostic checks OS queue identity, the IPP listener on localhost:8631, whether its output directory matches the Hub's output directory, and whether the CUPS queue is enabled. It gives specific repair instructions instead of treating a successfully queued job as successful printing. The **Verify OS Print → JPG** button now requires a ready path and still checks the actual generated JPG.

A common cause is an **old IPP service using a different --output directory**, so the app's Gallery looks empty even though another process captured the print job. Restart the stale service and run both the Hub and IPP with the same output folder; don't delete the original captured files.

For setup, log collection, manual Linux/macOS tests, and a checklist for OS registration problems, see **[OS printing diagnostics](docs/OS_PRINT_DIAGNOSTICS.md)**. These builds remain experimental and are not vendor-certified physical printers.

## v0.14.1 — Experimental Windows spooler diagnostics and JPG probe

On Windows, the System Integration **Check print path** now inspects the native Print Spooler service and saved queue status, in addition to the loopback IPP listener and output folder. When the printer's **exact simulator IPP endpoint is verifiable**, the **Verify OS Print → JPG** action offers an explicitly confirmed native Windows GDI sample page through the installed queue. It does not bypass the Windows spooler or submit directly to the simulator's IPP endpoint.

A successful PrintDocument submission is **not counted as printing success** until a unique tagged job appears with a nonempty JPG. Windows' IPP class driver may emit an unsupported document format; the app reports an error rather than falsely claiming output. The UI also refuses to run the test if the Windows port is opaque and the simulator cannot establish the exact endpoint—an installed queue name by itself is not proof of ownership. Review the diagnostics to resolve the problem.

**Verified in automated tests:** Print Spooler status classification, endpoint restrictions, approval gates, safe sample script generation, missing-JPG detection, and Windows PowerShell syntax. **Not yet verified:** a live Windows desktop's IPP queue actually delivers raster/PDF output that the simulator can render. This is a device-side capability test, not Windows IPP certification. See [Windows printing troubleshooting](docs/OS_PRINT_DIAGNOSTICS.md).

## Who it's for

**QA engineering:** Reproduce print payloads, rendering issues and device-failure scenarios in a controlled environment.

**Shipping & fulfillment software:** Preview 4 × 6 labels, packing slips and internal paperwork before testing the physical printer.

**Retail, POS and kiosk vendors:** Exercise queue selection and document flows before store deployment.

**Solution engineers and demo teams:** Demonstrate realistic workflows without carrying a whole set of devices to every meeting.

For pilots, deployment readiness, support boundaries and commercial-use questions, read the **[Company evaluation guide](docs/COMPANY_EVALUATION.md)**.

## macOS CUPS "Waiting for job to complete" / no JPG (v0.8.1)

The IPP server previously rejected streaming HTTP `Transfer-Encoding: chunked` requests because it required `Content-Length`. v0.8.1 decodes bounded chunked uploads and records CUPS job-state polls.

After installing the new build, fully quit the old simulator process, reopen the app, and check:

    curl -s http://127.0.0.1:8631/healthz | python3 -m json.tool
    curl -s http://127.0.0.1:8631/diagnostics | python3 -m json.tool
    lpstat -v Lulwa_SIM_Zebra_4x6
    lpstat -p Lulwa_SIM_Zebra_4x6 -l
    lpstat -o Lulwa_SIM_Zebra_4x6

If a previous simulator test job is still stuck, cancel that job in macOS printer queue, or intentionally cancel every pending job from the **simulated Zebra queue only** using `cancel -a Lulwa_SIM_Zebra_4x6`. Then use **System Integration → Verify OS Print → JPG** again.

Diagnostics track operation state codes (3=pending, 8=aborted, 9=completed). Installation in the OS is not proof of a captured JPG.

See [CUPS troubleshooting](docs/CUPS_JPG_TROUBLESHOOTING.md) for detailed interpretation and safeguards.
## Download the app

[**Browse published releases**](https://github.com/migtam628/devices-simulator/releases)

| Platform | Package | Important requirement |
|---|---|---|
| Windows x64 | Portable ZIP with <code>DevicesSimulator.exe</code> | Keep its bundled files; WebView2 may be required |
| macOS Apple Silicon | ZIP with <code>DevicesSimulator.app</code> | Unsigned early-access build |
| macOS Intel | ZIP with <code>DevicesSimulator.app</code> | Unsigned early-access build |
| Linux x64 | TAR.GZ with <code>DevicesSimulator</code> | Opens the hub in your system browser |

Python is bundled with the portable executables. Packages are development builds, **not signed or notarized installers**. Read [desktop packaging notes](docs/DESKTOP_BUILDS.md) for checksums and platform requirements.

### First run

1. Open Devices Simulator and select **Create Device**.
2. Choose **Brother Dual Tray** or **Zebra 4 × 6**, configure the profile, and save it.
3. Choose **Generate Sample** or import a document.
4. Open **Output Gallery** to inspect your real local JPG files.
5. Use **System Integration** only when you want to test experimental native printer queues.

By default, capture output is stored under the user's Documents folder, in a profile-named directory. A captured job keeps the original input, one or more JPG pages and a <code>job.json</code> record.

### Where your data goes

Core capture runs **locally** and does not require a cloud account. Your labels and documents can still contain sensitive order information. Control local filesystem permissions, storage location and manual cleanup; there is not yet an enterprise retention-management guarantee.

## What “installed” means

There are three separate milestones:

1. **Profile created:** the simulator knows what to emulate.
2. **OS printer queue registered:** Windows/macOS/Linux recognizes a local IPP queue, where supported.
3. **OS job captured:** a print job reaches the simulator and produces a verifiable JPG.

A successful result at milestone 2 **does not guarantee** milestone 3. Printer drivers, supported formats, queue status and operating-system behavior still matter.

### Fixing “CUPS accepted the job, but no JPG arrived”

The **v0.6.1 print-path update** addresses a protocol gap: the server now handles both a single IPP Print-Job and the two-stage **Create-Job → Send-Document** sequence used by some CUPS clients. It also reports IPP activity and distinguishes a captured job from a job that was merely accepted by the OS spooler.

First, download the newest release, **quit the previous simulator completely**, and restart the app. In **System Integration**, check that the simulated printer queue is registered, then run **OS Print → JPG verification**.

On macOS/Linux, use these diagnostics in Terminal:

    # Verify OS queue and local simulator
    lpstat -p
    lpstat -v
    curl http://127.0.0.1:8631/healthz

    # See IPP operations, format and capture status (not document contents)
    curl http://127.0.0.1:8631/diagnostics

    # Check whether the spooler is holding a Brother test job
    lpstat -p Lulwa_SIM_Brother -l
    lpstat -o Lulwa_SIM_Brother

If **no Print-Job or Send-Document request** appears in diagnostics, investigate CUPS queue delivery and document-format conversion. If an IPP request arrives but capture fails, inspect its status and error. Supported formats and conversions vary by OS.

> GitHub's automated tests check the IPP two-stage submission and local JPG pipeline. We cannot certify your particular Mac or driver configuration without testing that host. See [OS printer setup](docs/OS_PRINTERS.md).

## Simulated scanning and barcode entry

**Flatbed scan fixture:** Imports or generates sample images within the app. It does *not* install a scanner into macOS Printers & Scanners or Windows Devices & Printers.

**Barcode input simulator:** On macOS, the app can send barcode characters via Quartz keyboard events after explicit approval. It needs Accessibility permission and is **not** a permanent HID/USB device. Try it only with an empty, nonsensitive document or test form in focus.

## From source

Requires Git and Python 3.10+.

macOS and Linux:

    git clone https://github.com/migtam628/devices-simulator.git
    cd devices-simulator
    python3 -m venv .venv
    source .venv/bin/activate
    python3 -m pip install -e '.[test]'
    python3 -m pytest -q
    lulwa-hub

Windows PowerShell:

    git clone https://github.com/migtam628/devices-simulator.git
    cd devices-simulator
    py -3 -m venv .venv
    .\.venv\Scripts\Activate.ps1
    python -m pip install -e ".[test]"
    python -m pytest -q
    lulwa-hub

For the optional native desktop wrapper install the <code>desktop</code> dependency group and launch <code>lulwa-desktop</code>. Native OS webview prerequisites still apply.

### Implementation map

    Desktop hub and wizard
          │
          ├─ Device profiles and simulated fault states
          ├─ Jobs / gallery / diagnostics
          ├─ Capture engine: PDF, image, partial ZPL → JPG
          ├─ IPP service and experimental OS printer queues
          ├─ Scan preview fixture (not an OS scanner)
          └─ macOS barcode keyboard input (not HID hardware)

The Python package is in <code>src/lulwa_virtual_printer/</code>. Desktop packaging lives in <code>packaging/</code>. GitHub Actions builds Windows, macOS and Linux executables, smoke-tests them, and publishes versioned experimental [Releases](https://github.com/migtam628/devices-simulator/releases).

## Product roadmap

Tracked in [GitHub Issues](https://github.com/migtam628/devices-simulator/issues):

- Native eSCL/AirScan and Windows WIA scanner support
- True virtual HID/keyboard devices with platform-appropriate permissions and signing
- Full ZPL and ESC/POS support with barcode fidelity validation
- Verified PrintNode interoperability
- Editable workflow Studio, reusable test scenarios and persistence
- Signed installers, managed updates and retention controls

### Business use and licensing

**No software license terms are currently specified.** Public access to the repository does not automatically grant a company commercial-use or redistribution rights. Please contact the maintainer via the [issue tracker](https://github.com/migtam628/devices-simulator/issues) to establish appropriate licensing and support terms before deployment.

Devices Simulator is independent experimental software. References to Brother and Zebra identify representative test profiles, not an affiliation or endorsement.

---

<div align="center">
<strong>Test the workflow. Not your patience.</strong><br>
<a href="https://github.com/migtam628/devices-simulator/releases">Downloads</a> · <a href="docs/index.html">Product page</a> · <a href="docs/COMPANY_EVALUATION.md">For teams</a> · <a href="https://github.com/migtam628/devices-simulator/issues">Feedback</a>
</div>
