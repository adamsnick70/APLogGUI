"""The combined two-handle Start %/End % range slider (RangeSlider):
handles can't cross each other, and on_release only fires once a mouse
drag/keyboard nudge actually finishes - never mid-drag or on every
keypress, since each firing triggers an expensive replot."""
import sys
import tkinter as tk
import types
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_support  # noqa: E402,F401  (puts src/ on sys.path as a side effect)

from LogPlotterGUI import RangeSlider  # noqa: E402


def _range_vars(start=10.0, end=90.0):
    return types.SimpleNamespace(
        startPrctVar=tk.StringVar(value=f"{start:.1f}"),
        endPrctVar=tk.StringVar(value=f"{end:.1f}"),
        startScaleVar=tk.DoubleVar(value=start),
        endScaleVar=tk.DoubleVar(value=end),
    )


class RangeSliderTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.geometry("400x50")
        self.releases = []
        self.range_vars = _range_vars()
        self.slider = RangeSlider(self.root, self.range_vars, on_release=lambda: self.releases.append(1))
        self.slider.pack(fill="x")
        self.root.update_idletasks()

    def tearDown(self):
        self.root.destroy()

    def test_start_handle_cannot_be_dragged_past_the_end_handle(self):
        self.slider._set_value("start", 95.0)
        self.assertEqual(self.range_vars.startScaleVar.get(), self.range_vars.endScaleVar.get())

    def test_end_handle_cannot_be_dragged_past_the_start_handle(self):
        self.slider._set_value("end", 2.0)
        self.assertEqual(self.range_vars.endScaleVar.get(), self.range_vars.startScaleVar.get())

    def test_entries_update_live_as_values_change(self):
        self.slider._set_value("start", 33.0)
        self.assertEqual(self.range_vars.startPrctVar.get(), "33.0")

    def test_mouse_drag_does_not_fire_on_release_until_the_button_comes_up(self):
        self.slider._dragging = "start"
        self.slider._set_value("start", 20.0)
        self.assertEqual(self.releases, [], "must not fire mid-drag")
        self.slider._on_mouse_release(None)
        self.assertEqual(self.releases, [1], "must fire exactly once on release")

    def test_a_stray_release_with_no_prior_drag_does_not_fire(self):
        # e.g. a ButtonRelease that lands on this widget without a preceding
        # Button-1/B1-Motion here (focus/click started elsewhere).
        self.slider._on_mouse_release(None)
        self.assertEqual(self.releases, [])

    def test_keyboard_nudge_only_fires_on_key_release_not_keypress(self):
        self.slider._selected = "end"
        self.slider._move_selected(1.0)  # mirrors <KeyPress-Right>
        self.assertEqual(self.releases, [], "must not fire on key press")
        self.slider._on_key_release(None)  # mirrors <KeyRelease-Right>
        self.assertEqual(self.releases, [1])

    def test_clicking_the_rail_selects_whichever_handle_is_closer(self):
        near_start = self.slider._value_to_x(15.0)
        near_end = self.slider._value_to_x(85.0)
        self.assertEqual(self.slider._closest_handle(near_start), "start")
        self.assertEqual(self.slider._closest_handle(near_end), "end")


if __name__ == "__main__":
    unittest.main()
