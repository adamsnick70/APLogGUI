# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the Linux build (ToDo.txt section 11).

--onedir (not --onefile): onefile's self-extracting temp-dir unpack behaves
oddly under some sandboxing/AppArmor setups, and onedir keeps startup fast.
The output is named "ap-log-plotter" (lowercase-hyphenated, unlike the
Windows build's "AP Log Plotter") to match Linux path/package-name
conventions - no spaces, since it lands under /usr/lib/ap-log-plotter/ in
the .deb built by build_deb.sh.

No icon= for EXE() here - PyInstaller only embeds an icon resource on
Windows/macOS; Linux desktop icons come from the .desktop file instead.

Build with packaging/linux/build.sh, not directly - that runs the
tools/build_ui.py compile step first so ui_main_window.py exists to bundle.
"""
from pathlib import Path

REPO_ROOT = Path(SPECPATH).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"

a = Analysis(
    [str(SRC_DIR / "LogPlotterGUI.py")],
    pathex=[str(SRC_DIR)],
    datas=[
        (str(REPO_ROOT / "ui"), "ui"),
        (str(REPO_ROOT / "params"), "params"),
    ],
    # See packaging/windows/ap_log_plotter.spec - this dev environment's
    # global Python install has an unrelated ML/dev stack that pandas/
    # fsspec's optional-import probing otherwise drags in transitively.
    excludes=[
        "torch", "torchvision", "transformers", "sklearn", "tiktoken",
        "tokenizers", "h5py", "jedi", "IPython", "notebook", "jupyter",
        "jupyter_client", "jupyter_core", "pyarrow", "matplotlib", "PIL",
        "lxml", "fsspec", "s3fs", "gcsfs", "huggingface_hub", "datasets",
        "sympy", "numba", "llvmlite", "pydantic", "win32com", "Pythonwin",
        "scipy",
    ],
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ap-log-plotter",
    console=False,
)

COLLECT(
    exe,
    a.binaries,
    a.datas,
    name="ap-log-plotter",
)
