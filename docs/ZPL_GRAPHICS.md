# ZPL shipping-label graphics and QR preview (v0.14.2)

The local renderer produces **JPG previews**, not validated Zebra firmware output.
It accepts a carefully bounded subset of ZPL-II to avoid silently producing a
label that differs from a physical printer.

## Added operations

| Command | Support | Boundaries |
|---|---|---|
| `^GFA,b,c,d,hex` | Inline 1-bit image, row-major, 1=black | Compression type A, byte counts and row size validated |
| `^GFA,...,:B64:data:crc` | Base64 raster with CRC-16/XMODEM check | Decoded length must match declared raster |
| `^GFA,...,:Z64:data:crc` | zlib-compressed Base64 with CRC check | Bounded inflate, no trailing compressed data |
| ACS ASCII repeat encodings | Repeat characters and row-fill/repeat markers | Incomplete or oversized rows rejected |
| `^FH` | Printable ASCII hexadecimal field escapes | Nonprintable binary, arbitrary Unicode codepages unsupported |
| `^BQN,2,mag` + `^FDLA,text` | QR model 2 bitmap preview | Magnification 1–10, <=800 characters, fit entirely on page |

Graphic bytes are capped by the configured label size and an absolute ~1.1 MB
raster limit; the entire raw ZPL job is capped at 1 MiB. Decompression bombs,
CRC mismatches, unsupported encodings and invalid bitmap geometry fail explicitly.
These checks protect the local tool; they are not a substitute for verifying
barcode readability or label physical dimensions on a target printer.

## Example

```zpl
^XA
^PW812
^LL1218
^FO40,30^A0N,35,35^FDPACKING STATION^FS
^FO40,90^BQN,2,6^FDLA,ORDER-1001^FS
^FO40,300^GFA,8,8,2,FFFF80018001FFFF^FS
^XZ
```

The compact ^GFA data draws four 16-pixel rows at x=40, y=300;
the QR encodes ORDER-1001. Preview with the existing local JPG capture
or the Zebra device fixture.

## Known limitations

This is not a comprehensive carrier-label interpreter. Unsupported ZPL drawing
commands, arbitrary font download, full graphics download/recall, rotated QR,
multiline ^FB, variable format encodings, ESC/POS receipt commands, and
physical barcode scan validation remain separate work. This version does
not change Windows IPP printer driver formats; IPP Everywhere certification
requires standards-compliant PWG Raster and discovery support beyond the
current experimental service.

## References

- [Official Zebra Programming Guide](https://cpws.zebra.com/cpws/docs/zpl/zpl_manual.pdf)
- [Printer Working Group IPP Everywhere](https://www.pwg.org/ipp/everywhere.html)
