# Devices Simulator — Page-by-Page UI Specifications
**Version:** 1.0 · Companion to [Master Design System](01_MASTER_DESIGN_SYSTEM.md)  
**Status:** Design only, no application implementation  
**Priority:** P0 = essential MVP; P1 = next milestone; P2 = advanced/preview

## 0. Shared UI rules (all routes)
All pages use the same 248px sidebar, 64px top bar, breadcrumb, page title, action area, card language, status definitions, native OS system indicator, error toasts, and theme tokens from the master design system. Normal page gutters: 32px; max width 1440px. Default cards: 12px radius and 20–24px padding.

Top bar (left to right): sidebar collapse, breadcrumb, global search/command palette, service health indicator, notifications, theme/Settings. Search indexes virtual devices, templates, jobs, and outputs; never claims to find actual USB devices that are not registered.

Consistent right rail: 320px for optional Properties/Recent Activity; collapses below 1280px. All tables use the same toolbar, filter chip, row height, selectable states, loading skeleton, and empty state.

Each page supports: loading, initial empty, stale/offline, permission required, operation failed, and successful states. Error messages tell the user what action is possible and do not hide raw details from an Advanced expansion.

## 1. Welcome & First-run Setup — `/welcome` [P0]
**Purpose:** Make the first 2 minutes successful without requiring an account.  
**Layout:** Narrow onboarding hero left, right-side 4-step progress checklist and computer illustration/icon. Light background, blue accents, no dense dashboard widgets.

**Steps:** Welcome → Select output folder → Check local service / OS capabilities → Create first device (or use sample demo). Detect OS, permission model, ports, storage and simulator health; show discovered results rather than guesses.  
**Actions:** Start Setup, Choose Folder, Run Preflight, Open System Settings, Finish.  
**States:** Service not installed, service stopped, non-admin account, OS integration unsupported. A Skip for Now action creates an empty local workspace.  
**Acceptance:** No automatic OS printer modification, no account requirement; “Ready to Create” indicates app readiness, not OS device registration.

## 2. Home / Device Hub — `/` [P0]
**Purpose:** One-glance operational view and fast device creation.  
**Distinctive layout:** Upper-left welcome/title + dominant blue Create Device CTA; upper-right system-service mini panel. First row of 4 compact StatTiles: Configured Devices, OS-Registered Devices, Captured Jobs Today, Devices Needing Attention. Middle row: prominent “Your Devices” cards on left (2/3 width) and Setup/Health checklist right (1/3). Bottom row: Recent Jobs horizontal list and “Quick Actions” templates.

**Controls:** Create Device, Install Existing, Run Printer Test, Browse Outputs, Open Diagnostics.  
**Filters:** all/installed/needs attention.  
**Empty:** Hero checklist and large device category choices; no fake stats.  
**Acceptance:** Counters reflect actual device records, OS queries and job data; Studio is not primary navigation for new users.

## 3. My Devices / Device Library — `/devices` [P0]
**Purpose:** Browse, sort, filter and manage a growing fleet.  
**Distinctive layout:** Wide filter header + grid/list switch + category segmented control + searchable catalog table/grid. Not a duplicate of Home: shows bulk operations, identity, operating system, transport, registration, last test, output folder and actions.

**Actions:** Create, Duplicate, Start/Stop Simulator, Install/Uninstall in OS, Run Test, Archive, Delete. Bulk actions limited to safe actions; OS uninstall requires per-device confirmations.  
**Filters:** category, profile, status, platform, test date, keyword. Sort by name, most recent job, last verified, registration state.  
**Cards:** icon, name, device category, endpoint, last print/scan time, two separate badges “OS status” and “Test status”.  
**Empty:** “No devices match filters” with Clear Filters; first run prompts Create Device.  
**Acceptance:** No OS status is inferred solely from whether a device profile exists.

## 4. Create Device Wizard — `/devices/new` [P0]
**Purpose:** Friendly, reliably resumable six-step device setup.  
**Layout:** White centered content (760–920px), left stepper on wide screens, fixed footer actions, progress summary and “Save Draft” available throughout. Details/advanced options progressively disclosed.

**Step 1 — Choose Category**
Cards: Office Printer, Label Maker/Thermal Printer, Scanner, Barcode Scanner, Receipt Printer, Serial/COM Device, More (future types). Each card carries “Available / Experimental / Coming Later” tags for the CURRENT operating system. Selecting planned types allows “Design profile only” but disables OS Install with explanation.

