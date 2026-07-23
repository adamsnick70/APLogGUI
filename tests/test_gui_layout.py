"""Window structure: tab order, the field sidebar/tabgroup splitter, and
the field sidebar's placeholder/read-only-but-selectable behavior."""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_support import gui, make_log_csv, make_window  # noqa: E402,F401

from PySide6.QtCore import Qt  # noqa: E402


class TestTabStructure:
    def test_tabs_in_expected_order(self, gui):
        tabs = [gui.tabWidget.tabText(i) for i in range(gui.tabWidget.count())]
        assert tabs == ["Parameterized Plots", "Custom Plot", "User Parameters"]

    def test_sidebar_occupies_20_percent_of_body_width(self, gui, qtbot):
        qtbot.wait(10)
        sidebar_w, tabs_w = gui.bodySplitter.sizes()
        ratio = sidebar_w / (sidebar_w + tabs_w)
        assert abs(ratio - 0.20) < 0.04, f"ratio was {ratio:.3f}"

    def test_sidebar_width_is_capped_on_wide_windows(self, qtbot, tmp_path, monkeypatch):
        # The cap is applied once, on first show (see
        # MainWindow._apply_initial_sidebar_width) - so a wide size set
        # before that first show is what exercises it here.
        window = make_window(qtbot, tmp_path, monkeypatch, size=(3200, 900))
        qtbot.wait(10)

        sidebar_w, tabs_w = window.bodySplitter.sizes()
        assert sidebar_w <= window.bodySplitter.width() * 0.20 - 50, "cap did not engage on a wide window"
        window.close()


class TestFieldSidebar:
    def test_shows_placeholder_before_a_log_is_loaded(self, gui):
        assert gui.fieldPanel.toPlainText() == "No log file selected."

    def test_lists_every_csv_column_one_per_line(self, gui):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = make_log_csv(Path(tmp) / "log.csv")
            gui._refresh_fields(csv_path)

            import pandas as pd
            expected = list(pd.read_csv(csv_path, nrows=0).columns)
            lines = gui.fieldPanel.toPlainText().splitlines()
            assert lines == expected

    def test_field_text_is_read_only_but_still_selectable(self, gui):
        # Read-only blocks user edits, but TextSelectableByMouse/Keyboard
        # keeps mouse selection and Ctrl+C copy working - the same
        # "read-only but copyable" behavior the Tkinter version's
        # disabled-but-not-locked Text widget gave for free, now via
        # QPlainTextEdit's own flags instead of a custom class.
        assert gui.fieldPanel.isReadOnly()
        flags = gui.fieldPanel.textInteractionFlags()
        assert flags & Qt.TextInteractionFlag.TextSelectableByMouse
        assert flags & Qt.TextInteractionFlag.TextSelectableByKeyboard
