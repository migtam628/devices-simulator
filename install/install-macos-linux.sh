#!/usr/bin/env bash
# EXPERIMENTAL: installs CUPS printers; does not install/run background service.
set -euo pipefail
command -v lpadmin >/dev/null || { echo 'Install/start CUPS first (lpadmin missing).' >&2; exit 1; }
PORT="${LULWA_IPP_PORT:-8631}"
BASE="ipp://127.0.0.1:${PORT}/ipp"
if ! curl --silent --fail "http://127.0.0.1:${PORT}/healthz" >/dev/null; then
  echo 'Start lulwa-ipp in another terminal before installing printers.' >&2
  exit 1
fi
for spec in 'Lulwa_SIM_Brother:brother' 'Lulwa_SIM_Zebra_4x6:zebra'; do
  NAME="${spec%%:*}"
  ID="${spec#*:}"
  echo "Registering $NAME => $BASE/$ID"
  lpadmin -p "$NAME" -E -v "$BASE/$ID" -m everywhere
  lpoptions -p "$NAME" -l || true
done
lpstat -p Lulwa_SIM_Brother -p Lulwa_SIM_Zebra_4x6
echo 'Printers should now be listed in system printer settings, if driverless negotiation succeeded.'
echo 'EXPERIMENTAL: not validated on macOS/Linux OS installation. Leave lulwa-ipp running.'
