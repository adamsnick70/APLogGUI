#!/usr/bin/env bash
# Package packaging/linux/dist/ap-log-plotter/ (built by build.sh) into a
# .deb with fpm (ToDo.txt section 11). Requires fpm on PATH:
#   sudo gem install --no-document fpm
#
# Usage: bash packaging/linux/build_deb.sh [version]
# version defaults to whatever tools/stamp_version.py would compute.
set -euo pipefail

PACKAGING_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$PACKAGING_DIR/../.." && pwd)"
DIST_DIR="$PACKAGING_DIR/dist/ap-log-plotter"
OUT_DIR="$PACKAGING_DIR/installer_output"

if [ ! -d "$DIST_DIR" ]; then
    echo "No frozen build found at $DIST_DIR - run packaging/linux/build.sh first." >&2
    exit 1
fi

VERSION="${1:-$(python3 -c "import datetime,subprocess; sha=subprocess.run(['git','rev-parse','--short','HEAD'],capture_output=True,text=True,cwd='$REPO_ROOT').stdout.strip(); print(f'{datetime.date.today():%Y.%m.%d}+{sha}')")}"

mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/ap-log-plotter_*.deb

# /usr/bin needs a stable launch name (for the .desktop's Exec= and for
# command-line use); PyInstaller's onedir bootloader resolves its bundle
# directory by following symlinks, so a plain symlink is enough - staged
# here as a real symlink so fpm packages it as one rather than a copy.
STAGING="$PACKAGING_DIR/staging"
rm -rf "$STAGING"
mkdir -p "$STAGING/usr/bin"
ln -s /usr/lib/ap-log-plotter/ap-log-plotter "$STAGING/usr/bin/ap-log-plotter"

fpm -s dir -t deb -f \
    --name ap-log-plotter \
    --version "$VERSION" \
    --architecture amd64 \
    --description "Plot and analyze AccessPort datalogs" \
    --url "https://github.com/adamsnick70/APLogGUI" \
    --maintainer "Nick Adams" \
    --category utils \
    --depends libxcb-cursor0 \
    --depends libxkbcommon-x11-0 \
    --depends libgl1 \
    --depends libegl1 \
    --depends fonts-dejavu-core \
    --package "$OUT_DIR/" \
    "$DIST_DIR/=/usr/lib/ap-log-plotter/" \
    "$STAGING/usr/bin/ap-log-plotter=/usr/bin/ap-log-plotter" \
    "$PACKAGING_DIR/ap-log-plotter.desktop=/usr/share/applications/ap-log-plotter.desktop" \
    "$REPO_ROOT/assets/icons/icon.png=/usr/share/icons/hicolor/256x256/apps/ap-log-plotter.png"

rm -rf "$STAGING"

echo "Done: $OUT_DIR"
ls "$OUT_DIR"/ap-log-plotter_*.deb
