import json
import re
import sys
import tkinter as tk
import tkinter.font as tkfont
import types
from pathlib import Path
from tkinter import ttk, filedialog, messagebox

import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

import UserParams
from LogPlotUtil import LogPlotUtil
from ParamPlots import ParamPlotUtil
from CustomPlots import CustomPlotUtil

# config.json lives at the repo root (one level up from src/), not next to
# this script, so it stays put regardless of where the code is organized.
CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.json"

# VS Code "Dark+" inspired palette.
COLOR_BG = "#1e1e1e"
COLOR_BG_PANEL = "#252526"
COLOR_BG_INPUT = "#3c3c3c"
COLOR_BG_HOVER = "#2a2d2e"
COLOR_FG = "#cccccc"
COLOR_FG_MUTED = "#9d9d9d"
COLOR_BORDER = "#3c3c3c"
COLOR_ACCENT = "#0e639c"
COLOR_ACCENT_HOVER = "#1177bb"
COLOR_ACCENT_ACTIVE = "#005a9e"

# Plots were originally designed at a fixed figsize=(20, 8) (inches @ 100 dpi).
# That's now the reference size plots are scaled from to fill the plot area's
# current width; height is scaled at HEIGHT_FALLOFF of the width's rate of
# change so narrow windows don't squash plots into an unreadable sliver, and
# wide/high-res monitors don't stretch them absurdly tall.
BASE_FIGSIZE = (20, 8)
FIGURE_DPI = 100
HEIGHT_FALLOFF = 0.75

# The tabgroup (Parameterized Plots / Custom Plot) occupies the right 80% of
# the window; the field list sidebar occupies the left 20%. Expressed as a
# 1:4 grid weight ratio so it holds exactly regardless of window size.
SIDEBAR_WEIGHT = 1
TABS_WEIGHT = 4

# Reserve room below a Custom Plot chart for its NavigationToolbar2Tk plus
# the embedding holder's own padding, so the height cap in _plotCustom()
# accounts for everything that shares the plot area, not just the chart.
TOOLBAR_RESERVE_PX = 56


def _figsize_for_width(avail_width_px, dpi=FIGURE_DPI, avail_height_px=None):
    width_in = max(avail_width_px, 1) / dpi
    width_ratio = width_in / BASE_FIGSIZE[0]
    height_ratio = 1 - HEIGHT_FALLOFF * (1 - width_ratio)
    height_in = BASE_FIGSIZE[1] * height_ratio
    if avail_height_px is not None:
        # The Custom Plot tab shows one chart at a time and the whole point
        # is that it shouldn't need its own scrollbar to see all of it, so
        # cap the height to whatever room is actually available instead of
        # only ever deriving it from width.
        height_in = min(height_in, max(avail_height_px, 1) / dpi)
    return (width_in, height_in)


def _apply_matplotlib_dark_style():
    plt.rcParams.update({
        "figure.facecolor": COLOR_BG,
        "axes.facecolor": COLOR_BG,
        "axes.edgecolor": COLOR_BORDER,
        "axes.labelcolor": COLOR_FG,
        "text.color": COLOR_FG,
        "xtick.color": COLOR_FG_MUTED,
        "ytick.color": COLOR_FG_MUTED,
        "grid.color": COLOR_BORDER,
        "legend.facecolor": COLOR_BG_PANEL,
        "legend.edgecolor": COLOR_BORDER,
        "legend.labelcolor": COLOR_FG,
        "savefig.facecolor": COLOR_BG,
    })


def _apply_windows_dark_titlebar(root):
    """Best-effort native dark titlebar on Windows 10/11. No-op elsewhere."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        root.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
        value = ctypes.c_int(1)
        for attribute in (20, 19):  # DWMWA_USE_IMMERSIVE_DARK_MODE varies by build
            if ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, attribute, ctypes.byref(value), ctypes.sizeof(value)
            ) == 0:
                break
    except Exception:
        pass


def _recolor_classic_widget(widget):
    """NavigationToolbar2Tk is built from classic (non-ttk) widgets, which
    don't pick up ttk.Style theming and default to a light system look."""
    for option, value in (
        ("background", COLOR_BG_PANEL),
        ("activebackground", COLOR_BG_HOVER),
        ("highlightbackground", COLOR_BG_PANEL),
        ("highlightcolor", COLOR_BG_PANEL),
        ("foreground", COLOR_FG),
        ("activeforeground", COLOR_FG),
    ):
        try:
            widget.configure(**{option: value})
        except tk.TclError:
            pass
    for child in widget.winfo_children():
        _recolor_classic_widget(child)


def _load_config():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _save_config(cfg):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f)
    except OSError:
        pass