**Step 2 — Choose Profile**
Searchable preset gallery; Brother Office Dual Tray, Zebra 4×6 Thermal, Generic Office Printer, Custom Device. Preset tile: capabilities, DPI, media, supported formats, realistic OS support. Selecting template never means official Brother/Zebra driver or emulated physical USB identity.

**Step 3 — Configure Device**
Fields: display name, local unique identifier (read-only), transport, default output folder, category-specific capabilities. Printer: tray names/media, duplex, DPI, color; label printer: label size, gap, DPI, PDF vs ZPL support; scanner: source type, ADF vs flatbed (when supported), DPI, output files; barcode: symbologies, trigger, data source, HID availability. Advanced shows IPP URI/port and protocol mapping.

**Step 4 — Define Behavior**
Capture format JPG/PNG (JPG default), quality, page naming, per-job folders, simulated response delay, retries, failure injection profile, retention, local-only privacy. Preview an example artifact. Source changes should not take effect while a job is processing without a confirmation.

**Step 5 — Install in OS**
Show actual current OS and an installation readiness checklist: local service, required permissions, backend compatibility, unique queue name, registration action. The button label is “Install in [Windows/macOS/Linux]”. If integration is experimental, display that before prompting elevation. If unsupported, offer “Save Draft” and “View Platform Support”. Store OS registration details only after OS enumeration confirms them.

**Step 6 — Test & Finish**
Run sample print/scan/input flow from OS queue (or explicitly label as API-only test), show stage-by-stage progress with timestamp and corresponding JPG artifact. Final summary: device settings, OS Installed? yes/no, End-to-end Verified? yes/no, installed queue name, output folder, next actions. Show “View Device” and “Create Another”.

**Behavior:** Back preserves data; Save Draft never installs anything; Next validates only current step; cancellation asks to Save Draft/Discard when dirty; supports keyboard-only.  
**Failure:** Each step can show an inline fix and Retry; never navigate away from failed permissions silently.  
**Acceptance:** Draft can be resumed and edited; truthful OS/device/test state persists after app restart.

## 5. Device Detail / Overview — `/devices/:id` [P0]
**Purpose:** Canonical control panel for ONE device.  
**Distinctive layout:** Device identity masthead (icon, name, model/profile, OS registration badge, test badge) → tab strip **Overview | Configuration | Jobs | Diagnostics | Activity**. Body: operational status timeline and quick test left; right rail shows exact system endpoint, host OS, output directory and last verification evidence.

**Controls:** Run Test, Pause/Resume Simulator, Install/Repair/Remove OS Queue (state dependent), Open Output, Duplicate, Rename.  
**Summary cards:** Supported Capabilities, Recent Captures, Last Error, Device Health.  
**Acceptance:** Detected OS name and actual queue name are visible. Device details must not confuse simulation runtime status with system installation.

## 6. Printer Configuration / Brother — `/devices/:id/configure` [P0]
**Purpose:** Configure dual-tray office printing without exposing raw IPP first.  
**Distinctive layout:** Large labeled tray diagram occupying left region; settings accordion at right; two editable TrayCards with paper size, availability and default purpose.

**Groups:** Identity & Transport; Paper and Trays; Image/Rendering (monochrome/color, dpi, orientation, margins, copies); Document Routing (packing slips→Tray 1, invoices→Tray 2); Failure Simulation (out-of-paper per tray, jam, paused queue); Output Storage.  
**Actions:** Save Settings, Restore Preset, Test Tray 1, Test Tray 2, Re-verify Capabilities.  
**Special:** If host OS cannot expose named source tray, show “Tray selection unavailable in current OS dialog”; offer explicit Tray 1 / Tray 2 queues with clear naming.  
**Acceptance:** Chosen tray is recorded in job detail and test artifacts; OS tray support badge remains conditional on verification.

## 7. Label Printer Configuration / Zebra — `/devices/:id/configure` [P0]
**Purpose:** 4×6 thermal-specific configuration, visually unlike office printer view.  
**Distinctive layout:** Portrait 4×6 label live preview (left, ratio 2:3), media/calibration settings and command format options (right).  
**Groups:** Label size (4×6), 203/300 DPI, printable margins/rotation, gap, darkness/speed simulation, PDF/Image formats, raw ZPL support with explicit “Not available” until renderer exists, image export quality, job naming.  
**Actions:** Print Sample Label, Inspect 4×6 Capture, Rotate Preview, Save, Diagnostics.  
**States:** Invalid label dimensions, unsupported ZPL, barcode readability warning (JPG lossy). Recommend PNG for actual barcode verification.  
**Acceptance:** Page size expressed in inches/mm/pixels; exported label respects selected dimensions for PDF input.

