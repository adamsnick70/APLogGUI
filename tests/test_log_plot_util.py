"""LogPlotUtil helpers that don't need a GUI: pulling the AP version token
out of the log's own "AP Info:[...]" column header."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from LogPlotUtil import LogPlotUtil  # noqa: E402


class TestDetectApVersion:
    def test_extracts_version_from_ap_info_column(self):
        fields = [
            "Time (sec)",
            "Throttle Pos (%)",
            "AP Info:[AP3-SUB-006 v1.7.6.0-28785][2023 USDM WRX MT (H) CCF Gen3.1]"
            "[Reflash: Adams_DMann ACN91 OTS STG1 Map.ptm]",
        ]
        assert LogPlotUtil.detect_ap_version(fields) == "AP3-SUB-006"

    def test_returns_none_when_no_ap_info_column_present(self):
        fields = ["Time (sec)", "Throttle Pos (%)", "RPM (RPM)"]
        assert LogPlotUtil.detect_ap_version(fields) is None

    def test_ignores_unrelated_columns_that_merely_contain_brackets(self):
        fields = ["Time (sec)", "Some Field [not AP Info]"]
        assert LogPlotUtil.detect_ap_version(fields) is None
