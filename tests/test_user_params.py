"""UserParams: parsing/writing params/UserParams_<version>.txt (a flat set of
top-level `name = <python literal>` assignments, read with ast.literal_eval)
and listing which versions are available."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from UserParams import UserParams, DEFAULT_VERSION  # noqa: E402

SAMPLE_PARAMS_TEXT = '''\
throttleField = "Throttle Pos (%)"

plotNames = ["General"]

plotFields = {
    "General": [("Throttle Pos (%)", 0.1, False)],
}

plotLimits = {
    "General": (0, 23),
}

plotSpecs = {}
'''


class RealParamsFilesTests(unittest.TestCase):
    """The actual params/ files shipped with the repo - read-only checks,
    never written to."""

    def test_default_version_parses_with_the_expected_shape(self):
        params = UserParams()
        params.read_params(DEFAULT_VERSION)
        self.assertEqual(params.throttleField, "Throttle Pos (%)")
        self.assertIn("Boost", params.plotNames)
        self.assertIn("Boost", params.plotFields)
        self.assertEqual(params.plotLimits["Boost"], (-2, 20.5))
        self.assertEqual(params.plotSpecs["Boost"]["TD Boost Error (psi)"], [-1.5, 1.5])

    def test_ap3_sub_004_and_ap3_sub_006_share_the_same_throttle_field_and_core_groups(self):
        # The two AP versions are allowed to diverge in their exact group
        # set (e.g. AP3-SUB-006 has an "AVCS / EGR" group that AP3-SUB-004
        # doesn't) - this only pins down what both are expected to share.
        p006 = UserParams()
        p006.read_params("AP3-SUB-006")
        p004 = UserParams()
        p004.read_params("AP3-SUB-004")
        self.assertEqual(p006.throttleField, p004.throttleField)
        core_groups = {"General", "Boost", "Air", "Fuel", "Timing", "KS Noise"}
        self.assertTrue(core_groups.issubset(p006.plotNames))
        self.assertTrue(core_groups.issubset(p004.plotNames))

    def test_available_versions_lists_both_shipped_versions(self):
        versions = UserParams().available_versions()
        self.assertIn("AP3-SUB-006", versions)
        self.assertIn("AP3-SUB-004", versions)


class ParseAndRoundTripTests(unittest.TestCase):
    """Uses a throwaway temp directory as params_dir so nothing here ever
    touches the repo's real params/ files."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        Path(self.tmp.name, "UserParams_TEST-VER.txt").write_text(SAMPLE_PARAMS_TEXT, encoding="utf-8")
        self.params = UserParams(params_dir=self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_read_params_populates_every_field(self):
        self.params.read_params("TEST-VER")
        self.assertEqual(self.params.throttleField, "Throttle Pos (%)")
        self.assertEqual(self.params.plotNames, ["General"])
        self.assertEqual(self.params.plotFields, {"General": [("Throttle Pos (%)", 0.1, False)]})
        self.assertEqual(self.params.plotLimits, {"General": (0, 23)})
        self.assertEqual(self.params.plotSpecs, {})
        self.assertEqual(self.params.version, "TEST-VER")

    def test_constructor_defaults_fields_to_empty(self):
        fresh = UserParams(params_dir=self.tmp.name)
        self.assertEqual(fresh.throttleField, "")
        self.assertEqual(fresh.plotNames, [])
        self.assertEqual(fresh.plotFields, {})
        self.assertEqual(fresh.plotLimits, {})
        self.assertEqual(fresh.plotSpecs, {})

    def test_write_raw_persists_to_disk_and_reloads_the_active_version(self):
        self.params.read_params("TEST-VER")
        new_text = SAMPLE_PARAMS_TEXT.replace('"General"', '"Renamed"')
        self.params.write_raw(new_text)
        self.assertEqual(self.params.plotNames, ["Renamed"])

        reloaded = UserParams(params_dir=self.tmp.name)
        reloaded.read_params("TEST-VER")
        self.assertEqual(reloaded.plotNames, ["Renamed"])

    def test_write_raw_rejects_invalid_syntax_without_touching_the_file(self):
        self.params.read_params("TEST-VER")
        original = self.params.read_raw()
        with self.assertRaises(SyntaxError):
            self.params.write_raw("this is not ( valid python")
        self.assertEqual(self.params.read_raw(), original)

    def test_available_versions_reflects_the_directory_live(self):
        self.assertEqual(self.params.available_versions(), ["TEST-VER"])
        Path(self.tmp.name, "UserParams_OTHER.txt").write_text(SAMPLE_PARAMS_TEXT, encoding="utf-8")
        self.assertEqual(self.params.available_versions(), ["OTHER", "TEST-VER"])


if __name__ == "__main__":
    unittest.main()
