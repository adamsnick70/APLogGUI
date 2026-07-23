"""Compile ui/*.ui into src/ui_*.py via pyside6-uic.

The .ui file is the single source of truth; generated ui_*.py modules are
not committed (see .gitignore) and are regenerated here, either explicitly
(`python tools/build_ui.py`) or automatically by LogPlotterGUI.py when the
compiled module is missing or older than its .ui source.
"""
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
UI_DIR = REPO_ROOT / "ui"
SRC_DIR = REPO_ROOT / "src"


def _find_uic():
    """Locate the pyside6-uic console script. shutil.which() covers the
    normal case (pip put it on PATH); the Scripts/bin dir next to the
    running interpreter covers venvs/installs where PATH wasn't updated."""
    found = shutil.which("pyside6-uic")
    if found:
        return found
    exe_name = "pyside6-uic.exe" if sys.platform == "win32" else "pyside6-uic"
    scripts_dir = "Scripts" if sys.platform == "win32" else "bin"
    candidate = Path(sys.executable).resolve().parent / scripts_dir / exe_name
    if candidate.is_file():
        return str(candidate)
    raise FileNotFoundError(
        "pyside6-uic not found on PATH or next to the current interpreter - "
        "is PySide6 installed (pip install -r requirements.txt)?"
    )


def compiled_path_for(ui_path):
    return SRC_DIR / f"ui_{ui_path.stem}.py"


def is_stale(ui_path):
    out_path = compiled_path_for(ui_path)
    return not out_path.exists() or out_path.stat().st_mtime < ui_path.stat().st_mtime


def build(ui_path):
    out_path = compiled_path_for(ui_path)
    subprocess.run(
        [_find_uic(), str(ui_path), "-o", str(out_path)],
        check=True, stdin=subprocess.DEVNULL,
    )
    return out_path


def build_all(force=False):
    built = []
    if not UI_DIR.is_dir():
        # Nothing to compile from - e.g. a frozen build that ships
        # ui_main_window.py directly instead of the .ui sources.
        return built
    for ui_path in sorted(UI_DIR.glob("*.ui")):
        if force or is_stale(ui_path):
            built.append(build(ui_path))
    return built


if __name__ == "__main__":
    force = "--force" in sys.argv[1:]
    built = build_all(force=force)
    if built:
        for path in built:
            print(f"Compiled {path.relative_to(REPO_ROOT)}")
    else:
        print("Nothing to do; compiled ui_*.py already up to date.")
