"""Overwrite src/version.py's APP_VERSION with a real, comparable build
identifier before a packaging build - `YYYY.MM.DD+<short-sha>`. Sorts
correctly by date (AutoUpdate.py's "is a newer version available" check
just does a string/tuple compare of the date part), and the short SHA makes
each build traceable back to the exact commit that produced it.

Run manually (defaults to today's date + `git rev-parse --short HEAD`), or
pass an explicit value for CI to use instead:
    python tools/stamp_version.py                # local build
    python tools/stamp_version.py 2026.07.23+a1b2c3d   # CI-supplied
"""
import datetime
import subprocess
import sys
from pathlib import Path

VERSION_PATH = Path(__file__).resolve().parent.parent / "src" / "version.py"


def git_short_sha():
    return subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()


def default_version():
    date = datetime.date.today().strftime("%Y.%m.%d")
    return f"{date}+{git_short_sha()}"


def main():
    version = sys.argv[1] if len(sys.argv) > 1 else default_version()
    VERSION_PATH.write_text(
        '"""Build version identifier - see tools/stamp_version.py."""\n'
        f'APP_VERSION = "{version}"\n',
        encoding="utf-8",
    )
    print(f"Stamped {VERSION_PATH.relative_to(VERSION_PATH.parent.parent)} -> {version}")


if __name__ == "__main__":
    main()
