"""PDF export for plotted charts.

pyqtgraph has no equivalent to matplotlib.backends.backend_pdf.PdfPages
(what the Tkinter version used) - each pg.PlotWidget is instead rendered to
a QImage via pyqtgraph.exporters.ImageExporter and drawn onto a QPdfWriter
page, avoiding reintroducing Pillow (dropped in Phase 4) or adding reportlab
as a new dependency when Qt already ships everything needed. Output shape
matches the Tkinter version: one page per chart, one divider page per
"High Throttle Event N" header, in the same order shown on screen.
"""
from pyqtgraph.exporters import ImageExporter
from PySide6.QtCore import QMarginsF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPageLayout, QPageSize, QPainter, QPdfWriter

# Same dark theme as the rest of the app (see COLOR_BG/COLOR_FG in
# LogPlotterGUI.py) - the Tkinter version's matplotlib export set
# savefig.facecolor to match its dark rcParams, so pages here are filled the
# same way rather than defaulting to a blank-white PDF page.
COLOR_BG = "#1e1e1e"
COLOR_FG = "#cccccc"

# Raster width each chart is re-exported at before being placed on a page -
# higher than typical on-screen widget widths so the PDF stays crisp
# regardless of how large the window was when plotted. Height follows
# automatically to preserve the chart's on-screen aspect ratio.
EXPORT_WIDTH_PX = 1800
# 0 margins: the chart/divider content fills the whole page edge-to-edge,
# matching the Tkinter version's PDF pages (each page there was just the
# matplotlib figure's own canvas, with no separate page-margin concept).
PAGE_MARGIN_MM = 0.0
DIVIDER_FONT_POINT_SIZE = 28


def _render_plot_widget(plot_widget):
    exporter = ImageExporter(plot_widget.getPlotItem())
    exporter.parameters()["width"] = EXPORT_WIDTH_PX
    return exporter.export(toBytes=True)


def _draw_image_page(painter, page_rect, image):
    painter.fillRect(page_rect, QColor(COLOR_BG))
    scaled = image.size().scaled(page_rect.size().toSize(), Qt.AspectRatioMode.KeepAspectRatio)
    x = page_rect.x() + (page_rect.width() - scaled.width()) / 2
    y = page_rect.y() + (page_rect.height() - scaled.height()) / 2
    painter.drawImage(QRectF(x, y, scaled.width(), scaled.height()), image)


def _draw_divider_page(painter, page_rect, text):
    painter.fillRect(page_rect, QColor(COLOR_BG))
    font = QFont()
    font.setPointSize(DIVIDER_FONT_POINT_SIZE)
    font.setBold(True)
    painter.setFont(font)
    painter.setPen(QColor(COLOR_FG))
    painter.drawText(page_rect, Qt.AlignmentFlag.AlignCenter, text)


def save_plots_pdf(path, plot_sequence):
    """plot_sequence: [("figure", plot_widget) | ("event", evt_counter), ...]
    in display order (see LogPlotterGUI's paramPlotSequence/
    customPlotSequence). Raises OSError if the file can't be written."""
    writer = QPdfWriter(path)
    writer.setPageSize(QPageSize(QPageSize.PageSizeId.Letter))
    writer.setPageOrientation(QPageLayout.Orientation.Landscape)
    writer.setPageMargins(
        QMarginsF(PAGE_MARGIN_MM, PAGE_MARGIN_MM, PAGE_MARGIN_MM, PAGE_MARGIN_MM),
        QPageLayout.Unit.Millimeter,
    )

    painter = QPainter()
    if not painter.begin(writer):
        raise OSError(f"Could not open '{path}' for writing.")
    try:
        page_rect = QRectF(painter.viewport())
        first_page = True
        for kind, payload in plot_sequence:
            if not first_page:
                writer.newPage()
            first_page = False
            if kind == "event":
                _draw_divider_page(painter, page_rect, f"High Throttle Event {payload}")
            else:
                _draw_image_page(painter, page_rect, _render_plot_widget(payload))
    finally:
        painter.end()
