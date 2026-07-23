import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt

from LogPlotUtil import LogPlotUtil, _formatLabel, pen_for_index
from InteractiveViewBox import make_interactive_plot_widget

# Spec reference lines are always red-dashed, same as the Tkinter version's
# 'r--' lines, regardless of which series they accompany.
_SPEC_PEN = pg.mkPen(color="#d62728", width=1.5, style=Qt.PenStyle.DashLine)


class ParamPlotUtil(LogPlotUtil):
    """Backend for the "Parameterized Plots" tab: one pg.PlotWidget per named
    group in self.userParams.plotFields, either for an autofind-detected
    high-throttle event or for the whole log (the user zooms/pans on the
    charts themselves instead of picking a start/end % up front)."""

    def _makePlots(self , start , end , on_figure = None):
        # Read In File
        fl = self._readLog()
        time = np.array(fl['Time (sec)'])
        time_adj = time[start:end]
        throttle_field = self.userParams.throttleField

        for name in self.userParams.plotNames:
            series = []
            for field, scale, min_max_enbl in self.userParams.plotFields.get(name, []):
                if field not in fl.columns:
                    print(f"'{field}' not found in CSV")
                    continue

                data = np.array(fl[field], dtype=np.float64) * scale
                # Sliced to [start:end] so the shown min/max matches the
                # truncated range actually plotted (e.g. an autofind event),
                # not the whole log.
                label = _formatLabel(field, scale, data=data[start:end], min_max_enbl=min_max_enbl)
                dashed = field == throttle_field
                series.append((data, label, dashed))

            if not series:
                print(f"No fields for '{name}' found in CSV. Skipping plot...")
                continue

            plot_widget = make_interactive_plot_widget()
            plot_item = plot_widget.getPlotItem()
            plot_item.addLegend()
            for index, (data, label, dashed) in enumerate(series):
                plot_item.plot(time_adj, data[start:end], pen=pen_for_index(index, dashed=dashed), name=label)

            # Spec Lines
            plotSpecs = self.userParams.plotSpecs
            if name in plotSpecs.keys():
                for curr_spec in plotSpecs[name].keys():
                    spec_values = plotSpecs[name][curr_spec]
                    plot_item.plot(
                        [time_adj[0], time_adj[-1]], [spec_values[0], spec_values[0]],
                        pen=_SPEC_PEN, name=f"{curr_spec} Spec",
                    )
                    if len(spec_values) == 2:
                        plot_item.plot([time_adj[0], time_adj[-1]], [spec_values[1], spec_values[1]], pen=_SPEC_PEN)

            plot_item.setLabel('bottom', "Time")
            plot_item.setTitle(name)
            limits = self.userParams.plotLimits.get(name)
            if limits:
                plot_item.setYRange(*limits, padding=0)
            plot_item.showGrid(x=True, y=True, alpha=0.3)
            if on_figure:
                on_figure(plot_widget)

    def _plotLog (self , auto_find , on_figure = None , on_event_header = None):
        # Read In File
        fl = self._readLog()

        # Set up timing
        if auto_find:
            event_times = self._findThrottleEvents(fl)
            if event_times is None:
                return
            evt_counter = 1
            for evt_ind in range( 1 , len( event_times ) , 2 ):
                start = event_times[evt_ind - 1]
                end = event_times[evt_ind]
                if on_event_header:
                    on_event_header(evt_counter)
                else:
                    print("     ----------------------------------------------------------------- HIGH THROTTLE EVENT " + str(evt_counter) + " -----------------------------------------------------------------")
                self._makePlots(start , end , on_figure = on_figure)
                evt_counter = evt_counter + 1
        else:
            # No manual range anymore - the user zooms/pans on the plotted
            # chart itself (see LogPlotterGUI's x-axis linking) instead of
            # picking a start/end % up front.
            self._makePlots(0 , len(fl) , on_figure = on_figure)
