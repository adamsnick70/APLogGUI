# AP Log Plotter

This is an app for plotting Cobb Accessport-style ECU
datalog CSVs (Subaru WRX/STI logs, by default - see [Configuration](#configuration)
to adapt it to a different log format). This configuration is currently defaulted
to supporting VB WRX Accessport parameters

## Setup

1) Clone the repository from Github into the folder you wish it to be in.

An installer is available for MacOS and Windows 11 in the `installers/` directory
of this codebase. Double click the one for your Operating System in file explorer
to run it (on Windows, double click `install_windows.bat`, not the `.ps1` file).

## Manual Setup

1) Install Python

Windows:
https://www.python.org/downloads/windows/
INSTALL AS ADMIN AND ADD TO PATH

MacOS:
Use homebrew - In terminal run "brew install python"

2) Install Needed Python Packages

In terminal / CLI:
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
1) Right click on an empty Desktop space - Select New -> Shortcut
2) In the file browser, select to the codebase's src/LogPlotterGUI.py
3) The shortcut is now on your Desktop

## Using the app

1. **Browse...** (or type a path and press Enter) to load a log CSV.
   The left sidebar lists every column found in that file, one per line,
   purely for reference.
2. **AP Version** (next to the log file path) picks which
   `params/UserParams_<version>.txt` file the app reads its field/plot
   configuration from - see [Configuration](#configuration).
3. Pick a tab depending on what you want to see:

### Parameterized Plots

Renders one chart per predefined group in the selected AP version's
`plotFields` (General, Boost, Air, Fuel, Timing, KS Noise, AVCS by default),
each with a fixed y-axis range from `plotLimits`.

- **Autofind high-throttle events** (on by default): scans the log for
  throttle crossing the threshold below it, and produces one set of charts
  per high-throttle event found.
- Turn autofind off to plot a manually chosen **Start %/End %** range of the
  whole log instead. Dragging either slider after a chart already exists
  updates it in place.

### Interacting with charts

- **Click a plotted point** to show a data tip with that channel's name,
  the time (x value), and the value (y) at that point. Click elsewhere to
  dismiss it.
- **Ctrl + scroll wheel** zooms the x-axis (time), **Shift + scroll wheel**
  zooms the y-axis, both centered on whatever point the cursor is over.
  A plain scroll doesn't touch the chart - it scrolls the page normally,
  so you can scroll past a plot with the cursor resting over it.

### Custom Plot

Builds a single combined chart from whatever fields you pick, instead of
the predefined groups above.

- **Search fields** filters the field list below it (the field that's
  always the x-axis, `Time (sec)`, is never offered as a series). Select one
  or more and **Add Selected** to move them into **Selected fields**, where
  each gets its own scale multiplier.
- Autofind/threshold/Start %/End % work the same way as the Parameterized
  tab and apply to this chart's time range. Autofind always uses the
  selected AP version's `throttleField` to find events, even if you haven't
  added that field to the chart yourself.
- If the loaded log doesn't have `throttleField` as a column, autofind is
  disabled (and unchecked) in **both** tabs, since there'd be nothing to
  detect events from.

### User Parameters

Shows the raw contents of the currently selected AP version's params file,
directly editable. Edit it and a **Save Preferences** button appears -
click it to overwrite that version's file (the edit is validated first; an
invalid edit shows an error instead of saving). If the selected version
isn't the one the app starts up with by default, a **Mark Version as
Default** button also appears, which updates `config.json`.

## Configuration

Each supported Accessport version has its own
`params/UserParams_<version>.txt` file (e.g. `UserParams_AP3-SUB-006.txt`)
controlling what the app knows about that log format. Pick the active one
from the **AP Version** dropdown, or edit it directly from the **User
Parameters** tab. The dropdown's choices are read from whatever
`UserParams_*.txt` files exist in `params/`, so adding support for another
version is just dropping in a new file with that naming pattern.

Each file is a set of top-level `name = <value>` assignments, using plain
Python literal syntax (strings, lists, dicts, tuples, numbers, booleans -
parsed with `ast.literal_eval`, never executed):

- `throttleField` - the CSV column used for autofind's high-throttle
  detection. Point this at whatever that Accessport version calls it.
- `plotNames` / `plotFields` / `plotLimits` - the Parameterized Plots tab's
  predefined chart groups, their fields (each a `(field, scale, min_max_enbl)`
  tuple - `min_max_enbl` adds that line's min/max over the plotted range,
  rounded to 2 decimal places, to its legend label), and each group's y-axis
  range.
- `plotSpecs` - optional flat reference lines per group (e.g. a spec min/max
  band), keyed by group name then field name.

## Project layout

```
APLogger/
├── config.json       # saved window geometry/last-used folder/default AP version - not hand-edited
├── README.md
├── requirements.txt
├── params/           # per-AccessPort-version plot configuration
│   ├── UserParams_AP3-SUB-006.txt
│   └── UserParams_AP3-SUB-004.txt
├── src/              # application code
│   ├── LogPlotterGUI.py   # the Tkinter UI: window layout, tabs, plotting triggers
│   ├── LogPlotUtil.py     # shared backend: reading the CSV and autofind detection
│   ├── ParamPlots.py      # backend specific to the Parameterized Plots tab
│   ├── CustomPlots.py     # backend specific to the Custom Plot tab
│   └── UserParams.py      # reads/writes params/UserParams_<version>.txt
└── tests/            # test suite (see below)
```

## Tests

No extra dependency needed - the suite uses the standard library's
`unittest`:

```
python -m unittest discover -s tests -p "test_*.py" -v
```
