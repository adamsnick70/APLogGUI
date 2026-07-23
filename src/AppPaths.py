"""Resource/data-file locations for both source and PyInstaller-frozen runs.

Running from source, everything lives under the repo root (one level above
src/). Frozen, PyInstaller bundles read-only resources (ui/, params/) into
sys._MEIPASS instead, and config.json needs a real writable, per-user
location since a frozen build's own folder may not be writable (e.g.
Program Files) and a --onefile build's _MEIPASS is a throwaway extraction
directory, not a stable place to persist anything.
"""
import os
import sys
from pathlib import Path


def resource_root():
    """Where bundled read-only resources (ui/, params/) live."""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent


def user_data_dir():
    """Where writable per-user state (config.json) lives - each OS's normal
    per-user app-data convention, since a frozen build's own install
    directory may not be writable (e.g. Program Files, /usr) and a
    --onefile build's _MEIPASS is a throwaway extraction directory."""
    if getattr(sys, "frozen", False):
        if sys.platform == "win32":
            base = Path(os.environ.get("APPDATA", Path.home()))
            path = base / "AP Log Plotter"
        elif sys.platform == "darwin":
            path = Path.home() / "Library" / "Application Support" / "AP Log Plotter"
        else:
            base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
            path = base / "ap-log-plotter"
        path.mkdir(parents=True, exist_ok=True)
        return path
    return resource_root()
