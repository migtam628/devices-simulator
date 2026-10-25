from pathlib import Path
import shutil
import subprocess
import pytest
from lulwa_virtual_printer import hub


def test_ui_is_packaged_and_contains_required_views():
    html = Path(hub.__file__).with_name("ui").joinpath("index.html").read_text(encoding="utf-8")
    for label in ("Home", "My Devices", "Create Device", "Jobs & Queue", "Output Gallery", "Diagnostics", "System Integration", "Advanced Studio", "__HUB_TOKEN__"):
        assert label in html
    assert "device-name" in html
    assert "file_base64" in html


def test_browser_script_is_valid_javascript(tmp_path):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js not installed")
    html = Path(hub.__file__).with_name("ui").joinpath("index.html").read_text(encoding="utf-8")
    js = html.split("<script>", 1)[1].split("</script>", 1)[0]
    js_file = tmp_path / "hub-ui.js"
    js_file.write_text(js, encoding="utf-8")
    result = subprocess.run([node, "--check", str(js_file)], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
