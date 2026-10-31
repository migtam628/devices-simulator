"""Strict, bounded ESC/POS receipt preview (not an OS receipt driver).

Supported subset: ESC @, ESC a, ESC E, ESC !, GS !, GS V,
GS v 0 (legacy raster image), CR, LF, HT, printable CP437 text.
Unsupported control commands fail visibly instead of creating bad receipts.
"""
from __future__ import annotations
from PIL import Image, ImageDraw, ImageFont

WIDTH = 576  # 80 mm roll at typical 203dpi (printable width varies by model)
MAX_INPUT = 1024 * 1024
MAX_HEIGHT = 6000
MAX_RASTER_BYTES = 600000


def _font(size=22):
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size)
    except (OSError, ValueError):
        return ImageFont.load_default()


def render_escpos(data: bytes, dpi: int = 203) -> Image.Image:
    if len(data) > MAX_INPUT:
        raise ValueError("ESC/POS fixture exceeds 1 MiB limit")
    if not data.startswith(b"\x1b@"):
        raise ValueError("ESC/POS receipt must start with ESC @")
    if dpi != 203:
        raise ValueError("This ESC/POS preview models 203 DPI receipt paper")
    items = []
    line = bytearray()
    align, bold, scale_x, scale_y = 0, False, 1, 1
    cursor = 0

    def flush(force=False):
        if line or force:
            text = bytes(line).decode("cp437")
            line.clear()
            items.append(("line", text, align, bold, scale_x, scale_y))

    while cursor < len(data):
        ch = data[cursor]
        cursor += 1
        if ch == 0x1B:
            if cursor >= len(data):
                raise ValueError("Truncated ESC/POS ESC command")
            cmd = data[cursor]
            cursor += 1
            if cmd == ord("@"):
                flush()
                align, bold, scale_x, scale_y = 0, False, 1, 1
            elif cmd in (ord("a"), ord("E"), ord("!"), ord("d")):
                if cursor >= len(data):
                    raise ValueError("Truncated ESC/POS command argument")
                val = data[cursor]
                cursor += 1
                if cmd == ord("a"):
                    if val not in (0,1,2,48,49,50):
                        raise ValueError("Unsupported ESC/POS alignment")
                    flush()
                    align = val - 48 if val >= 48 else val
                elif cmd == ord("E"):
                    flush()
                    bold = bool(val & 1)
                elif cmd == ord("!"):
                    flush()
                    if val & ~0x38:
                        raise ValueError("Unsupported ESC/POS print-mode bits")
                    bold = bool(val & 0x08)
                    scale_x = 2 if val & 0x20 else 1
                    scale_y = 2 if val & 0x10 else 1
                else:
                    if val > 20:
                        raise ValueError("ESC/POS paper-feed too long")
                    flush()
                    for _ in range(val):
                        flush(force=True)
            else:
                raise ValueError(f"Unsupported ESC/POS ESC command 0x{cmd:02X}")
        elif ch == 0x1D:
            if cursor >= len(data):
                raise ValueError("Truncated ESC/POS GS command")
            cmd=data[cursor]
            cursor += 1
            if cmd == ord("!"):
                if cursor >= len(data):
                    raise ValueError("Truncated ESC/POS character-size command")
                val=data[cursor]
                cursor += 1
                if (val & 15) > 3 or (val >> 4) > 3:
                    raise ValueError("ESC/POS text magnification exceeds preview limit")
                flush()
                scale_x = 1 + (val >> 4)
                scale_y = 1 + (val & 15)
            elif cmd == ord("V"):
                if cursor >= len(data):
                    raise ValueError("Truncated ESC/POS paper-cut command")
                mode=data[cursor]
                cursor += 1
                if mode not in (0,1,48,49):
                    raise ValueError("Unsupported ESC/POS paper-cut mode")
                flush()
                # Cut is only a preview boundary, not a physical hardware action.
            elif cmd == ord("v"):
                if cursor + 6 > len(data) or data[cursor] != ord("0"):
                    raise ValueError("Unsupported ESC/POS raster graphics command")
                mode,xlo,xhi,ylo,yhi = data[cursor+1:cursor+6]
                cursor += 6
                if mode not in (0,1,2,3,48,49,50,51):
                    raise ValueError("Unsupported ESC/POS raster mode")
                mode = mode - 48 if mode >= 48 else mode
                row_bytes = xlo + 256*xhi
                height = ylo + 256*yhi
                size = row_bytes * height
                fx = 2 if mode & 1 else 1
                fy = 2 if mode & 2 else 1
                if not (1 <= row_bytes <= WIDTH // 8 and 1 <= height <= MAX_HEIGHT and
                        1 <= size <= MAX_RASTER_BYTES and row_bytes*8*fx <= WIDTH):
                    raise ValueError("ESC/POS raster dimensions out of range")
                if cursor + size > len(data):
                    raise ValueError("Truncated ESC/POS raster payload")
                raw=data[cursor:cursor+size]
                cursor += size
                flush()
                pix=Image.frombytes("1",(row_bytes*8,height),bytes(x^255 for x in raw))
                raster=pix.convert("RGB")
                if fx>1 or fy>1:
                    raster=raster.resize((raster.width*fx,raster.height*fy),Image.Resampling.NEAREST)
                items.append(("image",raster,align))
            else:
                raise ValueError(f"Unsupported ESC/POS GS command 0x{cmd:02X}")
        elif ch in (0x0A,0x0D):
            if ch == 0x0A:
                flush(force=True)
            # CR is ignored; CRLF creates only one line.
        elif ch == 0x09:
            line.extend(b"    ")
        elif ch >= 32:
            line.append(ch)
            if len(line) > 800:
                raise ValueError("ESC/POS line exceeds 800 characters")
        else:
            raise ValueError(f"Unsupported ESC/POS control byte 0x{ch:02X}")
    flush()

    planned=[]
    total_h=12
    for item in items:
        if item[0] == "image":
            block=item[1]
            height=block.height+6
            planned.append((item,block,height))
        else:
            _,txt,alignment,strong,sx,sy=item
            font=_font(22)
            bbox=font.getbbox(txt or " ")
            w=max(1,bbox[2]-bbox[0]+4)
            h=max(28,bbox[3]-bbox[1]+12)
            block=Image.new("RGB",(w,h),"white")
            draw=ImageDraw.Draw(block)
            draw.text((2-bbox[0],4-bbox[1]),txt,font=font,fill="black")
            if strong:
                draw.text((3-bbox[0],4-bbox[1]),txt,font=font,fill="black")
            if sx!=1 or sy!=1:
                block=block.resize((block.width*sx,block.height*sy),Image.Resampling.NEAREST)
            if block.width > WIDTH-16:
                raise ValueError("ESC/POS text exceeds receipt width")
            height=block.height+3
            planned.append((item,block,height))
        total_h += height
        if total_h > MAX_HEIGHT:
            raise ValueError("ESC/POS receipt exceeds maximum page height")
    canvas=Image.new("RGB",(WIDTH,max(48,total_h+12)),"white")
    y=8
    for item,block,inc in planned:
        alignment=item[2]
        x=(8 if alignment==0 else (WIDTH-block.width)//2 if alignment==1
           else WIDTH-8-block.width)
        canvas.paste(block,(max(0,x),y))
        y += inc
    return canvas