## 8. Scanner Configuration — `/devices/:id/configure` [P1 / OS support pending]
**Purpose:** Prepare a simulated scanner with no false OS scanner claims.  
**Distinctive layout:** Scan glass / ADF illustration, source controls, before/after document preview; blue scanner-specific icon.  
**Groups:** Flatbed vs ADF, color/grayscale, 75–600 DPI, page size, input fixture (PDF/images), output PNG/JPG/PDF, pages-per-scan, feeder error injection, local destinations.  
**Platform:** macOS/Linux eSCL/AirScan investigation; Windows WIA driver work needed. UI must mark “Profile Preview Only” until platform integration is verified.  
**Actions:** Import Sample Input, Simulate Scan (in-app), Install in OS (disabled until available), Save Profile.  
**Acceptance:** In-app scan preview never displays “Scanner installed” without OS scanner enumeration + application acquisition test.

## 9. Barcode Scanner & Other Devices — `/devices/:id/configure` [P2]
**Purpose:** Generic family-specific property editor, not a fake printer settings clone.  
**Barcode layout:** Symbology presets, scan trigger, generated decoded text timeline, data destination.  
**Serial/POS layout:** Virtual port, baud rate/parity, data frames, send/receive monitor.  
**HID/USB warning:** Native virtual HID/COM registration may require signed/platform-specific drivers and privileges; a simulated event in-app isn't an installed system device.  
**Acceptance:** Unsupported transport cannot be set to Installed. Future device plugins inherit canonical status and lifecycle.

## 10. System Integration Center — `/integrations/system` [P0]
**Purpose:** One authoritative screen for OS registration and service readiness.  
**Distinctive layout:** Big OS readiness panel (Windows/macOS/Linux version), 4-stage registration checklist, installed simulator queues table, last OS verification timestamp, expandable raw platform logs.

**Stages:** Service process reachable → Printer endpoint negotiates → Device registered in OS → End-to-end test captures output.  
**Actions:** Check System, Install/Repair Queue, Open OS Printer Settings, Restart Service (if installed), View Permissions, Uninstall.  
**States:** Permission denied, protocol mismatch, registration succeeded but system not enumerating, queue enumerated but print formats rejected, stale endpoint, unsupported OS.  
**Acceptance:** Never mark OS Registered based on `lpadmin` / PowerShell success alone; verify from OS printer enumeration and an OS print test independently. CUPS experimental/non-certified warnings visible.

## 11. Jobs & Queue — `/jobs` [P0]
**Purpose:** Monitor submitted jobs, not manage devices.  
**Distinctive layout:** Full-width sortable job table with a compact queue-stages ribbon and status filters above.  
**Columns:** Job ID, document/title, device, source (API/OS/PrintNode), date, tray/media, pages, stage, duration, artifact, actions.  
**Actions:** View Job, Retry, Cancel, Download Output, Clear Completed (with confirmation).  
**Filters:** date, source, device, status, format, failed-only.  
**Empty:** “No print jobs yet. Run a sample job.”  
**Acceptance:** A completed capture is called Captured; it must not imply physical printing or ecommerce fulfillment.

## 12. Job Detail — `/jobs/:id` [P0]
**Purpose:** Diagnose one captured/failed job and inspect evidence.  
**Distinctive layout:** Document preview on left; vertical stage timeline in center; technical metadata + file list on right.  
**Fields:** device, requested/actual profile, tray, media, source application, original format, DPI, output page count, timestamps, stored path, errors, retry chain.  
**Actions:** Open JPG, Open Original, Copy Job ID, Retry with Same Settings, Export Sanitized Debug Bundle.  
**Security:** Mask PII in default thumbnail sharing and exported logs.  
**Acceptance:** Missing/failed render shows a reason and original file preservation; no fabricated output thumbnail.

## 13. Output Gallery — `/outputs` [P0]
**Purpose:** A visually rich library of captured pages and labels; not another job table.  
**Distinctive layout:** Masonry/card thumbnail gallery with page-size badge and device colored dot; side-by-side compare mode for before/after test output.  
**Controls:** Device filters, date, JPG/PNG/PDF type, page orientation, filename, folder selection, Download, Open in File Manager, Delete Output.  
**Preview:** Large zoomable image with true-size/fit modes and pixel dimensions; redact-sensitive quick toggle.  
**Empty:** Example outline showing where captured JPGs will appear, not fake sample customer labels.  
**Acceptance:** Selecting an artifact deep-links to its originating Job Detail and device.

