"""MATLAB-figure-like chart interaction for every plotted pg.PlotWidget:
box-zoom/pan, Ctrl/Shift+scroll axis-only zoom, single-axis click-drag zoom
on an axis ruler, and pinned/draggable/removable multi-point data cursors
(mplcursors' equivalent - pyqtgraph has no built-in multi-cursor tool)."""
import numpy as np
import pyqtgraph as pg
from pyqtgraph import functions as fn
from pyqtgraph.Point import Point
from PySide6.QtCore import Qt

# Each wheel "click" zooms in/out by this factor on whichever axis/axes are
# selected by the held modifier, centered on the data point under the cursor
# - same behavior/constant as the Tkinter version's ZOOM_SCROLL_FACTOR.
ZOOM_SCROLL_FACTOR = 0.9

# Squared, per-axis-range-normalized distance a click must land within to
# count as "on" a curve (rather than empty plot area) for datatip placement/
# removal - e.g. 0.0016 is 4% of the visible span on each axis.
_CLICK_TOLERANCE_SQUARED = 0.0016
# Screen-pixel radius a right-click must land within an existing pinned
# datatip's marker to remove it.
_REMOVE_TOLERANCE_PX = 20


class InteractiveViewBox(pg.ViewBox):
    """A ViewBox configured for MATLAB-like mouse interaction instead of
    pyqtgraph's defaults: left-drag box-zooms (RectMode), middle-drag pans,
    dragging an axis ruler zooms just that axis, Ctrl/Shift+scroll zooms the
    x/y axis only (centered on the cursor), and a plain scroll is left alone
    so it can bubble up to whatever scrollable area the chart sits in.
    Also owns this chart's pinned data cursors (see mouseClickEvent)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setMouseMode(pg.ViewBox.RectMode)
        # Set by the factory function below once the owning PlotItem exists,
        # so click handling can search every curve plotted on this chart.
        self.plot_item = None
        self._datatips = []

    # ------------------------------------------------------------------
    # Box-zoom / pan / single-axis drag-zoom
    # ------------------------------------------------------------------
    def mouseDragEvent(self, ev, axis=None):
        if axis is not None:
            # Dragging on an axis ruler (not the plot area): pyqtgraph's
            # default translates (pans) just that axis regardless of
            # RectMode, but a MATLAB figure instead *zooms* the axis being
            # dragged - reuse ViewBox's own right-drag scale math (see
            # pyqtgraph.graphicsItems.ViewBox.ViewBox.mouseDragEvent),
            # scoped to the single axis and reachable via a plain drag.
            ev.accept()
            dif = ev.screenPos() - ev.lastScreenPos()
            dif = np.array([dif.x(), dif.y()])
            dif[0] *= -1
            mask = [0, 0]
            mask[axis] = 1
            s = ((np.array(mask) * 0.02) + 1) ** dif
            tr = fn.invertQTransform(self.childGroup.transform())
            center = Point(tr.map(ev.buttonDownPos()))
            x = s[0] if axis == 0 else None
            y = s[1] if axis == 1 else None
            self._resetTarget()
            self.scaleBy(x=x, y=y, center=center)
            self.sigRangeChangedManually.emit(self.state['mouseEnabled'])
            return

        if ev.button() == Qt.MouseButton.MiddleButton:
            # Pan on middle-drag regardless of RectMode - reuses ViewBox's
            # own translate math by temporarily flipping mouseMode for the
            # duration of this single event, rather than re-deriving it.
            prev_mode = self.state['mouseMode']
            self.state['mouseMode'] = pg.ViewBox.PanMode
            try:
                super().mouseDragEvent(ev, axis=axis)
            finally:
                self.state['mouseMode'] = prev_mode
            return

        super().mouseDragEvent(ev, axis=axis)

    # ------------------------------------------------------------------
    # Ctrl/Shift+scroll axis-only zoom
    # ------------------------------------------------------------------
    def wheelEvent(self, ev, axis=None):
        modifiers = ev.modifiers()
        zoom_x = bool(modifiers & Qt.KeyboardModifier.ControlModifier)
        zoom_y = bool(modifiers & Qt.KeyboardModifier.ShiftModifier)
        if not (zoom_x or zoom_y):
            # Leave a plain scroll alone - LogPlotterGUI forwards it to the
            # enclosing scroll area instead (see _plot_wheel_event_filter),
            # matching the Tkinter version's "plain scroll moves through the
            # stacked charts" behavior.
            ev.ignore()
            return

        factor = ZOOM_SCROLL_FACTOR if ev.delta() > 0 else 1.0 / ZOOM_SCROLL_FACTOR
        center = self.mapToView(ev.pos())
        self._resetTarget()
        self.scaleBy(x=factor if zoom_x else None, y=factor if zoom_y else None, center=center)
        ev.accept()
        self.sigRangeChangedManually.emit(self.state['mouseEnabled'])

    # ------------------------------------------------------------------
    # Data cursors: pin on left-click, drag along the curve, remove on
    # right-click (falling back to the default "View All" context menu
    # when the right-click doesn't land on a pinned cursor).
    # ------------------------------------------------------------------
    def mouseClickEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            self._add_datatip_near(ev.scenePos())
            ev.accept()
            return
        if ev.button() == Qt.MouseButton.RightButton:
            if self._remove_datatip_near(ev.scenePos()):
                ev.accept()
                return
        super().mouseClickEvent(ev)

    def _curves(self):
        return self.plot_item.listDataItems() if self.plot_item is not None else []

    def _nearest_point(self, view_pos, curves=None):
        (xmin, xmax), (ymin, ymax) = self.viewRange()
        xspan = (xmax - xmin) or 1.0
        yspan = (ymax - ymin) or 1.0
        best = None
        best_dist = None
        for curve in curves if curves is not None else self._curves():
            xdata, ydata = curve.getData()
            if xdata is None or len(xdata) == 0:
                continue
            dx = (xdata - view_pos.x()) / xspan
            dy = (ydata - view_pos.y()) / yspan
            dist = dx * dx + dy * dy
            idx = int(np.argmin(dist))
            d = float(dist[idx])
            if best_dist is None or d < best_dist:
                best_dist = d
                best = (curve, idx, float(xdata[idx]), float(ydata[idx]))
        return best, best_dist

    def _add_datatip_near(self, scene_pos):
        view_pos = self.mapSceneToView(scene_pos)
        best, dist = self._nearest_point(view_pos)
        if best is None or dist > _CLICK_TOLERANCE_SQUARED:
            return
        curve, idx, x, y = best
        name = curve.name() or ""

        def _label(px, py, name=name):
            return f"{name}\nTime: {px:.3f} s\nValue: {py:.3g}"

        target = pg.TargetItem(pos=(x, y), movable=True, label=_label)
        self.addItem(target, ignoreBounds=True)
        tip = {"curve": curve, "target": target}
        self._datatips.append(tip)
        target.sigPositionChanged.connect(lambda _t, tip=tip: self._snap_datatip(tip))

    def _snap_datatip(self, tip):
        if tip.get("_snapping"):
            return
        tip["_snapping"] = True
        try:
            pos = tip["target"].pos()
            xdata, ydata = tip["curve"].getData()
            if xdata is None or len(xdata) == 0:
                return
            dx = xdata - pos.x()
            dy = ydata - pos.y()
            idx = int(np.argmin(dx * dx + dy * dy))
            tip["target"].setPos(float(xdata[idx]), float(ydata[idx]))
        finally:
            tip["_snapping"] = False

    def _remove_datatip_near(self, scene_pos):
        for tip in list(self._datatips):
            target_scene_pos = self.mapViewToScene(tip["target"].pos())
            if (target_scene_pos - scene_pos).manhattanLength() <= _REMOVE_TOLERANCE_PX:
                self.removeItem(tip["target"])
                self._datatips.remove(tip)
                return True
        return False

    def clear_datatips(self):
        for tip in self._datatips:
            self.removeItem(tip["target"])
        self._datatips = []


def make_interactive_plot_widget():
    """pg.PlotWidget wired up with an InteractiveViewBox, with the back-
    reference the ViewBox needs to search this chart's curves on click."""
    view_box = InteractiveViewBox()
    plot_widget = pg.PlotWidget(viewBox=view_box)
    view_box.plot_item = plot_widget.getPlotItem()
    return plot_widget
