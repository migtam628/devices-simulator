"""Optional native window wrapper around the local Devices Simulator Hub.

Requires pywebview and an appropriate OS webview backend.
"""
from __future__ import annotations
import argparse
import threading
from pathlib import Path
from .hub import create_server, start_attached_ipp, stop_attached_ipp


def main():
    p = argparse.ArgumentParser(description="Devices Simulator desktop window (pywebview)")
    p.add_argument("--output", type=Path, default=None)
    p.add_argument("--state-dir", type=Path, default=None)
    args = p.parse_args()
    try:
        import webview
    except ImportError as exc:
        raise SystemExit("Desktop UI dependency missing. Install: python3 -m pip install -e '.[desktop]'") from exc

    ipp_server, ipp_thread = start_attached_ipp(output=args.output)
    try:
        server = create_server(port=0, state_dir=args.state_dir, output_dir=args.output)
        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.2}, daemon=True)
        thread.start()
        url = f"http://127.0.0.1:{server.server_port}/"
        try:
            webview.create_window("Devices Simulator — Device Hub Pro", url, width=1440, height=900, min_size=(980, 680))
            webview.start()
        finally:
            server.hub_hid.stop()
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)
    finally:
        stop_attached_ipp(ipp_server, ipp_thread)


if __name__ == "__main__":
    main()
