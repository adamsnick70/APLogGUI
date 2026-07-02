"""Shared fixtures for the GUI test suite.

messagebox.showerror/showwarning/showinfo open a real modal dialog with no
one to dismiss it under a test runner - that would hang the process and pop
a window on screen. They're patched once, at import time, to record into
`popups` instead.
"""
import sys
from pathlib import Path
from tkinter import messagebox

SRC_ROOT = Path(__file__).resolve().parent.parent / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

popups = []


def _record_popup(kind):
    def _show(title, message):
        popups.append((kind, title, message))
    return _show


messagebox.showerror = _record_popup("error")
messagebox.showwarning = _record_popup("warning")
messagebox.showinfo = _record_popup("info")

import numpy as np
import pandas as pd

from LogPlotterGUI import LogPlotterGUI


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


class GuiTestCase:
    """unittest.TestCase mixin: a fresh, normally-sized LogPlotterGUI per
    test, with teardown that actually lets the process exit afterward.

    matplotlib's TkAgg backend spins up a hidden Tk root per plt.figure()
    call; without closing them the interpreter never exits even after the
    main window is destroyed.
    """

    def setUp(self):
        popups.clear()
        self.app = LogPlotterGUI()
        self.app.state("normal")
        self.app.geometry("1600x900")
        self.app.update_idletasks()
        self.app.update()

    def tearDown(self):
        import matplotlib.pyplot as plt
        plt.close("all")
        self.app.destroy()
