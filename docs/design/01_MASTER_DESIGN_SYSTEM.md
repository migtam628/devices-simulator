# Devices Simulator — Master Design System
**Design ID:** DS-HYBRID-01  
**Version:** 1.0 · October 25, 2026  
**Status:** Design approved in principle; implementation not started  
**Source concept:** Concept 3 Device Hub Pro × Concept 1 Command Center × optional Concept 2 Device Studio

## 1. Product identity and UX principles
**Product name:** Devices Simulator  
**Application subtitle:** Device Hub Pro  
**Positioning:** A local-first, cross-platform control center for creating, installing, simulating, diagnosing, and removing virtual devices.

The visual experience is premium, calm, and useful on first launch. Technical depth should be available without making every user interact with protocol-level details.

1. **Create first, troubleshoot when needed.** Primary action on Home and Device Library: Create Device.
2. **A profile is not an OS-installed device.** Surface actual OS registration and end-to-end test status separately.
3. **Native installation requires explicit consent.** Do not silently elevate privilege, load a driver, or alter OS queues.
4. **Local-first and privacy-first.** Documents, scanned images, and diagnostic traces remain local by default.
5. **One design language across every module.** Each page inherits navigation, spacing, colors, status grammar, action placement, and density scale.
6. **Basic mode by default, advanced mode on request.** Studio and raw protocol settings sit behind explicit Advanced affordances.
7. **Platform truthfulness.** Unsupported device/platform combinations are visible as informational previews, never deceptive active installs.

## 2. Information architecture

Primary sidebar order:
- **Home** — `/`
- **My Devices** — `/devices`
- **Create Device** — `/devices/new` (prominent primary CTA and sidebar item)
- **Templates** — `/templates`
- **Jobs & Outputs** — `/jobs` (tabs: Jobs / Output Gallery)
- **Diagnostics** — `/diagnostics`
- **Studio** — `/studio` (Advanced, opt-in)
- **System Integration** — `/integrations/system`
- **Activity Log** — `/activity`
- **Settings** — `/settings`
- **Help & Compatibility** — `/help`

Context routes:
- `/devices/:deviceId` Overview
- `/devices/:deviceId/configure` Category-specific settings
- `/devices/:deviceId/diagnostics` Device-scoped testing
- `/jobs/:jobId` Job detail
- `/outputs` Output gallery
- `/studio/:workspaceId` Studio canvas

Avoid duplicating device inventory across Products, Jobs, and Studio. Every screen deep-links to the single canonical Device Detail.

## 3. Design tokens

### Core palette
| Token | Light | Dark | Usage |
|---|---|---|---|
| `bg.app` | #F5F7FA | #101820 | App canvas |
| `bg.surface` | #FFFFFF | #172333 | Cards/dialogs |
| `bg.subtle` | #EDF2F7 | #213247 | Alternate panels |
| `bg.inverse` | #15263E | #EAF1FA | Focused dark panels / contrasting title |
| `text.primary` | #18263A | #EEF3F9 | Main content |
| `text.secondary` | #5D6B7E | #B0BECE | Supporting text |
| `text.muted` | #7E8A9A | #8296AA | Metadata |
| `border.default` | #DCE3EB | #35475D | Containment / separators |
| `action.primary` | #2869B2 | #6CA9EF | Buttons and selected nav |
| `action.hover` | #1D518D | #90C0F3 | Hover |
| `accent.teal` | #138B81 | #5BD0BD | Diagnostic / operational detail |
| `studio.accent` | #7958A6 | #AA91DB | Graph nodes, advanced workspace |
| `semantic.success` | #20845F | #59C79B | Verified end-to-end only |
| `semantic.warning` | #B7791F | #F3B65A | Attention/degraded |
| `semantic.error` | #BD3943 | #FF7985 | Failure |
| `semantic.info` | #447FAE | #7CB4E8 | Informational only |

**Status rule:** Color is supplementary; every status uses text and icon. Never use a green success pill to mean only a simulated profile exists.

