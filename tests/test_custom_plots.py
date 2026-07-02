"""The Custom Plot tab: field search/select/scale, the time-axis exclusion,
and autofind sharing the same throttle field as the Parameterized tab."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_support import GuiTestCase, make_log_csv  # noqa: E402

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
    def test_has_its_own_autofind_threshold_control(self):
        self.assertTrue(hasattr(self.app, "customAutoFindVar"))
        self.assertTrue(hasattr(self.app, "customThreshVar"))

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

    def test_autofind_off_produces_one_chart_for_the_whole_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = make_log_csv(Path(tmp) / "log.csv")
            self.app.logPath.set(csv_path)
            self.app._refresh_fields(csv_path)
            _select_field(self.app, "Custom Sensor A")

            self.app.customAutoFindVar.set(False)
            self.app._plotCustom()
            self.assertEqual(len(self.app.customFigures), 1)


if __name__ == "__main__":
    unittest.main()
