# AP Log Plotter

This is an app for plotting Cobb Accessport-style ECU
datalog CSVs (Subaru WRX/STI logs, by default - see [Configuration](#configuration)
to adapt it to a different log format). This configuration is currently defaulted
to supporting VB WRX Accessport parameters

## Setup

```
pip install -r requirements.txt
```

On Ubuntu (20.04/22.04/24.04), Tkinter is a separate system package and
isn't pip-installable:

```
sudo apt-get install python3-tk
```

## Running

```
python src/LogPlotterGUI.py
```

On Windows, a desktop shortcut ("AP Log Plotter") launches the app the same
way via `pythonw.exe` (no console window).

## Using the app

1. **Browse...** (or type a path and press Enter) to load a log CSV.
   The left sidebar lists every column found in that file, one per line,
   purely for reference.
2. Pick a tab depending on what you want to see:

### Parameterized Plots

Renders one chart per predefined group in `UserParams.plotFields` (General,
Boost, Air, Fuel, Timing, KS Noise, AVCS by default), each with a fixed
y-axis range from `UserParams.plotLimits`.

- **Autofind high-throttle events** (on by default): scans the log for
  throttle crossing the threshold below it, and produces one set of charts
  per high-throttle event found.
- Turn autofind off to plot a manually chosen **Start %/End %** range of the
  whole log instead. Dragging either slider after a chart already exists
  updates it in place.

### Custom Plot

Builds a single combined chart from whatever fields you pick, instead of
the predefined groups above.

- **Search fields** filters the field list below it (the field that's
  always the x-axis, `Time (sec)`, is never offered as a series). Select one
  or more and **Add Selected** to move them into **Selected fields**, where
  each gets its own scale multiplier.
- Autofind/threshold/Start %/End % work the same way as the Parameterized
  tab and apply to this chart's time range. Autofind always uses
  `UserParams.throttleField` to find events, even if you haven't added that
  field to the chart yourself.
- If the loaded log doesn't have `UserParams.throttleField` as a column,
  autofind is disabled (and unchecked) in **both** tabs, since there'd be
  nothing to detect events from.

## Configuration

`UserParams.py` controls what the app knows about your log format:

- `throttleField` - the CSV column used for autofind's high-throttle
  detection. Point this at whatever your Accessport version calls it.
- `plotNames` / `plotFields` / `plotLimits` - the Parameterized Plots tab's
  predefined chart groups, their fields (each a `(field, scale, min_max_enbl)`
  tuple - `min_max_enbl` adds that line's min/max over the plotted range,
  rounded to 2 decimal places, to its legend label), and each group's y-axis
  range.

## Project layout

```
APLogger/
├── config.json       # saved window geometry/last-used folder - not hand-edited
├── README.md
├── requirements.txt
├── src/              # application code
│   ├── LogPlotterGUI.py   # the Tkinter UI: window layout, both tabs, plotting triggers
│   ├── LogPlotUtil.py     # shared backend: reading the CSV and autofind detection
│   ├── ParamPlots.py      # backend specific to the Parameterized Plots tab
│   ├── CustomPlots.py     # backend specific to the Custom Plot tab
│   └── UserParams.py      # the per-log-format configuration described above
└── tests/            # test suite (see below) - a sibling of src/, not nested in it
```

## Tests

No extra dependency needed - the suite uses the standard library's
`unittest`:

```
python -m unittest discover -s tests -p "test_*.py" -v
```
