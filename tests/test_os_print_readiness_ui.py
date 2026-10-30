"""Smoke-check shipped inline dashboard JavaScript and OS readiness controls."""
import shutil
import subprocess
from html.parser import HTMLParser
from pathlib import Path

import pytest

from lulwa_virtual_printer import hub


class Scripts(HTMLParser):
    def __init__(self):
        super().__init__()
        self.script = False
        self.inline = []
    def handle_starttag(self, tag, attrs):
        if tag == "script":
            self.script = dict(attrs).get("src") is None
            if self.script:
                self.inline.append("")
    def handle_endtag(self, tag):
        if tag == "script":
            self.script = False
    def handle_data(self, data):
        if self.script:
            self.inline[-1] += data


def test_dashboard_embeds_print_path_controls():
    html = (Path(hub.__file__).with_name("ui") / "index.html").read_text(encoding="utf-8")
    assert "Check print path" in html
    assert "osReadinessPanel(id)" in html
    assert "/api/system/print-readiness" in html
    assert 'osReadiness[id]?.status!=="ready"' in html
    assert "os-test:" in html


def test_dashboard_inline_javascript_has_valid_syntax():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js unavailable")
    html = (Path(hub.__file__).with_name("ui") / "index.html").read_text(encoding="utf-8")
    parser = Scripts()
    parser.feed(html)
    assert parser.inline, "Dashboard inline JS missing"
    for script in parser.inline:
        if not script.strip():
            continue
        result = subprocess.run([node, "--check"], input=script, text=True,
                                capture_output=True, timeout=15)
        assert result.returncode == 0, result.stderr
