import pytest
from PIL import Image
from lulwa_virtual_printer.zpl_renderer import render_zpl


def test_label_size_and_content():
    data = b"^XA^PW812^LL1218^FO30,50^A0N,40,30^FDLULWA SWIM^FS^FO30,130^GB450,4,4^FS^XZ"
    image = render_zpl(data, 203)
    assert image.size == (812, 1218)
    assert image.getbbox()
    assert image.getpixel((40, 131)) == (0, 0, 0)


def test_code128_renders_real_bars():
    image = render_zpl(b"^XA^PW812^LL1218^FO20,20^BY2,2,80^BCN,80,Y,N,N^FDORD1001^FS^XZ")
    white = image.getpixel((0, 0))
    assert white == (255, 255, 255)
    assert any(image.getpixel((x, 30)) == (0, 0, 0) for x in range(20, 350))


def test_unsupported_commands_are_not_falsely_rendered():
    with pytest.raises(ValueError, match="not supported"):
        render_zpl(b"^XA^FO20,20^BQN,2,8^FDXYZ^FS^XZ")


def test_barcode_overflow_rejected():
    with pytest.raises(ValueError, match="exceeds label width"):
        render_zpl(b"^XA^PW200^LL300^FO10,10^BY4^BCN,80^FDLONGER123456789^FS^XZ")
