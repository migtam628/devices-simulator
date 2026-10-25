#!/usr/bin/env bash
set -euo pipefail
for NAME in Lulwa_SIM_Brother Lulwa_SIM_Zebra_4x6; do
  if lpstat -p "$NAME" >/dev/null 2>&1; then
    lpadmin -x "$NAME"
    echo "Removed $NAME"
  fi
done
