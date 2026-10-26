import io
import json
from pathlib import Path
from PIL import Image
import fitz
import pytest
from lulwa_virtual_printer.engine import capture, detect_format, safe_name


def test_image_print(tmp_path):
    img = Image.new("RGB", (400, 600), "white")
    data = io.BytesIO()
    img.save(data, "PNG")
    result = capture(data.getvalue(), "zebra", tmp_path, "Order #44")
    assert result["status"] == "rendered"
    jpg = Path(result["directory"]) / "page-001.jpg"
    assert jpg.is_file()
    assert Image.open(jpg).size == (400, 600)
    assert json.loads((jpg.parent / "job.json").read_text())["profile"] == "zebra"


def test_pdf_multipage(tmp_path):
    doc = fitz.open()
    for _ in range(2):
        doc.new_page(width=72, height=72)
    result = capture(doc.tobytes(), "brother-tray2", tmp_path, "invoice", dpi=300)
    assert result["status"] == "rendered"
    assert len(result["images"]) == 2
    with Image.open(Path(result["directory"]) / result["images"][0]) as image:
        assert image.size == (300, 300)


def test_invalid_input(tmp_path):
    with pytest.raises(ValueError, match="Unsupported"):
        capture(b"bad", "zebra", tmp_path)


def test_zpl_preserved_and_not_false_success(tmp_path):
    result = capture(b"^XA^FO20,20^FDHi^FS^XZ", "zebra", tmp_path)
    assert result["status"] == "rendered"
    assert Path(result["directory"], "original.zpl").exists()
    assert Path(result["directory"], "page-001.jpg").exists()


def test_filename_sanitization():
    assert safe_name("../../hi there") == "hi-there"
