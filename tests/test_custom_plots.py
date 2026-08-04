"""The Custom Plot tab: field search/select/scale, the time-axis exclusion,
autofind sharing the same throttle field as the Parameterized tab, the
Save PDF button, and the side-by-side search/selected-fields layout."""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_support import gui, make_log_csv  # noqa: E402,F401

import numpy as np  # noqa: E402


class TestFieldSelection:
    def test_time_field_is_never_a_selectable_series(self, gui):
        # Time is always the plot's x-axis, never a y-series.
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = make_log_csv(Path(tmp) / "log.csv")
            gui.logPathEdit.setText(csv_path)
            gui._refresh_fields(csv_path)
            listed = [gui.customFieldListWidget.item(i).text() for i in range(gui.customFieldListWidget.count())]
            assert "Time (sec)" not in listed
            assert all("time" not in f.lower() for f in listed)

    def test_search_filters_the_field_list(self, gui):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = make_log_csv(Path(tmp) / "log.csv")
            gui.logPathEdit.setText(csv_path)
            gui._refresh_fields(csv_path)
            gui.customSearchEdit.setText("Custom")
            listed = [gui.customFieldListWidget.item(i).text() for i in range(gui.customFieldListWidget.count())]
            assert listed == ["Custom Sensor A (V)", "Custom Sensor B (V)"]

    def test_add_select_scale_and_remove_a_field(self, gui):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = make_log_csv(Path(tmp) / "log.csv")
            gui.logPathEdit.setText(csv_path)
            gui._refresh_fields(csv_path)
            gui.customSearchEdit.setText("Custom Sensor A")
            gui.customFieldListWidget.item(0).setSelected(True)
            gui._add_selected_custom_fields()

            assert len(gui.customFields) == 1
            entry = gui.customFields[0]
            assert entry["field"] == "Custom Sensor A (V)"
            assert entry["scale_edit"].text() == "1"

            entry["scale_edit"].setText("2.5")
            gui._remove_custom_field(entry)
            assert gui.customFields == []

    def test_re_adding_an_already_selected_field_does_not_duplicate_it(self, gui):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = make_log_csv(Path(tmp) / "log.csv")
            gui.logPathEdit.setText(csv_path)
            gui._refresh_fields(csv_path)
            gui.customSearchEdit.setText("Custom Sensor A")
            gui.customFieldListWidget.item(0).setSelected(True)
            gui._add_selected_custom_fields()
            gui._add_selected_custom_fields()
            assert len(gui.customFields) == 1


def _select_field(gui, search_text):
    gui.customSearchEdit.setText(search_text)
    gui.customFieldListWidget.item(0).setSelected(True)
    gui._add_selected_custom_fields()
    gui.customSearchEdit.setText("")


class TestCustomAutofind:
    def test_has_its_own_autofind_threshold_control(self, gui):
        assert hasattr(gui, "customAutoFindCheck")
        assert hasattr(gui, "customThreshEdit")

    def test_autofind_uses_throttle_field_even_when_not_itself_selected(self, gui):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = make_log_csv(Path(tmp) / "log.csv")
            gui.logPathEdit.setText(csv_path)
            gui._refresh_fields(csv_path)
            _select_field(gui, "Custom Sensor A")

            assert all(f["field"] != gui.userParams.throttleField for f in gui.customFields)

            gui.customAutoFindCheck.setChecked(True)
            gui._regenerate_custom_plot()
            assert len(gui.customFigures) >= 1

    def test_autofind_off_produces_one_chart_for_the_whole_log(self, gui):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = make_log_csv(Path(tmp) / "log.csv")
            gui.logPathEdit.setText(csv_path)
            gui._refresh_fields(csv_path)
            _select_field(gui, "Custom Sensor A")

            gui.customAutoFindCheck.setChecked(False)
            gui._regenerate_custom_plot()
            assert len(gui.customFigures) == 1


