# Devices Simulator v0.15.0 — In-app ESC/POS receipt capture

- Functional 80mm, nominal 203dpi receipt preview from fixed-format ESC/POS byte streams, producing persistent JPGs via the existing local capture engine.
- Added `receipt` profile in the device Hub, sample receipt generation, receipt device detail controls and raw `.escpos`/`.bin` import.
- Supports ESC @, ESC a, ESC E, ESC !, ESC d, GS !, GS v 0 1-bit raster, GS V, CP437 text, line feed, carriage return and tabs.
- Validates byte counts, raster dimensions, text width, maximum input and page height; unknown printer commands fail explicitly.
- Added pixel-level raster, malformed input, capture persistence and Hub-device tests.
- README, receipt guide, company evaluation, and GitHub Pages download links updated.

Limitations: The receipt profile is in-app only, not enumerated as a printer by an operating system. It does not offer real ESC/POS printer transport, PrintNode certification, cash-drawer or cutter hardware, or ESC/POS command completeness.
