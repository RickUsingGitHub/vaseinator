"""Render the application icon to assets/icon.png and assets/icon.ico."""

import math
import os
import sys

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QGuiApplication, QImage, QLinearGradient, QPainter, QPainterPath, QPen

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def render(size: int) -> QImage:
    img = QImage(size, size, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    s = size / 256.0
    p.scale(s, s)

    bg = QLinearGradient(0, 0, 0, 256)
    bg.setColorAt(0, QColor(52, 60, 74))
    bg.setColorAt(1, QColor(22, 25, 31))
    p.setPen(Qt.NoPen)
    p.setBrush(bg)
    p.drawRoundedRect(QRectF(8, 8, 240, 240), 44, 44)

    # a twisted vase in three bands, its outline traced from the default design
    def half_width(t):                     # t: 0 at the foot, 1 at the rim
        return 44 + 40 * math.sin(math.pi * min(t / 0.75, 1.0) * 0.9) - (22 * max(t - 0.62, 0) / 0.38) \
            + 14 * max(t - 0.86, 0) / 0.14

    top, foot = 40.0, 222.0
    bands = [QColor(14, 124, 134), QColor(63, 193, 201), QColor(245, 245, 245)]
    for k in range(3):
        t0, t1 = k / 3, (k + 1) / 3
        path = QPainterPath()
        ts = [t0 + (t1 - t0) * i / 24 for i in range(25)]
        path.moveTo(QPointF(128 - half_width(t0), foot - t0 * (foot - top)))
        for t in ts:
            path.lineTo(QPointF(128 + half_width(t), foot - t * (foot - top)))
        for t in reversed(ts):
            path.lineTo(QPointF(128 - half_width(t), foot - t * (foot - top)))
        path.closeSubpath()
        shade = QLinearGradient(60, 0, 196, 0)
        c = bands[k]
        shade.setColorAt(0, c.darker(150))
        shade.setColorAt(0.42, c.lighter(118))
        shade.setColorAt(1, c.darker(170))
        p.setBrush(shade)
        p.drawPath(path)
    # spiral ridges winding up it
    p.setPen(QPen(QColor(20, 40, 48, 150), 4, Qt.SolidLine, Qt.RoundCap))
    for k in range(5):
        path = QPainterPath()
        for i in range(41):
            t = i / 40
            ang = 2.2 * t * math.pi + k * 2 * math.pi / 5
            if math.cos(ang) < 0:
                continue
            x = 128 + half_width(t) * math.sin(ang) * 0.96
            y = foot - t * (foot - top)
            if path.elementCount() == 0 or abs(path.currentPosition().y() - y) > 6:
                path.moveTo(QPointF(x, y))
            else:
                path.lineTo(QPointF(x, y))
        p.drawPath(path)
    # the rim, an ellipse
    p.setPen(QPen(QColor(255, 255, 255, 200), 3))
    p.setBrush(QColor(30, 34, 42))
    w = half_width(1.0)
    p.drawEllipse(QRectF(128 - w, top - 9, 2 * w, 18))
    p.end()
    return img


def main():
    app = QGuiApplication(sys.argv)  # noqa: F841
    out = os.path.join(ROOT, "assets")
    os.makedirs(out, exist_ok=True)
    render(256).save(os.path.join(out, "icon.png"))
    render(256).save(os.path.join(out, "icon.ico"))
    print("icon written to", out)


if __name__ == "__main__":
    main()
