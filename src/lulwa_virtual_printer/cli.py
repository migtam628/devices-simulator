import argparse
import json
import os
import sys
from pathlib import Path
from .engine import capture, PROFILES


def main():
    parser = argparse.ArgumentParser(description="Lulwa simulated printer job capture")
    parser.add_argument("input", nargs="?", help="PDF, JPG, PNG, or ZPL file (defaults to stdin)")
    parser.add_argument("--profile", choices=PROFILES, required=True)
    parser.add_argument("--output", default=os.environ.get("LULWA_PRINT_OUTPUT", str(Path.home() / "Documents" / "Lulwa Virtual Printer")))
    parser.add_argument("--title", default="print")
    parser.add_argument("--dpi", type=int, choices=[203, 300, 600])
    args = parser.parse_args()
    result = capture(Path(args.input).read_bytes() if args.input else sys.stdin.buffer.read(), args.profile, args.output, args.title, dpi=args.dpi)
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "rendered" else 2


if __name__ == "__main__":
    raise SystemExit(main())
