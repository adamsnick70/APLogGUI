"""Overwrite src/version.py's APP_VERSION with a real, comparable build
identifier before a packaging build - `YYYY.MM.DD+<run-number>.<short-sha>`.
AutoUpdate.py's "is a newer version available" check orders builds by the
run number, not the date: GitHub Actions' GITHUB_RUN_NUMBER increments by
one on every workflow run regardless of what day it lands on, so two
releases published the same calendar day (the date part alone would compare
equal) still order correctly. Falls back to "0" for a local, non-CI run,
where there's no real GITHUB_RUN_NUMBER and no distributed release to
compare against anyway. The short SHA makes each build traceable back to
the exact commit that produced it, but isn't itself used for ordering (git
short SHAs aren't sequential).

Run manually (defaults to today's date + run number + `git rev-parse
--short HEAD`), or pass an explicit value for CI to use instead:
    python tools/stamp_version.py                # local build
    python tools/stamp_version.py 2026.07.23+142.a1b2c3d   # CI-supplied
"""
import datetime
import os
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
    run_number = os.environ.get("GITHUB_RUN_NUMBER", "0")
    return f"{date}+{run_number}.{git_short_sha()}"


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
