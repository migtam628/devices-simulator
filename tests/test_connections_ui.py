"""Hub UI wiring and browser-script syntax for universal TCP connections."""
import http.client
import shutil
import subprocess
import threading
from pathlib import Path

import pytest
from lulwa_virtual_printer import hub


def test_connection_page_is_wired():
    root=Path(hub.__file__).with_name("ui")
    html=(root/"index.html").read_text(encoding="utf-8")
    js=(root/"connections.js").read_text(encoding="utf-8")
    assert '["connections","Connections"]' in html
    assert 'integration,studio,connections,settings' in html
    assert 'src="/connections.js"' in html
    assert 'function connections()' in js
    for action in ('tcp-start:', 'tcp-stop:', 'tcp-weight:', 'tcp-probe:', 'tcp-fault:'):
        assert action in js
    assert "/api/connections/probe" in js
    assert '127.0.0.1' in js
    assert "No Network scale profiles yet" in js


def test_connection_script_parses_with_node():
    node=shutil.which("node")
    if not node:
        pytest.skip("Node.js is not installed")
    src=Path(hub.__file__).with_name("ui").joinpath("connections.js")
    check=subprocess.run([node,"--check",str(src)],capture_output=True,text=True,timeout=90)
    assert check.returncode == 0, check.stderr


def test_connections_browser_asset_served(tmp_path):
    server=hub.create_server(port=0,state_dir=tmp_path/"s",output_dir=tmp_path/"o")
    worker=threading.Thread(target=server.serve_forever,daemon=True)
    worker.start()
    try:
        conn=http.client.HTTPConnection("127.0.0.1",server.server_port,timeout=20)
        conn.request("GET","/connections.js")
        resp=conn.getresponse()
        js=resp.read()
        assert resp.status==200 and b"function connectionAction" in js
        assert resp.getheader("Content-Type").startswith("application/javascript")
        conn.close()
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=4)


def test_serial_controls_present_in_connections_view():
    text = Path(hub.__file__).with_name("ui").joinpath("connections.js").read_text(encoding="utf-8")
    for action in ("serial-start:", "serial-stop:", "serial-weight:", "serial-fault:"):
        assert action in text
    assert "function serialAction" in text
    assert "serial-probe:" in text