### Type and iconography
- Font stack: Inter (bundled if licensed) → system UI; macOS SF Pro, Windows Segoe UI, Linux system sans as native fallbacks.
- Display: 30/38 semibold (first-run and Home only).
- H1 page: 24/32 semibold; H2 section: 18/26 semibold; H3 card: 15/22 semibold.
- Body: 14/21 regular; secondary: 13/20; metadata/caption: 12/18; monospaced diagnostics: 12/18.
- Body weight: 400; button/nav: 550–600; tabular numerals for counters and timings.
- Icon set: Lucide-style 20px base, 16px dense, 24px category cards; consistent 1.75 stroke.
- Never rely on realistic manufacturer logos or impersonate official drivers; use generic device silhouettes.

### Spacing and size
- Spacing scale (px): 4, 8, 12, 16, 20, 24, 32, 40, 48, 64.
- Radius: 8px controls; 12px cards; 16px hero/modals; 20px major workspace.
- Sidebar: 248px expanded / 72px collapsed. Utility top bar: 64px.
- Content width: max 1440px; normal page padding 32px desktop, 24px laptop, 16px tablet.
- Grid: 12 columns desktop, 8 tablet, 4 compact; gutter 20px.
- Control heights: 36px compact / 40px default / 48px wizard primary.
- Touch targets at least 44×44px in touch-focused layouts.
- Shadows: restrained; elevate dialogs, dropdowns, dragged Studio nodes only.
- Motion: 120ms hover, 180–220ms panels, 240ms page transitions; honor reduced-motion.

### Layout families
**Hub page:** Breadcrumb → Page title/action → summary row → main panels → helpful empty state.  
**Detail page:** Device header with truth-status → horizontal tab bar → 2/3 main + 1/3 properties/health.  
**Wizard page:** Centered 760–920px step canvas, progress bar, persistent Back/Continue/Save Draft footer.  
**Diagnostics page:** Optional dark instrumentation surface with readable tables and graphs; base shell remains consistent.  
**Studio page:** Full-height split workspace: 256px palette + canvas + 320px inspector with collapsible panes.

## 4. Shared component library
| Component | Variants and behavior |
|---|---|
| AppShell | Sidebar, top bar, breadcrumbs, system-service indicator, quick create |
| PageHeader | Title, subtitle, primary CTA, overflow; fixed title/actions grammar |
| DeviceCard | Identity, category icon, registration status, runtime health, last test, overflow |
| DeviceListRow | Dense DeviceCard; keyboard selectable; bulk actions with safeguards |
| StatusPill | Draft / Service Offline / OS Registered / Test Passed / Degraded / Error / Unsupported |
| StatTile | Metric, baseline/time-range, link; not misleading simulated metrics |
| CapabilityChip | Feature and support level: Available / Experimental / Planned |
| WizardStepCard | Single purpose, explanatory example, inline validation, persistence |
| OutputPreview | JPG/PDF thumbnail with page size, orientation, dpi, inspect/download |
| TrayDiagram | Diagram + explicit tray selection (not a decorative picture only) |
| JobRow / JobTimeline | Source, device, stage, timestamp, outcome, error |
| LogViewer | Search/filter, copy redacted, export locally, wrap/monospace toggle |
| DeviceTestPanel | Submit sample, status progression, evidence artifacts |
| InstallationChecklist | OS permission, service status, registration, print/scan verification |
| InspectorPanel | Reusable right rail for settings, node properties and diagnostics |
| BlankSlate | Explains why empty and has one next useful action |
| ConfirmDialog | Destructive actions: exact device name and effect on OS; rollback if possible |
| Toast / InlineNotice | Success, caution, error with separate retry action and error detail |

### Shared field patterns
- Device names: 1–64 characters, OS name availability check, duplicate warning, slug generated internally.
- Device category is immutable after registration; use Duplicate Device if switching categories.
- Show media size in both human and technical form (e.g., **4 × 6 in · 101.6 × 152.4 mm**).
- File path field: native directory picker, path verification, free-space and permission warnings.
- Protocol fields: hostname, URI and port hidden behind Advanced; syntax validated inline.
- All user-triggered install/uninstall flows require permission confirmation and an observable outcome.

## 5. Status grammar and device lifecycle
These labels are independent of the optimistic preview of a configured device:

