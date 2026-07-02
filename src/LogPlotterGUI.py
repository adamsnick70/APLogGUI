import json
import re
import sys
import tkinter as tk
import tkinter.font as tkfont
from pathlib import Path
from tkinter import ttk, filedialog, messagebox

import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.backends.backend_pdf import PdfPages

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


class SelectableFieldList(ttk.Frame):
    """A read-only, line-per-field list the user can still mouse-select and
    copy (Ctrl+C). Tk's Text widget keeps selection/<<Copy>> bindings active
    even when state=DISABLED - only programmatic edits (insert/delete) are
    blocked - so this gets "read-only" without giving up copy/paste, unlike
    a plain Label per field."""

    def __init__(self, parent, bg=COLOR_BG_PANEL, fg=COLOR_FG):
        super().__init__(parent)
        self.text = tk.Text(
            self, background=bg, foreground=fg, wrap="none",
            highlightthickness=0, borderwidth=0, padx=6, pady=4,
            selectbackground=COLOR_ACCENT, selectforeground="white",
            insertwidth=0, cursor="arrow", state="disabled",
        )
        vscroll = ttk.Scrollbar(self, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=vscroll.set)

        self.text.grid(row=0, column=0, sticky="nsew")
        vscroll.grid(row=0, column=1, sticky="ns")
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

    def set_lines(self, lines):
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", "\n".join(lines))
        self.text.configure(state="disabled")


