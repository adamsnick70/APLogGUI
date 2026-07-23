"""The Parameterized Plots tab: threshold-as-percentage, autofind, and
x-axis linking across plots (whole tab when autofind is off, per-event
when it's on)."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_support import (  # noqa: E402
    gui, make_log_csv, make_log_csv_two_events, make_log_csv_without_throttle,
)

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from UserParams import UserParams  # noqa: E402
from ParamPlots import ParamPlotUtil  # noqa: E402


class TestThresholdDisplay:
    def test_default_threshold_is_a_true_percentage(self, gui):
        # Previously the comparison silently divided by 10, so "7.5" in the
        # box actually meant "75% throttle". The box now means what it says.
        assert gui.paramAutoFindThreshEdit.text() == "75"


class TestAutofind:
    def test_autofind_locates_the_high_throttle_event(self, gui):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = make_log_csv(Path(tmp) / "log.csv")
            gui.logPathEdit.setText(csv_path)
            gui._refresh_fields(csv_path)
            gui._plot_parameterized()
            assert len(gui.paramFigures) >= 1

    def test_autofind_off_plots_the_whole_log(self, gui):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = make_log_csv(Path(tmp) / "log.csv")
            gui.logPathEdit.setText(csv_path)
            gui._refresh_fields(csv_path)
            gui.paramAutoFindCheck.setChecked(False)
            gui._plot_parameterized()
            assert len(gui.paramFigures) >= 1

    def test_autofind_disabled_when_throttle_field_missing(self, gui):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = make_log_csv_without_throttle(Path(tmp) / "log.csv")
            gui._refresh_fields(csv_path)
            assert not gui.paramAutoFindCheck.isEnabled()
            assert not gui.paramAutoFindCheck.isChecked()

    def test_autofind_re_enabled_once_throttle_field_is_present_again(self, gui):
        with tempfile.TemporaryDirectory() as tmp:
            no_throttle = make_log_csv_without_throttle(Path(tmp) / "no_throttle.csv")
            with_throttle = make_log_csv(Path(tmp) / "log.csv")
            gui._refresh_fields(no_throttle)
            gui._refresh_fields(with_throttle)
            assert gui.paramAutoFindCheck.isEnabled()


class TestAxisLinking:
    """Every plot lives in its own separate pg.PlotWidget (one per
    UserParams.plotNames group), so pyqtgraph's setXLink is used to mirror
    pan/zoom across them - see LogPlotterGUI._link_x_axes, wired up from
    _plot_parameterized."""

    def test_links_x_axes_across_the_whole_tab_when_autofind_is_off(self, gui):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = make_log_csv(Path(tmp) / "log.csv")
            gui.logPathEdit.setText(csv_path)
            gui._refresh_fields(csv_path)
            gui.paramAutoFindCheck.setChecked(False)
            gui._plot_parameterized()
            assert len(gui.paramFigures) >= 2

            view_boxes = [fig.getPlotItem().getViewBox() for fig in gui.paramFigures]
            view_boxes[0].setXRange(2.0, 5.0, padding=0)
            for vb in view_boxes[1:]:
                assert tuple(round(v, 6) for v in vb.viewRange()[0]) == (2.0, 5.0)

    def test_links_x_axes_only_within_each_high_throttle_event(self, gui):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = make_log_csv_two_events(Path(tmp) / "log.csv")
            gui.logPathEdit.setText(csv_path)
            gui._refresh_fields(csv_path)
            gui.paramAutoFindCheck.setChecked(True)
            gui._plot_parameterized()

            event_groups = [g for g in gui.paramAxisGroups if g]
            assert len(event_groups) == 2, "expected one axis group per high-throttle event"
            group1, group2 = event_groups
            assert len(group1) >= 2
            assert len(group2) >= 2

            vb1 = [w.getPlotItem().getViewBox() for w in group1]
            vb2 = [w.getPlotItem().getViewBox() for w in group2]
            original_xlim = vb2[0].viewRange()[0]
            vb1[0].setXRange(2.0, 5.0, padding=0)
            for vb in vb1[1:]:
                assert tuple(round(v, 6) for v in vb.viewRange()[0]) == (2.0, 5.0)
            for vb in vb2:
                assert vb.viewRange()[0] == original_xlim, "a different event's axes must not move"


class AutofindBoundsTests(unittest.TestCase):
    """A throttle rise within the last 12 samples of the log used to index
    _autoFind's "avoid spikes" lookahead past the end of the array (see
    LogPlotUtil._autoFind) instead of being clamped to the last sample."""

    def test_rise_near_end_of_log_does_not_crash(self):
        util = ParamPlotUtil("unused.csv", thresh=75)
        throttle = np.full(200, 5.0, dtype=np.float32)
        throttle[195:] = 85.0  # rise 5 samples before the very end
        event_times = util._autoFind(throttle)
        self.assertIsInstance(event_times, list)


class MinMaxLabelTests(unittest.TestCase):
    """UserParams.plotFields' third tuple element (min_max_enbl): when set,
    a line's legend label should also show its min/max - over whatever
    range was actually plotted, not the whole log (so an autofind-truncated
    event shows that event's min/max, not the full file's).

    Uses an isolated, temp-dir UserParams (rather than the shipped
    params/UserParams_*.txt) so this test's expectations don't silently
    drift if those files' min_max_enbl flags ever change.
    """

    SAMPLE_PARAMS_TEXT = '''\
throttleField = "Throttle Pos (%)"
plotNames = ["General"]
plotFields = {
    "General": [
        ("RPM (RPM)", 0.001, True),
        ("Coolant Temp (F)", 0.1, False),
    ],
}
plotLimits = {}
plotSpecs = {}
'''

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        Path(self.tmp.name, "UserParams_TEST-VER.txt").write_text(self.SAMPLE_PARAMS_TEXT, encoding="utf-8")
        self.userParams = UserParams(params_dir=self.tmp.name)
        self.userParams.read_params("TEST-VER")

    def tearDown(self):
        self.tmp.cleanup()

    def _plot_general_group(self, df, start, end):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "log.csv"
            df.to_csv(csv_path, index=False)
            util = ParamPlotUtil(str(csv_path), thresh=75, userParams=self.userParams)
            captured = []
            util._makePlots(start, end, on_figure=captured.append)
            self.assertEqual(len(captured), 1, "expected exactly one plot widget (the 'General' group)")
            items = captured[0].getPlotItem().listDataItems()
            return {item.name(): item for item in items if item.name()}

    def test_enabled_field_shows_min_max_of_the_truncated_range(self):
        rows = 200
        df = pd.DataFrame({
            "Time (sec)": np.round(np.arange(rows) * 0.1, 2),
            # scale is 0.001 for RPM, so raw = index * 1000 displays as index.
            "RPM (RPM)": np.arange(rows) * 1000.0,
        })
        # start=50, end=150 -> displayed RPM range is exactly [50, 149],
        # not the full file's [0, 199].
        lines = self._plot_general_group(df, 50, 150)
        matches = [label for label in lines if label.startswith("RPM")]
        self.assertEqual(len(matches), 1)
        self.assertIn("(50.00/149.00)", matches[0])

    def test_disabled_field_does_not_show_min_max(self):
        rows = 200
        df = pd.DataFrame({
            "Time (sec)": np.round(np.arange(rows) * 0.1, 2),
            "Coolant Temp (F)": np.arange(rows, dtype=float),  # min_max_enbl=False
        })
        lines = self._plot_general_group(df, 0, rows)
        matches = [label for label in lines if label.startswith("Coolant Temp")]
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0], "Coolant Temp (F / 10)", "no min/max suffix should be appended")


if __name__ == "__main__":
    unittest.main()
