"""The Custom Plot tab: field search/select/scale, the time-axis exclusion,
autofind sharing the same throttle field as the Parameterized tab, and
live-replot-on-drag (including the silent-skip regression)."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_support import GuiTestCase, make_log_csv, popups  # noqa: E402

import UserParams  # noqa: E402


class FieldSelectionTests(GuiTestCase, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.csv_path = make_log_csv(Path(self.tmp.name) / "log.csv")
        self.app.logPath.set(self.csv_path)
        self.app._refresh_fields(self.csv_path)

    def tearDown(self):
        self.tmp.cleanup()
        super().tearDown()

    def test_time_field_is_never_a_selectable_series(self):
        # Time is always the plot's x-axis, never a y-series.
        listed = list(self.app.fieldListbox.get(0, "end"))
        self.assertNotIn("Time (sec)", listed)
        self.assertTrue(all("time" not in f.lower() for f in listed))

    def test_search_filters_the_field_list(self):
        self.app.customSearchVar.set("Custom")
        self.app.update_idletasks()
        self.assertEqual(
            list(self.app.fieldListbox.get(0, "end")),
            ["Custom Sensor A (V)", "Custom Sensor B (V)"],
        )

    def test_add_select_scale_and_remove_a_field(self):
        self.app.customSearchVar.set("Custom Sensor A")
        self.app.update_idletasks()
        self.app.fieldListbox.selection_set(0)
        self.app._add_selected_custom_fields()

        self.assertEqual(len(self.app.customFields), 1)
        entry = self.app.customFields[0]
        self.assertEqual(entry["field"], "Custom Sensor A (V)")
        self.assertEqual(entry["scale_var"].get(), "1")

        entry["scale_var"].set("2.5")
        self.app._remove_custom_field(entry)
        self.assertEqual(self.app.customFields, [])

    def test_re_adding_an_already_selected_field_does_not_duplicate_it(self):
        self.app.customSearchVar.set("Custom Sensor A")
        self.app.update_idletasks()
        self.app.fieldListbox.selection_set(0)
        self.app._add_selected_custom_fields()
        self.app._add_selected_custom_fields()
        self.assertEqual(len(self.app.customFields), 1)


def _select_field(app, search_text):
    app.customSearchVar.set(search_text)
    app.update_idletasks()
    app.fieldListbox.selection_set(0)
    app._add_selected_custom_fields()
    app.customSearchVar.set("")
    app.update_idletasks()


class CustomAutofindTests(GuiTestCase, unittest.TestCase):
    def test_has_its_own_autofind_threshold_and_range_controls(self):
        self.assertTrue(hasattr(self.app, "customAutoFindVar"))
        self.assertTrue(hasattr(self.app, "customThreshVar"))
        self.assertTrue(hasattr(self.app, "customRange"))

    def test_autofind_uses_throttle_field_even_when_not_itself_selected(self):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = make_log_csv(Path(tmp) / "log.csv")
            self.app.logPath.set(csv_path)
            self.app._refresh_fields(csv_path)
            _select_field(self.app, "Custom Sensor A")

            self.assertTrue(all(f["field"] != UserParams.throttleField for f in self.app.customFields))

            self.app.customAutoFindVar.set(True)
            self.app._plotCustom()
            self.assertGreaterEqual(len(self.app.customFigures), 1)

    def test_manual_range_path_produces_one_chart(self):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = make_log_csv(Path(tmp) / "log.csv")
            self.app.logPath.set(csv_path)
            self.app._refresh_fields(csv_path)
            _select_field(self.app, "Custom Sensor A")

            self.app.customAutoFindVar.set(False)
            self.app._toggle_autofind(
                self.app.customAutoFindVar, self.app.customRangeFrame, self.app._customRangeGridKw
            )
            self.app.customRange.startPrctVar.set("0.0")
            self.app.customRange.endPrctVar.set("100.0")
            self.app._plotCustom()
            self.assertEqual(len(self.app.customFigures), 1)


class LiveReplotTests(GuiTestCase, unittest.TestCase):
    def test_dragging_end_slider_after_a_plot_exists_replots_in_place(self):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = make_log_csv(Path(tmp) / "log.csv")
            self.app.logPath.set(csv_path)
            self.app._refresh_fields(csv_path)
            _select_field(self.app, "Custom Sensor A")

            self.app.customAutoFindVar.set(False)
            self.app._toggle_autofind(
                self.app.customAutoFindVar, self.app.customRangeFrame, self.app._customRangeGridKw
            )
            self.app.customRange.startPrctVar.set("0.0")
            self.app.customRange.endPrctVar.set("50.0")
            self.app._plotCustom()
            self.assertEqual(len(self.app.customFigures), 1)
            first_fig = self.app.customFigures[0]

            self.app._on_end_scale(self.app.customRange, "90.0", self.app._replot_custom_if_live)

            self.assertEqual(len(self.app.customFigures), 1)
            self.assertIsNot(self.app.customFigures[0], first_fig)
            self.assertEqual(self.app.customRange.endPrctVar.get(), "90.0")

    def test_dragging_a_slider_with_no_fields_selected_does_not_pop_a_dialog(self):
        """Regression: clearing the selected fields after plotting, then
        dragging a slider, used to call straight through to _plotCustom()'s
        validation, which shows a blocking messagebox - fine for an explicit
        Plot click, but a frozen/invisible dialog when fired from a slider
        drag with no one there to dismiss it. The live-replot path must
        skip silently instead."""
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = make_log_csv(Path(tmp) / "log.csv")
            self.app.logPath.set(csv_path)
            self.app._refresh_fields(csv_path)
            _select_field(self.app, "Custom Sensor A")

            self.app.customAutoFindVar.set(False)
            self.app._toggle_autofind(
                self.app.customAutoFindVar, self.app.customRangeFrame, self.app._customRangeGridKw
            )
            self.app._plotCustom()
            self.assertEqual(len(self.app.customFigures), 1)
            stale_fig = self.app.customFigures[0]

            self.app._reset_custom_fields()
            self.app._on_start_scale(self.app.customRange, "5.0", self.app._replot_custom_if_live)

            self.assertEqual(popups, [], "slider drag popped a dialog instead of skipping silently")
            self.assertIs(
                self.app.customFigures[0], stale_fig,
                "stale chart should be left alone, not cleared, when the replot is skipped",
            )


if __name__ == "__main__":
    unittest.main()
