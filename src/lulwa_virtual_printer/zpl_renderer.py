"""Limited local ZPL-II renderer for development labels only.

Supported: ^XA,^XZ,^PW,^LL,^FO,^FT,^A0,^CF,^FD,^FS,^GB,^BY,^BC,^FX.
Code128 is rendered with python-barcode. Unsupported drawing commands FAIL,
rather than silently produce an inaccurate shipping label. Not a Zebra emulator.
"""
from __future__ import annotations
import re
from PIL import Image, ImageDraw, ImageFont


def _font(height):
    try:
        return ImageFont.truetype("DejaVuSans.ttf", max(8, min(int(height), 160)))
    except (OSError, ValueError):
        return ImageFont.load_default()


def render_zpl(data: bytes, dpi: int = 203) -> Image.Image:
    try:
        text = data.decode("ascii")
    except UnicodeDecodeError as exc:
        raise ValueError("ZPL requires ASCII input for this renderer") from exc
    if not text.lstrip().startswith("^XA") or "^XZ" not in text:
        raise ValueError("ZPL job requires ^XA and ^XZ")
    if len(data) > 1024 * 1024:
        raise ValueError("ZPL label exceeds 1 MiB limit")
    # Coordinates are interpreted as dots at the configured print resolution.
    width, length = 4 * dpi, 6 * dpi
    command_list = re.findall(r"\^([A-Z0-9]{2})([^\^~]*)", text)
    for op, args in command_list:
        if op == "PW":
            width = int(args.strip())
        if op == "LL":
            length = int(args.strip())
    if not (64 <= width <= 2400 and 64 <= length <= 3600):
        raise ValueError("ZPL label dimensions out of supported range")
    img = Image.new("RGB", (width, length), "white")
    draw = ImageDraw.Draw(img)
    x = y = 0
    font_height = 30
    barcode_width, barcode_height = 2, 100
    barcode = False
    current_text = None
    seen_end = False
    ignored = {"XA", "PW", "LL", "CI", "LH", "LS", "PR", "MD", "MN", "MM", "LT", "BY", "PQ", "FX", "FS", "FO", "FT", "A0", "CF", "FD", "GB", "BC", "XZ"}
    for op, args in command_list:
        arg = args.strip()
        if op == "XZ":
            seen_end = True
            break
        if op not in ignored:
            raise ValueError(f"ZPL command ^{op} is not supported by this preview renderer")
        if op in {"FO", "FT"}:
            vals = arg.split(",")
            if len(vals) >= 2:
                x, y = int(vals[0]), int(vals[1])
        elif op == "A0":
            vals = arg.split(",")
            font_height = int(vals[1]) if len(vals) >= 2 and vals[1] else 30
        elif op == "CF":
            vals = arg.split(",")
            font_height = int(vals[1]) if len(vals) >= 2 and vals[1] else 30
        elif op == "BY":
            vals = arg.split(",")
            barcode_width = max(1, min(int(vals[0]), 8)) if vals[0] else 2
            if len(vals) > 2 and vals[2]:
                barcode_height = int(vals[2])
        elif op == "BC":
            vals = arg.split(",")
            if vals and vals[0] not in ("N", ""):
                raise ValueError("Only horizontal ^BC Code128 is supported")
            barcode_height = int(vals[1]) if len(vals) > 1 and vals[1] else barcode_height
            barcode = True
        elif op == "GB":
            vals = arg.split(",")
            if len(vals) >= 2:
                w, h = int(vals[0]), int(vals[1])
                thick = max(1, int(vals[2])) if len(vals) > 2 and vals[2] else 1
                if w < 0 or h < 0:
                    raise ValueError("Invalid ^GB dimensions")
                draw.rectangle((x, y, x+w, y+h), outline="black", width=thick)
        elif op == "FD":
            current_text = arg
        elif op == "FS":
            if current_text is not None:
                if barcode:
                    if not re.fullmatch(r"[\x20-\x7e]{1,100}", current_text):
                        raise ValueError("Code128 data must be printable ASCII")
                    from barcode.codex import Code128
                    bits = "".join(Code128(current_text).build())
                    extent = len(bits) * barcode_width
                    if extent > width - x:
                        raise ValueError("Code128 barcode exceeds label width")
                    left = x
                    for bit in bits:
                        if bit == "1":
                            draw.rectangle((left, y, left + barcode_width - 1, y + barcode_height - 1), fill="black")
                        left += barcode_width
                else:
                    draw.text((x, y), current_text, font=_font(font_height), fill="black")
                current_text = None
            barcode = False
    if not seen_end:
        raise ValueError("ZPL missing ^XZ")
    return img
