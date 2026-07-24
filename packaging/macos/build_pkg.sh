#!/usr/bin/env bash
# Wrap packaging/macos/dist/AP Log Plotter.app (built by build.sh) into a
# .pkg installer (ToDo.txt sections 10/12). A plain drag-to-Applications
# .dmg has no hook to run the legacy-migration scripts below, so a scripted
# .pkg (via pkgbuild) is used instead of a .dmg.
#
# --install-location is /Applications (system-wide, admin password prompt -
# standard for a macOS .pkg) rather than install_mac.command's ~/Applications
# (per-user), so this does NOT land at the same path as a legacy install -
# scripts/preinstall migrates the old config then removes the old
# ~/Applications bundle itself (see ToDo.txt section 12: "remove it if the
# new install target path differs"), and scripts/postinstall re-registers
# Launch Services so Spotlight/Launchpad reflect the change immediately.
#
# Usage: bash packaging/macos/build_pkg.sh [version]
set -euo pipefail

PACKAGING_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$PACKAGING_DIR/../.." && pwd)"
APP_BUNDLE="$PACKAGING_DIR/dist/AP Log Plotter.app"
OUT_DIR="$PACKAGING_DIR/installer_output"

if [ ! -d "$APP_BUNDLE" ]; then
    echo "No frozen app bundle found at $APP_BUNDLE - run packaging/macos/build.sh first." >&2
    exit 1
fi

VERSION="${1:-$(python3 -c "import datetime,subprocess; sha=subprocess.run(['git','rev-parse','--short','HEAD'],capture_output=True,text=True,cwd='$REPO_ROOT').stdout.strip(); print(f'{datetime.date.today():%Y.%m.%d}+{sha}')")}"

mkdir -p "$OUT_DIR"

pkgbuild \
    --component "$APP_BUNDLE" \
    --install-location "/Applications" \
    --scripts "$PACKAGING_DIR/scripts" \
    --identifier com.adamsnick.aplogplotter \
    --version "$VERSION" \
    "$OUT_DIR/AP-Log-Plotter.pkg"

echo "Done: $OUT_DIR/AP-Log-Plotter.pkg"
