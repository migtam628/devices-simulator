"""Frozen Devices Simulator entry: full hub, or no-GUI packaging smoke test."""
from __future__ import annotations
import http.client
import importlib.util
import platform
import sys
import tempfile
import threading
from pathlib import Path


def self_test():
    from lulwa_virtual_printer.hub import create_server
    from lulwa_virtual_printer.native_printers import PRINTERS
    import lulwa_virtual_printer
    assert set(PRINTERS) == {"brother", "zebra"}
    root = Path(lulwa_virtual_printer.__file__).parent
    assert (root / "ui" / "index.html").is_file(), "Bundled HTML missing"
    assert (root / "ppd" / "brother.ppd").is_file(), "Bundled Brother PPD missing"
    assert (root / "ppd" / "zebra.ppd").is_file(), "Bundled Zebra PPD missing"
    if platform.system() in ("Windows", "Darwin"):
        assert importlib.util.find_spec("webview"), "Native webview backend missing"
    with tempfile.TemporaryDirectory(prefix="devices-simulator-test-") as folder:
        root = Path(folder)
        server = create_server(port=0, state_dir=root / "state", output_dir=root / "output")
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=15)
            connection.request("GET", "/")
            response = connection.getresponse()
            body = response.read()
            assert response.status == 200 and b"Devices Simulator" in body
            d = server.hub_store.create_device({"preset": "zebra", "name": "Bundled smoke test"})
            job = server.hub_store.test_device(d["id"])
            assert job["status"] == "rendered", job.get("error")
            assert (Path(job["directory"]) / "page-001.jpg").is_file()
            connection.close()
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=3)
    if sys.stdout is not None:
        print("PASS: bundled resources, local hub, PDF to JPG", flush=True)


def main():
    if "--self-test" in sys.argv[1:]:
        self_test()
        if "--self-test-report" in sys.argv:
            index = sys.argv.index("--self-test-report")
            if index + 1 >= len(sys.argv):
                raise SystemExit("--self-test-report needs a path")
            Path(sys.argv[index + 1]).write_text("PASS: frozen app smoke test\n", encoding="utf-8")
        return 0
    if platform.system() == "Linux":
        # Browser-hosted UI avoids external GTK/Qt runtime dependency.
        from lulwa_virtual_printer.hub import main as launch
    else:
        from lulwa_virtual_printer.desktop import main as launch
    return launch() or 0


if __name__ == "__main__":
    raise SystemExit(main())
