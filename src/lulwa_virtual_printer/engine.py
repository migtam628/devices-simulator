"""Safe job capture and rasterization. Processed output is separate from input."""
from __future__ import annotations

import io
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from PIL import Image

PROFILES = {
    "brother-tray1": {"printer": "Brother", "tray": "Tray 1", "dpi": 300},
    "brother-tray2": {"printer": "Brother", "tray": "Tray 2", "dpi": 300},
    "zebra": {"printer": "Zebra", "tray": "4x6 roll", "dpi": 203},
    "scanner": {"printer": "Scanner Fixture", "tray": "flatbed preview", "dpi": 300},
    "receipt": {"printer": "Generic Receipt Fixture", "tray": "80mm roll", "dpi": 203},
}


def safe_name(text: str) -> str:
    return (re.sub(r"[^A-Za-z0-9_-]+", "-", text).strip("-")[:64] or "job")


def detect_format(data: bytes) -> str:
    if data.startswith(b"RaS2"):
        return "pwg-raster"
    if data.startswith(b"%PDF-"):
        return "pdf"
    if data.startswith(b"%!"):
        return "postscript"
    if data.lstrip().startswith(b"^XA"):
        return "zpl"
    if data.startswith(b"\x1b@"):
        return "escpos"
    if data[:4] == b"\x89PNG" or data.startswith(b"\xff\xd8\xff"):
        return "image"
    raise ValueError("Unsupported job data. Supply PDF, PostScript, JPG, PNG, PWG Raster, ZPL or ESC/POS.")


def render_pdf(data: bytes, dpi: int) -> list[Image.Image]:
    import fitz
    pages = []
    with fitz.open(stream=data, filetype="pdf") as document:
        if document.page_count > 100:
            raise ValueError("Maximum 100 pages per job")
        for page in document:
            pix = page.get_pixmap(matrix=fitz.Matrix(dpi / 72, dpi / 72), colorspace=fitz.csRGB, alpha=False)
            pages.append(Image.frombytes("RGB", (pix.width, pix.height), pix.samples))
    return pages


def render_job(data: bytes, dpi: int, fmt: str | None = None) -> list[Image.Image]:
    fmt = fmt or detect_format(data)
    if fmt == "pwg-raster":
        from .pwg_raster import decode_pwg_raster
        return decode_pwg_raster(data)
    if fmt == "pdf":
        return render_pdf(data, dpi)
    if fmt == "image":
        with Image.open(io.BytesIO(data)) as img:
            return [img.convert("RGB").copy()]
    if fmt == "postscript":
        raise ValueError("PostScript input requires conversion to PDF first (ps2pdf).")
    if fmt == "zpl":
        from .zpl_renderer import render_zpl
        return [render_zpl(data, dpi)]
    if fmt == "escpos":
        from .escpos_renderer import render_escpos
        return [render_escpos(data, dpi)]
    raise ValueError(f"Unsupported format: {fmt}")


def capture(data: bytes, profile: str, output: str | Path, title: str = "print", *, dpi: int | None = None) -> dict:
    if profile not in PROFILES:
        raise ValueError(f"Unknown profile: {profile}")
    if len(data) > 25 * 1024 * 1024:
        raise ValueError("Job exceeds 25 MB input limit")
    config = PROFILES[profile]
    output = Path(output).expanduser().resolve()
    format_name = detect_format(data)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    job_id = f"{timestamp}-{uuid.uuid4().hex[:8]}"
    directory = output / profile / f"{safe_name(title)}-{job_id}"
    directory.mkdir(parents=True, exist_ok=False)
    ext = {"pdf": ".pdf", "postscript": ".ps", "zpl": ".zpl", "escpos": ".bin", "pwg-raster": ".pwg", "image": ".img"}[format_name]
    original = directory / f"original{ext}"
    original.write_bytes(data)
    images = []
    status = "rendered"
    error = None
    try:
        pages = render_job(data, dpi or config["dpi"], format_name)
        for number, img in enumerate(pages, start=1):
            filename = f"page-{number:03d}.jpg"
            img.save(directory / filename, "JPEG", quality=95, subsampling=0)
            images.append(filename)
    except Exception as exc:
        status = "needs-renderer"
        error = str(exc)
    metadata = {
        "id": job_id, "profile": profile, "printer": config["printer"],
        "tray": config["tray"], "title": title, "format": format_name,
        "dpi": dpi or config["dpi"], "status": status, "images": images,
        "original": original.name, "error": error,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    (directory / "job.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return {**metadata, "directory": str(directory)}