class LogPlotterGUI(tk.Tk):
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

        self.customAutoFindVar = tk.BooleanVar(value=True)
        self.customThreshVar = tk.StringVar(value="75")
        self.customSearchVar = tk.StringVar()

        # Each tab keeps its own figure list/output area so switching tabs
        # doesn't discard the other tab's plots.
        self.paramFigures = []
        self.customFigures = []

        # Mirrors paramFigures but interleaved with ("event", n) markers in
        # display order, so the PDF export can reproduce the same High
        # Throttle Event separators shown on screen.
        self.paramPlotSequence = []

        # Axes are grouped the same way: one group per High Throttle Event
        # when autofind is on, or a single group for the whole tab when it's
        # off, so zoom/pan on one plot can be mirrored across the rest of
        # its group (see _link_x_axes).
        self.paramAxisGroups = []

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
            family=base_font.actual("family"), size=header_size * 2, weight="bold"
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
        self.fieldPanel = SelectableFieldList(fieldContainer, bg=COLOR_BG_PANEL)
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

        self.autoFindCheck = ttk.Checkbutton(
            tab, text="Autofind high-throttle events", variable=self.autoFindVar,
        )
        self.autoFindCheck.grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 0))

        # Save PDF sits immediately left of Plot, but only once there's at
        # least one plot to export - hidden (never gridded) until then; see
        # _update_param_pdf_button.
        self._paramPdfButtonGridKw = dict(row=0, column=3, rowspan=2, padx=(16, 0), sticky="ns")
        self.paramPdfButton = ttk.Button(tab, text="Save PDF", command=self._savePdfParam)

        # Plot button anchored top-right, spanning the controls so it's
        # always reachable without scrolling.
        ttk.Button(tab, text="Plot", command=self._plotParameterized).grid(
            row=0, column=4, rowspan=2, padx=(16, 0), sticky="ns"
        )

        self.paramScrollArea = ScrollableFrame(tab, bg=COLOR_BG)
        self.paramScrollArea.grid(row=2, column=0, columnspan=5, sticky="nsew", pady=(8, 0))

        tab.grid_columnconfigure(2, weight=1)
        tab.grid_rowconfigure(2, weight=1)

    def _build_custom_tab(self, notebook):
        tab = ttk.Frame(notebook, padding=8)
        notebook.add(tab, text="Custom Plot")

        # Search fields (left) and Selected fields (right) sit side by side
        # instead of stacked, each filling the tab's height down to the Plot
        # button divider below - that's the width the two of them used to
        # spend stacked on top of each other, now spent stretching down.
        searchFrame = ttk.Frame(tab)
        searchFrame.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        searchFrame.grid_columnconfigure(1, weight=1)
        searchFrame.grid_rowconfigure(1, weight=1)

        ttk.Label(searchFrame, text="Search fields:", style="Header.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        searchEntry = ttk.Entry(searchFrame, textvariable=self.customSearchVar)
        searchEntry.grid(row=0, column=1, sticky="we", padx=4)
        self.customSearchVar.trace_add("write", lambda *_: self._filter_custom_listbox())

        listFrame = ttk.Frame(searchFrame)
        listFrame.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(4, 0))
        listFrame.grid_rowconfigure(0, weight=1)
        listFrame.grid_columnconfigure(0, weight=1)
        self.fieldListbox = tk.Listbox(
            listFrame, selectmode="extended", height=1, exportselection=False,
            background=COLOR_BG_INPUT, foreground=COLOR_FG,
            selectbackground=COLOR_ACCENT, selectforeground="white",
            highlightthickness=0, borderwidth=0,
        )
        listScroll = ttk.Scrollbar(listFrame, orient="vertical", command=self.fieldListbox.yview)
        self.fieldListbox.configure(yscrollcommand=listScroll.set)
        self.fieldListbox.grid(row=0, column=0, sticky="nsew")
        listScroll.grid(row=0, column=1, sticky="ns")
        self.fieldListbox.bind("<Double-Button-1>", lambda e: self._add_selected_custom_fields())

        ttk.Button(searchFrame, text="Add Selected →", command=self._add_selected_custom_fields).grid(
            row=2, column=0, columnspan=2, sticky="w", pady=(6, 0)
        )

        selectedFrame = ttk.Frame(tab)
        selectedFrame.grid(row=0, column=1, sticky="nsew")
        selectedFrame.grid_columnconfigure(0, weight=1)
        selectedFrame.grid_rowconfigure(1, weight=1)

        ttk.Label(selectedFrame, text="Selected fields:", style="Header.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        # height=1 gives the canvas a 1-px natural request so it doesn't
        # inflate selectedFrame's reported size to the outer grid — the
        # canvas still expands to fill whatever space row 1 actually gets.
        self.customSelectedScroll = ScrollableFrame(selectedFrame, bg=COLOR_BG, height=1)
        self.customSelectedScroll.grid(row=1, column=0, sticky="nsew", pady=(2, 0))
        self.customSelectedContainer = self.customSelectedScroll.content

        # Label and entry packed side-by-side in their own sub-frame so the
        # entry sits immediately after the label text rather than being pushed
        # to the far right by selectedFrame's column weight.
        threshRow = ttk.Frame(selectedFrame)
        threshRow.grid(row=2, column=0, sticky="w", pady=(10, 0))
        ttk.Label(threshRow, text="Auto-Find Throttle Threshold (%): ", style="Header.TLabel").pack(side="left")
        ttk.Entry(threshRow, textvariable=self.customThreshVar, width=6).pack(side="left")

        self.customAutoFindCheck = ttk.Checkbutton(
            selectedFrame, text="Autofind high-throttle events", variable=self.customAutoFindVar,
        )
        self.customAutoFindCheck.grid(row=3, column=0, sticky="w", pady=(8, 0))

        # Plot button now sits in its own thin row underneath both setup
        # areas, dividing setup from the plots below, rather than spanning
        # the full height off to the side. A 35/30/35 column split keeps the
        # button itself at 30% of the tab's width, centered.
        buttonRow = ttk.Frame(tab)
        buttonRow.grid(row=1, column=0, columnspan=2, sticky="ew", pady=8)
        buttonRow.grid_columnconfigure(0, weight=35)
        buttonRow.grid_columnconfigure(1, weight=30)
        buttonRow.grid_columnconfigure(2, weight=35)
        ttk.Button(buttonRow, text="Plot", command=self._plotCustom).grid(
            row=0, column=1, sticky="ew"
        )

        # height=1 for the same reason as customSelectedScroll above.
        self.customScrollArea = ScrollableFrame(tab, bg=COLOR_BG, height=1)
        self.customScrollArea.grid(row=2, column=0, columnspan=2, sticky="nsew")

        tab.grid_columnconfigure(0, weight=1, uniform="customSetup")
        tab.grid_columnconfigure(1, weight=1, uniform="customSetup")
        # Setup (row 0) and plot output (row 2) share any extra vertical
        # space, with the thin Plot button row in between left
        # unweighted so it stays exactly as tall as its contents.
        # minsize values are kept small so the weight ratio dominates
        # proportionally on every screen size rather than letting large
        # absolute floors eat all the available space on smaller displays.
        tab.grid_rowconfigure(0, weight=1, minsize=120)
        tab.grid_rowconfigure(2, weight=4, minsize=100)

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

    def _populate_field_panel(self, fields):
        self.fieldPanel.set_lines(fields if fields else ["No log file selected."])

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
    def _plotParameterized(self):
        path = self.logPath.get().strip()
        if not path:
            messagebox.showerror("No log selected", "Choose a log file first.")
            return

        try:
            thresh = float(self.threshVar.get())
        except ValueError:
            messagebox.showerror("Invalid input", "Throttle threshold must be a number.")
            return

        auto_find = self.autoFindVar.get()

        self._clear_plots(self.paramScrollArea, self.paramFigures)
        self.paramPlotSequence = []
        # A fresh single group to start - if autofind fires, the first
        # on_event_header call replaces it with its own group; if it
        # doesn't (manual full-range plot), every figure lands in this one
        # group so the whole tab's x-axes end up linked together.
        self.paramAxisGroups = [[]]
        self.status.configure(text="Plotting...")
        self.update_idletasks()

        # holder.pack(..., padx=8) below eats 8px on each side of the canvas
        # viewport's width.
        avail_width = self.paramScrollArea.canvas.winfo_width() - 16
        figsize = _figsize_for_width(avail_width)

        try:
            util = ParamPlotUtil(path, thresh, figsize=figsize)
            util._plotLog(
                auto_find,
                on_figure=self._on_param_figure,
                on_event_header=self._on_param_event_header,
            )
        except Exception as exc:
            messagebox.showerror("Plotting failed", str(exc))
            self.status.configure(text="Plotting failed.")
            self._update_param_pdf_button()
            return

        if not self.paramFigures:
            self.status.configure(text="No plots produced (no high-throttle events found?).")
        else:
            self.status.configure(text=f"Plotted {len(self.paramFigures)} chart(s).")
        for group in self.paramAxisGroups:
            self._link_x_axes(group)
        self._update_param_pdf_button()

    def _plotCustom(self):
        path = self.logPath.get().strip()
        if not path:
            messagebox.showerror("No log selected", "Choose a log file first.")
            return
        if not self.customFields:
            messagebox.showerror("No fields selected", "Search and add at least one field to plot.")
            return

        fields_scales = []
        for f in self.customFields:
            try:
                scale = float(f["scale_var"].get())
            except ValueError:
                messagebox.showerror("Invalid input", f"Scale for '{f['field']}' must be a number.")
                return
            fields_scales.append((f["field"], scale))

        try:
            thresh = float(self.customThreshVar.get())
        except ValueError:
            messagebox.showerror("Invalid input", "Throttle threshold must be a number.")
            return

        auto_find = self.customAutoFindVar.get()

        self._clear_plots(self.customScrollArea, self.customFigures)
        self.status.configure(text="Plotting...")
        self.update_idletasks()

        avail_width = self.customScrollArea.canvas.winfo_width() - 16
        avail_height = self.customScrollArea.canvas.winfo_height() - TOOLBAR_RESERVE_PX
        figsize = _figsize_for_width(avail_width, avail_height_px=avail_height)

        try:
            util = CustomPlotUtil(path, thresh, figsize=figsize)
            util._plotCustomLog(
                fields_scales, auto_find,
                on_figure=lambda fig: self._embed_figure(fig, self.customScrollArea, self.customFigures),
                on_event_header=lambda n: self._add_event_header(n, self.customScrollArea),
            )
        except Exception as exc:
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

    def _on_param_figure(self, fig):
        self._embed_figure(fig, self.paramScrollArea, self.paramFigures)
        self.paramPlotSequence.append(("figure", fig))
        self.paramAxisGroups[-1].extend(fig.axes)

    def _on_param_event_header(self, evt_counter):
        self._add_event_header(evt_counter, self.paramScrollArea)
        self.paramPlotSequence.append(("event", evt_counter))
        # Each event gets its own fresh group, so panning/zooming one
        # event's charts never drags another event's charts along with it.
        self.paramAxisGroups.append([])

    def _link_x_axes(self, axes):
        """Mirror xlim changes (zoom/pan via the toolbar) across every Axes
        in the group. Each Axes lives in its own separate Figure/canvas (one
        per plotted field group), so this can't be done with matplotlib's
        built-in sharex - it only works for Axes within a single Figure."""
        if len(axes) < 2:
            return
        sync_state = {"syncing": False}

        def on_xlim_changed(changed_ax):
            if sync_state["syncing"]:
                return
            sync_state["syncing"] = True
            try:
                xlim = changed_ax.get_xlim()
                for ax in axes:
                    if ax is not changed_ax and ax.get_xlim() != xlim:
                        ax.set_xlim(xlim)
                        ax.figure.canvas.draw_idle()
            finally:
                sync_state["syncing"] = False

        for ax in axes:
            ax.callbacks.connect("xlim_changed", on_xlim_changed)

    def _update_param_pdf_button(self):
        if self.paramFigures:
            self.paramPdfButton.grid(**self._paramPdfButtonGridKw)
        else:
            self.paramPdfButton.grid_remove()

    def _savePdfParam(self):
        if not self.paramFigures:
            return
        initial_dir = self.app_config.get("last_dir")
        if not initial_dir or not Path(initial_dir).is_dir():
            initial_dir = str(Path.home())
        path = filedialog.asksaveasfilename(
            title="Save plots as PDF",
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
            initialdir=initial_dir,
        )
        if not path:
            return

        try:
            with PdfPages(path) as pdf:
                for kind, payload in self.paramPlotSequence:
                    if kind == "event":
                        header_fig = plt.figure(figsize=self.paramFigures[0].get_size_inches())
                        header_fig.text(
                            0.5, 0.5, f"High Throttle Event {payload}",
                            ha="center", va="center", fontsize=28,
                        )
                        pdf.savefig(header_fig)
                        plt.close(header_fig)
                    else:
                        pdf.savefig(payload)
        except OSError as exc:
            messagebox.showerror("Save failed", str(exc))
            return

        self.status.configure(text=f"Saved PDF to {path}")

    def _add_event_header(self, evt_counter, scroll_area):
        ttk.Separator(scroll_area.content).pack(fill="x", pady=(12, 4))
        ttk.Label(
            scroll_area.content,
            text=f"High Throttle Event {evt_counter}",
            font=self.event_header_font,
            foreground=COLOR_ACCENT_HOVER,
            anchor="center",
            justify="center",
        ).pack(fill="x", padx=8, pady=(0, 4))

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