## 14. Diagnostics Command Center — `/diagnostics` [P0]
**Purpose:** Monitor and repair technical issues; inherits Concept 1’s dense dark command panels.  
**Distinctive layout:** Dark telemetry cards within shared app shell: service status, IPP request flow, OS queue availability, recent failures, response latency, renderer health.  
**Tests:** Service ping, IPP Get-Printer-Attributes, OS enumeration, PDF print roundtrip, Brother tray routing, Zebra media output; show “Not supported” for raw ZPL or scanners.  
**Log views:** request/response activity (content redacted), trace timeline, latest OS errors, categorized probable cause and remediation.  
**Actions:** Run Full Diagnostic, Run Selected Test, Copy Sanitized Logs, Open System Integration, Compare Last Run.  
**Acceptance:** Every check shows its scope “API-only” vs “OS end-to-end” and displays timestamp, duration and evidence.

## 15. Templates Library — `/templates` [P1]
**Purpose:** Quick device creation from proven reusable recipes.  
**Distinctive layout:** Filterable tile gallery with grouped sections (Office, Shipping, POS, Advanced) and visual category art; not a table.  
**Presets:** Brother Dual Tray, Zebra 4×6, Generic Letter Printer, Generic A4 Printer, Sample Scanner (profile-only), Receipt Printer (planned), Studio Packing Station Bundle.  
**Actions:** Preview Capabilities, Customize, Create from Template, Duplicate, Save Custom Template.  
**Acceptance:** Preset labels show platform availability and unsupported features before wizard starts.

## 16. Studio Workspaces — `/studio` [P2, opt-in]
**Purpose:** Manage named advanced layouts that map devices to simulated I/O workflows.  
**Distinctive layout:** Large workspace thumbnails and activity, separate from primary Devices grid.  
**Actions:** New Workspace, Open, Duplicate, Import/Export Local, Archive.  
**First template:** “Lulwa Shipping Station” with Order Document → Brother (packing slip/invoice) + Zebra (4×6 label) → JPG Output Gallery.  
**Acceptance:** Studio can be hidden while baseline device install/print functionality remains complete.

## 17. Advanced Studio Canvas — `/studio/:id` [P2, opt-in]
**Purpose:** Graph-based flow authoring; follows Concept 2 visually.  
**Distinctive layout:** Full-bleed dot-grid canvas, 256px node palette, 320px inspector, top mode bar (Edit / Test), bottom minimap/zoom. Purple accent limited to graph workflow.  
**Node types:** Document Input, Device Printer, Device Scanner (preview where unsupported), Transformer, Delay/Failure Injector, Output Folder, Inspector. Typed connection ports prevent invalid links.  
**Interactions:** Drag/drop, snap grid, multi-select, arrow-key nudge, connect nodes via pointer OR accessible menu, undo/redo, pan/zoom, fit canvas, keyboard commands.  
**Test:** Simulate run with actual job IDs, visualization of route/events, open outputs; never bypass underlying OS-verification checks.  
**Acceptance:** Graph edits don't uninstall/reconfigure devices silently; apply/install changes separately with review.

## 18. Activity Log — `/activity` [P1]
**Purpose:** Auditable chronological operations, especially privileged OS installation.  
**Distinctive layout:** Timeline with date grouping and activity taxonomy; expandable event drawer.  
**Events:** device created, config edited, service started, OS install attempted/verified, permission denied, test job captured/failed, output deleted, profile removed.  
**Controls:** filter category/device/date, export redacted JSON/CSV, copy event ID.  
**Acceptance:** Log export omits sensitive print content and filesystem secrets by default.

## 19. Settings — `/settings` [P0]
**Purpose:** Global preferences, not device-specific print/tray settings.  
**Distinctive layout:** Settings sidebar tabs: General, Appearance, Storage, Service, Privacy, Notifications, Advanced. Consistent form width ~720px.  
**General:** launch at login (if supported), preferred units, default device template.  
**Appearance:** light/dark/system, density, reduce motion.  
**Storage:** output root, JPG/PNG quality, retention schedule, preview cache size, data export.  
**Service:** localhost port, autostart health, restart service, OS permission status.  
**Privacy:** default local-only, scrub diagnostics, clean metadata, no telemetry without opt-in.  
**Advanced:** developer logging, compatibility flag, raw IPP settings, feature flags Studio/experimental device types.  
**Acceptance:** Settings impact preview immediately but do not override per-device settings without warning; OS-impacting changes require confirmation.

