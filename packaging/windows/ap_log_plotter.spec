# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the Windows build (ToDo.txt section 10).

--onedir (not --onefile): faster startup (no self-extraction on every
launch) and a plain folder of files is what the Inno Setup installer in
this same directory installs/uninstalls/updates in place.

Build with packaging/windows/build.ps1, not directly - that runs the
tools/build_ui.py compile step first so ui_main_window.py exists to bundle.
"""
from pathlib import Path

REPO_ROOT = Path(SPECPATH).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
ICON = REPO_ROOT / "assets" / "icons" / "icon.ico"

# This dev machine's global (non-venv) Python env has a large,
# app-unrelated ML/dev stack installed (torch, transformers, sklearn,
# jupyter, etc.) that PyInstaller's modulegraph pulls in transitively -
# not because this app imports any of it, but because pandas/fsspec probe
# for optional plugins (e.g. fsspec's entry-point filesystem registry) that
# happen to resolve to packages installed elsewhere in the same
# environment. None of it is reachable from this app's actual code path
# (verified: LogPlotterGUI/LogPlotUtil/ParamPlots/CustomPlots/PdfExport/
# UserParams import only pandas, numpy, PySide6, and pyqtgraph) - excluded
# here rather than shipping several GB of unrelated libraries.
EXCLUDES = [
    "torch", "torchvision", "transformers", "sklearn", "tiktoken",
    "tokenizers", "h5py", "jedi", "IPython", "notebook", "jupyter",
    "jupyter_client", "jupyter_core", "pyarrow", "matplotlib", "PIL",
    "lxml", "fsspec", "s3fs", "gcsfs", "huggingface_hub", "datasets",
    "sympy", "numba", "llvmlite", "pydantic", "win32com", "Pythonwin",
    "scipy",
]

a = Analysis(
    [str(SRC_DIR / "LogPlotterGUI.py")],
    pathex=[str(SRC_DIR)],
    datas=[
        (str(REPO_ROOT / "ui"), "ui"),
        (str(REPO_ROOT / "params"), "params"),
    ],
    excludes=EXCLUDES,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="AP Log Plotter",
    icon=str(ICON),
    console=False,
)

COLLECT(
    exe,
    a.binaries,
    a.datas,
    name="AP Log Plotter",
)
