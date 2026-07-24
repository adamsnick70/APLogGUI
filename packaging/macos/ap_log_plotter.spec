# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the macOS build (ToDo.txt section 10).

Produces AP Log Plotter.app via BUNDLE(), wrapping the same --onedir
Analysis/EXE/COLLECT structure the Windows/Linux specs use. Needs
assets/icons/icon.icns to exist first - packaging/macos/build.sh generates
it (via `iconutil`, macOS-only) from assets/icons/AppIcon.iconset before
running PyInstaller.

Build with packaging/macos/build.sh, not directly - that also runs the
tools/build_ui.py compile step first so ui_main_window.py exists to bundle.
"""
import sys
from pathlib import Path

REPO_ROOT = Path(SPECPATH).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
ICON = REPO_ROOT / "assets" / "icons" / "icon.icns"

sys.path.insert(0, str(SRC_DIR))
from version import APP_VERSION  # noqa: E402

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
    name="AP Log Plotter",
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    name="AP Log Plotter",
)

app = BUNDLE(
    coll,
    name="AP Log Plotter.app",
    icon=str(ICON),
    bundle_identifier="com.adamsnick.aplogplotter",
    info_plist={
        "CFBundleShortVersionString": APP_VERSION,
        "NSHighResolutionCapable": True,
    },
)
