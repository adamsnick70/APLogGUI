"""LogPlotUtil helpers that don't need a GUI: pulling the AP version token
out of the log's own "AP Info:[...]" column header, and _findThrottleEvents'
quiet mode."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from LogPlotUtil import LogPlotUtil  # noqa: E402
from UserParams import UserParams, DEFAULT_VERSION  # noqa: E402


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


def _no_events_util():
    # Throttle never crosses the (very high) threshold, so _autoFind
    # reports zero events regardless of quiet.
    params = UserParams()
    params.read_params(DEFAULT_VERSION)
    util = LogPlotUtil("unused.csv", thresh=90.0, userParams=params)
    fl = pd.DataFrame({params.throttleField: np.full(50, 10.0)})
    return util, fl


class TestFindThrottleEventsQuiet:
    """LogPlotterGUI's background autofind-availability scan runs on every
    log load/threshold edit rather than a deliberate Plot click, so it
    passes quiet=True to avoid spamming the console every time (see
    LogPlotterGUI._log_has_throttle_events) - a real Plot-time "no events
    found" is still worth printing, so the default stays noisy."""

    def test_prints_by_default_when_no_events_found(self, capsys):
        util, fl = _no_events_util()
        assert util._findThrottleEvents(fl) is None
        assert "No Full Throttle events found" in capsys.readouterr().out

    def test_silent_when_quiet_and_no_events_found(self, capsys):
        util, fl = _no_events_util()
        assert util._findThrottleEvents(fl, quiet=True) is None
        assert capsys.readouterr().out == ""

    def test_silent_when_quiet_and_throttle_field_missing(self, capsys):
        params = UserParams()
        params.read_params(DEFAULT_VERSION)
        util = LogPlotUtil("unused.csv", thresh=90.0, userParams=params)
        fl = pd.DataFrame({"Some Other Field (V)": np.zeros(10)})
        assert util._findThrottleEvents(fl, quiet=True) is None
        assert capsys.readouterr().out == ""
