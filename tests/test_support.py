"""Shared fixtures for the GUI test suite.

QMessageBox.critical/warning/information would open a real modal dialog
with no one to dismiss it under a test runner - that would hang the
process and pop a window on screen. They're patched once, at import time,
to record into `popups` instead (mirrors the Tkinter version's
messagebox.showerror/showwarning/showinfo patching).
"""
import sys
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parent.parent / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

popups = []


def _record_popup(kind):
    def _show(*args, **kwargs):
        # QMessageBox.critical(parent, title, text, ...) - every call site
        # in LogPlotterGUI uses exactly (parent, title, text).
        _parent, title, text = args[:3]
        popups.append((kind, title, text))
    return _show


import pytest  # noqa: E402
from PySide6.QtWidgets import QMessageBox  # noqa: E402

QMessageBox.critical = staticmethod(_record_popup("error"))
QMessageBox.warning = staticmethod(_record_popup("warning"))
QMessageBox.information = staticmethod(_record_popup("info"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import LogPlotterGUI as gui_module  # noqa: E402
from LogPlotterGUI import MainWindow  # noqa: E402


def make_log_csv(path, throttle_low=5.0, throttle_high=85.0, rows=200, extra_fields=None):
    """A synthetic AP log: throttle steps from low to high and back once
    (one high-throttle "event"), plus a couple of extra plottable columns."""
    t = np.round(np.arange(rows) * 0.1, 2)
    throttle = np.full(rows, throttle_low)
    throttle[rows // 5: rows * 4 // 5] = throttle_high

    data = {"Time (sec)": t, "Throttle Pos (%)": throttle}
    data.update(extra_fields if extra_fields is not None else {
        "RPM (RPM)": np.where(throttle > 50, 5500000.0, 1200000.0),
        "Coolant Temp (F)": np.full(rows, 9000.0),
        "Custom Sensor A (V)": np.sin(np.linspace(0, 10, rows)),
        "Custom Sensor B (V)": np.cos(np.linspace(0, 10, rows)),
    })
    pd.DataFrame(data).to_csv(path, index=False)
    return str(path)


def make_log_csv_two_events(path, throttle_low=5.0, throttle_high=85.0, rows=400):
    """A synthetic AP log with two distinct high-throttle events separated
    by an 8s low-throttle gap - comfortably past the autofind algorithm's
    5s "no second rise" window - so autofind reliably reports two separate
    events instead of merging them into one."""
    t = np.round(np.arange(rows) * 0.1, 2)
    throttle = np.full(rows, throttle_low)
    throttle[20:80] = throttle_high
    throttle[180:260] = throttle_high

    data = {
        "Time (sec)": t,
        "Throttle Pos (%)": throttle,
        "RPM (RPM)": np.where(throttle > 50, 5500000.0, 1200000.0),
        "Coolant Temp (F)": np.full(rows, 9000.0),
    }
    pd.DataFrame(data).to_csv(path, index=False)
    return str(path)


def make_log_csv_without_throttle(path, rows=50):
    """A log missing UserParams.throttleField entirely, to exercise the
    "autofind disabled when throttle field is absent" behavior."""
    t = np.round(np.arange(rows) * 0.1, 2)
    data = {
        "Time (sec)": t,
        "Coolant Temp (F)": np.full(rows, 9000.0),
        "Custom Sensor A (V)": np.sin(np.linspace(0, 5, rows)),
    }
    pd.DataFrame(data).to_csv(path, index=False)
    return str(path)


def make_window(qtbot, tmp_path, monkeypatch, size=(1600, 900)):
    """A fresh MainWindow, sized as requested. CONFIG_PATH is redirected to
    a throwaway file so the window's closeEvent (which saves window
    geometry) never touches the repo's real config.json - callers must
    close() the window themselves before `monkeypatch` reverts (see the
    `gui` fixture below), since that undoes the redirect."""
    popups.clear()
    monkeypatch.setattr(gui_module, "CONFIG_PATH", tmp_path / "config.json")
    window = MainWindow()
    qtbot.addWidget(window)
    window.resize(*size)
    window.show()
    qtbot.waitExposed(window)
    return window


@pytest.fixture
def gui(qtbot, tmp_path, monkeypatch):
    """A fresh, normally-sized MainWindow per test. qtbot.addWidget()
    registers it for automatic close/cleanup after the test, replacing the
    Tkinter version's manual tearDown(self.app.destroy())."""
    window = make_window(qtbot, tmp_path, monkeypatch)
    yield window
    # Closed here (rather than relying solely on qtbot.addWidget's automatic
    # close) so closeEvent's config save happens while CONFIG_PATH is still
    # patched - fixture teardown order reverts monkeypatch's patches before
    # qtbot's own widget-closing teardown would otherwise run.
    window.close()
