"""Bounded, offline ZPL-II label preview for development and shipping QA.

Partial renderer, not Zebra firmware or barcode scannability certification.
Supported: ^XA,^XZ,^PW,^LL,^FO,^FT,^A0,^CF,^FD,^FS,^GB,^BY,^BC,
^FX,^FH, ^GFA (hex, ACS, :B64:, :Z64:), ^BQN model 2.
Commands not implemented deliberately fail rather than print silently wrong.
"""
from __future__ import annotations
import base64
import binascii
import re
import zlib

from PIL import Image, ImageDraw, ImageFont

MAX_LABEL_BYTES = 1024 * 1024
MAX_GRAPHIC_BYTES = 1100000
SUPPORTED = {
    "XA", "XZ", "PW", "LL", "FO", "FT", "A0", "CF", "FD", "FS",
    "GB", "BY", "BC", "FX", "FH", "GF", "BQ", "CI", "LH",
    "LS", "PR", "MD", "MN", "MM", "LT", "PQ",
}


def _font(height):
    try:
        return ImageFont.truetype("DejaVuSans.ttf", max(8, min(int(height), 160)))
    except (OSError, ValueError):
        return ImageFont.load_default()


def _hex_field(text: str, marker: str) -> str:
    """^FH escapes are bytes; this subset admits printable ASCII only."""
    def sub(match):
        ch = int(match.group(1), 16)
        if ch < 32 or ch > 126:
            raise ValueError("^FH preview supports printable ASCII escapes only")
        return chr(ch)
    return re.sub(re.escape(marker) + r"([0-9A-Fa-f]{2})", sub, text)


def _acs_raster(encoded: str, size: int, per_row: int) -> bytes:
    """Decode Zebra ASCII compressed hex (ACS) with strict row boundaries."""
    encoded = "".join(encoded.split())
    row_chars = per_row * 2
    rows = []
    row = ""
    prior = None
    i = 0
    while i < len(encoded):
        c = encoded[i]
        i += 1
        if c == ":":
            if row or prior is None:
                raise ValueError("Invalid ^GFA ACS previous-row marker")
            rows.append(prior)
            if len(rows) * per_row > size:
                raise ValueError("^GFA ACS raster exceeds expected size")
            continue
        if c in ",!":
            row += ("0" if c == "," else "F") * (row_chars - len(row))
        elif c in "GHIJKLMNOPQRSTUVWXY":
            if i >= len(encoded):
                raise ValueError("Incomplete ^GFA ACS repeat")
            n = ord(c) - ord("G") + 1
            row += encoded[i] * n
            i += 1
        elif c in "ghijklmnopqrstuvwxyz":
            if i >= len(encoded):
                raise ValueError("Incomplete ^GFA ACS repeat")
            n = (ord(c) - ord("g") + 1) * 20
            row += encoded[i] * n
            i += 1
        elif c in "0123456789abcdefABCDEF":
            row += c
        else:
            raise ValueError("Unsupported ^GFA ASCII-hex character")
        if len(row) > row_chars:
            raise ValueError("^GFA compressed row exceeds bytes-per-row")
        if len(row) == row_chars:
            rows.append(row)
            prior = row
            row = ""
            if len(rows) * per_row > size:
                raise ValueError("^GFA raster exceeds expected size")
    if row:
        raise ValueError("Incomplete ^GFA row")
    raw = bytes.fromhex("".join(rows))
    if len(raw) != size:
        raise ValueError("^GFA byte count does not match raster")
    return raw