class TestCustomPdfButton:
    """The Custom Plot tab has the same Save PDF capability as the
    Parameterized Plots tab - hidden until there's a plot. isVisible()
    reflects the tab actually being the active/shown page, so these
    select it first."""

    def test_hidden_until_a_plot_exists(self, gui):
        gui.tabWidget.setCurrentIndex(1)
        assert not gui.customPdfButton.isVisible()

    def test_shown_after_plotting_and_matches_param_tab_button_width(self, gui):
        gui.tabWidget.setCurrentIndex(1)
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = make_log_csv(Path(tmp) / "log.csv")
            gui.logPathEdit.setText(csv_path)
            gui._refresh_fields(csv_path)
            _select_field(gui, "Custom Sensor A")

            gui.customAutoFindCheck.setChecked(False)
            gui._regenerate_custom_plot()

            assert gui.customPdfButton.isVisible()
            assert gui.customPdfButton.sizeHint().width() == gui.paramPdfButton.sizeHint().width()


class TestCustomTabLayout:
    def test_search_and_selected_fields_are_side_by_side(self, gui):
        # Both live directly under customSetupWidget (search/selected are
        # each a bare nested QVBoxLayout, not a separate container widget),
        # in separate columns rather than stacked one above the other. A
        # hidden QTabWidget page doesn't get its children positioned until
        # it's actually the current tab, hence selecting it first.
        gui.tabWidget.setCurrentIndex(1)
        assert gui.customSearchEdit.parentWidget() is gui.customSelectedScrollArea.parentWidget()
        assert gui.customSearchEdit.x() < gui.customSelectedScrollArea.x()

    def test_plotted_chart_has_the_expected_title(self, gui):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = make_log_csv(Path(tmp) / "log.csv")
            gui.logPathEdit.setText(csv_path)
            gui._refresh_fields(csv_path)
            _select_field(gui, "Custom Sensor A")
            gui.customAutoFindCheck.setChecked(False)
            gui._regenerate_custom_plot()

            assert len(gui.customFigures) == 1
            assert gui.customFigures[0].getPlotItem().titleLabel.text == "Custom Plot"

    def test_no_plot_button_on_this_tab(self, gui):
        # Replaced by regeneration on every add/remove/rescale/autofind
        # change - see TestAutoRegeneration below.
        assert not hasattr(gui, "customPlotButton")


class TestFieldSelectionsAcrossLogReloads:
    """Loading a new log used to unconditionally wipe the Custom Plots
    tab's selections. Now it only does that when the new log's AP version
    differs from the previous one - see LogPlotterGUI._refresh_fields."""

    def test_kept_when_the_new_log_is_the_same_ap_version(self, gui):
        with tempfile.TemporaryDirectory() as tmp:
            first = make_log_csv(Path(tmp) / "first.csv")
            second = make_log_csv(Path(tmp) / "second.csv", extra_fields={
                "AP Info:[AP3-SUB-006 v1.7.6.0-28785][Test Vehicle]": np.zeros(200),
                "Custom Sensor A (V)": np.sin(np.linspace(0, 10, 200)),
            })
            gui.logPathEdit.setText(first)
            gui._refresh_fields(first)
            _select_field(gui, "Custom Sensor A")
            assert len(gui.customFields) == 1

            gui.logPathEdit.setText(second)
            gui._refresh_fields(second)
            assert gui.userParams.version == "AP3-SUB-006"
            assert [f["field"] for f in gui.customFields] == ["Custom Sensor A (V)"]

    def test_cleared_when_the_new_log_names_a_different_ap_version(self, gui):
        with tempfile.TemporaryDirectory() as tmp:
            first = make_log_csv(Path(tmp) / "first.csv")
            second = make_log_csv(Path(tmp) / "second.csv", extra_fields={
                "AP Info:[AP3-SUB-004 v1.0.0.0-11111][Test Vehicle]": np.zeros(200),
                "Custom Sensor A (V)": np.sin(np.linspace(0, 10, 200)),
            })
            gui.logPathEdit.setText(first)
            gui._refresh_fields(first)
            _select_field(gui, "Custom Sensor A")
            assert len(gui.customFields) == 1

            gui.logPathEdit.setText(second)
            gui._refresh_fields(second)
            assert gui.userParams.version == "AP3-SUB-004"
            assert gui.customFields == []

    def test_plot_is_regenerated_against_the_new_log_when_version_is_unchanged(self, gui):
        with tempfile.TemporaryDirectory() as tmp:
            first = make_log_csv(Path(tmp) / "first.csv")
            second = make_log_csv(Path(tmp) / "second.csv", extra_fields={
                "AP Info:[AP3-SUB-006 v1.7.6.0-28785][Test Vehicle]": np.zeros(200),
                "Custom Sensor A (V)": np.sin(np.linspace(0, 10, 200)),
            })
            gui.logPathEdit.setText(first)
            gui._refresh_fields(first)
            _select_field(gui, "Custom Sensor A")
            gui.customAutoFindCheck.setChecked(False)
            gui._regenerate_custom_plot()
            assert len(gui.customFigures) == 1

            # Loading the second log should re-plot on its own, with no
            # explicit _regenerate_custom_plot() call needed.
            gui.logPathEdit.setText(second)
            gui._refresh_fields(second)
            assert len(gui.customFigures) == 1


