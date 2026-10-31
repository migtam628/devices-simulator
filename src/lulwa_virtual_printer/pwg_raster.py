"""Bounded subset of the PWG 5102.4 RaS2 raster format.

Only 8-bit sGray (CUPS colorspace 18) and 24-bit sRGB (19), chunky order,
are supported. Unsupported color orders, bpp, stream variants and malformed
PackBits fail closed. This is not an IPP Everywhere certification.
"""
from __future__ import annotations

import struct
from PIL import Image

PWG_MAGIC = b"RaS2"
HEADER_SIZE = 1796
MAX_PAGES = 12
MAX_PAGE_PIXELS = 12_000_000
MAX_TOTAL_DECODED_BYTES = 128 * 1024 * 1024
MAX_DIMENSION = 8000


def _uint(header: bytes, offset: int) -> int:
    return struct.unpack_from(">I", header, offset)[0]


def decode_pwg_raster(data: bytes) -> list[Image.Image]:
    """Parse a complete PWG raster stream with no trailing bytes.

    The input has already been capped by the HTTP/IP P capture layer. Decoder
    limits additionally protect against tiny compressed streams claiming
    enormous uncompressed output.
    """
    if not isinstance(data, bytes) or not data.startswith(PWG_MAGIC):
        raise ValueError("PWG Raster requires a big-endian RaS2 header")
    pos = 4
    pages: list[Image.Image] = []
    total_decoded = 0
    while pos < len(data):
        if len(pages) >= MAX_PAGES:
            raise ValueError("PWG Raster page count exceeds limit")
        if len(data) - pos < HEADER_SIZE:
            raise ValueError("Truncated PWG Raster page header")
        header = data[pos:pos + HEADER_SIZE]
        pos += HEADER_SIZE
        width, height = _uint(header, 372), _uint(header, 376)
        bits_per_color = _uint(header, 384)
        bits_per_pixel = _uint(header, 388)
        bytes_per_line = _uint(header, 392)
        color_order = _uint(header, 396)
        color_space = _uint(header, 400)
        colors = _uint(header, 420)
        if not 1 <= width <= MAX_DIMENSION or not 1 <= height <= MAX_DIMENSION:
            raise ValueError("PWG Raster page dimensions out of range")
        if width * height > MAX_PAGE_PIXELS:
            raise ValueError("PWG Raster page pixel limit exceeded")
        if color_space == 18:
            channels, mode = 1, "L"
        elif color_space == 19:
            channels, mode = 3, "RGB"
        else:
            raise ValueError("Only PWG sGray_8 and sRGB_8 color spaces are supported")
        if (bits_per_color != 8 or bits_per_pixel != channels * 8
                or colors != channels or color_order != 0
                or bytes_per_line != width * channels):
            raise ValueError("Unsupported PWG Raster packing, sample depth or stride")
        page_size = bytes_per_line * height
        total_decoded += page_size
        if total_decoded > MAX_TOTAL_DECODED_BYTES:
            raise ValueError("PWG Raster decoded bytes exceed safety limit")
        page_bytes = bytearray()
        rows = 0
        while rows < height:
            if pos >= len(data):
                raise ValueError("Truncated PWG Raster row repetition count")
            repetitions = data[pos] + 1
            pos += 1
            if repetitions > height - rows:
                raise ValueError("PWG Raster row repeat exceeds page height")
            row = bytearray()
            while len(row) < bytes_per_line:
                if pos >= len(data):
                    raise ValueError("Truncated PWG Raster pixel run")
                run = data[pos]
                pos += 1
                if run < 128:
                    count = run + 1
                    if count * channels > bytes_per_line - len(row):
                        raise ValueError("PWG Raster pixel run exceeds row boundary")
                    if len(data) - pos < channels:
                        raise ValueError("Truncated PWG Raster repeated color")
                    pixel = data[pos:pos + channels]
                    pos += channels
                    row.extend(pixel * count)
                elif run > 128:
                    count = 257 - run
                    byte_count = count * channels
                    if byte_count > bytes_per_line - len(row):
                        raise ValueError("PWG Raster literal run exceeds row boundary")
                    if len(data) - pos < byte_count:
                        raise ValueError("Truncated PWG Raster literal colors")
                    row.extend(data[pos:pos + byte_count])
                    pos += byte_count
                else:
                    # 0x80 is PackBits's undefined/no-op code; deliberately
                    # disallow it so malformed input cannot skip boundaries.
                    raise ValueError("Unsupported PWG Raster PackBits control 0x80")
            page_bytes.extend(row * repetitions)
            rows += repetitions
        pages.append(Image.frombytes(mode, (width, height), bytes(page_bytes)).convert("RGB"))
    if not pages:
        raise ValueError("PWG Raster contains no pages")
    return pages
