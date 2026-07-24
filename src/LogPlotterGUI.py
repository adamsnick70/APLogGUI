import json
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent
REPO_ROOT = SRC_DIR.parent

from AppPaths import resource_root, user_data_dir  # noqa: E402

# The compiled ui_*.py modules are generated (gitignored, not committed - see
# tools/build_ui.py) - regenerate anything missing/stale before importing
# them, so a fresh checkout or an edited .ui file never needs a manual build
# step. A frozen PyInstaller build ships ui_main_window.py already compiled
# into the bundle (a normal import, no .ui/pyside6-uic involved), so this
# whole dev-only compile step is skipped there.
if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(REPO_ROOT / "tools"))
    try:
        from build_ui import build_all
        build_all()
    except Exception as exc:
        if not (SRC_DIR / "ui_main_window.py").exists():
            raise RuntimeError(
                "src/ui_main_window.py is missing and could not be generated "
                "from ui/main_window.ui - run `python tools/build_ui.py` "
                "manually and check the error above."
            ) from exc

import pyqtgraph as pg
from PySide6.QtCore import QByteArray, QEvent, QObject, QThread, QTimer, Qt, Signal
from PySide6.QtGui import QFontMetrics, QPalette, QColor
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QFrame, QMainWindow, QMessageBox, QWidget,
    QHBoxLayout, QVBoxLayout, QLabel, QLineEdit, QPushButton,
)

from UserParams import UserParams, DEFAULT_VERSION
from version import APP_VERSION
from LogPlotUtil import LogPlotUtil
from ParamPlots import ParamPlotUtil
from CustomPlots import CustomPlotUtil
from PdfExport import save_plots_pdf
from LegendPlacement import position_legend_to_avoid_overlap
from ui_main_window import Ui_MainWindow

# Running from source, config.json lives at the repo root (one level up from
# src/). Frozen, it lives under %APPDATA% instead - see AppPaths.py.
CONFIG_PATH = user_data_dir() / "config.json"

# VS Code "Dark+" inspired palette, matching ui/style.qss's. Applied
# globally so every pg.PlotWidget picks it up automatically.
COLOR_BG = "#1e1e1e"
COLOR_FG = "#cccccc"
pg.setConfigOption("background", COLOR_BG)
pg.setConfigOption("foreground", COLOR_FG)
pg.setConfigOptions(antialias=True)


