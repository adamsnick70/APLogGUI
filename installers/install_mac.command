#!/bin/bash
# AP Log Plotter installer for macOS.
#
# - Installs Homebrew (if missing), then Python 3 + Tk support via Homebrew
#   (if missing).
# - Installs/updates the packages in requirements.txt.
# - Builds an "AP Log Plotter.app" bundle in ~/Applications so the app shows
#   up in Spotlight and Launchpad search.
#
# Run by double-clicking this file in Finder (it opens in Terminal), or
# directly with:  bash install_mac.command

set -e

INSTALLER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$INSTALLER_DIR/.." && pwd)"
GUI_SCRIPT="$REPO_ROOT/src/LogPlotterGUI.py"
REQUIREMENTS="$REPO_ROOT/requirements.txt"

echo "== AP Log Plotter installer =="

# 1. Homebrew -----------------------------------------------------------------
if ! command -v brew >/dev/null 2>&1; then
    echo "Homebrew not found - installing (this may prompt for your password)..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi

if [[ -d /opt/homebrew/bin ]]; then
    eval "$(/opt/homebrew/bin/brew shellenv)"
elif [[ -d /usr/local/bin ]]; then
    eval "$(/usr/local/bin/brew shellenv)"
fi

# 2. Python (+ Tk support) ------------------------------------------------------
if ! command -v python3 >/dev/null 2>&1; then
    echo "Python3 not found - installing via Homebrew..."
    brew install python
fi

if ! python3 -c "import tkinter" >/dev/null 2>&1; then
    echo "Installing Tk support for Python..."
    brew install python-tk || true
fi

echo "Using Python: $(python3 --version)"

# 3. Requirements ---------------------------------------------------------------
echo "Installing/upgrading required packages..."
python3 -m pip install --upgrade pip
python3 -m pip install -r "$REQUIREMENTS"

# 4. App bundle (makes the app searchable via Spotlight/Launchpad) --------------
APP_DIR="$HOME/Applications/AP Log Plotter.app"
echo "Creating app bundle at $APP_DIR ..."
rm -rf "$APP_DIR"
mkdir -p "$APP_DIR/Contents/MacOS"

cat > "$APP_DIR/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>AP Log Plotter</string>
    <key>CFBundleDisplayName</key>
    <string>AP Log Plotter</string>
    <key>CFBundleIdentifier</key>
    <string>com.aplogplotter.app</string>
    <key>CFBundleVersion</key>
    <string>1.0</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleExecutable</key>
    <string>AP Log Plotter</string>
</dict>
</plist>
PLIST

cat > "$APP_DIR/Contents/MacOS/AP Log Plotter" <<LAUNCHER
#!/bin/bash
cd "$REPO_ROOT"
exec python3 "$GUI_SCRIPT"
LAUNCHER
chmod +x "$APP_DIR/Contents/MacOS/AP Log Plotter"

# Refresh Launch Services so Spotlight/Launchpad pick up the new app right away.
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f "$APP_DIR" >/dev/null 2>&1 || true

echo ""
echo "Done! Search for 'AP Log Plotter' in Spotlight (Cmd+Space) or find it in Launchpad."
read -p "Press Enter to close this window..."