class ScrollableFrame(ttk.Frame):
    """A vertically scrollable container, mirroring how a Jupyter cell's
    output area scrolls through a stack of inline plot images."""

    def __init__(self, parent, bg=COLOR_BG, height=None):
        super().__init__(parent)

        canvas_kwargs = {"highlightthickness": 0, "background": bg}
        if height is not None:
            # A fixed height keeps this region small and scrollable-on-its-
            # own (e.g. the Custom Plot tab's "Selected fields" list) rather
            # than growing to fit its content and pushing everything below
            # it down the page.
            canvas_kwargs["height"] = height
        self.canvas = tk.Canvas(self, **canvas_kwargs)
        self.vscroll = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)

        self.content = ttk.Frame(self.canvas)
        self.content_id = self.canvas.create_window((0, 0), window=self.content, anchor="nw")

        self.canvas.configure(yscrollcommand=self.vscroll.set)

        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.vscroll.grid(row=0, column=1, sticky="ns")
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Pin the content frame's width to the canvas viewport so its children
        # (plots sized to fill the window, see _figsize_for_width) never have
        # to overflow horizontally - there is deliberately no horizontal
        # scrollbar here.
        self.content.bind("<Configure>", self._on_content_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.bind("<Enter>", lambda e: self.canvas.bind_all("<MouseWheel>", self._on_mousewheel))
        self.canvas.bind("<Leave>", lambda e: self.canvas.unbind_all("<MouseWheel>"))

    def _on_content_configure(self, event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self.canvas.itemconfig(self.content_id, width=event.width)

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-event.delta / 120), "units")

    def clear(self):
        for child in self.content.winfo_children():
            child.destroy()
        self.canvas.yview_moveto(0)


