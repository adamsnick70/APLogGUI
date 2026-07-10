import re

import pandas
import numpy as np

from UserParams import UserParams, DEFAULT_VERSION

_FIELD_RE = re.compile(r'^(.*)\(([^()]*)\)\s*$')


def _default_user_params():
    params = UserParams()
    params.read_params(DEFAULT_VERSION)
    return params


def _formatLabel(field, scale, data=None, min_max_enbl=False):
    match = _FIELD_RE.match(field.strip())
    name, unit = (match.group(1).strip(), match.group(2).strip()) if match else (field.strip(), "")

    if scale == 1:
        unit_part = unit
    elif scale < 1:
        unit_part = f"{unit} / {1 / scale:g}".strip()
    else:
        unit_part = f"{unit} * {scale:g}".strip()

    label = f"{name} ({unit_part})" if unit_part else name

    if min_max_enbl and data is not None and len(data) > 0:
        # data must already be sliced to whatever range is actually being
        # plotted (e.g. an autofind-truncated event), not the full series,
        # so the shown min/max matches what's on the chart.
        label += f" ({np.min(data):.2f}/{np.max(data):.2f})"

    return label


class LogPlotUtil:
    """Shared backend: reading the CSV log and finding high-throttle events.
    Tab-specific plot rendering lives in ParamPlots.ParamPlotUtil and
    CustomPlots.CustomPlotUtil, both of which subclass this."""

    def __init__(self , logPath , thresh , figsize = (20, 8), userParams = None):
        self.logPath_ = logPath
        self.throttle_threshold = thresh
        self.sps = 13
        self.figsize = figsize
        # Falls back to a fresh, default-version UserParams when the caller
        # doesn't supply one (e.g. direct/test use of ParamPlotUtil rather
        # than going through LogPlotterGUI's version-aware instance).
        self.userParams = userParams if userParams is not None else _default_user_params()

    @staticmethod
    def list_fields(logPath):
        return list(pandas.read_csv(logPath, encoding='unicode_escape', nrows=0).columns)

    def _readLog(self):
        fl = pandas.read_csv( self.logPath_ , encoding = 'unicode_escape' )
        self._updateSps(fl)
        return fl

    def _updateSps(self, fl):
        if 'Time (sec)' not in fl.columns:
            return
        time = np.array(fl['Time (sec)'], dtype=np.float64)
        if time.shape[0] < 2:
            return
        dt = np.diff(time)
        dt = dt[dt > 0]
        if dt.size == 0:
            return
        self.sps = int(np.round(1.0 / np.median(dt)))

    def _autoFind(self , throttle_array):
        arr_out = []
        pull_bool = 0

        for ind in range (1 , throttle_array.shape[0]):
            if pull_bool == 0:
                # Just went full throttle
                if throttle_array[ind] > self.throttle_threshold and throttle_array[ind - 1] <= self.throttle_threshold:
                    # Avoid spikes - clamped so a rise within the last 12
                    # samples of the log checks the last available sample
                    # instead of indexing past the end of the array.
                    spike_check_ind = min(ind + 12, throttle_array.shape[0] - 1)
                    if throttle_array[spike_check_ind] > self.throttle_threshold:
                        # Add one second prior to arr_out
                        if (ind - self.sps) > 0:
                            start_ind = ind - self.sps
                        else:
                            start_ind = 0

                        arr_out.append(start_ind)
                        # print("Found start at ind: " + str(start_ind))
                        pull_bool = 1
            else:
                # Just throttled down
                if throttle_array[ind] < self.throttle_threshold and throttle_array[ind - 1] >= self.throttle_threshold:
                    # Make sure we dont go full throttle again within 5 seconds
                    if (ind + 5 * self.sps) <= throttle_array.shape[0]:
                        test_ind = ind + 5 * self.sps
                    else:
                        test_ind = throttle_array.shape[0]
                    if np.max( throttle_array[ind : test_ind] ) < self.throttle_threshold:
                        # Try to add one second after to arr_out
                        if (ind + self.sps) < throttle_array.shape[0]:
                            end_ind = ind + self.sps
                        else:
                            end_ind = throttle_array.shape[0] - 1

                        arr_out.append(end_ind)
                        # print("Found end at ind: " + str(end_ind))
                        pull_bool = 0
                        ind = ind + test_ind - 1

        return arr_out

    def _findThrottleEvents(self, fl):
        throttle_field = self.userParams.throttleField
        if throttle_field not in fl.columns:
            print(f"ERROR - '{throttle_field}' not found in CSV. Turn off autofind to view log...")
            return None
        # throttle_threshold is a 0-100 percentage (see UserParams/GUI); the
        # throttle column is already in percentage units, so it's compared
        # directly with no rescaling.
        throttle = np.float32([fl[throttle_field]]).reshape((-1))
        event_times = self._autoFind(throttle)
        if len(event_times) == 0:
            print("ERROR - No Full Throttle events found. Turn off autofind to view log...")
            return None
        return event_times