## 20. Help, Support & Compatibility — `/help` [P0]
**Purpose:** Give honest supported-device guidance and reproducible troubleshooting.  
**Distinctive layout:** Searchable help articles + OS-specific compatibility tiles and a diagnostics support bundle flow.  
**Sections:** Quick Start, Install/Uninstall, Why Devices Don’t Appear, Printer vs Scanner, Supported Formats, Using PrintNode, Privacy & Output Storage, Release Notes.  
**Actions:** Run Compatibility Check, Open Documentation, Copy Redacted Error Details, Report Issue (link, no automatic upload).  
**Acceptance:** Support matrices match actual backend state; all “Coming Soon” category cards lead here.

## 21. Global dialogs, navigation and overlays [P0]
- **Quick Create:** Category popover, no accidental direct OS installation.
- **Rename:** Validate unique name and explain OS queue renaming consequences.
- **Delete vs Uninstall:** Three separately explicit choices: Remove OS Queue, Delete Simulator Profile, Delete Captured Data. No bundled destructive default.
- **Service Offline Overlay:** Non-blocking ribbon with Start Service / Diagnostics; browsing saved devices remains possible.
- **Permission Request:** Explains exact OS operation, source/target queue, privilege rationale, Cancel.
- **Unsupported Feature:** Alternatives and ETA-free roadmap wording; no dead “Install” button.
- **Command Palette:** Search, go to device, run safe tests, open outputs; dangerous actions require separate confirmation.
- **Notifications:** latest failures and completed captures; no pop-up for every routine job.

## 22. Page transitions and crucial journeys
**A. First device:** Welcome → Home → Wizard → Save Profile → Service Ready → OS Install → Verify OS → Test → Device Detail → Output Gallery.  
**B. Shipping workflow:** Home → Brother Tray 1 Test → Jobs → JPG Output → Zebra 4×6 Test → Output Gallery → Compare sizes.  
**C. Install fails:** Wizard Step 5 → error detail → Diagnostics → System Integration fix → Retry → OS Registered → Test.  
**D. Scanner unsupported:** Choose Scanner → profile preview label → configure fixture → Save Draft → no Install CTA → Help compatibility.  
**E. Advanced workflow:** Settings enable Studio → Studio Template → connect device nodes → Test canvas → individual Job Details.  
**F. Safe removal:** Device Detail → Manage → Remove OS Queue first → verify removed → optionally delete profile/output separately.

## 23. States, responsive views and acceptance tests by page
Global view tests across primary routes: default 1440×900, 1280×800, compact 1024×768, dark theme, 200% zoom, keyboard navigation, offline service, permission denied, empty state, 500+ devices, 10k+ jobs (pagination/virtualization), private paths, high DPI.

Functional acceptance:
- First-run clearly differentiates ready service from installed queue.
- A Draft scanner never appears as an OS-installed scanner.
- Brother and Zebra configuration pages are visually and functionally distinct.
- OS printer settings link is exact per platform when available.
- Wizard draft survives app restart and interrupted setup.
- IPP-compatible print job shows stage, capture JPG, job ID and source.
- Multi-page jobs produce independently inspectable page artifacts.
- Error injection visibly labels simulation and never modifies live customer orders.
- Native install/uninstall needs explicit consent and verifies postcondition.
- User can access output files without Studio.
- Studio has accessible non-drag alternatives for critical operations.
- All incomplete backends are labeled Experimental/Planned instead of Ready.

## 24. Priority and visual approval checklist
**P0 Design+Build:** Home, Devices, Wizard, Device Detail, Brother Config, Zebra Config, System Integration, Jobs, Job Detail, Output Gallery, Diagnostics, Settings, Help, shared dialogs.  
**P1:** Templates, Activity Log, Scanner profile and non-OS preview.  
**P2:** Studio, additional device plugins, barcode/HID, eSCL/WIA OS scanner integrations.

**Visual sign-off requirements:** Review Home, Wizard Step 3, Brother Config, Zebra Config, Jobs, Output Gallery, Diagnostics and Studio side by side in light + dark themes. Confirm shared shell, contrast, spacing and distinct page purposes before coding.
