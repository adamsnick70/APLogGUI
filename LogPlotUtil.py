import pandas
import matplotlib.pyplot as plt
import numpy as np

class LogPlotUtil:
    def __init__(self , logPath , thresh , figsize = (20, 8)):
        self.logPath_ = logPath
        self.throttle_threshold = thresh
        self.sps = 13
        self.figsize = figsize

    def autoFind(self , throttle_array):
        arr_out = []
        pull_bool = 0

        for ind in range (1 , throttle_array.shape[0]):
            if pull_bool == 0:
                # Just went full throttle
                if throttle_array[ind] > self.throttle_threshold and throttle_array[ind - 1] <= self.throttle_threshold:
                    # Avoid spikes
                    if throttle_array[ind + 5] > self.throttle_threshold:
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
    
    def makePlots(self , start , end , on_figure = None):
        # Read In File
        fl = pandas.read_csv( self.logPath_ , encoding = 'unicode_escape' )
        time = np.array(fl['Time (sec)'])
        throttle = np.float32([fl['Throttle Pos (%)']]).reshape((-1))
        throttle = np.divide(throttle , 10)
        time_adj = time[start:end]

        # ----------------------------------------------------------------
        # GENERAL
        # ----------------------------------------------------------------
        rpm = np.float32([fl['RPM (RPM)']]).reshape((-1))
        rpm  = np.divide(rpm , 1000)
        coolantTemp = np.float32(fl['Coolant Temp (F)'])
        # coolantTemp = np.divide(coolantTemp , 10)
        oilTemp = np.float32(fl['Oil Temp (F)'])
        # oilTemp = np.divide(oilTemp , 10)
        gear = np.array(fl['Gear Position (gear)'])

        fig = plt.figure(figsize=self.figsize)
        plt.plot(time_adj, throttle[start:end], label = "Throttle (% / 10)" , linestyle = '--')
        plt.plot(time_adj, rpm[start:end], label = f"RPM / 1000 ({float("{0:.3f}".format(np.min(rpm[start:end])))}/{float("{0:.3f}".format(np.max(rpm[start:end])))})" )
        plt.plot(time_adj, gear[start:end], label = "Gear")
        plt.plot(time_adj[0], coolantTemp[0], label = f"Coolant Temp (°F) ({float("{0:.3f}".format(np.min(coolantTemp[start:end])))}/{float("{0:.3f}".format(np.max(coolantTemp[start:end])))})")
        plt.plot(time_adj[0], oilTemp[0], label = f"Oil Temp (°F) ({float("{0:.3f}".format(np.min(oilTemp[start:end])))}/{float("{0:.3f}".format(np.max(oilTemp[start:end])))})")
        plt.xlabel("Time")
        plt.legend()
        plt.title("General")
        plt.ylim([0 , 10.1])
        plt.grid(linestyle = '--')
        if on_figure:
            on_figure(fig)
        else:
            plt.show()

        # ----------------------------------------------------------------
        # BOOST
        # ----------------------------------------------------------------
        fig = plt.figure(figsize=self.figsize)
        plt.plot(time_adj, throttle[start:end], label = "Throttle (% / 10)" , linestyle = '--')

        boost = np.array(fl['Boost (psi)'])
        plt.plot(time_adj, boost[start:end], label = f"Boost (PSI) ({np.min(boost[start:end])}/{np.max(boost[start:end])})")

        if "Wastegate Pos Comm Final (mm)" in fl.columns:
            wastegatePosComm = np.array(fl['Wastegate Pos Comm Final (mm)'])
            # wastegatePosComm = np.divide(wastegatePosComm , 10.0)
            plt.plot(time_adj , wastegatePosComm[start:end], label = f"Wastegate Pos Comm Final (mm)")
        else:
            print("'Wastegate Pos Comm Final (mm)' not found in CSV")

        if "Wastegate Pos Actual (mm)" in fl.columns:
            wastegatePos = np.array(fl['Wastegate Pos Actual (mm)'])
            # wastegatePos = np.divide(wastegatePos , 10.0)
            plt.plot(time_adj , wastegatePos[start:end], label = f"Wastegate Position (mm)")
        else:
            print("'Wastegate Pos Actual (mm)' not found in CSV")
        
        if "TD Boost Error (psi)" in fl.columns:
            boostErr = np.array(fl['TD Boost Error (psi)'])
            boostErr_spec_low = -1.5 * np.ones((time.shape[0]))
            boostErr_spec_high = 1.5 * np.ones((time.shape[0]))
            plt.plot(time_adj, boostErr[start:end], label = "Boost Err")
            plt.plot(time_adj, boostErr_spec_low[start:end], label = "Boost Error Spec" , linestyle='dashed' , color=[1,0,0])
            plt.plot(time_adj, boostErr_spec_high[start:end], linestyle='dashed' , color=[1,0,0])
        else:
            print("'TD Boost Error (psi)' not found in CSV")
            
        plt.xlabel("Time")
        plt.legend()
        plt.title("Boost")
        plt.ylim([-2 , 20.5])
        plt.grid(linestyle = '--')
        if on_figure:
            on_figure(fig)
        else:
            plt.show()

        # ----------------------------------------------------------------
        # AIR
        # ----------------------------------------------------------------
        fig = plt.figure(figsize=self.figsize)
        plt.plot(time_adj, throttle[start:end], label = "Throttle (% / 10)" , linestyle = '--')

        airTempMan = np.float32(fl['Intake Temp Manifold (F)'])
        airTempMan = np.divide(airTempMan , 10)
        plt.plot(time_adj , airTempMan[start:end], label = f"Manifold Temp (°F/10) ({int(np.min(airTempMan[start:end])*10)}/{int(np.max(airTempMan[start:end])*10)})")

        if "MAF Corr Final (g/s)" in fl.columns:
            mafCorr = np.float32(fl['MAF Corr Final (g/s)'])
            plt.plot(time_adj , mafCorr[start:end], label = f"MAF Correction (g/s) ({int(np.min(mafCorr[start:end]))}/{int(np.max(mafCorr[start:end]))})")
        else:
            print("'MAF Corr Final (g/s)' not found in CSV")

        if "MAF Volts (V)" in fl.columns:
            mafVolts = np.array(fl['MAF Volts (V)'])
            mafVolts = np.multiply(mafVolts , 10.0)
            plt.plot(time_adj , mafVolts[start:end], label = f"MAF Voltage (V) ({np.min(mafVolts[start:end])}/{np.max(mafVolts[start:end])})")# , color=[0,0,1])
        else:
            print("'MAF Volts (V)' not found in CSV")

        if "AF Sens 1 Ratio (AFR)" in fl.columns:
            afr = np.array(fl['AF Sens 1 Ratio (AFR)'])
            plt.plot(time_adj, afr[start:end], label = "AFR" , color=[1,0,0])
        else:
            print("'AF Sens 1 Ratio (AFR)' not found in CSV")

        if "CL Fuel Target (AFR)" in fl.columns:
            fuelTargetAfr = np.array(fl['CL Fuel Target (AFR)'])
            plt.plot(time_adj, fuelTargetAfr[start:end], label = "Target AFR" , linestyle='dashed' , color=[1,0,0])
        else:
            print("'CL Fuel Target (AFR)' not found in CSV")
        
        plt.xlabel("Time")
        plt.legend()
        plt.title("Air")
        plt.ylim([0 , 15])
        plt.grid(linestyle = '--')
        if on_figure:
            on_figure(fig)
        else:
            plt.show()

        # ----------------------------------------------------------------
        # FUEL
        # ----------------------------------------------------------------
        fig = plt.figure(figsize=self.figsize)
        plt.plot(time_adj, throttle[start:end], label = "Throttle (% / 10)" , linestyle = '--')

        STFT1 = np.array(fl['AF Correction 1 (%)'])
        plt.plot(time_adj, STFT1[start:end], label = "AF Correction 1")

        LTFT = np.array(fl['AF Learning 1 (%)'])
        plt.plot(time_adj, LTFT[start:end], label = "AF Learning 1")

        # if "AF Correction 3 (%)" in fl.columns:
        #     STFT3 = np.array(fl['AF Correction 3 (%)'])
        #     plt.plot(time_adj, STFT3[start:end], label = "STFT3 (AFC 3)")
        # else:
        #     print("'AF Correction 3 (%)' not found in CSV")
        
        if "Fuel Pressure (psi)" in fl.columns:
            fuel_pressure = np.array(fl['Fuel Pressure (psi)'])
            fuel_pressure = np.divide(fuel_pressure , 1000)
            plt.plot(time_adj, fuel_pressure[start:end], label = "Fuel Pressure (psi / 1000)" , color=[1,0,0])
        else:
            print("'Fuel Pressure (psi)' not found in CSV")

        if "Fuel Pressure Target (psi)" in fl.columns:
            fuel_pressure_trgt = np.array(fl['Fuel Pressure Target (psi)'])
            fuel_pressure_trgt = np.divide(fuel_pressure_trgt , 1000)
            plt.plot(time_adj, fuel_pressure_trgt[start:end], label = "Fuel Pressure Target (psi / 1000)" , linestyle = '--' , color=[1,0,0])
        else:
            print("'Fuel Pressure Target (psi)' not found in CSV")

        plt.xlabel("Time")
        plt.legend()
        plt.title("Fuel")
        plt.ylim([-15 , 24])
        plt.grid(linestyle = '--')
        if on_figure:
            on_figure(fig)
        else:
            plt.show()

        # ----------------------------------------------------------------
        # TIMING
        # ----------------------------------------------------------------
        FbKnock = np.array(fl['Feedback Knock (°)'])
        KnockLearn = np.array(fl['Fine Knock Learn (°)'])
        timing = np.float32([fl['Ignition Timing (°)']]).reshape((-1))
        dam = np.array(fl['Dyn Adv Mult (DAM)'])

        fig = plt.figure(figsize=self.figsize)
        plt.plot(time_adj, throttle[start:end], label = "Throttle (% / 10)" , linestyle = '--')
        plt.plot(time_adj, FbKnock[start:end], label = f"Feedback Knock ({np.min(FbKnock[start:end])}/{np.max(FbKnock[start:end])})")
        plt.plot(time_adj, KnockLearn[start:end], label = f"KnockLearn ({np.min(KnockLearn[start:end])}/{np.max(KnockLearn[start:end])})")
        plt.plot(time_adj, dam[start:end], label = f"DAM ({np.min(dam[start:end])}/{np.max(dam[start:end])})")# , linestyle='dashed')
        plt.plot(time_adj, timing[start:end], label = "Ignition Timing (°)")
        plt.xlabel("Time")
        plt.legend()
        plt.title("Timing")
        plt.ylim([-5 , 10.1])
        plt.grid(axis='x' , linestyle = '--')
        if on_figure:
            on_figure(fig)
        else:
            plt.show()

        # ----------------------------------------------------------------
        # KS Noise
        # ----------------------------------------------------------------
        if "KS Noise Cyl 1 (raw)" in fl.columns:
            ksCyl1 = np.float32(fl['KS Noise Cyl 1 (raw)'])
            ksCyl2 = np.float32(fl['KS Noise Cyl 2 (raw)'])
            ksCyl3 = np.float32(fl['KS Noise Cyl 3 (raw)'])
            ksCyl4 = np.float32(fl['KS Noise Cyl 4 (raw)'])

            fig = plt.figure(figsize=self.figsize)
            plt.plot(time_adj, ksCyl1[start:end], label = "KS Noise Cylinder 1")
            plt.plot(time_adj, ksCyl2[start:end], label = "KS Noise Cylinder 2")
            plt.plot(time_adj, ksCyl3[start:end], label = "KS Noise Cylinder 3")
            plt.plot(time_adj, ksCyl4[start:end], label = "KS Noise Cylinder 4")
            plt.xlabel("Time")
            plt.legend()
            plt.title("KS Noise")
            plt.ylim([0 , 3000])
            plt.grid(axis='x' , linestyle = '--')
            if on_figure:
                on_figure(fig)
            else:
                plt.show()
        else:
            print("KS Noise Cyl 1-4 not being logged. Skipping plot...")
        # ----------------------------------------------------------------
        # AVCS
        # ----------------------------------------------------------------
        if "AVCS Exh Left (°)" in fl.columns and "AVCS Exh Right (°)" in fl.columns:
            avExLeft = np.array(fl['AVCS Exh Left (°)'])
            avExRight = np.array(fl['AVCS Exh Right (°)'])
            avInLeft = np.array(fl['AVCS In Left (°)'])
            avInRight = np.array(fl['AVCS In Right (°)'])

            fig = plt.figure(figsize=self.figsize)
            plt.plot(time_adj, avExLeft[start:end], label = "AVCS Exhaust Left (°)")
            plt.plot(time_adj, avExRight[start:end], label = "AVCS Exhaust Right (°)")
            plt.plot(time_adj, avInLeft[start:end], label = "AVCS Intake Left (°)")
            plt.plot(time_adj, avInRight[start:end], label = "AVCS Intake Right (°)")
            plt.xlabel("Time")
            plt.legend()
            plt.title("AVCS")
            plt.ylim([-10 , 31])
            plt.grid(axis='x' , linestyle = '--')
            if on_figure:
                on_figure(fig)
            else:
                plt.show()
        else:
            print("AVCS not being logged. Skipping plot...")
        


    def plotLog (self , start_prct , end_prct , auto_find , on_figure = None , on_event_header = None):
        # Read In File
        fl = pandas.read_csv( self.logPath_ , encoding = 'unicode_escape' )
        throttle = np.float32([fl['Throttle Pos (%)']]).reshape((-1))
        throttle = np.divide(throttle , 10)

        # Set up timing
        if auto_find:
            event_times = self.autoFind(throttle)
            if len(event_times) == 0:
                print("ERROR - No Full Throttle events found. Turn off autofind to view log...")
                return
            else:
                evt_counter = 1
                for evt_ind in range( 1 , len( event_times ) , 2 ):
                    start = event_times[evt_ind - 1]
                    end = event_times[evt_ind]
                    if on_event_header:
                        on_event_header(evt_counter)
                    else:
                        print("     ----------------------------------------------------------------- HIGH THROTTLE EVENT " + str(evt_counter) + " -----------------------------------------------------------------")
                    self.makePlots(start , end , on_figure = on_figure)
                    evt_counter = evt_counter + 1
        else:
            start = np.int32( np.round(start_prct * throttle.shape[0]) )
            end =  np.int32( np.round(end_prct * throttle.shape[0]) )
            self.makePlots(start , end , on_figure = on_figure)
        

        