# PWG Raster (RaS2) → JPG integration — v0.16.0

Devices Simulator now accepts an explicitly constrained subset of the
[PWG Raster Format (PWG 5102.4)](https://ftp.pwg.org/pub/pwg/candidates/cs-ippraster10-20120420-5102.4.pdf)
on its **loopback-only** IPP endpoints. This milestone implements **real
bitmap parsing**, not a generic PDF pass-through or image with an invented
extension.

## Supported subset

| Item | Implementation |
|---|---|
| IPP MIME type | `image/pwg-raster` |
| Signature | Big-endian `RaS2` (CUPS raster v2 / PWG raster family) |
| Header | Exactly 1796 bytes per page, network-order integers |
| Pixel formats | 8-bit sGray (colorspace 18), 24-bit sRGB (19) |
| Raster layout | Chunky color order 0 with exact per-row pixel stride |
| Compression | PackBits-style repeated / literal pixel runs and repeated scanlines |
| Multi-page | Up to 12 independent pages in one stream; one JPG per page |
| Preserved sources | `original.pwg`, `job.json`, `page-001.jpg`, etc. |
| Maximum page | 8,000 pixels on a side and 12,000,000 pixels per page |
| Decoded bytes | 128 MiB across the entire input stream |

The IPP printer attributes advertise `document-format-supported` for
PDF/PNG/JPEG and PWG raster (plus vendor ZPL for the simulated Zebra).
The `pwg-raster-document-type-supported` values are limited to
`sgray_8` and `srgb_8`. Clients can also use
`application/octet-stream` if the `RaS2` magic is present.

Unsupported `RaS3`, `2SaR`, 1-bit monochrome, CMYK, 16-bit,
banded/planar, arbitrary CUPS-specific rasters and Apple URF are
**rejected**, not silently reinterpreted. The parser checks row
repetition boundaries, pixel runs, declared stride, total page
dimensions and memory before decoding or saving JPGs.

## Test procedure

1. Start the Devices Simulator Hub/desktop and the attached local IPP
   listener.
2. Choose a **simulator** endpoint:
   `ipp://127.0.0.1:8631/ipp/brother` (Letter) or
   `ipp://127.0.0.1:8631/ipp/zebra` (4x6 label).
3. Use an IPP client that can send `image/pwg-raster` directly or let
   the operating-system spooler produce the supported raster format.
4. Inspect `http://127.0.0.1:8631/diagnostics` for the incoming
   `document_format`, IPP status and capture status.
5. Open the local Gallery; verify a nonempty JPG and the preserved
   `original.pwg` under the selected printer profile.

The automated suite `tests/test_pwg_raster.py` constructs independent
PWG-formatted byte streams (gray, RGB, repeated rows and multi-page)
and sends real socket IPP requests. The separate Linux CI CUPS test
verifies OS spooler → IPP → JPG on its configured runtime.

**Scope boundary:** This is a subset decoder only. It does not
implement all of IPP Everywhere's discovery, printer-state or
media/color contract and has **not** been validated through a real
Windows/macOS print dialog or PrintNode Client. Treat those as
separate device-side acceptance milestones.

### Technical references

- [CUPS Raster Format, version 2 and compressed scanline coding](https://www.cups.org/doc/spec-raster.html)
- [Chromium PWG encoder source and header fields](https://chromium.googlesource.com/chromium/src/+/refs/tags/141.0.7345.1/components/pwg_encoder/pwg_encoder.cc)
- [OpenPrinting CUPS Raster API](https://openprinting.github.io/cups/doc/api-raster.html)
