"""The Parameterized Plots tab: threshold-as-percentage, autofind, the
start/end % sliders, and live-replot-on-drag."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_support import GuiTestCase, make_log_csv, make_log_csv_without_throttle, popups  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

from ParamPlots import ParamPlotUtil  # noqa: E402


class ThresholdAndSliderDisplayTests(GuiTestCase, unittest.TestCase):
    def test_default_threshold_is_a_true_percentage(self):
        # Previously the comparison silently divided by 10, so "7.5" in the
        # box actually meant "75% throttle". The box now means what it says.
        self.assertEqual(self.app.threshVar.get(), "75")

    def test_sliders_display_percentages_not_fractions(self):
        self.assertEqual(self.app.paramRange.startPrctVar.get(), "10.0")
        self.assertEqual(self.app.paramRange.endPrctVar.get(), "90.0")

    def test_dragging_a_slider_updates_the_entry_as_a_percentage(self):
        self.app.rangeFrame.range_slider._set_value("start", 37.4)
        self.assertEqual(self.app.paramRange.startPrctVar.get(), "37.4")


class AutofindTests(GuiTestCase, unittest.TestCase):
    def test_autofind_locates_the_high_throttle_event(self):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = make_log_csv(Path(tmp) / "log.csv")
            self.app.logPath.set(csv_path)
            self.app._refresh_fields(csv_path)
            self.app._plotParameterized()
            self.assertGreaterEqual(len(self.app.paramFigures), 1)

    def test_manual_range_path_produces_one_set_of_charts(self):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = make_log_csv(Path(tmp) / "log.csv")
            self.app.logPath.set(csv_path)
            self.app._refresh_fields(csv_path)
            self.app.autoFindVar.set(False)
            self.app._toggle_autofind(self.app.autoFindVar, self.app.rangeFrame, self.app._paramRangeGridKw)
            self.app.paramRange.startPrctVar.set("0.0")
            self.app.paramRange.endPrctVar.set("100.0")
            self.app._plotParameterized()
            self.assertGreaterEqual(len(self.app.paramFigures), 1)

    def test_autofind_disabled_when_throttle_field_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = make_log_csv_without_throttle(Path(tmp) / "log.csv")
            self.app._refresh_fields(csv_path)
            self.assertEqual(str(self.app.autoFindCheck.cget("state")), "disabled")
            self.assertFalse(self.app.autoFindVar.get())
            self.assertTrue(bool(self.app.rangeFrame.winfo_manager()), "sliders should be visible instead")

    def test_autofind_re_enabled_once_throttle_field_is_present_again(self):
        with tempfile.TemporaryDirectory() as tmp:
            no_throttle = make_log_csv_without_throttle(Path(tmp) / "no_throttle.csv")
            with_throttle = make_log_csv(Path(tmp) / "log.csv")
            self.app._refresh_fields(no_throttle)
            self.app._refresh_fields(with_throttle)
            self.assertEqual(str(self.app.autoFindCheck.cget("state")), "normal")


class LiveReplotTests(GuiTestCase, unittest.TestCase):
    def test_replot_is_deferred_until_the_slider_is_released(self):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = make_log_csv(Path(tmp) / "log.csv")
            self.app.logPath.set(csv_path)
            self.app._refresh_fields(csv_path)
            self.app.autoFindVar.set(False)
            self.app._toggle_autofind(self.app.autoFindVar, self.app.rangeFrame, self.app._paramRangeGridKw)
            self.app.paramRange.startPrctVar.set("0.0")
            self.app.paramRange.endPrctVar.set("50.0")
            self.app._plotParameterized()
            # One figure per UserParams group with at least one matching
            # field (every group but KS Noise/AVCS includes Throttle Pos).
            figure_count = len(self.app.paramFigures)
            self.assertGreaterEqual(figure_count, 1)
            first_fig = self.app.paramFigures[0]

            slider = self.app.rangeFrame.range_slider
            slider._dragging = "end"  # simulate an in-progress mouse drag
            slider._set_value("end", 90.0)

            self.assertEqual(
                self.app.paramRange.endPrctVar.get(), "90.0",
                "the displayed value should update live while dragging",
            )
            self.assertIs(
                self.app.paramFigures[0], first_fig,
                "must not replot mid-drag - only once the slider is released",
            )

            slider._on_mouse_release(None)

            self.assertEqual(len(self.app.paramFigures), figure_count)
            self.assertIsNot(self.app.paramFigures[0], first_fig, "expected a fresh replot once released")
            self.assertEqual(popups, [], "a slider drag must never pop a dialog")


class MinMaxLabelTests(unittest.TestCase):
    """UserParams.plotFields' third tuple element (min_max_enbl): when set,
    a line's legend label should also show its min/max - over whatever
    range was actually plotted, not the whole log (so an autofind-truncated
    event shows that event's min/max, not the full file's)."""

    def _plot_general_group(self, df, start_prct, end_prct):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "log.csv"
            df.to_csv(csv_path, index=False)
            util = ParamPlotUtil(str(csv_path), thresh=75)
            captured = []
            try:
                util._plotLog(start_prct, end_prct, False, on_figure=captured.append)
                self.assertEqual(len(captured), 1, "expected exactly one figure (the 'General' group)")
                return {line.get_label(): line for line in captured[0].axes[0].get_lines()}
            finally:
                for fig in captured:
                    plt.close(fig)

    def test_enabled_field_shows_min_max_of_the_truncated_range(self):
        rows = 200
        df = pd.DataFrame({
            "Time (sec)": np.round(np.arange(rows) * 0.1, 2),
            # scale is 0.001 for RPM, so raw = index * 1000 displays as index.
            "RPM (RPM)": np.arange(rows) * 1000.0,
        })
        # start=50, end=150 -> displayed RPM range is exactly [50, 149],
        # not the full file's [0, 199].
        lines = self._plot_general_group(df, 0.25, 0.75)
        matches = [label for label in lines if label.startswith("RPM")]
        self.assertEqual(len(matches), 1)
        self.assertIn("(50.00/149.00)", matches[0])

    def test_disabled_field_does_not_show_min_max(self):
        rows = 200
        df = pd.DataFrame({
            "Time (sec)": np.round(np.arange(rows) * 0.1, 2),
            "Coolant Temp (F)": np.arange(rows, dtype=float),  # min_max_enbl=False
        })
        lines = self._plot_general_group(df, 0.0, 1.0)
        matches = [label for label in lines if label.startswith("Coolant Temp")]
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0], "Coolant Temp (F / 10)", "no min/max suffix should be appended")


if __name__ == "__main__":
    unittest.main()
