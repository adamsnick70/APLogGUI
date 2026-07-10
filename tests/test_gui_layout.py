"""Window structure: the field sidebar, the tabgroup split, and the Custom
Plot tab's "no scrollbar needed for a normal chart" layout."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_support import GuiTestCase, make_log_csv  # noqa: E402


class TabStructureTests(GuiTestCase, unittest.TestCase):
    def test_tabs_in_expected_order(self):
        tabs = [self.app.notebook.tab(i, "text") for i in self.app.notebook.tabs()]
        self.assertEqual(tabs, ["Parameterized Plots", "Custom Plot", "User Parameters"])

    def test_sidebar_occupies_20_percent_of_body_width(self):
        sidebar_w = self.app.fieldPanel.master.winfo_width()
        notebook_w = self.app.notebook.winfo_width()
        ratio = sidebar_w / (sidebar_w + notebook_w)
        self.assertAlmostEqual(ratio, 0.20, delta=0.04, msg=f"ratio was {ratio:.3f}")

    def test_sidebar_width_is_capped_on_wide_windows(self):
        # Past a certain window width, 20% would leave the sidebar far wider
        # than any field name needs - it's capped to roughly the width of an
        # AccessPort version line instead of continuing to scale up.
        self.app.geometry("3200x900")
        self.app.update_idletasks()
        self.app.update()
        sidebar_w = self.app.fieldPanel.master.winfo_width()
        self.assertLessEqual(sidebar_w, self.app._sidebar_max_width + 2)
        self.assertLess(sidebar_w, 0.20 * 3200 - 50, "cap did not engage on a wide window")


class FieldSidebarTests(GuiTestCase, unittest.TestCase):
    def test_shows_placeholder_before_a_log_is_loaded(self):
        text = self.app.fieldPanel.text.get("1.0", "end-1c")
        self.assertEqual(text, "No log file selected.")

    def test_lists_every_csv_column_one_per_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = make_log_csv(Path(tmp) / "log.csv")
            self.app._refresh_fields(csv_path)

            import pandas as pd
            expected = list(pd.read_csv(csv_path, nrows=0).columns)
            lines = self.app.fieldPanel.text.get("1.0", "end-1c").splitlines()
            self.assertEqual(lines, expected)

    def test_field_text_is_read_only_but_still_selectable(self):
        # DISABLED blocks programmatic edits (insert/delete) but Tk's Text
        # widget still allows mouse selection and Ctrl+C copy - that's the
        # whole point of using Text instead of a Label per field.
        self.assertEqual(str(self.app.fieldPanel.text.cget("state")), "disabled")


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

    def test_setup_and_output_rows_have_correct_weights(self):
        # Plot row (2) has 6x the weight of the setup row (0) so it
        # dominates proportionally on every screen size. The button
        # divider (row 1) stays thin/unweighted.
        self.assertEqual(self.custom_tab.grid_rowconfigure(0)["weight"], 1)
        self.assertEqual(self.custom_tab.grid_rowconfigure(1)["weight"], 0)
        self.assertEqual(self.custom_tab.grid_rowconfigure(2)["weight"], 6)

    def test_row_minsizes_are_small_enough_to_not_dominate_on_small_screens(self):
        # If minsize values are too large they eat all the vertical space
        # on small displays and leave nothing for the weight ratio to act
        # on. Both setup and plot rows are capped at 120 px maximum minsize.
        self.assertLessEqual(self.custom_tab.grid_rowconfigure(0)["minsize"], 120)
        self.assertLessEqual(self.custom_tab.grid_rowconfigure(2)["minsize"], 120)

    def test_search_and_selected_fields_are_side_by_side(self):
        # Both setup areas live in row 0, in separate columns, rather than
        # stacked one above the other.
        search_info = self.app.fieldListbox.master.master.grid_info()
        selected_info = self.app.customSelectedScroll.master.grid_info()
        self.assertEqual(search_info["row"], 0)
        self.assertEqual(selected_info["row"], 0)
        self.assertNotEqual(search_info["column"], selected_info["column"])

    def test_plot_button_spans_30_percent_width_centered(self):
        button_row = self.custom_tab.grid_slaves(row=1, column=0)[0]
        weights = [button_row.grid_columnconfigure(c)["weight"] for c in range(3)]
        self.assertEqual(weights, [35, 30, 35])

    def test_plotted_chart_fits_without_internal_scrolling(self):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = make_log_csv(Path(tmp) / "log.csv")
            self.app.logPath.set(csv_path)
            self.app._refresh_fields(csv_path)

            self.app.customAutoFindVar.set(False)
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
