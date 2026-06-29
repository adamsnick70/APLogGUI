import matplotlib.pyplot as plt
import numpy as np

import UserParams
from LogPlotUtil import LogPlotUtil, THROTTLE_FIELD, _formatLabel


class ParamPlotUtil(LogPlotUtil):
    """Backend for the "Parameterized Plots" tab: one figure per named group
    in UserParams.plotFields, either for an autofind-detected high-throttle
    event or for a manually chosen start/end % range of the whole log."""

    def _makePlots(self , start , end , on_figure = None):
        # Read In File
        fl = self._readLog()
        time = np.array(fl['Time (sec)'])
        time_adj = time[start:end]

        for name in UserParams.plotNames:
            series = []
            for field, scale, min_max_enbl in UserParams.plotFields.get(name, []):
                if field not in fl.columns:
                    print(f"'{field}' not found in CSV")
                    continue

                data = np.array(fl[field], dtype=np.float64) * scale
                # Sliced to [start:end] so the shown min/max matches the
                # truncated range actually plotted (e.g. an autofind event),
                # not the whole log.
                label = _formatLabel(field, scale, data=data[start:end], min_max_enbl=min_max_enbl)
                linestyle = '--' if field == THROTTLE_FIELD else '-'
                series.append((data, label, linestyle))

            if not series:
                print(f"No fields for '{name}' found in CSV. Skipping plot...")
                continue

            fig = plt.figure(figsize=self.figsize)
            for data, label, linestyle in series:
                plt.plot(time_adj, data[start:end], label = label , linestyle = linestyle)

            # Spec Lines
            if name in UserParams.plotSpecs.keys():
                for curr_spec in UserParams.plotSpecs[name].keys():
                    plt.plot([ time_adj[0] , time_adj[-1] ], [ UserParams.plotSpecs[name][curr_spec][0] , UserParams.plotSpecs[name][curr_spec][0] ] , 'r--' , label = f"{curr_spec} Spec")
                    if len( UserParams.plotSpecs[name][curr_spec] ) == 2:
                        plt.plot([ time_adj[0] , time_adj[-1] ], [ UserParams.plotSpecs[name][curr_spec][1] , UserParams.plotSpecs[name][curr_spec][1] ] , 'r--')
                       
            plt.xlabel("Time")
            plt.legend()
            plt.title(name)
            limits = UserParams.plotLimits.get(name)
            if limits:
                plt.ylim(limits)
            plt.grid(linestyle = '--')
            if on_figure:
                on_figure(fig)
            else:
                plt.show()

    def _plotLog (self , start_prct , end_prct , auto_find , on_figure = None , on_event_header = None):
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
            start = np.int32( np.round(start_prct * len(fl)) )
            end =  np.int32( np.round(end_prct * len(fl)) )
            self._makePlots(start , end , on_figure = on_figure)
