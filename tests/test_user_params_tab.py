"""The AP Version dropdown (top bar) and the User Parameters tab: switching
versions re-reads params/, the raw editor tracks unsaved edits, and the
Save Preferences / Mark Version as Default buttons appear only when
relevant."""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_support import gui, popups  # noqa: E402,F401

import LogPlotterGUI as gui_module  # noqa: E402
from test_param_plots import MinMaxLabelTests  # noqa: E402

SAMPLE_PARAMS_TEXT = MinMaxLabelTests.SAMPLE_PARAMS_TEXT


class TestVersionDropdown:
    def test_defaults_to_the_configured_ap_version(self, gui):
        expected = gui.app_config.get("ap_version", "AP3-SUB-006")
        assert gui.apVersionCombo.currentText() == expected
        assert gui.userParams.version == expected

    def test_dropdown_lists_every_version_file_in_params_dir(self, gui):
        gui._refresh_ap_version_choices()
        values = [gui.apVersionCombo.itemText(i) for i in range(gui.apVersionCombo.count())]
        assert "AP3-SUB-006" in values
        assert "AP3-SUB-004" in values

    def test_selecting_a_version_rereads_its_params(self, gui):
        gui._select_ap_version("AP3-SUB-004")
        assert gui.userParams.version == "AP3-SUB-004"
        assert gui.apVersionCombo.currentText() == "AP3-SUB-004"


class TestUserParamsEditor:
    def test_editor_shows_the_active_version_raw_file_contents(self, gui):
        gui.tabWidget.setCurrentIndex(2)
        expected = gui.userParams.read_raw()
        assert gui.userParamsTextEdit.toPlainText() == expected
        assert gui.userParamsVersionLabel.text() == gui.userParams.version

    def test_save_prefs_button_hidden_until_text_is_edited(self, gui):
        gui.tabWidget.setCurrentIndex(2)
        assert not gui.savePrefsButton.isVisible()

    def test_save_prefs_button_appears_after_an_edit_and_hides_when_reverted(self, gui):
        gui.tabWidget.setCurrentIndex(2)
        baseline = gui._userParamsBaseline

        gui.userParamsTextEdit.setPlainText(baseline + "\n# a comment\n")
        assert gui.savePrefsButton.isVisible()

        gui.userParamsTextEdit.setPlainText(baseline)
        assert not gui.savePrefsButton.isVisible()

    def test_switching_version_reloads_editor_and_clears_dirty_state(self, gui):
        gui.tabWidget.setCurrentIndex(2)
        gui.userParamsTextEdit.setPlainText(gui._userParamsBaseline + "\n# unsaved\n")
        assert gui.savePrefsButton.isVisible()

        gui._select_ap_version("AP3-SUB-004")
        assert not gui.savePrefsButton.isVisible()
        assert gui.userParamsTextEdit.toPlainText() == gui.userParams.read_raw()


class TestSavePreferences:
    """write_raw actually touches disk, so this points userParams at a
    throwaway temp directory rather than the repo's real params/ files."""

    def test_save_preferences_writes_the_file_and_reloads_fields(self, gui):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "UserParams_TEST-VER.txt").write_text(SAMPLE_PARAMS_TEXT, encoding="utf-8")
            gui.userParams.params_dir = Path(tmp)
            gui._select_ap_version("TEST-VER")
            gui.tabWidget.setCurrentIndex(2)

            new_text = SAMPLE_PARAMS_TEXT.replace('"General"', '"Renamed"')
            gui.userParamsTextEdit.setPlainText(new_text)

            gui._save_preferences()

            assert gui.userParams.plotNames == ["Renamed"]
            assert Path(tmp, "UserParams_TEST-VER.txt").read_text(encoding="utf-8") == new_text
            assert not gui.savePrefsButton.isVisible()

    def test_invalid_edits_are_rejected_and_left_dirty(self, gui):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "UserParams_TEST-VER.txt").write_text(SAMPLE_PARAMS_TEXT, encoding="utf-8")
            gui.userParams.params_dir = Path(tmp)
            gui._select_ap_version("TEST-VER")
            gui.tabWidget.setCurrentIndex(2)

            original = gui.userParamsTextEdit.toPlainText()
            gui.userParamsTextEdit.setPlainText("not ( valid")

            gui._save_preferences()

            assert len(popups) == 1
            assert popups[0][0] == "error"
            # The file on disk is untouched, and the box still holds the user's edit.
            assert gui.userParamsTextEdit.toPlainText() != original
            assert gui.savePrefsButton.isVisible()


class TestMarkVersionDefault:
    """_mark_version_default writes config.json - _save_config is patched
    to a no-op so tests never touch the repo's real config file."""

    def test_hidden_for_the_current_default_version(self, gui, monkeypatch):
        monkeypatch.setattr(gui_module, "_save_config", lambda cfg: None)
        gui.tabWidget.setCurrentIndex(2)
        assert not gui.markDefaultButton.isVisible()

    def test_shown_for_a_non_default_version(self, gui, monkeypatch):
        monkeypatch.setattr(gui_module, "_save_config", lambda cfg: None)
        gui.tabWidget.setCurrentIndex(2)
        gui._select_ap_version("AP3-SUB-004")
        assert gui.markDefaultButton.isVisible()

    def test_marking_default_updates_config_and_hides_the_button(self, gui, monkeypatch):
        monkeypatch.setattr(gui_module, "_save_config", lambda cfg: None)
        gui.tabWidget.setCurrentIndex(2)
        gui._select_ap_version("AP3-SUB-004")
        gui._mark_version_default()
        assert gui.app_config["ap_version"] == "AP3-SUB-004"
        assert not gui.markDefaultButton.isVisible()
