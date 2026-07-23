# AP Log Plotter

This is an app for plotting Cobb Accessport-style ECU
datalog CSVs (Subaru WRX/STI logs, by default - see [Configuration](#configuration)
to adapt it to a different log format). This configuration is currently defaulted
to supporting VB WRX Accessport parameters

## Setup

Download the installer for your OS from the
[GitHub Releases page](https://github.com/adamsnick70/APLogGUI/releases) and run it:

- **Windows**: `AP-Log-Plotter-Setup.exe` - installs for your user only, no
  admin prompt. Find "AP Log Plotter" in the Start Menu afterward.
- **macOS**: `AP-Log-Plotter.pkg` - installs to `/Applications`, will prompt
  for your password. Find "AP Log Plotter" in Launchpad/Spotlight afterward.
- **Linux (Debian/Ubuntu)**: `ap-log-plotter_<version>_amd64.deb` - install
  with `sudo apt install ./ap-log-plotter_<version>_amd64.deb` (or open it in
  your file manager's package installer). Find "AP Log Plotter" in your
  application launcher afterward.

The app checks for a newer release on startup and offers to download and
install it automatically. None of these installers are code-signed yet, so
your OS will likely warn you the first time you run one (Windows
SmartScreen / macOS Gatekeeper) - that's expected until code signing is set
up, not a sign anything's wrong.

## Manual Setup

This setup is for development, or for running from source instead of an
installer.

1) Install Python 3.11+

Windows:
https://www.python.org/downloads/windows/
INSTALL AS ADMIN AND ADD TO PATH

macOS:
Use homebrew - In terminal run "brew install python"

2) Install needed Python packages

In terminal / CLI at codebase folder:
```
pip install -r requirements.txt
```

This installs PySide6/pyqtgraph (the GUI/plotting stack) along with
pandas/numpy. On Ubuntu (20.04/22.04/24.04), Qt also needs a few runtime
libraries that pip alone won't pull in:

```
sudo apt-get install libxcb-cursor0 libxkbcommon-x11-0 libgl1 fonts-dejavu-core
```

3) Compile the UI

The first run of `src/LogPlotterGUI.py` automatically compiles
`ui/main_window.ui` into `src/ui_main_window.py` (via `pyside6-uic`) if it's
missing or stale, so this step is usually automatic. To do it by hand (or to
regenerate after editing the `.ui` file in Qt Designer):

```
python tools/build_ui.py
```

## Running

If installed via the Windows/macOS/Linux installer, a shortcut/launcher
entry ("AP Log Plotter") launches the app with no console window.

If you set up manually:
1) Right click on an empty Desktop space - Select New -> Shortcut
2) In the file browser, select to the codebase's src/LogPlotterGUI.py
3) The shortcut is now on your Desktop

or call the app directly in CLI:
```
python src/LogPlotterGUI.py
```

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

- **Click and drag** on a chart draws a box to zoom into (release to apply).
- **Middle-click and drag** pans the chart.
- **Click and drag an axis' ruler** (the numbers along an edge, not the plot
  area itself) zooms just that one axis.
- **Ctrl + scroll wheel** zooms the x-axis (time), **Shift + scroll wheel**
  zooms the y-axis, both centered on whatever point the cursor is over.
  A plain scroll doesn't touch the chart - it scrolls the page normally,
  so you can scroll past a plot with the cursor resting over it.
- **Click a plotted point** to pin a data tip there (channel name, time, and
  value) - multiple tips can be pinned at once, on the same or different
  charts. Drag a pinned tip along its curve to move it, or right-click it to
  remove it. Right-clicking empty chart area instead opens pyqtgraph's
  built-in context menu (includes a "View All" option to reset zoom/pan).

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
├── ui/                    # Qt Designer source - the single source of truth for static chrome
│   ├── main_window.ui
│   ├── style.qss          # dark "modern webapp" stylesheet
│   └── checkmark.svg
├── src/                   # application code
│   ├── LogPlotterGUI.py   # the PySide6 UI: window layout, tabs, plotting triggers
│   ├── LogPlotUtil.py     # shared backend: reading the CSV and autofind detection
│   ├── ParamPlots.py      # backend specific to the Parameterized Plots tab
│   ├── CustomPlots.py     # backend specific to the Custom Plot tab
│   ├── InteractiveViewBox.py  # MATLAB-like chart zoom/pan/datatip interaction
│   ├── PdfExport.py       # renders plotted charts to a PDF
│   ├── UserParams.py      # reads/writes params/UserParams_<version>.txt
│   ├── AppPaths.py        # resource/config-file locations (source run vs. frozen install)
│   ├── AutoUpdate.py      # GitHub Releases update check/download/relaunch
│   ├── version.py         # build version, stamped by CI (see tools/stamp_version.py)
│   └── ui_main_window.py  # generated from ui/main_window.ui - not committed
├── tools/
│   ├── build_ui.py        # compiles ui/*.ui -> src/ui_*.py
│   ├── generate_icon.py   # (re)generates assets/icons/ from scratch
│   └── stamp_version.py   # writes src/version.py's APP_VERSION before a packaging build
├── assets/icons/          # app icon source (icon.ico, icon.png, AppIcon.iconset/)
├── packaging/             # PyInstaller specs + installer build scripts, one dir per OS
│   ├── windows/           # PyInstaller spec + Inno Setup installer.iss
│   ├── macos/              # PyInstaller spec + pkgbuild .pkg (+ legacy-install migration scripts)
│   └── linux/              # PyInstaller spec + fpm .deb + .desktop file
├── .github/workflows/release.yml  # builds/checksums/publishes all 3 installers on push to master
└── tests/            # test suite (see below)
```

## Tests

Uses `pytest` + `pytest-qt` (installed via `requirements.txt`):

```
pytest tests/
```

Runs fine with a normal display (windows may briefly flash on screen); for
a headless/CI environment, set `QT_QPA_PLATFORM=offscreen` first so Qt
doesn't need a real display at all.
