"""Window structure: the field sidebar, the tabgroup split, and the Custom
Plot tab's "no scrollbar needed for a normal chart" layout."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_support import GuiTestCase, make_log_csv  # noqa: E402


class TabStructureTests(GuiTestCase, unittest.TestCase):
    def test_two_tabs_in_expected_order(self):
        tabs = [self.app.notebook.tab(i, "text") for i in self.app.notebook.tabs()]
        self.assertEqual(tabs, ["Parameterized Plots", "Custom Plot"])

    def test_sidebar_occupies_20_percent_of_body_width(self):
        sidebar_w = self.app.fieldPanel.master.winfo_width()
        notebook_w = self.app.notebook.winfo_width()
        ratio = sidebar_w / (sidebar_w + notebook_w)
        self.assertAlmostEqual(ratio, 0.20, delta=0.04, msg=f"ratio was {ratio:.3f}")


class FieldSidebarTests(GuiTestCase, unittest.TestCase):
    def test_shows_placeholder_before_a_log_is_loaded(self):
        children = self.app.fieldPanel.content.winfo_children()
        self.assertEqual(len(children), 1)

    def test_lists_every_csv_column_one_per_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = make_log_csv(Path(tmp) / "log.csv")
            self.app._refresh_fields(csv_path)

            import pandas as pd
            expected = list(pd.read_csv(csv_path, nrows=0).columns)
            labels = [w.cget("text") for w in self.app.fieldPanel.content.winfo_children()]
            self.assertEqual(labels, expected)


class CustomPlotLayoutTests(GuiTestCase, unittest.TestCase):
    """Regression coverage for: 'the plot in the Custom Plot tab needs
    scrolling to see its contents.' The fix has two parts - the controls
    above the plot are capped to a small fixed height, and the rendered
    figure's height is itself capped to whatever room is actually left -
    so both halves are checked here."""

    def setUp(self):
        super().setUp()
        self.app.notebook.select(1)
        self.app.update_idletasks()
        self.app.update()
        self.custom_tab = self.app.notebook.nametowidget(self.app.notebook.tabs()[1])

    def test_field_list_and_selected_fields_rows_are_unweighted(self):
        # Only the plot output row should grow with extra window space;
        # the controls above it stay a small, fixed size.
        self.assertEqual(self.custom_tab.grid_rowconfigure(1)["weight"], 0)
        self.assertEqual(self.custom_tab.grid_rowconfigure(4)["weight"], 0)
        self.assertEqual(self.custom_tab.grid_rowconfigure(8)["weight"], 1)

    def test_plotted_chart_fits_without_internal_scrolling(self):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = make_log_csv(Path(tmp) / "log.csv")
            self.app.logPath.set(csv_path)
            self.app._refresh_fields(csv_path)

            self.app.customAutoFindVar.set(False)
            self.app._toggle_autofind(
                self.app.customAutoFindVar, self.app.customRangeFrame, self.app._customRangeGridKw
            )
            self.app.customRange.startPrctVar.set("0.0")
            self.app.customRange.endPrctVar.set("100.0")
            self.app.customSearchVar.set("Custom Sensor A")
            self.app.update_idletasks()
            self.app.fieldListbox.selection_set(0)
            self.app._add_selected_custom_fields()

            self.app._plotCustom()
            self.app.update_idletasks()
            self.app.update()

            canvas_h = self.app.customScrollArea.canvas.winfo_height()
            content_h = self.app.customScrollArea.content.winfo_height()
            self.assertLessEqual(
                content_h, canvas_h,
                f"plotted content ({content_h}px) overflows the visible area ({canvas_h}px)",
            )


if __name__ == "__main__":
    unittest.main()