def _graphic_payload(arg: str) -> tuple[bytes, int]:
    fields = arg.split(",", 4)
    if len(fields) != 5 or fields[0] != "A":
        raise ValueError("Only ^GFA ASCII graphics are supported")
    try:
        sent, total, row_bytes = (int(v) for v in fields[1:4])
    except ValueError as exc:
        raise ValueError("Invalid ^GFA byte counts") from exc
    if not (1 <= total <= MAX_GRAPHIC_BYTES and 1 <= row_bytes <= 300
            and total % row_bytes == 0 and total // row_bytes <= 3600
            and 1 <= sent <= MAX_GRAPHIC_BYTES):
        raise ValueError("^GFA raster dimensions or byte counts exceed limits")
    data = fields[4].strip()
    if data.startswith((":Z64:", ":B64:")):
        mode = data[1:4]
        chunks = data.split(":")
        if len(chunks) != 4 or not re.fullmatch("[0-9A-Fa-f]{4}", chunks[3]):
            raise ValueError("Invalid ^GFA Base64 envelope or CRC")
        encoded = chunks[2]
        if not encoded or len(encoded) > MAX_LABEL_BYTES:
            raise ValueError("Oversized ^GFA Base64 graphic")
        crc = binascii.crc_hqx(encoded.encode("ascii"), 0)
        if crc != int(chunks[3], 16):
            raise ValueError("^GFA Base64 CRC mismatch")
        try:
            payload = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise ValueError("Invalid ^GFA Base64 data") from exc
        # Common encoders use either compressed byte count or uncompressed count.
        if sent not in (len(payload), total):
            raise ValueError("^GFA transmitted byte count mismatch")
        if mode == "Z64":
            decomp = zlib.decompressobj()
            try:
                raw = decomp.decompress(payload, total + 1)
                if len(raw) > total:
                    raise ValueError("Oversized ^GFA Z64 stream")
                raw += decomp.flush(total + 1 - len(raw))
            except zlib.error as exc:
                raise ValueError("Invalid ^GFA Z64 stream") from exc
            if not decomp.eof or decomp.unused_data or decomp.unconsumed_tail:
                raise ValueError("Incomplete or oversized ^GFA Z64 stream")
        else:
            raw = payload
        if len(raw) != total:
            raise ValueError("^GFA decompressed byte count mismatch")
        return raw, row_bytes
    if sent != total:
        raise ValueError("^GFA ASCII byte counts must match")
    return _acs_raster(data, total, row_bytes), row_bytes