def _apply_dark_theme(app):
    """Fusion style + a dark QPalette (so any unstyled/native-ish widget
    still reads as dark) plus ui/style.qss for the actual "modern webapp"
    look - rounded corners, hover/pressed/focus states, card-like panels,
    a QSS-styled QCheckBox indicator instead of the old Pillow-drawn PNGs.
    Dark-only, no light theme/toggle (confirmed scope)."""
    app.setStyle("Fusion")

    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(COLOR_BG))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(COLOR_FG))
    palette.setColor(QPalette.ColorRole.Base, QColor("#3c3c3c"))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(COLOR_BG))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#252526"))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(COLOR_FG))
    palette.setColor(QPalette.ColorRole.Text, QColor(COLOR_FG))
    palette.setColor(QPalette.ColorRole.Button, QColor("#3c3c3c"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(COLOR_FG))
    palette.setColor(QPalette.ColorRole.BrightText, QColor("#ff5555"))
    palette.setColor(QPalette.ColorRole.Link, QColor("#1177bb"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#0e639c"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor("#9d9d9d"))
    app.setPalette(palette)

    # Native dark titlebar/chrome on platforms that support it (Windows 10
    # 1809+/11 via Qt's own color-scheme hint) - tried first, before ever
    # reintroducing the old ctypes DWM hack the Tkinter version needed (see
    # 2)/7) in ToDo.txt: "revisit whether Qt6's Fusion style + dark QPalette
    # is enough on Windows 11 before reintroducing any ctypes hack").
    style_hints = app.styleHints()
    if hasattr(style_hints, "setColorScheme"):
        style_hints.setColorScheme(Qt.ColorScheme.Dark)

    qss_path = resource_root() / "ui" / "style.qss"
    checkmark_path = resource_root() / "ui" / "checkmark.svg"
    stylesheet = qss_path.read_text(encoding="utf-8")
    stylesheet = stylesheet.replace("{CHECKMARK_URL}", checkmark_path.as_posix())
    app.setStyleSheet(stylesheet)

# The tabgroup (Parameterized Plots / Custom Plot) occupies the right 80% of
# the window; the field list sidebar occupies the left 20%, expressed as a
# 1:4 ratio so the split holds proportionally regardless of window size, but
# capped to SIDEBAR_MAX_WIDTH_REFERENCE_TEXT's rendered width so the sidebar
# doesn't keep growing into acres of empty space on wide monitors.
SIDEBAR_WEIGHT = 1
TABS_WEIGHT = 4
SIDEBAR_MAX_WIDTH_REFERENCE_TEXT = "AP Info:[AP3-xxx-00x vx.x.x.x-xxxxx]"

# Plots were originally designed at a fixed 2000x800px (20x8in @ 100dpi, the
# old Tkinter/matplotlib version's BASE_FIGSIZE) - that's the reference size
# plots are scaled from to fill the plot area's current width; height is
# scaled at HEIGHT_FALLOFF of the width's rate of change so narrow windows
# don't squash plots into an unreadable sliver, and wide/high-res monitors
# don't stretch them absurdly tall (ported from nickDev's _figsize_for_width).
BASE_PLOT_WIDTH_PX = 2000
BASE_PLOT_HEIGHT_PX = 800
HEIGHT_FALLOFF = 0.75


def _plot_height_for_width(avail_width_px, avail_height_px=None):
    width_ratio = max(avail_width_px, 1) / BASE_PLOT_WIDTH_PX
    height_ratio = 1 - HEIGHT_FALLOFF * (1 - width_ratio)
    height_px = BASE_PLOT_HEIGHT_PX * height_ratio
    if avail_height_px is not None:
        # The Custom Plot tab shows one chart at a time and the whole point
        # is that it shouldn't need its own scrollbar to see all of it, so
        # cap the height to whatever room is actually available instead of
        # only ever deriving it from width.
        height_px = min(height_px, max(avail_height_px, 1))
    return max(int(height_px), 1)


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


class _UpdateCheckWorker(QObject):
    """Runs AutoUpdate.check_for_update()'s network call off the GUI
    thread, so a slow/hanging GitHub API response never freezes the
    window. finished carries its result (None, or a (version, installer,
    checksum) tuple - see AutoUpdate.py) back to the main thread; Qt
    marshals a cross-thread signal emission onto the receiver's own
    thread automatically, so no extra locking is needed here."""
    finished = Signal(object)

    def run(self):
        import AutoUpdate
        try:
            result = AutoUpdate.check_for_update()
        except Exception:
            result = None
        self.finished.emit(result)


class MainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self):
        super().__init__()
        self.setupUi(self)

        self.app_config = _load_config()
        if "ap_version" not in self.app_config:
            # The default AP version lives in config.json, not in code - seed
            # it on first run (or for an existing config.json predating this
            # setting) so it's genuinely stored there rather than only ever
            # existing as DEFAULT_VERSION's in-memory fallback. From here on,
            # only "Mark Version as Default" changes it.
            self.app_config["ap_version"] = DEFAULT_VERSION
            _save_config(self.app_config)

        self.statusLabel = QLabel("Select a log file to begin.")
        self.statusbar.addWidget(self.statusLabel)

        self.userParams = UserParams()
        self.allFields = []
        self.customFields = []  # [{"field", "scale_edit", "row"}]
        self._fields_loaded_path = None
        self._userParamsBaseline = ""
        self._sidebar_sized = False

        # Each tab keeps its own plot-widget list so switching tabs doesn't
        # discard the other tab's plots.
        self.paramFigures = []
        self.customFigures = []
        # Mirrors paramFigures/customFigures but interleaved with
        # ("event", n) markers in display order, so PDF export can
        # reproduce the same High Throttle Event separators shown on screen.
        self.paramPlotSequence = []
        self.customPlotSequence = []
        # One group per High Throttle Event when autofind is on, or a single
        # group for the whole tab when it's off, so zoom/pan on one plot can
        # be mirrored across the rest of its group (see _link_x_axes).
        # Custom Plot has no equivalent - it never had more than one linked
        # chart to begin with.
        self.paramAxisGroups = []
        # Maps an embedded plot widget to the QScrollArea it lives in, so an
        # unmodified wheel scroll over it can be redirected there instead of
        # zooming (see eventFilter).
        self._plot_scroll_map = {}
        # Recomputed whenever the plot area's size changes - on the initial
        # plot pass (see _plot_parameterized/_plot_custom) and again on every
        # live resize of the scroll area's viewport (see eventFilter) so a
        # window snapped to a different size re-scales plots already on
        # screen instead of leaving them at whatever size they were plotted
        # at - see _plot_height_for_width.
        self._paramPlotHeight = BASE_PLOT_HEIGHT_PX
        self._customPlotHeight = BASE_PLOT_HEIGHT_PX

        self._restore_geometry()
        self.apVersionCombo.installEventFilter(self)
        self.paramPlotScrollArea.viewport().installEventFilter(self)
        self.customPlotScrollArea.viewport().installEventFilter(self)

        self.browseButton.clicked.connect(self._browse)
        self.logPathEdit.editingFinished.connect(self._on_log_path_committed)
        self.apVersionCombo.textActivated.connect(self._select_ap_version)
        self.customSearchEdit.textChanged.connect(self._filter_custom_listbox)
        self.customFieldListWidget.itemDoubleClicked.connect(lambda _item: self._add_selected_custom_fields())
        self.customAddSelectedButton.clicked.connect(self._add_selected_custom_fields)
        self.savePrefsButton.clicked.connect(self._save_preferences)
        self.markDefaultButton.clicked.connect(self._mark_version_default)
        self.userParamsTextEdit.textChanged.connect(self._update_save_prefs_button)
        self.paramPlotButton.clicked.connect(self._plot_parameterized)
        self.customPlotButton.clicked.connect(self._plot_custom)
        self.paramPdfButton.clicked.connect(self._save_pdf_param)
        self.customPdfButton.clicked.connect(self._save_pdf_custom)

        self._populate_field_panel([])
        self._select_ap_version(self.app_config.get("ap_version", DEFAULT_VERSION))

        # Without this, initial keyboard focus can land on some other
        # focusable control built along the way. The log path is the natural
        # first thing to type into, so it gets focus explicitly instead.
        self.logPathEdit.setFocus()

        # Only a frozen (installed) build has an installer to update itself
        # into - a from-source run has nothing for AutoUpdate to replace,
        # and APP_VERSION stays "dev" there anyway (see version.py), which
        # AutoUpdate.is_newer() never treats as older than a real release.
        if getattr(sys, "frozen", False):
            self._start_update_check()

    def _start_update_check(self):
        self._updateThread = QThread(self)
        self._updateWorker = _UpdateCheckWorker()
        self._updateWorker.moveToThread(self._updateThread)
        self._updateThread.started.connect(self._updateWorker.run)
        self._updateWorker.finished.connect(self._on_update_check_finished)
        self._updateWorker.finished.connect(self._updateThread.quit)
        self._updateThread.start()

    def _on_update_check_finished(self, result):
        if result is None:
            return
        remote_version, installer_asset, checksum_asset = result
        reply = QMessageBox.question(
            self, "Update available",
            f"AP Log Plotter {remote_version} is available (you have "
            f"{APP_VERSION}). Download and install it now?\n\n"
            "The app will close so the installer can run.",
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        import AutoUpdate
        try:
            installer_path = AutoUpdate.download_and_verify(installer_asset, checksum_asset)
        except Exception as exc:
            QMessageBox.critical(self, "Update failed", str(exc))
            return
        AutoUpdate.launch_installer_and_exit(installer_path)

    # ------------------------------------------------------------------
    # Window geometry (config.json)
    # ------------------------------------------------------------------
    def _restore_geometry(self):
        raw = self.app_config.get("window_state")
        restored = False
        if raw:
            # The old Tk-style plain geometry string ("2100x1300+208+101",
            # possibly with a separate window_zoomed bool) is not valid
            # input to restoreGeometry() - it lives under a different config
            # key ("window_geometry") than the one used here, so it's simply
            # never looked at rather than needing an explicit format check.
            try:
                restored = self.restoreGeometry(QByteArray.fromBase64(raw.encode("ascii")))
            except Exception:
                restored = False
        if not restored:
            screen = QApplication.primaryScreen()
            target_w, target_h = 2100, 1300
            if screen is not None:
                avail = screen.availableGeometry()
                target_w = min(target_w, avail.width() - 60)
                target_h = min(target_h, avail.height() - 100)
            self.resize(target_w, target_h)

    def closeEvent(self, event):
        self.app_config["window_state"] = bytes(self.saveGeometry().toBase64()).decode("ascii")
        _save_config(self.app_config)
        super().closeEvent(event)

    def showEvent(self, event):
        super().showEvent(event)
        if not self._sidebar_sized:
            self._sidebar_sized = True
            self._apply_initial_sidebar_width()

    def _apply_initial_sidebar_width(self):
        total = self.bodySplitter.width()
        if total <= 0:
            return
        metrics = QFontMetrics(self.fieldPanel.font())
        max_width = metrics.horizontalAdvance(SIDEBAR_MAX_WIDTH_REFERENCE_TEXT) + 40
        target = int(total * SIDEBAR_WEIGHT / (SIDEBAR_WEIGHT + TABS_WEIGHT))
        width = min(target, max_width)
        self.bodySplitter.setSizes([width, max(total - width, 0)])

    # ------------------------------------------------------------------
    # AP Version / User Parameters
    # ------------------------------------------------------------------
    def eventFilter(self, obj, event):
        # Refreshed right before the dropdown opens (rather than once at
        # startup) so a version file added or removed later shows up
        # without restarting the app.
        if obj is self.apVersionCombo and event.type() == QEvent.Type.MouseButtonPress:
            self._refresh_ap_version_choices()
            return super().eventFilter(obj, event)

        if event.type() == QEvent.Type.Wheel and obj in self._plot_scroll_map:
            # A plain scroll over a chart moves through the stacked charts
            # instead of zooming (matching the Tkinter version) - Ctrl/Shift
            # zoom is handled by InteractiveViewBox itself, so only a plain
            # scroll is intercepted and redirected here.
            modifiers = event.modifiers()
            if not (modifiers & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)):
                scrollbar = self._plot_scroll_map[obj].verticalScrollBar()
                scrollbar.setValue(scrollbar.value() - event.angleDelta().y())
                return True

        if event.type() == QEvent.Type.Resize:
            # A plain resize of the scroll area's viewport (window snapped/
            # resized, splitter dragged, etc.) re-scales whatever plots are
            # already on screen, not just the next ones plotted - otherwise
            # plots stay stuck at whatever size they were plotted at.
            # Reshaping a plot also changes which corner (if any) the
            # legend can sit in without covering data, so it's
            # re-optimized alongside the height (see LegendPlacement).
            if obj is self.paramPlotScrollArea.viewport():
                self._update_param_plot_heights()
                self._reposition_param_legends()
            elif obj is self.customPlotScrollArea.viewport():
                self._update_custom_plot_heights()
                self._reposition_custom_legends()

        return super().eventFilter(obj, event)

    def _refresh_ap_version_choices(self):
        current = self.apVersionCombo.currentText()
        versions = self.userParams.available_versions()
        self.apVersionCombo.blockSignals(True)
        self.apVersionCombo.clear()
        self.apVersionCombo.addItems(versions)
        if current in versions:
            self.apVersionCombo.setCurrentText(current)
        self.apVersionCombo.blockSignals(False)

    def _select_ap_version(self, version):
        try:
            self.userParams.read_params(version)
        except (OSError, SyntaxError, ValueError, TypeError) as exc:
            QMessageBox.critical(self, "Could not load parameters", f"'{version}': {exc}")
            return
        self._refresh_ap_version_choices()
        self.apVersionCombo.blockSignals(True)
        if self.apVersionCombo.findText(version) < 0:
            self.apVersionCombo.addItem(version)
        self.apVersionCombo.setCurrentText(version)
        self.apVersionCombo.blockSignals(False)
        self._update_autofind_availability()
        self._load_user_params_editor()
        self._update_mark_default_button()

    def _load_user_params_editor(self):
        self._userParamsBaseline = self.userParams.read_raw()
        self.userParamsTextEdit.setPlainText(self._userParamsBaseline)
        self.userParamsVersionLabel.setText(self.userParams.version)
        self._update_save_prefs_button()

    def _update_save_prefs_button(self):
        current = self.userParamsTextEdit.toPlainText()
        self.savePrefsButton.setVisible(current != self._userParamsBaseline)

    def _update_mark_default_button(self):
        is_default = self.userParams.version == self.app_config.get("ap_version", DEFAULT_VERSION)
        self.markDefaultButton.setVisible(not is_default)

    def _save_preferences(self):
        text = self.userParamsTextEdit.toPlainText()
        try:
            self.userParams.write_raw(text)
        except (SyntaxError, ValueError, TypeError) as exc:
            QMessageBox.critical(self, "Invalid parameters", str(exc))
            return
        self._userParamsBaseline = text
        self._update_save_prefs_button()
        self._update_autofind_availability()
        self.statusLabel.setText(f"Saved preferences for {self.userParams.version}.")

    def _mark_version_default(self):
        self.app_config["ap_version"] = self.userParams.version
        _save_config(self.app_config)
        self._update_mark_default_button()
        self.statusLabel.setText(f"{self.userParams.version} is now the default AccessPort version.")

    # ------------------------------------------------------------------
    # Log file selection
    # ------------------------------------------------------------------
    def _browse(self):
        initial_dir = self.app_config.get("last_dir")
        if not initial_dir or not Path(initial_dir).is_dir():
            initial_dir = str(Path.home())
        path, _filter = QFileDialog.getOpenFileName(
            self, "Select AP log", initial_dir, "CSV log files (*.csv);;All files (*.*)"
        )
        if path:
            self.logPathEdit.setText(path)
            self.app_config["last_dir"] = str(Path(path).parent)
            _save_config(self.app_config)
            try:
                self._refresh_fields(path)
            except Exception as exc:
                self.statusLabel.setText(f"Could not read fields: {exc}")

    def _on_log_path_committed(self):
        path = self.logPathEdit.text().strip()
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
        # Throttle-event autofind needs self.userParams.throttleField;
        # without it there's nothing to detect events from, in either tab.
        # Before any log is loaded there's nothing to check yet - both boxes
        # stay at their checked-by-default state instead of being disabled,
        # since this also runs at startup (via _select_ap_version) before
        # the user has picked a log.
        if not self.allFields:
            return
        throttle_present = self.userParams.throttleField in self.allFields
        self.paramAutoFindCheck.setEnabled(throttle_present)
        self.customAutoFindCheck.setEnabled(throttle_present)
        if not throttle_present:
            self.paramAutoFindCheck.setChecked(False)
            self.customAutoFindCheck.setChecked(False)

    def _populate_field_panel(self, fields):
        self.fieldPanel.setPlainText("\n".join(fields) if fields else "No log file selected.")

    def _filter_custom_listbox(self):
        # Time is always the plot's x-axis, never a selectable y-series.
        query = self.customSearchEdit.text().strip().lower()
        self.customFieldListWidget.clear()
        for field in self.allFields:
            lowered = field.lower()
            if "time" in lowered:
                continue
            if query in lowered:
                self.customFieldListWidget.addItem(field)

    def _add_selected_custom_fields(self):
        selected_items = self.customFieldListWidget.selectedItems()
        if not selected_items:
            return
        existing = {f["field"] for f in self.customFields}
        for item in selected_items:
            field = item.text()
            if field in existing:
                continue
            self._add_custom_field_row(field)
            existing.add(field)

    def _add_custom_field_row(self, field):
        row = QWidget(self.customSelectedContainer)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(QLabel(field), stretch=1)
        layout.addWidget(QLabel("Scale:"))
        scale_edit = QLineEdit("1")
        scale_edit.setMaximumWidth(60)
        layout.addWidget(scale_edit)
        entry = {"field": field, "scale_edit": scale_edit, "row": row}
        remove_button = QPushButton("Remove")
        remove_button.clicked.connect(lambda: self._remove_custom_field(entry))
        layout.addWidget(remove_button)
        # Inserted just before the trailing stretch spacer that keeps rows
        # top-aligned in the container (see ui/main_window.ui).
        self.customSelectedContainerLayout.insertWidget(self.customSelectedContainerLayout.count() - 1, row)
        self.customFields.append(entry)

    def _remove_custom_field(self, entry):
        self.customFields = [f for f in self.customFields if f is not entry]
        entry["row"].deleteLater()

    def _reset_custom_fields(self):
        for f in self.customFields:
            f["row"].deleteLater()
        self.customFields = []

    # ------------------------------------------------------------------
    # Plotting
    # ------------------------------------------------------------------
    def _plot_parameterized(self):
        path = self.logPathEdit.text().strip()
        if not path:
            QMessageBox.critical(self, "No log selected", "Choose a log file first.")
            return
        try:
            thresh = float(self.paramAutoFindThreshEdit.text())
        except ValueError:
            QMessageBox.critical(self, "Invalid input", "Throttle threshold must be a number.")
            return

        auto_find = self.paramAutoFindCheck.isChecked()

        self._clear_plot_layout(self.paramPlotScrollLayout, self.paramFigures)
        self.paramPlotSequence = []
        # A fresh single group to start - if autofind fires, the first
        # on_event_header call replaces it with its own group; if it
        # doesn't (manual full-range plot), every chart lands in this one
        # group so the whole tab's x-axes end up linked together.
        self.paramAxisGroups = [[]]
        self.statusLabel.setText("Plotting...")

        self._update_param_plot_heights()

        try:
            util = ParamPlotUtil(path, thresh, userParams=self.userParams)
            util._plotLog(
                auto_find,
                on_figure=self._on_param_figure,
                on_event_header=self._on_param_event_header,
            )
        except Exception as exc:
            QMessageBox.critical(self, "Plotting failed", str(exc))
            self.statusLabel.setText("Plotting failed.")
            self._update_param_pdf_button()
            return

        if not self.paramFigures:
            self.statusLabel.setText("No plots produced (no high-throttle events found?).")
        else:
            self.statusLabel.setText(f"Plotted {len(self.paramFigures)} chart(s).")
        for group in self.paramAxisGroups:
            self._link_x_axes(group)
        self._update_param_pdf_button()
        # Deferred rather than called directly: a just-inserted plot widget
        # doesn't have its real on-screen size yet (that's only assigned once
        # Qt processes the pending layout pass), and legend placement needs
        # that real size - see LegendPlacement.
        QTimer.singleShot(0, self._reposition_param_legends)

    def _plot_custom(self):
        path = self.logPathEdit.text().strip()
        if not path:
            QMessageBox.critical(self, "No log selected", "Choose a log file first.")
            return
        if not self.customFields:
            QMessageBox.critical(self, "No fields selected", "Search and add at least one field to plot.")
            return

        fields_scales = []
        for entry in self.customFields:
            try:
                scale = float(entry["scale_edit"].text())
            except ValueError:
                QMessageBox.critical(self, "Invalid input", f"Scale for '{entry['field']}' must be a number.")
                return
            fields_scales.append((entry["field"], scale))

        try:
            thresh = float(self.customThreshEdit.text())
        except ValueError:
            QMessageBox.critical(self, "Invalid input", "Throttle threshold must be a number.")
            return

        auto_find = self.customAutoFindCheck.isChecked()

        self._clear_plot_layout(self.customPlotScrollLayout, self.customFigures)
        self.customPlotSequence = []
        self.statusLabel.setText("Plotting...")

        self._update_custom_plot_heights()

        try:
            util = CustomPlotUtil(path, thresh, userParams=self.userParams)
            util._plotCustomLog(
                fields_scales, auto_find,
                on_figure=self._on_custom_figure,
                on_event_header=self._on_custom_event_header,
            )
        except Exception as exc:
            QMessageBox.critical(self, "Plotting failed", str(exc))
            self.statusLabel.setText("Plotting failed.")
            self._update_custom_pdf_button()
            return

        if not self.customFigures:
            self.statusLabel.setText("No plot produced (check selected fields).")
        else:
            self.statusLabel.setText(f"Plotted {len(self.customFigures)} chart(s).")
        self._update_custom_pdf_button()
        # See the matching comment in _plot_parameterized.
        QTimer.singleShot(0, self._reposition_custom_legends)

    def _clear_plot_layout(self, layout, figures):
        # Every scroll area's layout ends in a trailing stretch spacer (see
        # ui/main_window.ui) that keeps charts top-aligned when there are
        # few of them - everything before it is a previous plot/header to
        # tear down.
        while layout.count() > 1:
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                # Only plot widgets (QAbstractScrollArea) were registered by
                # their viewport() - see _on_param_figure/_on_custom_figure.
                # Event header widgets have no viewport() and were never
                # registered at all.
                if hasattr(widget, "viewport"):
                    self._plot_scroll_map.pop(widget.viewport(), None)
                widget.deleteLater()
        figures.clear()

    def _insert_before_spacer(self, layout, widget):
        layout.insertWidget(layout.count() - 1, widget)

    def _avail_plot_width(self, scroll_area, layout):
        margins = layout.contentsMargins()
        return scroll_area.viewport().width() - margins.left() - margins.right()

    def _update_param_plot_heights(self):
        avail_width = self._avail_plot_width(self.paramPlotScrollArea, self.paramPlotScrollLayout)
        self._paramPlotHeight = _plot_height_for_width(avail_width)
        for widget in self.paramFigures:
            widget.setMinimumHeight(self._paramPlotHeight)

    def _update_custom_plot_heights(self):
        avail_width = self._avail_plot_width(self.customPlotScrollArea, self.customPlotScrollLayout)
        avail_height = self.customPlotScrollArea.viewport().height()
        self._customPlotHeight = _plot_height_for_width(avail_width, avail_height_px=avail_height)
        for widget in self.customFigures:
            widget.setMinimumHeight(self._customPlotHeight)

    def _reposition_param_legends(self):
        for widget in self.paramFigures:
            self._reposition_legend(widget)

    def _reposition_custom_legends(self):
        for widget in self.customFigures:
            self._reposition_legend(widget)

    def _reposition_legend(self, plot_widget):
        # _legend_series is stashed by ParamPlotUtil/CustomPlotUtil - the
        # (x, y) arrays actually plotted, needed to know what the legend
        # would be covering (see LegendPlacement).
        series = getattr(plot_widget, "_legend_series", None)
        if not series:
            return
        plot_item = plot_widget.getPlotItem()
        if plot_item.legend is None:
            return
        position_legend_to_avoid_overlap(plot_item.getViewBox(), plot_item.legend, series)

    def _add_event_header(self, layout, evt_counter):
        header = QWidget()
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(0, 12, 0, 4)
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        header_layout.addWidget(line)
        label = QLabel(f"High Throttle Event {evt_counter}")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = label.font()
        font.setPointSize(font.pointSize() + 6)
        font.setBold(True)
        header_layout.addWidget(label)
        self._insert_before_spacer(layout, header)

    def _on_param_figure(self, plot_widget):
        plot_widget.setMinimumHeight(self._paramPlotHeight)
        self._insert_before_spacer(self.paramPlotScrollLayout, plot_widget)
        self.paramFigures.append(plot_widget)
        self.paramPlotSequence.append(("figure", plot_widget))
        self.paramAxisGroups[-1].append(plot_widget)
        # plot_widget is a QAbstractScrollArea (QGraphicsView) - real mouse/
        # wheel events are delivered to its viewport() child widget, not to
        # plot_widget itself, so the filter has to be installed there or it
        # silently never fires (see eventFilter).
        viewport = plot_widget.viewport()
        self._plot_scroll_map[viewport] = self.paramPlotScrollArea
        viewport.installEventFilter(self)

    def _on_param_event_header(self, evt_counter):
        self._add_event_header(self.paramPlotScrollLayout, evt_counter)
        self.paramPlotSequence.append(("event", evt_counter))
        # Each event gets its own fresh group, so panning/zooming one
        # event's charts never drags another event's charts along with it.
        self.paramAxisGroups.append([])

    def _on_custom_figure(self, plot_widget):
        plot_widget.setMinimumHeight(self._customPlotHeight)
        self._insert_before_spacer(self.customPlotScrollLayout, plot_widget)
        self.customFigures.append(plot_widget)
        self.customPlotSequence.append(("figure", plot_widget))
        # See the matching comment in _on_param_figure.
        viewport = plot_widget.viewport()
        self._plot_scroll_map[viewport] = self.customPlotScrollArea
        viewport.installEventFilter(self)

    def _on_custom_event_header(self, evt_counter):
        self._add_event_header(self.customPlotScrollLayout, evt_counter)
        self.customPlotSequence.append(("event", evt_counter))

    def _link_x_axes(self, group):
        # Every plot in a group lives in its own separate pg.PlotWidget (one
        # per plotted field group), so pyqtgraph's own setXLink is used to
        # mirror pan/zoom across them instead of matplotlib's Figure-scoped
        # sharex.
        if len(group) < 2:
            return
        anchor = group[0]
        for widget in group[1:]:
            widget.setXLink(anchor)

    def _update_param_pdf_button(self):
        self.paramPdfButton.setVisible(bool(self.paramFigures))

    def _update_custom_pdf_button(self):
        self.customPdfButton.setVisible(bool(self.customFigures))

    def _save_pdf_param(self):
        self._save_plots_pdf(self.paramPlotSequence)

    def _save_pdf_custom(self):
        self._save_plots_pdf(self.customPlotSequence)

    def _save_plots_pdf(self, plot_sequence):
        if not plot_sequence:
            return
        initial_dir = self.app_config.get("last_dir")
        if not initial_dir or not Path(initial_dir).is_dir():
            initial_dir = str(Path.home())
        path, _filter = QFileDialog.getSaveFileName(
            self, "Save plots as PDF", str(Path(initial_dir) / "plots.pdf"),
            "PDF files (*.pdf);;All files (*.*)",
        )
        if not path:
            return
        if not path.lower().endswith(".pdf"):
            path += ".pdf"

        try:
            save_plots_pdf(path, plot_sequence)
        except OSError as exc:
            QMessageBox.critical(self, "Save failed", str(exc))
            return

        self.statusLabel.setText(f"Saved PDF to {path}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    _apply_dark_theme(app)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