class TestAutoRegeneration:
    """The Custom Plot tab has no Plot button - the chart regenerates
    itself whenever a field is added, removed, or rescaled, or the
    autofind checkbox/threshold changes."""

    def test_adding_a_field_regenerates_the_plot(self, gui):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = make_log_csv(Path(tmp) / "log.csv")
            gui.logPathEdit.setText(csv_path)
            gui._refresh_fields(csv_path)
            gui.customAutoFindCheck.setChecked(False)

            assert gui.customFigures == []
            _select_field(gui, "Custom Sensor A")
            assert len(gui.customFigures) == 1

    def test_removing_the_last_field_clears_the_plot(self, gui):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = make_log_csv(Path(tmp) / "log.csv")
            gui.logPathEdit.setText(csv_path)
            gui._refresh_fields(csv_path)
            gui.customAutoFindCheck.setChecked(False)
            _select_field(gui, "Custom Sensor A")
            assert len(gui.customFigures) == 1

            gui._remove_custom_field(gui.customFields[0])
            assert gui.customFigures == []

    def test_finishing_a_rescale_edit_regenerates_the_plot(self, gui):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = make_log_csv(Path(tmp) / "log.csv")
            gui.logPathEdit.setText(csv_path)
            gui._refresh_fields(csv_path)
            gui.customAutoFindCheck.setChecked(False)
            _select_field(gui, "Custom Sensor A")

            entry = gui.customFields[0]
            entry["scale_edit"].setText("2.5")
            entry["scale_edit"].editingFinished.emit()

            assert len(gui.customFigures) == 1
            label = gui.customFigures[0].getPlotItem().legend.items[0][1].text
            assert "* 2.5" in label

    def test_toggling_autofind_regenerates_the_plot(self, gui):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = make_log_csv(Path(tmp) / "log.csv")
            gui.logPathEdit.setText(csv_path)
            gui._refresh_fields(csv_path)
            gui.customAutoFindCheck.setChecked(False)
            _select_field(gui, "Custom Sensor A")
            assert len(gui.customFigures) == 1

            gui.customAutoFindCheck.setChecked(True)
            assert len(gui.customFigures) >= 1

    def test_invalid_scale_is_reported_without_a_modal_popup(self, gui):
        # No Plot button/click to blame this on anymore - an in-progress
        # edit shouldn't interrupt typing with a dialog (see popups).
        from test_support import popups
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = make_log_csv(Path(tmp) / "log.csv")
            gui.logPathEdit.setText(csv_path)
            gui._refresh_fields(csv_path)
            gui.customAutoFindCheck.setChecked(False)
            _select_field(gui, "Custom Sensor A")
            popups.clear()

            entry = gui.customFields[0]
            entry["scale_edit"].setText("not-a-number")
            entry["scale_edit"].editingFinished.emit()

            assert popups == []
            assert "must be a number" in gui.statusLabel.text()
