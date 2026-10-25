# Devices Simulator — Visual Mockup Review v1.0
**Date:** October 25, 2026  
**Direction:** Hybrid — Device Hub Pro + Command Center + Advanced Studio  
**Status:** Seven visual screens rendered for review; **design prototype only**

## Visual preview deliverable
Seven independent 1440×900 full-screen mockups and an HTML screen-switching preview were delivered as a separate ZIP in the design review conversation. Binary PNGs are **not** stored in the repository by this commit. They can be copied into `docs/design/mockups/screens/` after approval; the repository remains the canonical source for specifications.

The preview package includes:
- `preview.html` — static browser design preview with navigation among seven pages
- `screens/home.png` — Home dashboard and quick create
- `screens/wizard.png` — Six-step creation wizard
- `screens/brother.png` — Brother two-tray configuration
- `screens/zebra.png` — Zebra 4×6 thermal label configuration
- `screens/diagnostics.png` — Operational diagnostics surface
- `screens/gallery.png` — Output image gallery
- `screens/studio.png` — Optional node-based workflow canvas
- `contact-sheet.png` and `assets/concept-board.png` — comparative visuals

The mockups supplement, rather than supersede, [Master Design System](01_MASTER_DESIGN_SYSTEM.md), [Page Specifications](02_PAGE_SPECIFICATIONS.md) and [Support Matrix](03_SUPPORT_MATRIX_AND_HANDOFF.md).

## Cross-screen design decisions
- Dark navy 232–248px sidebar on premium light page canvas, consistent top bar and typography
- Restrained blue for primary controls, teal for operations, purple for Studio
- Distinct Brother tray illustrations vs Zebra vertical label preview
- Dark diagnostic telemetry area retained inside the same global app shell
- No baseline task requires the advanced Studio
- Device creation remains a six-step wizard with explicit OS-registration verification
- Sample data is explicitly marked as illustrative; current OS support is **experimental**
- JPG capture results are not equivalent to actual physical printing or shipping fulfillment

## Review checklist by screen
| Screen | Priority | Key acceptance |
| --- | --- | --- |
| Home | P0 | Device states and test status separate; clear Create Device path |
| Create Wizard | P0 | Six steps, Save Draft, OS compatibility before install |
| Brother Config | P0 | Tray 1/Tray 2 distinct, output size/DPI, test routing |
| Zebra Config | P0 | True 4×6 portrait media ratio, 203 DPI, ZPL plainly planned |
| Diagnostics | P0 | API-only vs OS integration tests never conflated |
| Output Gallery | P0 | JPG previews and job metadata; example content visibly demo |
| Studio | P2 | Optional graph view; no implicit OS changes |

## Before implementation
1. Approve or revise shell density, palette and spacing.
2. Confirm wizard supports both experienced and new users.
3. Confirm Brother and Zebra configuration screens feel meaningfully distinct.
4. Validate design at 1280×800, dark theme, 200% scaling, reduced motion, and keyboard-only usage.
5. Complete the current backend compatibility checklist before allowing the UI to show “OS Registered”.
6. Build shared UI foundation and implement the first **true native installed virtual printer** vertical slice, not merely sample dashboard cards.

## Out of scope of this design pass
No working desktop backend, installer, scanner registration, ZPL renderer or PrintNode integration was added in this work. The live repository's experimental IPP implementation remains unchanged.

## Suggested commit structure for implementation
- feat(ui): shared tokens, shell and route skeleton
- feat(ui): device catalog and wizard draft flow
- feat(ui): Brother & Zebra configuration
- feat(ui): captured jobs, outputs, diagnostics
- feat(native): platform printer installation and OS verification
- feat(ui): advanced Studio after printer workflow is proven

**Release gate:** Do not mark printer installation or native scanner functionality ready until tested on actual Windows, macOS and Linux hosts.
