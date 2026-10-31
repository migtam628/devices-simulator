# ESC/POS 80mm receipt fixture — v0.15.0

The Devices Simulator receipt profile can now produce a **real local JPG**
preview from a subset of ESC/POS command streams. It is not an installed
Windows/macOS/Linux receipt printer, a USB peripheral, a network-connected
receipt server, or an Epson vendor-certified emulator.

## Create and test a receipt

Open **Create Device → Receipt Printer** and save a supported profile.
Open the device and select **Generate Sample**. The resulting JPG, original
ESC/POS bytes and job.json metadata are written to the normal local output
root under `receipt/<job-name>/`. You can also import a test file ending in
`.escpos` or `.bin` from the device detail. File bytes must start with
`ESC @` (`1B 40`).

The renderer currently models a 576-dot wide, nominal 80mm roll at 203dpi.
Actual printers have model-specific print widths and fonts; do not use the
preview to certify physical receipts.

| ESC/POS operation | Preview behavior |
|---|---|
| ESC @ | Reset text style, scaling and alignment |
| ESC a n | Left/center/right aligned lines |
| ESC E n | Emphasized/bold text |
| ESC ! n, GS ! n | Constrained character scaling |
| LF, CR, HT | Line feed, ignored CR, expanded tab |
| ESC d n | Bounded paper feed |
| GS v 0 m xL xH yL yH data | 1-bit raster image, scaled only in valid modes |
| GS V m | Recognizes valid paper-cut modes; no physical cut |

The raster command uses Epson's documented row-major 1-bit layout. Every
embedded image and command argument is length-checked; bad or unsupported
commands fail rather than quietly creating an inaccurate receipt. Source
bytes are capped at 1 MiB, raster data at 600,000 bytes, and final preview
height at 6,000 dots. Code page handling is CP437 only.

Example source bytes in Python:

```python
sample = (b"\x1b@\x1ba\x01LULWA SWIM\n"
          b"\x1ba\x00\x1bE\x01TOTAL $20.00\x1bE\x00\n"
          b"\x1dV\x00")
```

Use `lulwa-print sample.escpos --profile receipt` to inspect output
without a saved device. Do not feed actual customer receipts into a
publicly shared folder; locally captured files can contain PII.

**Not implemented:** native OS printer registration for this receipt profile,
cash drawer pulses, full code pages, downloaded fonts, all graphics modes,
NV memory, fiscal protocol, printer status queries, real cutting, and
PrintNode/physical-device certification. Unsupported commands are explicit
errors, not simulated successes.

References:
- [Epson official ESC/POS command catalog](https://download4.epson.biz/sec_pubs/pos/reference_en/escpos/commands.html)
- [Epson GS v 0 raster layout](https://download4.epson.biz/sec_pubs/pos/reference_en/escpos/gs_lv_0.html)
