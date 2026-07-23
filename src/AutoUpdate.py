"""Auto-update: check GitHub Releases for a newer build than this one, then
download/verify/relaunch that OS's installer (ToDo.txt sections 10/11).

Only meaningful for frozen builds - APP_VERSION stays "dev" running from
source, and is_newer() always returns False against "dev", so this whole
flow is inert unless PyInstaller stamped a real version in (see
tools/stamp_version.py).

CI (see .github/workflows/release.yml) publishes one GitHub Release per
build, tagged with that build's exact APP_VERSION string, rather than a
single reused "latest" tag - GitHub's own `/releases/latest` API already
resolves to the most recently published release regardless of its tag
name, so this stays simple and every release keeps a distinct, inspectable
tag.
"""
import hashlib
import json
import platform
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

from version import APP_VERSION

REPO = "adamsnick70/APLogGUI"
RELEASES_API = f"https://api.github.com/repos/{REPO}/releases/latest"

# Installer filename suffix each OS's release build publishes - matched
# against each release asset's name to pick the right download.
_ASSET_SUFFIX = {
    "Windows": ".exe",
    "Darwin": ".pkg",
    "Linux": ".deb",
}


def _release_date(version_string):
    """The sortable "YYYY.MM.DD" part of an APP_VERSION-shaped string
    ("YYYY.MM.DD+sha") - falls back to the whole string for anything else
    (e.g. "dev"), which never compares as newer than a real date."""
    return version_string.split("+", 1)[0]


def is_newer(remote_version, local_version=None):
    # local_version is looked up here (module global), not as the default
    # argument value, so monkeypatching AutoUpdate.APP_VERSION in tests (or
    # any other runtime change to it) is actually honored - a default
    # argument expression is evaluated once at def time and would freeze in
    # whatever APP_VERSION was at import time instead.
    if local_version is None:
        local_version = APP_VERSION
    return _release_date(remote_version) > _release_date(local_version)


def fetch_latest_release(timeout=10):
    """The parsed GitHub Releases API response, or None on any failure
    (network down, rate-limited, no releases published yet) - callers treat
    that the same as "no update available" rather than surfacing an error
    for what's just a best-effort background check."""
    try:
        with urllib.request.urlopen(RELEASES_API, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def pick_asset(release, system=None):
    """The installer asset (and its .sha256 sibling, if published) for the
    current OS from a release's `assets` list."""
    suffix = _ASSET_SUFFIX.get(system or platform.system())
    if suffix is None or not release:
        return None, None
    installer = None
    checksum = None
    for asset in release.get("assets", []):
        name = asset.get("name", "")
        if name.endswith(suffix + ".sha256"):
            checksum = asset
        elif name.endswith(suffix):
            installer = asset
    return installer, checksum


def check_for_update():
    """The one entry point most callers need: None if no update is
    available (or the check failed), else
    (remote_version, installer_asset, checksum_asset)."""
    release = fetch_latest_release()
    if not release:
        return None
    remote_version = release.get("tag_name", "")
    if not is_newer(remote_version):
        return None
    installer, checksum = pick_asset(release)
    if installer is None:
        return None
    return remote_version, installer, checksum


def _download(url, dest, timeout=30):
    with urllib.request.urlopen(url, timeout=timeout) as resp, open(dest, "wb") as f:
        f.write(resp.read())


def _sha256_of(path):
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_checksum(path, expected_hex):
    return _sha256_of(path) == expected_hex.strip().lower()


def download_and_verify(installer_asset, checksum_asset, dest_dir=None):
    """Downloads the installer (and its .sha256, if published) into
    dest_dir (a fresh temp dir by default), verifies it, and returns the
    installer's local path. Raises ValueError on a checksum mismatch -
    callers must never launch an unverified download."""
    dest_dir = Path(dest_dir) if dest_dir else Path(tempfile.mkdtemp(prefix="aplogplotter_update_"))
    dest_dir.mkdir(parents=True, exist_ok=True)
    installer_path = dest_dir / installer_asset["name"]
    _download(installer_asset["browser_download_url"], installer_path)

    if checksum_asset:
        checksum_path = dest_dir / checksum_asset["name"]
        _download(checksum_asset["browser_download_url"], checksum_path)
        expected = checksum_path.read_text(encoding="utf-8").split()[0]
        if not verify_checksum(installer_path, expected):
            raise ValueError(
                f"Checksum mismatch for {installer_path.name} - the download "
                "may be corrupt or tampered with. Not launching it."
            )
    return installer_path


def launch_installer_and_exit(installer_path, system=None):
    """Launches the downloaded installer and exits this process so it can
    overwrite the running install. Linux's .deb installs system-wide (under
    /usr), so overwriting it needs root - shelled out via pkexec (a
    graphical polkit password prompt, no terminal needed) rather than
    silently failing partway through a plain `dpkg -i`."""
    system = system or platform.system()
    if system == "Linux":
        subprocess.Popen(["pkexec", "dpkg", "-i", str(installer_path)])
    else:
        subprocess.Popen([str(installer_path)])
    sys.exit(0)