def _paint_graphic(canvas: Image.Image, data: str, x: int, y: int):
    raw, row_bytes = _graphic_payload(data)
    pixels = bytes(b ^ 255 for b in raw)
    raster = Image.frombytes("1", (row_bytes * 8, len(raw) // row_bytes), pixels)
    canvas.paste(raster.convert("RGB"), (x, y))


def _paint_qr(canvas: Image.Image, data: str, magnification: int, x: int, y: int):
    if not data.startswith("LA,"):
        raise ValueError("Only ^BQN model 2 with ^FDLA,data is supported")
    content = data[3:]
    if not content or len(content) > 800:
        raise ValueError("^BQN data must contain 1 to 800 characters")
    import qrcode
    qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_M,
                       box_size=1, border=0)
    qr.add_data(content)
    try:
        qr.make(fit=True)
    except (ValueError, qrcode.exceptions.DataOverflowError) as exc:
        raise ValueError("^BQN content exceeds QR capacity") from exc
    bitmap = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    w, h = bitmap.size
    if x < 0 or y < 0 or x + w * magnification > canvas.width or y + h * magnification > canvas.height:
        raise ValueError("^BQN QR code exceeds label dimensions")
    bitmap = bitmap.resize((w * magnification, h * magnification), Image.Resampling.NEAREST)
    canvas.paste(bitmap, (x, y))


def render_zpl(data: bytes, dpi: int = 203) -> Image.Image:
    if len(data) > MAX_LABEL_BYTES:
        raise ValueError("ZPL label exceeds 1 MiB limit")
    try:
        text = data.decode("ascii")
    except UnicodeDecodeError as exc:
        raise ValueError("ZPL requires ASCII data (^FH for escaped printable bytes)") from exc
    if not text.lstrip().startswith("^XA") or "^XZ" not in text:
        raise ValueError("ZPL job requires ^XA and ^XZ")
    commands = re.findall(r"\^([A-Z0-9]{2})([^\^~]*)", text)
    width, height = 4 * dpi, 6 * dpi
    for op, args in commands:
        if op == "PW":
            width = int(args.strip())
        elif op == "LL":
            height = int(args.strip())
    if not (64 <= width <= 2400 and 64 <= height <= 3600):
        raise ValueError("ZPL label dimensions out of supported range")
    canvas = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(canvas)
    x = y = 0
    font_height = 30
    bar_width, bar_height = 2, 100
    field_type = "text"
    field_hex = None
    field_text = None
    qr_magnification = 4
    seen_end = False
    for op, args in commands:
        arg = args.strip()
        if op == "XZ":
            seen_end = True
            break
        if op not in SUPPORTED:
            raise ValueError(f"ZPL command ^{op} is not supported by this preview renderer")
        if op == "FH":
            marker = arg or "_"
            if len(marker) != 1 or marker in "^~":
                raise ValueError("Invalid ^FH escape indicator")
            field_hex = marker
        elif op in {"FO", "FT"}:
            vals = arg.split(",")
            if len(vals) >= 2:
                x, y = int(vals[0]), int(vals[1])
            if x < 0 or y < 0:
                raise ValueError("Negative ZPL field location")
        elif op in {"A0", "CF"}:
            vals = arg.split(",")
            font_height = int(vals[1]) if len(vals) >= 2 and vals[1] else 30
        elif op == "BY":
            vals = arg.split(",")
            bar_width = max(1, min(int(vals[0]), 8)) if vals[0] else 2
            if len(vals) > 2 and vals[2]:
                bar_height = int(vals[2])
        elif op == "BC":
            vals = arg.split(",")
            if vals and vals[0] not in ("N", ""):
                raise ValueError("Only horizontal ^BC Code128 is supported")
            bar_height = int(vals[1]) if len(vals) > 1 and vals[1] else bar_height
            field_type = "barcode"
        elif op == "BQ":
            vals = arg.split(",")
            if len(vals) < 2 or vals[0] not in ("N", "") or vals[1] != "2":
                raise ValueError("Only ^BQN model 2 is supported")
            qr_magnification = int(vals[2]) if len(vals) > 2 and vals[2] else 4
            if not 1 <= qr_magnification <= 10:
                raise ValueError("^BQN magnification out of range")
            field_type = "qr"
        elif op == "GB":
            vals = arg.split(",")
            if len(vals) >= 2:
                w, h = int(vals[0]), int(vals[1])
                thick = max(1, int(vals[2])) if len(vals) > 2 and vals[2] else 1
                if w < 0 or h < 0:
                    raise ValueError("Invalid ^GB dimensions")
                draw.rectangle((x, y, x+w, y+h), outline="black", width=thick)
        elif op == "GF":
            _paint_graphic(canvas, arg, x, y)
        elif op == "FD":
            field_text = _hex_field(arg, field_hex) if field_hex else arg
            field_hex = None
        elif op == "FS":
            if field_text is not None:
                if field_type == "barcode":
                    if not re.fullmatch(r"[\x20-\x7e]{1,100}", field_text):
                        raise ValueError("Code128 data must be printable ASCII")
                    from barcode.codex import Code128
                    bits = "".join(Code128(field_text).build())
                    extent = len(bits) * bar_width
                    if extent > width - x:
                        raise ValueError("Code128 barcode exceeds label width")
                    for i, bit in enumerate(bits):
                        if bit == "1":
                            left = x + i * bar_width
                            draw.rectangle((left, y, left + bar_width - 1, y + bar_height - 1), fill="black")
                elif field_type == "qr":
                    _paint_qr(canvas, field_text, qr_magnification, x, y)
                else:
                    draw.text((x, y), field_text, font=_font(font_height), fill="black")
                field_text = None
            field_type = "text"
    if not seen_end:
        raise ValueError("ZPL missing ^XZ")
    return canvas
