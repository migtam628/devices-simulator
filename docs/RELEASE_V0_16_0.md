# Devices Simulator v0.16.0 — PWG Raster IPP-to-JPG

- Implements a bounded, streamable page parser for PWG `RaS2` documents: 1796-byte CUPS v2 page headers, 8-bit sGray and 24-bit sRGB chunky pixel formats and PackBits-style compressed scanlines.
- Supports up to 12 pages / 12 million pixels per page / 128 MiB decoded total; page/stride/row controls are strictly checked.
- IPP advertises `image/pwg-raster` for the simulated Brother and Zebra endpoints, including supported sGray_8 and sRGB_8 document types.
- Persists original.pwg and a JPG for every decoded page; rejects incorrect MIME, malformed bytes, unsupported raster variants and excessive output without false success claims.
- Adds bitmap-accurate, adversarial and live HTTP IPP integration tests.
- Updates README, PWG raster guide, OS diagnostics and GitHub Pages version links.

Still experimental and **not IPP Everywhere certification**. Live physical Windows/macOS spooler compatibility, PrintNode acceptance, URF, proprietary scanner/HID/USB drivers and signed installers remain separate tasks.
