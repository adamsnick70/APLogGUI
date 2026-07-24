"""Moves a plot's legend to whichever candidate corner overlaps the fewest
plotted points, instead of pyqtgraph's fixed top-left default - mirrors
matplotlib's loc='best'."""
import numpy as np

# Candidate positions for the legend's top-left corner, as (x_fraction,
# y_fraction) of the space left over once the legend's own size and the
# margin are subtracted from the plot area - four corners, four edge
# midpoints, then dead center, tried in that order (corners are preferred
# as a tiebreaker since that's the most familiar/expected legend spot).
_CANDIDATE_FRACTIONS = [
    (1, 0), (0, 0), (1, 1), (0, 1),
    (0.5, 0), (0.5, 1), (0, 0.5), (1, 0.5),
    (0.5, 0.5),
]

# Breathing room (px) between the legend box and the plot area's edge.
_MARGIN_PX = 8


def position_legend_to_avoid_overlap(view_box, legend, series):
    """series: an iterable of (x_array, y_array) pairs already plotted on
    view_box's PlotItem. Anchors legend at whichever candidate corner's
    legend-sized box contains the fewest of those points."""
    rect = view_box.boundingRect()
    legend_w, legend_h = legend.width(), legend.height()
    avail_w = rect.width() - legend_w - 2 * _MARGIN_PX
    avail_h = rect.height() - legend_h - 2 * _MARGIN_PX
    if avail_w <= 0 or avail_h <= 0:
        return  # Legend doesn't fit with margin either way - leave it be.

    xs, ys = [], []
    for x, y in series:
        x = np.asarray(x, dtype=np.float64)
        y = np.asarray(y, dtype=np.float64)
        if x.size:
            xs.append(x)
            ys.append(y)
    if not xs:
        return
    xs = np.concatenate(xs)
    ys = np.concatenate(ys)

    (xmin, xmax), (ymin, ymax) = view_box.viewRange()
    xspan = (xmax - xmin) or 1.0
    yspan = (ymax - ymin) or 1.0
    px = rect.left() + (xs - xmin) / xspan * rect.width()
    # Data-y increases upward on screen (standard, non-inverted axis - the
    # only orientation used anywhere in this app), pixel-y increases
    # downward, hence the flip here.
    py = rect.top() + (ymax - ys) / yspan * rect.height()

    best_pos = None
    best_count = None
    for fx, fy in _CANDIDATE_FRACTIONS:
        left = rect.left() + _MARGIN_PX + fx * avail_w
        top = rect.top() + _MARGIN_PX + fy * avail_h
        inside = (px >= left) & (px <= left + legend_w) & (py >= top) & (py <= top + legend_h)
        count = int(np.count_nonzero(inside))
        if best_count is None or count < best_count:
            best_count = count
            best_pos = (left, top)
        if count == 0:
            break

    # itemPos=parentPos=(0,0): legend's own top-left corner pinned to the
    # ViewBox's top-left corner plus an absolute pixel offset - same anchor
    # mechanism addLegend()'s default offset uses, so this integrates with
    # (rather than fights) pyqtgraph's own auto-repositioning on resize.
    legend.anchor(itemPos=(0, 0), parentPos=(0, 0), offset=best_pos)
