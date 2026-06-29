# Field used to detect high-throttle events for autofind. Different
# log formats can name this column differently; point this at
# whichever column holds throttle position for your log format.
throttleField = "Throttle Pos (%)"

plotNames = ["General", "Boost", "Air", "Fuel", "Timing", "KS Noise", "AVCS"]

# Each tuple is (field, scale factor, min_max_enbl). When min_max_enbl is
# True, that line's legend label also shows its min/max over the plotted
# range.
plotFields = {}
plotFields["General"] = [("Throttle Pos (%)", 0.1, False),
                          ("RPM (RPM)", 0.001, True),
                          ("Gear Position (gear)", 1, False),
                          ("Coolant Temp (F)", 0.1, False),
                          ("Oil Temp (F)", 0.1, False)]

plotFields["Boost"] = [("Throttle Pos (%)", 0.1, False),
                        ("Boost (psi)", 1, True),
                        ("Wastegate Pos Comm Final (mm)", 1, False),
                        ("Wastegate Pos Actual (mm)", 1, False),
                        ("TD Boost Error (psi)", 1, False)]

plotFields["Air"] = [("Throttle Pos (%)", 0.1, False),
                      ("Intake Temp Manifold (F)", 0.1, True),
                      ("AF Sens 1 Ratio (AFR)", 1, False),
                      ("CL Fuel Target (AFR)", 1, False)]

plotFields["Fuel"] = [("Throttle Pos (%)", 0.1, False),
                       ("AF Correction 1 (%)", 1, False),
                       ("AF Learning 1 (%)", 1, False),
                       ("Fuel Pressure (psi)", 0.01, False),
                       ("Fuel Pressure Target (psi)", 0.01, False)]

plotFields["Timing"] = [("Throttle Pos (%)", 0.1, False),
                         ("Feedback Knock (°)", 1, True),
                         ("Fine Knock Learn (°)", 1, True),
                         ("Dyn Adv Mult (DAM)", 1, True),
                         ("Ignition Timing (°)", 1, False)]

plotFields["KS Noise"] = [("KS Noise Cyl 1 (raw)", 1, False),
                           ("KS Noise Cyl 2 (raw)", 1, False),
                           ("KS Noise Cyl 3 (raw)", 1, False),
                           ("KS Noise Cyl 4 (raw)", 1, False)]

plotFields["AVCS"] = [("AVCS Exh Left (°)", 1, False),
                       ("AVCS Exh Right (°)", 1, False),
                       ("AVCS In Left (°)", 1, False),
                       ("AVCS In Right (°)", 1, False)]

plotLimits = {}
plotLimits["General"]  = (0, 23)
plotLimits["Boost"]    = (-2, 20.5)
plotLimits["Air"]      = (0, 15)
plotLimits["Fuel"]     = (-15, 33)
plotLimits["Timing"]   = (-5, 10.1)
plotLimits["KS Noise"] = (0, 3000)
plotLimits["AVCS"]     = (-10, 31)

plotSpecs = {}
plotSpecs["Boost"] = {}
plotSpecs["Boost"]["TD Boost Error (psi)"] = [-1.5 , 1.5]