class LogPlotterGUI(tk.Tk):
    @staticmethod
    def _make_range_vars(start_pct, end_pct):
        """A start/end % slider's paired StringVar (entry, 0-100) + DoubleVar
        (scale, 0-100) state. The Parameterized and Custom Plot tabs each get
        their own independent instance of this."""
        return types.SimpleNamespace(
            startPrctVar=tk.StringVar(value=f"{start_pct:.1f}"),
            endPrctVar=tk.StringVar(value=f"{end_pct:.1f}"),
            startScaleVar=tk.DoubleVar(value=start_pct),
            endScaleVar=tk.DoubleVar(value=end_pct),
        )

    def __init__(self):
        super().__init__()
        self.title("AP Log Plotter")
        self.app_config = _load_config()
        self._size_to_plots()
        _apply_matplotlib_dark_style()
        self._apply_ttk_theme()
        _apply_windows_dark_titlebar(self)

        self.logPath = tk.StringVar()
        self.autoFindVar = tk.BooleanVar(value=True)
        self.threshVar = tk.StringVar(value="75")
        self.paramRange = self._make_range_vars(10.0, 90.0)

        self.customAutoFindVar = tk.BooleanVar(value=True)
        self.customThreshVar = tk.StringVar(value="75")
        self.customRange = self._make_range_vars(10.0, 90.0)
        self.customSearchVar = tk.StringVar()

        # Each tab keeps its own figure list/output area so switching tabs
        # doesn't discard the other tab's plots.
        self.paramFigures = []
        self.customFigures = []

        self.allFields = []
        self.customFields = []  # [{"field", "scale_var", "row"}]
        self._fields_loaded_path = None

        # self.geometry() queried at close time doesn't reliably reflect a window
        # last moved/resized by the OS/WM (e.g. Windows Aero Snap, or a Linux
        # tiling/edge-snap WM), so track the geometry continuously via
        # <Configure>, which fires on every move/resize regardless of cause.
        # The "zoomed"/maximized case is tracked separately from the normal
        # geometry: Windows can report stale winfo_x/y/width/height while
        # zoomed, and X11 doesn't expose maximize via state() at all, so the
        # last *normal* rect (i.e. right before maximizing) is what's used to
        # know which monitor to re-maximize onto.
        self._last_normal_geometry = None
        self._last_zoomed = False
        self.bind("<Configure>", self._on_window_configure)

        self._build_top_bar()
        self._build_status_bar()
        self._build_body()
        self._populate_field_panel([])
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_window_configure(self, event):
        # Some X11 window managers report <Configure>'s x/y relative to the
        # reparented decoration frame rather than the screen, so query Tk's
        # corrected absolute position instead of trusting the event fields.
        # Windows 11 snap zones (left-half, 2/3 layouts, etc.) keep state()
        # "normal" and report accurate geometry, so they fall through to the
        # plain geometry tracking below; only minimized/withdrawn states
        # report a placeholder rect worth ignoring.
        if event.widget is not self or self.state() not in ("normal", "zoomed"):
            return
        self._last_zoomed = self._is_zoomed()
        if not self._last_zoomed:
            self._last_normal_geometry = (
                f"{self.winfo_width()}x{self.winfo_height()}+{self.winfo_x()}+{self.winfo_y()}"
            )

    def _is_zoomed(self):
        """True if truly OS-maximized. Windows surfaces this via state();
        X11 (Ubuntu/GNOME etc.) never reports state() == 'zoomed' and uses
        the separate '-zoomed' wm attribute instead."""
        if sys.platform == "win32":
            return self.state() == "zoomed"
        try:
            return bool(self.attributes("-zoomed"))
        except tk.TclError:
            return self.state() == "zoomed"

    def _maximize(self):
        if sys.platform == "win32":
            self.state("zoomed")
        else:
            try:
                self.attributes("-zoomed", True)
            except tk.TclError:
                self.state("zoomed")

    def _on_close(self):
        # plt.figure() spins up its own hidden Tk root per figure (matplotlib's
        # TkAgg backend does this even though we never call plt.show() on them).
        # Tkinter's mainloop() only returns once every Tk window in the process
        # is gone, so leaving these open hangs the process after this window closes.
        plt.close("all")
        self.app_config["window_geometry"] = self._last_normal_geometry or self.geometry()
        self.app_config["window_zoomed"] = self._last_zoomed
        _save_config(self.app_config)
        self.destroy()

    def _apply_ttk_theme(self):
        self.configure(background=COLOR_BG)

        style = ttk.Style(self)
        style.theme_use("clam")

        # Upper control bar (file selector through plot configuration) gets a
        # 30% larger font than the rest of the app (status text, plot headers).
        base_font = tkfont.nametofont("TkDefaultFont")
        base_size = base_font.actual("size")
        header_size = round(abs(base_size) * 1.3) * (-1 if base_size < 0 else 1)
        self.header_font = tkfont.Font(family=base_font.actual("family"), size=header_size)
        self.event_header_font = tkfont.Font(
            family=base_font.actual("family"), size=header_size, weight="bold"
        )

        style.configure(
            ".", background=COLOR_BG, foreground=COLOR_FG,
            fieldbackground=COLOR_BG_INPUT, bordercolor=COLOR_BORDER,
            darkcolor=COLOR_BG, lightcolor=COLOR_BG, troughcolor=COLOR_BG_INPUT,
        )
        style.configure("TFrame", background=COLOR_BG)
        style.configure("TLabel", background=COLOR_BG, foreground=COLOR_FG)
        style.configure("Header.TLabel", background=COLOR_BG, foreground=COLOR_FG, font=self.header_font)
        style.configure("TSeparator", background=COLOR_BORDER)

        style.configure(
            "TEntry", fieldbackground=COLOR_BG_INPUT, foreground=COLOR_FG,
            insertcolor=COLOR_FG, bordercolor=COLOR_BORDER,
            lightcolor=COLOR_BG_INPUT, darkcolor=COLOR_BG_INPUT, font=self.header_font,
        )
        style.map("TEntry", fieldbackground=[("disabled", COLOR_BG_PANEL)])

        style.configure(
            "TButton", background=COLOR_ACCENT, foreground="white",
            borderwidth=0, focuscolor=COLOR_ACCENT_HOVER, padding=6, font=self.header_font,
        )
        style.map(
            "TButton",
            background=[("active", COLOR_ACCENT_HOVER), ("pressed", COLOR_ACCENT_ACTIVE)],
            foreground=[("disabled", COLOR_FG_MUTED)],
        )

        style.configure(
            "TCheckbutton", background=COLOR_BG, foreground=COLOR_FG,
            indicatorbackground=COLOR_BG_INPUT, indicatorforeground=COLOR_FG, font=self.header_font,
        )
        style.map(
            "TCheckbutton",
            background=[("active", COLOR_BG)],
            indicatorbackground=[("selected", COLOR_ACCENT), ("active", COLOR_BG_HOVER)],
        )

        style.configure("TNotebook", background=COLOR_BG, borderwidth=0)
        style.configure(
            "TNotebook.Tab", background=COLOR_BG_PANEL, foreground=COLOR_FG,
            padding=(14, 6), font=self.header_font, borderwidth=0,
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", COLOR_ACCENT), ("active", COLOR_BG_HOVER)],
            foreground=[("selected", "white")],
        )

        for orientation in ("Horizontal", "Vertical"):
            style.configure(
                f"{orientation}.TScale", background=COLOR_BG, troughcolor=COLOR_BG_INPUT,
                bordercolor=COLOR_BG, lightcolor=COLOR_ACCENT, darkcolor=COLOR_ACCENT,
            )
            style.configure(
                f"{orientation}.TScrollbar", background=COLOR_BG_PANEL, troughcolor=COLOR_BG,
                bordercolor=COLOR_BG, arrowcolor=COLOR_FG_MUTED, lightcolor=COLOR_BG_PANEL,
                darkcolor=COLOR_BG_PANEL,
            )
            style.map(f"{orientation}.TScrollbar", background=[("active", COLOR_BG_HOVER)])

    _GEOMETRY_RE = re.compile(r"^(\d+)x(\d+)([+-]\d+)([+-]\d+)$")

    def _virtual_screen_bounds(self):
        """Bounding box of the whole multi-monitor desktop. winfo_screenwidth/
        height() only reports the primary monitor's resolution on Windows
        (GetSystemMetrics(SM_CXSCREEN)), which would reject any saved geometry
        sitting on a secondary monitor. X11 (Ubuntu/GNOME) already reports one
        combined desktop rect starting at (0, 0), so it needs no special-case."""
        if sys.platform == "win32":
            try:
                import ctypes
                user32 = ctypes.windll.user32
                x = user32.GetSystemMetrics(76)  # SM_XVIRTUALSCREEN
                y = user32.GetSystemMetrics(77)  # SM_YVIRTUALSCREEN
                w = user32.GetSystemMetrics(78)  # SM_CXVIRTUALSCREEN
                h = user32.GetSystemMetrics(79)  # SM_CYVIRTUALSCREEN
                if w > 0 and h > 0:
                    return x, y, w, h
            except Exception:
                pass
        return 0, 0, self.winfo_screenwidth(), self.winfo_screenheight()

    def _usable_saved_geometry(self, geometry):
        """Validate a saved geometry string still lands on a connected screen
        (e.g. the window was last closed on a monitor that's now unplugged)."""
        match = geometry and self._GEOMETRY_RE.match(geometry)
        if not match:
            return None
        w, h, x, y = (int(v) for v in match.groups())
        screen_x, screen_y, screen_w, screen_h = self._virtual_screen_bounds()
        margin = 50
        if (x + w < screen_x + margin or x > screen_x + screen_w - margin
                or y + h < screen_y + margin or y > screen_y + screen_h - margin):
            return None
        return geometry

    def _size_to_plots(self):
        saved = self._usable_saved_geometry(self.app_config.get("window_geometry"))
        if saved:
            self.geometry(saved)
        else:
            # Plots size themselves to whatever window they end up in, so the
            # default just needs to be a reasonable size, capped to the screen.
            target_w, target_h = 2100, 1300
            win_w = min(target_w, self.winfo_screenwidth() - 60)
            win_h = min(target_h, self.winfo_screenheight() - 100)
            self.geometry(f"{win_w}x{win_h}")

        if saved and self.app_config.get("window_zoomed"):
            # Re-maximizing needs the window already positioned (above) on the
            # target monitor first, since both Windows and X11 maximize onto
            # whichever monitor the window currently sits on.
            self.update_idletasks()
            self._maximize()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_top_bar(self):
        bar = ttk.Frame(self, padding=8)
        bar.pack(side="top", fill="x")

        ttk.Label(bar, text="Log file:", style="Header.TLabel").grid(row=0, column=0, sticky="w")
        entry = ttk.Entry(bar, textvariable=self.logPath, width=80)
        entry.grid(row=0, column=1, sticky="we", padx=4)
        entry.bind("<Return>", lambda e: self._on_log_path_committed())
        entry.bind("<FocusOut>", lambda e: self._on_log_path_committed())
        ttk.Button(bar, text="Browse...", command=self._browse).grid(row=0, column=2, padx=4)

        bar.grid_columnconfigure(1, weight=1)

    def _build_status_bar(self):
        self.status = ttk.Label(self, text="Select a log file to begin.", padding=(8, 0))
        self.status.pack(side="bottom", fill="x")

    def _build_body(self):
        # Field sidebar (0-20% width) + tabgroup (20-100% width), expressed as
        # a 1:4 grid weight ratio so the split holds at any window size.
        body = ttk.Frame(self)
        body.grid_rowconfigure(0, weight=1)
        body.grid_columnconfigure(0, weight=SIDEBAR_WEIGHT, uniform="body")
        body.grid_columnconfigure(1, weight=TABS_WEIGHT, uniform="body")
        body.pack(side="top", fill="both", expand=True)

        fieldContainer = ttk.Frame(body)
        fieldContainer.grid(row=0, column=0, sticky="nsew")
        fieldContainer.grid_rowconfigure(1, weight=1)
        fieldContainer.grid_columnconfigure(0, weight=1)
        ttk.Label(fieldContainer, text="CSV Fields", style="Header.TLabel").grid(
            row=0, column=0, sticky="w", padx=6, pady=(4, 2)
        )
        self.fieldPanel = ScrollableFrame(fieldContainer, bg=COLOR_BG_PANEL)
        self.fieldPanel.grid(row=1, column=0, sticky="nsew")

        self.notebook = ttk.Notebook(body)
        self.notebook.grid(row=0, column=1, sticky="nsew")

        self._build_parameterized_tab(self.notebook)
        self._build_custom_tab(self.notebook)

    def _build_parameterized_tab(self, notebook):
        tab = ttk.Frame(notebook, padding=8)
        notebook.add(tab, text="Parameterized Plots")

        ttk.Label(tab, text="Auto-Find Throttle Threshold (%): ", style="Header.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Entry(tab, textvariable=self.threshVar, width=6).grid(row=0, column=1, sticky="w")

        self._paramRangeGridKw = dict(row=2, column=0, columnspan=4, sticky="we", pady=(8, 0))

        self.autoFindCheck = ttk.Checkbutton(
            tab, text="Autofind high-throttle events", variable=self.autoFindVar,
            command=lambda: self._toggle_autofind(self.autoFindVar, self.rangeFrame, self._paramRangeGridKw)
        )
        self.autoFindCheck.grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 0))

        self.rangeFrame = self._build_range_frame(tab, self.paramRange, on_change=self._replot_param_if_live)

        # Plot button anchored top-right, spanning the controls so it's
        # always reachable without scrolling, regardless of autofind state.
        ttk.Button(tab, text="Plot", command=self._plotParameterized).grid(
            row=0, column=4, rowspan=3, padx=(16, 0), sticky="ns"
        )

        self.paramScrollArea = ScrollableFrame(tab, bg=COLOR_BG)
        self.paramScrollArea.grid(row=3, column=0, columnspan=5, sticky="nsew", pady=(8, 0))

        tab.grid_columnconfigure(2, weight=1)
        tab.grid_rowconfigure(3, weight=1)

        self._toggle_autofind(self.autoFindVar, self.rangeFrame, self._paramRangeGridKw)

    def _build_custom_tab(self, notebook):
        tab = ttk.Frame(notebook, padding=8)
        notebook.add(tab, text="Custom Plot")

        ttk.Label(tab, text="Search fields:", style="Header.TLabel").grid(row=0, column=0, sticky="w")
        searchEntry = ttk.Entry(tab, textvariable=self.customSearchVar)
        searchEntry.grid(row=0, column=1, sticky="we", padx=4)
        self.customSearchVar.trace_add("write", lambda *_: self._filter_custom_listbox())

        listFrame = ttk.Frame(tab)
        listFrame.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(4, 0))
        listFrame.grid_rowconfigure(0, weight=1)
        listFrame.grid_columnconfigure(0, weight=1)
        self.fieldListbox = tk.Listbox(
            listFrame, selectmode="extended", height=4, exportselection=False,
            background=COLOR_BG_INPUT, foreground=COLOR_FG,
            selectbackground=COLOR_ACCENT, selectforeground="white",
            highlightthickness=0, borderwidth=0,
        )
        listScroll = ttk.Scrollbar(listFrame, orient="vertical", command=self.fieldListbox.yview)
        self.fieldListbox.configure(yscrollcommand=listScroll.set)
        self.fieldListbox.grid(row=0, column=0, sticky="nsew")
        listScroll.grid(row=0, column=1, sticky="ns")
        self.fieldListbox.bind("<Double-Button-1>", lambda e: self._add_selected_custom_fields())

        ttk.Button(tab, text="Add Selected →", command=self._add_selected_custom_fields).grid(
            row=2, column=0, columnspan=2, sticky="w", pady=(6, 0)
        )

        ttk.Label(tab, text="Selected fields:", style="Header.TLabel").grid(
            row=3, column=0, columnspan=2, sticky="w", pady=(10, 0)
        )
        self.customSelectedScroll = ScrollableFrame(tab, bg=COLOR_BG, height=70)
        self.customSelectedScroll.grid(row=4, column=0, columnspan=2, sticky="nsew", pady=(2, 0))
        self.customSelectedContainer = self.customSelectedScroll.content

        ttk.Label(tab, text="Auto-Find Throttle Threshold (%): ", style="Header.TLabel").grid(
            row=5, column=0, sticky="w", pady=(10, 0)
        )
        ttk.Entry(tab, textvariable=self.customThreshVar, width=6).grid(
            row=5, column=1, sticky="w", pady=(10, 0)
        )

        self._customRangeGridKw = dict(row=7, column=0, columnspan=4, sticky="we", pady=(8, 0))

        self.customAutoFindCheck = ttk.Checkbutton(
            tab, text="Autofind high-throttle events", variable=self.customAutoFindVar,
            command=lambda: self._toggle_autofind(
                self.customAutoFindVar, self.customRangeFrame, self._customRangeGridKw
            ),
        )
        self.customAutoFindCheck.grid(row=6, column=0, columnspan=2, sticky="w", pady=(8, 0))

        self.customRangeFrame = self._build_range_frame(tab, self.customRange, on_change=self._replot_custom_if_live)

        # Plot button anchored top-right, spanning the whole controls
        # column so it stays reachable regardless of how many fields are
        # selected or how far the field list/output below has scrolled.
        ttk.Button(tab, text="Plot", command=self._plotCustom).grid(
            row=0, column=2, rowspan=8, padx=(16, 0), sticky="ns"
        )

        self.customScrollArea = ScrollableFrame(tab, bg=COLOR_BG)
        self.customScrollArea.grid(row=8, column=0, columnspan=3, sticky="nsew", pady=(8, 0))

        tab.grid_columnconfigure(1, weight=1)
        # Rows 1 (field list) and 4 (selected fields) are deliberately
        # unweighted/fixed-height (capped via the listbox's height=4 and the
        # ScrollableFrame's height=70 above) - each has its own internal
        # scrollbar for when its content overflows, so there's no need to
        # let them grow. That leaves row 8 (plot output) as the *only*
        # weighted row, so it claims 100% of any extra vertical space and
        # its top edge sits right below the (now compact) controls instead
        # of needing the window to be huge before it's visible.
        tab.grid_rowconfigure(1, minsize=90)
        tab.grid_rowconfigure(4, minsize=80)
        tab.grid_rowconfigure(8, weight=1, minsize=200)

        self._toggle_autofind(self.customAutoFindVar, self.customRangeFrame, self._customRangeGridKw)

    def _build_range_frame(self, parent, range_vars, on_change=None):
        """Start %/End % entry+slider pair, shared by both tabs. Caller owns
        showing/hiding it (via _toggle_autofind) since visibility depends on
        that tab's own autofind checkbox. on_change, if given, fires after
        every slider drag or entry edit, e.g. to live-replot an existing chart."""
        frame = ttk.Frame(parent)
        ttk.Label(frame, text="Start %:", style="Header.TLabel").grid(row=0, column=0, sticky="w")
        startEntry = ttk.Entry(frame, textvariable=range_vars.startPrctVar, width=6)
        startEntry.grid(row=0, column=1, padx=4)
        startEntry.bind("<Return>", lambda e: self._sync_entry_to_scale(range_vars, "start", on_change))
        startEntry.bind("<FocusOut>", lambda e: self._sync_entry_to_scale(range_vars, "start", on_change))
        ttk.Scale(
            frame, from_=0.0, to=100.0, orient="horizontal", length=400,
            variable=range_vars.startScaleVar,
            command=lambda v: self._on_start_scale(range_vars, v, on_change),
        ).grid(row=0, column=2, sticky="we", padx=4)

        ttk.Label(frame, text="End %:", style="Header.TLabel").grid(row=1, column=0, sticky="w", pady=(4, 0))
        endEntry = ttk.Entry(frame, textvariable=range_vars.endPrctVar, width=6)
        endEntry.grid(row=1, column=1, padx=4, pady=(4, 0))
        endEntry.bind("<Return>", lambda e: self._sync_entry_to_scale(range_vars, "end", on_change))
        endEntry.bind("<FocusOut>", lambda e: self._sync_entry_to_scale(range_vars, "end", on_change))
        ttk.Scale(
            frame, from_=0.0, to=100.0, orient="horizontal", length=400,
            variable=range_vars.endScaleVar,
            command=lambda v: self._on_end_scale(range_vars, v, on_change),
        ).grid(row=1, column=2, sticky="we", padx=4, pady=(4, 0))
        frame.grid_columnconfigure(2, weight=1)
        return frame

    def _toggle_autofind(self, auto_find_var, range_frame, range_grid_kw):
        if auto_find_var.get():
            range_frame.grid_remove()
        else:
            range_frame.grid(**range_grid_kw)

    @staticmethod
    def _clamp_pct(value):
        return max(0.0, min(100.0, value))

    def _on_start_scale(self, range_vars, value, on_change=None):
        v = self._clamp_pct(float(value))
        if v > range_vars.endScaleVar.get():
            range_vars.endScaleVar.set(v)
            range_vars.endPrctVar.set(f"{v:.1f}")
        range_vars.startPrctVar.set(f"{v:.1f}")
        if on_change:
            on_change()

    def _on_end_scale(self, range_vars, value, on_change=None):
        v = self._clamp_pct(float(value))
        if v < range_vars.startScaleVar.get():
            range_vars.startScaleVar.set(v)
            range_vars.startPrctVar.set(f"{v:.1f}")
        range_vars.endPrctVar.set(f"{v:.1f}")
        if on_change:
            on_change()

    def _sync_entry_to_scale(self, range_vars, which, on_change=None):
        var = range_vars.startPrctVar if which == "start" else range_vars.endPrctVar
        scale_var = range_vars.startScaleVar if which == "start" else range_vars.endScaleVar
        try:
            v = self._clamp_pct(float(var.get()))
        except ValueError:
            v = scale_var.get()
        var.set(f"{v:.1f}")
        scale_var.set(v)
        if on_change:
            on_change()

    def _browse(self):
        initial_dir = self.app_config.get("last_dir")
        if not initial_dir or not Path(initial_dir).is_dir():
            initial_dir = str(Path.home())
        path = filedialog.askopenfilename(
            title="Select AP log",
            initialdir=initial_dir,
            filetypes=[("CSV log files", "*.csv"), ("All files", "*.*")],
        )
        if path:
            self.logPath.set(path)
            self.app_config["last_dir"] = str(Path(path).parent)
            _save_config(self.app_config)
            try:
                self._refresh_fields(path)
            except Exception as exc:
                self.status.configure(text=f"Could not read fields: {exc}")

    def _on_log_path_committed(self):
        path = self.logPath.get().strip()
        if not path or path == self._fields_loaded_path:
            return
        try:
            self._refresh_fields(path)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Field list sidebar + custom field picker
    # ------------------------------------------------------------------
    def _refresh_fields(self, path):
        fields = LogPlotUtil.list_fields(path)
        self.allFields = fields
        self._fields_loaded_path = path
        self._populate_field_panel(fields)
        self._reset_custom_fields()
        self._filter_custom_listbox()
        self._update_autofind_availability()

    def _update_autofind_availability(self):
        """Throttle-event autofind needs UserParams.throttleField; without it
        there's nothing to detect events from, in either tab."""
        throttle_present = UserParams.throttleField in self.allFields
        state = "normal" if throttle_present else "disabled"
        self.autoFindCheck.configure(state=state)
        self.customAutoFindCheck.configure(state=state)
        if not throttle_present:
            self.autoFindVar.set(False)
            self.customAutoFindVar.set(False)
        self._toggle_autofind(self.autoFindVar, self.rangeFrame, self._paramRangeGridKw)
        self._toggle_autofind(self.customAutoFindVar, self.customRangeFrame, self._customRangeGridKw)

    def _populate_field_panel(self, fields):
        for child in self.fieldPanel.content.winfo_children():
            child.destroy()
        if not fields:
            ttk.Label(
                self.fieldPanel.content, text="No log file selected.", foreground=COLOR_FG_MUTED
            ).pack(anchor="w", padx=6, pady=4)
            return
        for field in fields:
            ttk.Label(self.fieldPanel.content, text=field, anchor="w").pack(
                fill="x", anchor="w", padx=6, pady=1
            )

    def _filter_custom_listbox(self):
        # Time is always the plot's x-axis, never a selectable y-series.
        query = self.customSearchVar.get().strip().lower()
        self.fieldListbox.delete(0, "end")
        for field in self.allFields:
            lowered = field.lower()
            if "time" in lowered:
                continue
            if query in lowered:
                self.fieldListbox.insert("end", field)

    def _add_selected_custom_fields(self):
        selected_indices = self.fieldListbox.curselection()
        if not selected_indices:
            return
        existing = {f["field"] for f in self.customFields}
        for idx in selected_indices:
            field = self.fieldListbox.get(idx)
            if field in existing:
                continue
            self._add_custom_field_row(field)
            existing.add(field)

    def _add_custom_field_row(self, field):
        scale_var = tk.StringVar(value="1")
        row = ttk.Frame(self.customSelectedContainer)
        row.pack(fill="x", pady=1)
        ttk.Label(row, text=field, anchor="w").pack(side="left", fill="x", expand=True)
        ttk.Label(row, text="Scale:").pack(side="left", padx=(8, 2))
        ttk.Entry(row, textvariable=scale_var, width=8).pack(side="left")
        entry = {"field": field, "scale_var": scale_var, "row": row}
        ttk.Button(
            row, text="Remove", command=lambda: self._remove_custom_field(entry)
        ).pack(side="left", padx=(4, 0))
        self.customFields.append(entry)

    def _remove_custom_field(self, entry):
        self.customFields = [f for f in self.customFields if f is not entry]
        entry["row"].destroy()

    def _reset_custom_fields(self):
        for f in self.customFields:
            f["row"].destroy()
        self.customFields = []

    # ------------------------------------------------------------------
    # Plotting
    # ------------------------------------------------------------------
    def _replot_param_if_live(self):
        """Dragging the start/end sliders should immediately reflect on an
        already-plotted chart, but only once there's something on screen to
        update and autofind isn't the one driving the time range. silent=True
        so a slider drag can never pop a blocking error dialog (e.g. if the
        threshold field happens to be invalid mid-edit) - it just skips the
        update and leaves the stale chart up until the user fixes the input
        and clicks Plot again."""
        if not self.autoFindVar.get() and self.paramFigures:
            self._plotParameterized(silent=True)

    def _replot_custom_if_live(self):
        if not self.customAutoFindVar.get() and self.customFigures:
            self._plotCustom(silent=True)

    def _plotParameterized(self, silent=False):
        path = self.logPath.get().strip()
        if not path:
            if not silent:
                messagebox.showerror("No log selected", "Choose a log file first.")
            return

        try:
            thresh = float(self.threshVar.get())
        except ValueError:
            if not silent:
                messagebox.showerror("Invalid input", "Throttle threshold must be a number.")
            return

        auto_find = self.autoFindVar.get()
        start_prct = end_prct = 0.0
        if not auto_find:
            try:
                start_prct = float(self.paramRange.startPrctVar.get()) / 100.0
                end_prct = float(self.paramRange.endPrctVar.get()) / 100.0
            except ValueError:
                if not silent:
                    messagebox.showerror("Invalid input", "Start/End % must be numbers.")
                return

        self._clear_plots(self.paramScrollArea, self.paramFigures)
        self.status.configure(text="Plotting...")
        self.update_idletasks()

        # holder.pack(..., padx=8) below eats 8px on each side of the canvas
        # viewport's width.
        avail_width = self.paramScrollArea.canvas.winfo_width() - 16
        figsize = _figsize_for_width(avail_width)

        try:
            util = ParamPlotUtil(path, thresh, figsize=figsize)
            util._plotLog(
                start_prct, end_prct, auto_find,
                on_figure=lambda fig: self._embed_figure(fig, self.paramScrollArea, self.paramFigures),
                on_event_header=lambda n: self._add_event_header(n, self.paramScrollArea),
            )
        except Exception as exc:
            if not silent:
                messagebox.showerror("Plotting failed", str(exc))
            self.status.configure(text="Plotting failed.")
            return

        if not self.paramFigures:
            self.status.configure(text="No plots produced (no high-throttle events found?).")
        else:
            self.status.configure(text=f"Plotted {len(self.paramFigures)} chart(s).")

    def _plotCustom(self, silent=False):
        path = self.logPath.get().strip()
        if not path:
            if not silent:
                messagebox.showerror("No log selected", "Choose a log file first.")
            return
        if not self.customFields:
            if not silent:
                messagebox.showerror("No fields selected", "Search and add at least one field to plot.")
            return

        fields_scales = []
        for f in self.customFields:
            try:
                scale = float(f["scale_var"].get())
            except ValueError:
                if not silent:
                    messagebox.showerror("Invalid input", f"Scale for '{f['field']}' must be a number.")
                return
            fields_scales.append((f["field"], scale))

        try:
            thresh = float(self.customThreshVar.get())
        except ValueError:
            if not silent:
                messagebox.showerror("Invalid input", "Throttle threshold must be a number.")
            return

        auto_find = self.customAutoFindVar.get()
        start_prct = end_prct = 0.0
        if not auto_find:
            try:
                start_prct = float(self.customRange.startPrctVar.get()) / 100.0
                end_prct = float(self.customRange.endPrctVar.get()) / 100.0
            except ValueError:
                if not silent:
                    messagebox.showerror("Invalid input", "Start/End % must be numbers.")
                return

        self._clear_plots(self.customScrollArea, self.customFigures)
        self.status.configure(text="Plotting...")
        self.update_idletasks()

        avail_width = self.customScrollArea.canvas.winfo_width() - 16
        avail_height = self.customScrollArea.canvas.winfo_height() - TOOLBAR_RESERVE_PX
        figsize = _figsize_for_width(avail_width, avail_height_px=avail_height)

        try:
            util = CustomPlotUtil(path, thresh, figsize=figsize)
            util._plotCustomLog(
                fields_scales, start_prct, end_prct, auto_find,
                on_figure=lambda fig: self._embed_figure(fig, self.customScrollArea, self.customFigures),
                on_event_header=lambda n: self._add_event_header(n, self.customScrollArea),
            )
        except Exception as exc:
            if not silent:
                messagebox.showerror("Plotting failed", str(exc))
            self.status.configure(text="Plotting failed.")
            return

        if not self.customFigures:
            self.status.configure(text="No plot produced (check selected fields).")
        else:
            self.status.configure(text=f"Plotted {len(self.customFigures)} chart(s).")

    def _clear_plots(self, scroll_area, figures):
        for fig in figures:
            plt.close(fig)
        figures.clear()
        scroll_area.clear()

    def _add_event_header(self, evt_counter, scroll_area):
        ttk.Separator(scroll_area.content).pack(fill="x", pady=(12, 4))
        ttk.Label(
            scroll_area.content,
            text=f" High Throttle Event {evt_counter} ---------------------------------------",
            font=self.event_header_font,
            foreground=COLOR_ACCENT_HOVER,
        ).pack(anchor="w", padx=8, pady=(0, 4))

    def _embed_figure(self, fig, scroll_area, figures):
        figures.append(fig)
        holder = ttk.Frame(scroll_area.content)
        holder.pack(fill="x", padx=8, pady=4)

        canvas = FigureCanvasTkAgg(fig, master=holder)
        canvas.draw()
        # No fill: the figure was already sized to the plot area's width in
        # _plotParameterized()/_plotCustom(), and matplotlib's TkAgg backend
        # auto-rescales (and distorts the carefully computed width/height
        # ratio) whenever its widget is resized, which fill="x" would trigger
        # on every window resize.
        canvas.get_tk_widget().pack()

        toolbar = NavigationToolbar2Tk(canvas, holder, pack_toolbar=False)
        toolbar.update()
        toolbar.pack(anchor="w", fill="x")
        _recolor_classic_widget(toolbar)


if __name__ == "__main__":
    app = LogPlotterGUI()
    app.mainloop()
