# Devices Simulator v0.16.1 — Monochrome PWG and macOS CUPS gate

- Adds bounded `sgray_1` bit-packed PWG Raster decoding with one-bit pixel polarity, MSB-first bytes, and padded scanline strides.
- Existing 8-bit sGray and 24-bit sRGB paths remain unchanged; `pwg-raster-document-type-supported` now includes `sgray_1`.
- Adds independent in-app, source-JPG, and true HTTP IPP regression cases for monochrome data and malformed headers.
- Introduces a GitHub Actions macOS Apple Silicon CUPS end-to-end acceptance gate: driverless CUPS attempt (falling back to bundled PPD when macOS cannot generate driverless PPD) → IPP → persisted JPG for Brother and Zebra, with explicit cleanup and diagnostics.
- Updates README, IPP/PWG guide, diagnostic guide, GitHub Pages links and release notes.

Limitations: Does not certify IPP Everywhere or PrintNode, real Windows print-driver/OS output, physical printers, WIA/eSCL scanners, HID/USB/BLE devices or signed installers.

- Known limitation: the initial macOS hosted runner's `-m everywhere` negotiation failed with “Unable to create PPD file”; the fallback tests OS queue-to-JPG but does not certify driverless registration.
