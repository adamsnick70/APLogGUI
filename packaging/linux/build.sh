#!/usr/bin/env bash
# Build the frozen Linux app (dist/ap-log-plotter/ap-log-plotter).
#
# Run from anywhere: bash packaging/linux/build.sh
# Requires: pip install -r requirements.txt (PyInstaller included) and the
# runtime libs noted in packaging/linux/build_deb.sh's Depends list, since
# PyInstaller needs to actually launch Qt during analysis on some setups.
set -euo pipefail

PACKAGING_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$PACKAGING_DIR/../.." && pwd)"

echo "== Compiling .ui files =="
python3 "$REPO_ROOT/tools/build_ui.py" --force

echo "== Running PyInstaller =="
pyinstaller "$PACKAGING_DIR/ap_log_plotter.spec" \
    --distpath "$PACKAGING_DIR/dist" \
    --workpath "$PACKAGING_DIR/build" \
    --noconfirm

echo
echo "Done: $PACKAGING_DIR/dist/ap-log-plotter/ap-log-plotter"
