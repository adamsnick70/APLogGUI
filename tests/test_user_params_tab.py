"""The AP Version dropdown (top bar) and the User Parameters tab: switching
versions re-reads params/, the raw editor tracks unsaved edits, and the
Save Preferences / Mark Version as Default buttons appear only when
relevant."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_support import GuiTestCase, popups  # noqa: E402

import LogPlotterGUI as gui_module  # noqa: E402
from test_user_params import SAMPLE_PARAMS_TEXT  # noqa: E402


class VersionDropdownTests(GuiTestCase, unittest.TestCase):
    def test_defaults_to_the_configured_ap_version(self):
        expected = self.app.app_config.get("ap_version", "AP3-SUB-006")
        self.assertEqual(self.app.apVersionVar.get(), expected)
        self.assertEqual(self.app.userParams.version, expected)

    def test_dropdown_lists_every_version_file_in_params_dir(self):
        self.app._refresh_ap_version_choices()
        values = list(self.app.apVersionCombo["values"])
        self.assertIn("AP3-SUB-006", values)
        self.assertIn("AP3-SUB-004", values)

    def test_selecting_a_version_rereads_its_params(self):
        self.app._select_ap_version("AP3-SUB-004")
        self.assertEqual(self.app.userParams.version, "AP3-SUB-004")
        self.assertEqual(self.app.apVersionVar.get(), "AP3-SUB-004")


class UserParamsEditorTests(GuiTestCase, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.app.notebook.select(2)
        self.app.update_idletasks()
        self.app.update()

    def test_editor_shows_the_active_version_raw_file_contents(self):
        expected = self.app.userParams.read_raw()
        shown = self.app.userParamsText.get("1.0", "end-1c")
        self.assertEqual(shown, expected)
        self.assertEqual(self.app.userParamsVersionLabel.cget("text"), self.app.userParams.version)

    def test_save_prefs_button_hidden_until_text_is_edited(self):
        self.assertEqual(self.app.savePrefsButton.winfo_manager(), "")

    def test_save_prefs_button_appears_after_an_edit_and_hides_when_reverted(self):
        self.app.userParamsText.insert("end", "\n# a comment\n")
        self.app._update_save_prefs_button()
        self.assertEqual(self.app.savePrefsButton.winfo_manager(), "pack")

        self.app.userParamsText.delete("1.0", "end")
        self.app.userParamsText.insert("1.0", self.app._userParamsBaseline)
        self.app._update_save_prefs_button()
        self.assertEqual(self.app.savePrefsButton.winfo_manager(), "")

    def test_switching_version_reloads_editor_and_clears_dirty_state(self):
        self.app.userParamsText.insert("end", "\n# unsaved\n")
        self.app._update_save_prefs_button()
        self.assertEqual(self.app.savePrefsButton.winfo_manager(), "pack")

        self.app._select_ap_version("AP3-SUB-004")
        self.assertEqual(self.app.savePrefsButton.winfo_manager(), "")
        self.assertEqual(
            self.app.userParamsText.get("1.0", "end-1c"),
            self.app.userParams.read_raw(),
        )


class SavePreferencesTests(GuiTestCase, unittest.TestCase):
    """write_raw actually touches disk, so this points userParams at a throwaway
    temp directory rather than the repo's real params/ files."""

    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        Path(self.tmp.name, "UserParams_TEST-VER.txt").write_text(SAMPLE_PARAMS_TEXT, encoding="utf-8")
        self.app.userParams.params_dir = Path(self.tmp.name)
        self.app._select_ap_version("TEST-VER")
        self.app.notebook.select(2)
        self.app.update_idletasks()
        self.app.update()

    def tearDown(self):
        self.tmp.cleanup()
        super().tearDown()

    def test_save_preferences_writes_the_file_and_reloads_fields(self):
        new_text = SAMPLE_PARAMS_TEXT.replace('"General"', '"Renamed"')
        self.app.userParamsText.delete("1.0", "end")
        self.app.userParamsText.insert("1.0", new_text)
        self.app._update_save_prefs_button()

        self.app._save_preferences()

        self.assertEqual(self.app.userParams.plotNames, ["Renamed"])
        self.assertEqual(
            Path(self.tmp.name, "UserParams_TEST-VER.txt").read_text(encoding="utf-8"), new_text
        )
        self.assertEqual(self.app.savePrefsButton.winfo_manager(), "")

    def test_invalid_edits_are_rejected_and_left_dirty(self):
        original = self.app.userParamsText.get("1.0", "end-1c")
        self.app.userParamsText.delete("1.0", "end")
        self.app.userParamsText.insert("1.0", "not ( valid")
        self.app._update_save_prefs_button()

        self.app._save_preferences()

        self.assertEqual(len(popups), 1)
        self.assertEqual(popups[0][0], "error")
        # The file on disk is untouched, and the box still holds the user's edit.
        self.assertNotEqual(self.app.userParamsText.get("1.0", "end-1c"), original)
        self.assertEqual(self.app.savePrefsButton.winfo_manager(), "pack")


class MarkVersionDefaultTests(GuiTestCase, unittest.TestCase):
    """_mark_version_default writes config.json - _save_config is patched to
    a no-op so tests never touch the repo's real config file."""

    def setUp(self):
        super().setUp()
        self._orig_save_config = gui_module._save_config
        gui_module._save_config = lambda cfg: None
        self.app.notebook.select(2)
        self.app.update_idletasks()
        self.app.update()

    def tearDown(self):
        gui_module._save_config = self._orig_save_config
        super().tearDown()

    def test_hidden_for_the_current_default_version(self):
        self.assertEqual(self.app.markDefaultButton.winfo_manager(), "")

    def test_shown_for_a_non_default_version(self):
        self.app._select_ap_version("AP3-SUB-004")
        self.assertEqual(self.app.markDefaultButton.winfo_manager(), "pack")

    def test_marking_default_updates_config_and_hides_the_button(self):
        self.app._select_ap_version("AP3-SUB-004")
        self.app._mark_version_default()
        self.assertEqual(self.app.app_config["ap_version"], "AP3-SUB-004")
        self.assertEqual(self.app.markDefaultButton.winfo_manager(), "")


if __name__ == "__main__":
    unittest.main()
