"""Marketing site stays self-contained and its illustrated assets are valid XML."""
from html.parser import HTMLParser
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


class SiteParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.local = set()
        self.ids = set()
        self.anchors = set()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get("id"):
            self.ids.add(attrs["id"])
        for key in ("href", "src"):
            url = attrs.get(key, "")
            if not url or url.startswith("https:") or url.startswith("http:"):
                continue
            if url.startswith("#"):
                self.anchors.add(url[1:])
                continue
            if url.startswith(("mailto:", "tel:", "data:")):
                continue
            self.local.add(url.split("#")[0])


def test_website_assets_and_navigation():
    folder = ROOT / "docs"
    parser = SiteParser()
    parser.feed((folder / "index.html").read_text(encoding="utf-8"))
    assert {"main", "features", "workflows", "compatibility", "faq"}.issubset(parser.ids)
    assert parser.anchors.issubset(parser.ids)
    missing = [p for p in parser.local if not (folder / p).is_file()]
    assert not missing, f"Missing marketing site assets: {missing}"
    for name in ("product-hero.svg", "workflow.svg", "device-preview.svg", "icon.svg"):
        ET.parse(folder / "assets" / name)


def test_readme_illustrations_exist():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for name in ("product-hero.svg", "workflow.svg", "device-preview.svg"):
        assert (ROOT / "docs" / "assets" / name).is_file()
        assert "docs/assets/" + name in readme
    assert "Company evaluation" in readme
    assert "HID" in readme
    assert "CUPS" in readme
