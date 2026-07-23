"""Build version identifier, stamped by CI before each PyInstaller build.

Running from source, APP_VERSION stays "dev" - AutoUpdate.py treats that as
"never offer an update" (there's no source-run install to replace). Each of
packaging/{windows,macos,linux}/build.* overwrites this file (via
tools/stamp_version.py) with the real value just before invoking
PyInstaller, so the frozen build ships this file resembling
"2026.07.23+a1b2c3d" (date + short commit SHA), not the literal word "dev".
"""
APP_VERSION = "dev"
