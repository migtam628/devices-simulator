# Devices Simulator v0.14.2 — Zebra graphics and QR label preview

- Support `^GFA` inline bitmap fields with strict dimensions, ASCII hex, ACS repeat/row markers, `:B64:`, and `:Z64:` deflated raster.
- Validate Base64 CRC16, raster byte counts, bounded decompress size and image placement.
- Support `^BQN,2,N` model-2 QR preview and printable ASCII escapes with `^FH`.
- Preserve existing Code128, text, boxes, local captures and JPEG storage.
- Include pixel-level regression tests and malformed-input/fuzz-style safety cases.
- README, GitHub Pages, and detailed documentation updated.

Limits: noncomprehensive ZPL, not a Zebra emulator or label scan certification; Windows/macOS native OS printing and IPP Everywhere support remain experimental; native USB/BLE and production signing remain open.
