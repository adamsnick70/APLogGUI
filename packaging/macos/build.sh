#!/usr/bin/env bash
# Build the frozen macOS app bundle (dist/AP Log Plotter.app). macOS only -
# `iconutil` (used below) doesn't exist on other platforms.
#
# Run from anywhere: bash packaging/macos/build.sh
# Requires: pip install -r requirements.txt (PyInstaller included).
set -euo pipefail

PACKAGING_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$PACKAGING_DIR/../.." && pwd)"

echo "== Compiling .ui files =="
python3 "$REPO_ROOT/tools/build_ui.py" --force

echo "== Building AppIcon.icns =="
iconutil -c icns "$REPO_ROOT/assets/icons/AppIcon.iconset" -o "$REPO_ROOT/assets/icons/icon.icns"

echo "== Running PyInstaller =="
pyinstaller "$PACKAGING_DIR/ap_log_plotter.spec" \
    --distpath "$PACKAGING_DIR/dist" \
    --workpath "$PACKAGING_DIR/build" \
    --noconfirm

echo
echo "Done: $PACKAGING_DIR/dist/AP Log Plotter.app"
