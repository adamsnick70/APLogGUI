"""Generate the app icon (assets/icons/icon.ico, icon.png, AppIcon.iconset/)
from scratch with QPainter, so no external image-editing tool or extra
dependency (e.g. Pillow, dropped in Phase 4) is needed. Re-run this after
changing the design below; the outputs are committed, not generated at
build time.

Windows' Explorer/Start Menu/taskbar all expect an .ico with several baked-in
sizes rather than one image stretched at display time, so this renders the
same vector design at each size independently instead of just downscaling a
single 256x256 bitmap. Qt's own ICO plugin only writes one frame, so the
multi-size .ico container is assembled by hand (PNG frames, the format
Vista+ has supported for years - see MS-ICO / SDK docs).

The macOS build additionally needs an .icns, but `iconutil` (the tool that
compiles a .iconset folder into one) only exists on macOS - this script
writes the .iconset folder here (portable), and packaging/macos/build.sh
runs `iconutil` over it as its own last step, on the Mac/CI runner.
"""
import struct
import sys
from pathlib import Path

from PySide6.QtCore import QBuffer, QIODevice, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPen

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "assets" / "icons"

BG = QColor("#1e1e1e")
LINE = QColor("#4ec9b0")
DOT = QColor("#ffffff")

ICO_SIZES = [16, 24, 32, 48, 64, 128, 256]

# Apple's required .iconset filenames -> the pixel size each represents.
ICONSET_SIZES = {
    "icon_16x16.png": 16,
    "icon_16x16@2x.png": 32,
    "icon_32x32.png": 32,
    "icon_32x32@2x.png": 64,
    "icon_128x128.png": 128,
    "icon_128x128@2x.png": 256,
    "icon_256x256.png": 256,
    "icon_256x256@2x.png": 512,
    "icon_512x512.png": 512,
    "icon_512x512@2x.png": 1024,
}


def render(size):
    image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)

    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    margin = size * 0.06
    rect = QRectF(margin, margin, size - 2 * margin, size - 2 * margin)
    radius = size * 0.2
    path = QPainterPath()
    path.addRoundedRect(rect, radius, radius)
    painter.fillPath(path, BG)

    # A simple rising log-plot trace: three segments stepping up-left to
    # bottom-right to up-right, plus a "current sample" dot - reads as a
    # chart at every size down to 16px instead of blurring into noise.
    pts = [
        QPointF(size * 0.22, size * 0.62),
        QPointF(size * 0.40, size * 0.74),
        QPointF(size * 0.58, size * 0.40),
        QPointF(size * 0.80, size * 0.28),
    ]
    pen = QPen(LINE)
    pen.setWidthF(max(1.5, size * 0.07))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    for a, b in zip(pts, pts[1:]):
        painter.drawLine(a, b)

    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(DOT)
    r = size * 0.06
    painter.drawEllipse(pts[-1], r, r)

    painter.end()
    return image


def png_bytes(image):
    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buf, "PNG")
    return bytes(buf.data())


def write_ico(path, sizes):
    frames = [png_bytes(render(s)) for s in sizes]

    header = struct.pack("<HHH", 0, 1, len(frames))
    entries = b""
    offset = 6 + 16 * len(frames)
    for size, data in zip(sizes, frames):
        wh = size if size < 256 else 0
        entries += struct.pack("<BBBBHHII", wh, wh, 0, 0, 1, 32, len(data), offset)
        offset += len(data)

    path.write_bytes(header + entries + b"".join(frames))


def write_iconset(path):
    path.mkdir(parents=True, exist_ok=True)
    for filename, size in ICONSET_SIZES.items():
        (path / filename).write_bytes(png_bytes(render(size)))


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    write_ico(OUT_DIR / "icon.ico", ICO_SIZES)
    (OUT_DIR / "icon.png").write_bytes(png_bytes(render(256)))
    write_iconset(OUT_DIR / "AppIcon.iconset")
    print(f"Wrote {OUT_DIR / 'icon.ico'}, {OUT_DIR / 'icon.png'}, and {OUT_DIR / 'AppIcon.iconset'}/")


if __name__ == "__main__":
    # A QImage/QPainter needs a QGuiApplication instance to exist first.
    from PySide6.QtGui import QGuiApplication
    app = QGuiApplication(sys.argv)
    main()
