#!/usr/bin/env bash
set -euo pipefail
if [[ "$(uname -s)" != Linux && "$(uname -s)" != Darwin ]]; then
  echo 'This installer supports Linux/macOS with CUPS only.' >&2
  exit 1
fi
command -v lpadmin >/dev/null || { echo 'CUPS lpadmin is required.' >&2; exit 1; }
command -v python3 >/dev/null || { echo 'python3 is required.' >&2; exit 1; }
python3 -c 'import PIL,fitz,lulwa_virtual_printer' || {
  echo 'Install the package and dependencies in the Python environment used by CUPS.' >&2
  exit 1
}
BACKEND_DIR="$(cups-config --serverbin)/backend"
[[ -d "$BACKEND_DIR" ]] || { echo "CUPS backend folder unavailable: $BACKEND_DIR" >&2; exit 1; }
sudo install -o root -g "$(id -gn root)" -m 755 "$(dirname "$0")/cups-backend" "$BACKEND_DIR/lulwasim"
for spec in 'Lulwa_SIM_Brother_Tray1:brother-tray1' 'Lulwa_SIM_Brother_Tray2:brother-tray2' 'Lulwa_SIM_Zebra_4x6:zebra'; do
  name="${spec%%:*}"
  profile="${spec##*:}"
  sudo lpadmin -p "$name" -E -v "lulwasim:/$profile" -m raw
  echo "Installed $name"
done
echo 'EXPERIMENTAL: Raw CUPS queues may not work on recent CUPS or macOS.'
