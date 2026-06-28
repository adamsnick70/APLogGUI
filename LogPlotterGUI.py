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

from LogPlotUtil import LogPlotUtil

CONFIG_PATH = Path(__file__).resolve().parent / "config.json"

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


def _figsize_for_width(avail_width_px, dpi=FIGURE_DPI):
    width_in = max(avail_width_px, 1) / dpi
    width_ratio = width_in / BASE_FIGSIZE[0]
    height_ratio = 1 - HEIGHT_FALLOFF * (1 - width_ratio)
    height_in = BASE_FIGSIZE[1] * height_ratio
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

    def __init__(self, parent, bg=COLOR_BG):
        super().__init__(parent)

        self.canvas = tk.Canvas(self, highlightthickness=0, background=bg)
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
        self.threshVar = tk.StringVar(value="7.5")
        self.startPrctVar = tk.StringVar(value="0.10")
        self.endPrctVar = tk.StringVar(value="0.90")
        self.startScaleVar = tk.DoubleVar(value=0.10)
        self.endScaleVar = tk.DoubleVar(value=0.90)

        self.figures = []  # keep references so they aren't garbage collected

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

        self._build_controls()
        self._build_plot_area()
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
    def _build_controls(self):
        bar = ttk.Frame(self, padding=8)
        bar.pack(side="top", fill="x")

        ttk.Label(bar, text="Log file:", style="Header.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Entry(bar, textvariable=self.logPath, width=70).grid(row=0, column=1, columnspan=3, sticky="we", padx=4)
        ttk.Button(bar, text="Browse...", command=self._browse).grid(row=0, column=4, padx=4)

        ttk.Label(bar, text="Auto-Find Throttle Threshold: ", style="Header.TLabel").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(bar, textvariable=self.threshVar, width=6).grid(row=1, column=1, sticky="w", pady=(8, 0))

        ttk.Button(bar, text="Plot", command=self._plot).grid(row=0, column=5, rowspan=2, padx=(16, 0), sticky="ns")

        self.autoFindCheck = ttk.Checkbutton(
            bar, text="Autofind high-throttle events", variable=self.autoFindVar,
            command=self._toggle_autofind
        )
        self.autoFindCheck.grid(row=2, column=0, columnspan=2, sticky="w", pady=(8, 0))

        self.rangeFrame = ttk.Frame(bar)
        ttk.Label(self.rangeFrame, text="Start %:", style="Header.TLabel").grid(row=0, column=0, sticky="w")
        self.startEntry = ttk.Entry(self.rangeFrame, textvariable=self.startPrctVar, width=6)
        self.startEntry.grid(row=0, column=1, padx=4)
        self.startEntry.bind("<Return>", lambda e: self._sync_entry_to_scale("start"))
        self.startEntry.bind("<FocusOut>", lambda e: self._sync_entry_to_scale("start"))
        self.startScale = ttk.Scale(
            self.rangeFrame, from_=0.0, to=1.0, orient="horizontal", length=400,
            variable=self.startScaleVar, command=self._on_start_scale,
        )
        self.startScale.grid(row=0, column=2, sticky="we", padx=4)

        ttk.Label(self.rangeFrame, text="End %:", style="Header.TLabel").grid(row=1, column=0, sticky="w", pady=(4, 0))
        self.endEntry = ttk.Entry(self.rangeFrame, textvariable=self.endPrctVar, width=6)
        self.endEntry.grid(row=1, column=1, padx=4, pady=(4, 0))
        self.endEntry.bind("<Return>", lambda e: self._sync_entry_to_scale("end"))
        self.endEntry.bind("<FocusOut>", lambda e: self._sync_entry_to_scale("end"))
        self.endScale = ttk.Scale(
            self.rangeFrame, from_=0.0, to=1.0, orient="horizontal", length=400,
            variable=self.endScaleVar, command=self._on_end_scale,
        )
        self.endScale.grid(row=1, column=2, sticky="we", padx=4, pady=(4, 0))

        self.rangeFrame.grid_columnconfigure(2, weight=1)

        bar.grid_columnconfigure(1, weight=1)

        self.status = ttk.Label(self, text="Select a log file to begin.", padding=(8, 0))
        self.status.pack(side="top", fill="x")

        self._toggle_autofind()

    def _build_plot_area(self):
        self.scroll_area = ScrollableFrame(self)
        self.scroll_area.pack(side="top", fill="both", expand=True)

    def _toggle_autofind(self):
        if self.autoFindVar.get():
            self.rangeFrame.grid_remove()
        else:
            self.rangeFrame.grid(row=3, column=0, columnspan=6, sticky="we", pady=(8, 0))

    @staticmethod
    def _clamp01(value):
        return max(0.0, min(1.0, value))

    def _on_start_scale(self, value):
        v = self._clamp01(float(value))
        if v > self.endScaleVar.get():
            self.endScaleVar.set(v)
            self.endPrctVar.set(f"{v:.2f}")
        self.startPrctVar.set(f"{v:.2f}")

    def _on_end_scale(self, value):
        v = self._clamp01(float(value))
        if v < self.startScaleVar.get():
            self.startScaleVar.set(v)
            self.startPrctVar.set(f"{v:.2f}")
        self.endPrctVar.set(f"{v:.2f}")

    def _sync_entry_to_scale(self, which):
        var = self.startPrctVar if which == "start" else self.endPrctVar
        scale_var = self.startScaleVar if which == "start" else self.endScaleVar
        try:
            v = self._clamp01(float(var.get()))
        except ValueError:
            v = scale_var.get()
        var.set(f"{v:.2f}")
        scale_var.set(v)

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

    # ------------------------------------------------------------------
    # Plotting
    # ------------------------------------------------------------------
    def _plot(self):
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
        start_prct = end_prct = 0.0
        if not auto_find:
            try:
                start_prct = float(self.startPrctVar.get())
                end_prct = float(self.endPrctVar.get())
            except ValueError:
                messagebox.showerror("Invalid input", "Start/End % must be numbers.")
                return

        self._clear_plots()
        self.status.configure(text="Plotting...")
        self.update_idletasks()

        # holder.pack(..., padx=8) below eats 8px on each side of the canvas
        # viewport's width.
        avail_width = self.scroll_area.canvas.winfo_width() - 16
        figsize = _figsize_for_width(avail_width)

        try:
            util = LogPlotUtil(path, thresh, figsize=figsize)
            util.plotLog(
                start_prct, end_prct, auto_find,
                on_figure=self._embed_figure,
                on_event_header=self._add_event_header,
            )
        except Exception as exc:
            messagebox.showerror("Plotting failed", str(exc))
            self.status.configure(text="Plotting failed.")
            return

        if not self.figures:
            self.status.configure(text="No plots produced (no high-throttle events found?).")
        else:
            self.status.configure(text=f"Plotted {len(self.figures)} chart(s).")

    def _clear_plots(self):
        for fig in self.figures:
            plt.close(fig)
        self.figures.clear()
        self.scroll_area.clear()

    def _add_event_header(self, evt_counter):
        ttk.Separator(self.scroll_area.content).pack(fill="x", pady=(12, 4))
        ttk.Label(
            self.scroll_area.content,
            text=f"High Throttle Event {evt_counter}",
            font=("Segoe UI", 12, "bold"),
            foreground=COLOR_ACCENT_HOVER,
        ).pack(anchor="w", padx=8, pady=(0, 4))

    def _embed_figure(self, fig):
        self.figures.append(fig)
        holder = ttk.Frame(self.scroll_area.content)
        holder.pack(fill="x", padx=8, pady=4)

        canvas = FigureCanvasTkAgg(fig, master=holder)
        canvas.draw()
        # No fill: the figure was already sized to the plot area's width in
        # _plot(), and matplotlib's TkAgg backend auto-rescales (and distorts
        # the carefully computed width/height ratio) whenever its widget is
        # resized, which fill="x" would trigger on every window resize.
        canvas.get_tk_widget().pack()

        toolbar = NavigationToolbar2Tk(canvas, holder, pack_toolbar=False)
        toolbar.update()
        toolbar.pack(anchor="w", fill="x")
        _recolor_classic_widget(toolbar)


if __name__ == "__main__":
    app = LogPlotterGUI()
    app.mainloop()
