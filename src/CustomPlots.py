import matplotlib.pyplot as plt
import numpy as np

from LogPlotUtil import LogPlotUtil, _formatLabel


class CustomPlotUtil(LogPlotUtil):
    """Backend for the "Custom Plot" tab: a single figure built from
    whichever fields/scales the user picked, either for an autofind-detected
    high-throttle event or for a manually chosen start/end % range of the
    whole log. Autofind still relies on UserParams.throttleField even if
    that field isn't one of the chosen fields to plot."""

    def _makeCustomPlot(self, fl, start, end, fields_scales, on_figure=None):
        time = np.array(fl['Time (sec)'])
        time_adj = time[start:end]

        series = []
        for field, scale in fields_scales:
            if field not in fl.columns:
                print(f"'{field}' not found in CSV")
                continue
            data = np.array(fl[field], dtype=np.float64) * scale
            label = _formatLabel(field, scale)
            series.append((data, label))

        if not series:
            print("No selected fields found in CSV. Skipping plot...")
            return

        fig = plt.figure(figsize=self.figsize)
        for data, label in series:
            plt.plot(time_adj, data[start:end], label=label)
        plt.xlabel("Time")
        plt.legend()
        plt.title("Custom Plot")
        plt.grid(linestyle='--')
        if on_figure:
            on_figure(fig)
        else:
            plt.show()

    def _plotCustomLog(self, fields_scales, start_prct, end_prct, auto_find, on_figure=None, on_event_header=None):
        # Read In File
        fl = self._readLog()

        if auto_find:
            event_times = self._findThrottleEvents(fl)
            if event_times is None:
                return
            evt_counter = 1
            for evt_ind in range(1, len(event_times), 2):
                start = event_times[evt_ind - 1]
                end = event_times[evt_ind]
                if on_event_header:
                    on_event_header(evt_counter)
                self._makeCustomPlot(fl, start, end, fields_scales, on_figure=on_figure)
                evt_counter += 1
        else:
            start = np.int32(np.round(start_prct * len(fl)))
            end = np.int32(np.round(end_prct * len(fl)))
            self._makeCustomPlot(fl, start, end, fields_scales, on_figure=on_figure)
