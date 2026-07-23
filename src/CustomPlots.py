import numpy as np
import pyqtgraph as pg

from LogPlotUtil import LogPlotUtil, _formatLabel, pen_for_index
from InteractiveViewBox import make_interactive_plot_widget


class CustomPlotUtil(LogPlotUtil):
    """Backend for the "Custom Plot" tab: a single pg.PlotWidget built from
    whichever fields/scales the user picked, either for an autofind-detected
    high-throttle event or for the whole log (the user zooms/pans on the
    chart itself instead of picking a start/end % up front). Autofind still
    relies on UserParams.throttleField even if that field isn't one of the
    chosen fields to plot."""

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

        plot_widget = make_interactive_plot_widget()
        plot_item = plot_widget.getPlotItem()
        plot_item.addLegend()
        for index, (data, label) in enumerate(series):
            plot_item.plot(time_adj, data[start:end], pen=pen_for_index(index), name=label)
        plot_item.setLabel('bottom', "Time")
        plot_item.setTitle("Custom Plot")
        plot_item.showGrid(x=True, y=True, alpha=0.3)
        if on_figure:
            on_figure(plot_widget)

    def _plotCustomLog(self, fields_scales, auto_find, on_figure=None, on_event_header=None):
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
            # No manual range anymore - there's only one chart here, so the
            # user just zooms/pans on it directly instead of picking a
            # start/end % up front.
            self._makeCustomPlot(fl, 0, len(fl), fields_scales, on_figure=on_figure)