| State | Meaning | UI treatment |
|---|---|---|
| Draft | Saved config, no running device endpoint | Neutral dot; Set Up action |
| Service Ready | Local simulator endpoint passes health probe | Blue/teal; Install in OS |
| OS Registered | System API confirms a print/scanner queue/device registration | Blue; Run End-to-End Test |
| Test Passed | Last end-to-end simulated task captured valid output | Green + checked timestamp |
| Degraded | OS entry exists but a function has failed | Amber + Diagnose |
| Service Offline | Endpoint unavailable | Gray/amber + Start Service |
| Failed Install | Registration did not complete | Red + error + Retry |
| Unsupported | Device/OS integration not implemented | Neutral + Preview or Docs |

Never display “Installed” from a successful installer process alone. Verify with OS enumeration; “Test Passed” requires a real OS-submitted task and its output artifact.

Job lifecycle: Created → Queued → Receiving → Rendering → Captured / Failed / Canceled.  
A captured JPG is never evidence that physical paper printed or an ecommerce order shipped.

## 6. Responsive and desktop behavior
- Desktop primary target: 1280×800 and larger; Windows, macOS, Linux.
- 1024–1279: collapse right inspectors and reduce stat tiles to 2×2.
- 768–1023: collapsible sidebar, two-column devices, wizard one column.
- Under 768: responsive read-only/limited configuration where OS install requires desktop-native permissions; Studio displays “Open on desktop” if drag/zoom cannot be supported accessibly.
- State persists when navigating away: filters, open tabs, wizard drafts, workspace camera position.
- Dark mode matches feature parity; diagnostics does not override system theme unpredictably.

## 7. Accessibility and localization
- WCAG 2.2 AA contrast where practical; 4.5:1 normal text, 3:1 UI boundaries.
- Keyboard reachability for all device and installation actions; visible focus ring.
- Screen reader labels for device status, job changes, tab activation and installation stages.
- No hover-only essentials; expose equivalent menus and keyboard commands.
- Non-drag alternative for every Studio connection/arrangement action.
- Support English first, localization-ready strings and measurements; OS-specific terminology localized.
- Reduced motion, high contrast, 200% zoom, system text scaling.
- Destructive confirmation asks what will be removed: app config, OS queue, output files separately.

## 8. Security, privacy, and offline rules
- No account required for local use; sign-in only if future sync/cloud capabilities are added.
- Listen on loopback by default; remote access opt-in with explicit warnings/authentication.
- Store sensitive generated outputs in a user-selected local path, permissions checked.
- Redact addresses, barcodes, customer names and document payloads from default analytics/log export.
- Print history retention configurable (default 30 days suggested), with “never auto-delete” opt-in.
- No printer/drivers/OS changes without explicit button and native permission dialogue.
- Use system credential stores, never plaintext credentials.
- Clear separation between simulator side effects and real fulfillment/shipping events.

## 9. Content and naming
Navigation text uses title case; actions use verbs: **Create Device**, **Install in OS**, **Run Test**, **Open Output**.  
Distinguish “Simulator online” from “Device installed”.  
Use descriptions like “Local printer queue detected” rather than “Real Brother printer connected”.  
Empty-state example: “No virtual devices yet. Create a printer or label maker to get started.”  
Unsupported-state example: “Windows scanner installation isn't available in this version. You can save a configuration preview.”

## 10. Design quality gates
1. Every page uses one visual token set and one app shell.
2. Wizard creates a Draft device even when OS installation is unsupported.
3. All install claims are backed by OS checks, not only engine responses.
4. Every printable device exposes an output artifact and retryable diagnostics.
5. Studio is optional; no baseline workflow depends on it.
6. No category is falsely presented as functional when only a mock card exists.
7. Light/dark, offline, permission denied, empty, busy and failed conditions are specified.
8. Tested at 1280×800, 1440×900, 1920×1080, 1024×768 and high-DPI scaling.
9. Save, Cancel, Delete, Uninstall and Restore are unambiguous and keyboard accessible.
10. Design sign-off occurs before implementing route/component scaffolding.
