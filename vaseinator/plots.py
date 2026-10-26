"""Two flat pictures of the vase: its outline from the side, and its layers seen from above."""

from __future__ import annotations

import math

import numpy as np
from PySide6.QtCore import QLineF, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QSizePolicy, QWidget

SLICES = 14


def _qcolor(rgb, alpha=255):
    return QColor(int(rgb[0] * 255), int(rgb[1] * 255), int(rgb[2] * 255), alpha)


def gradient_rgb(colours, phase):
    """The same blend the 3D view uses for a gradient spool."""
    n = max(1, len(colours))
    q = (phase % 1.0) * n
    k = int(math.floor(q)) % n
    t = q - math.floor(q)
    t = t * t * (3 - 2 * t)
    a, b = np.array(colours[k]), np.array(colours[(k + 1) % n])
    return tuple(a + (b - a) * t)


class ShapePlots(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.d = None
        self.colours = {}
        self.slices = []
        self.setMinimumHeight(170)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def set_design(self, d, colours):
        self.d = d
        self.colours = colours
        H = d.H
        self.slices = []
        for k in range(SLICES + 1):
            z = min(max(H * k / SLICES, 0.02), H - 0.02)
            self.slices.append((z, d.contour(z)))
        self.update()

    def colour_at(self, z):
        d = self.d
        if d.gradient:
            return gradient_rgb([self.colours[f] for f in d.gradient_fils], float(d.colour_phase(z)))
        fil = d.bands[0][1]
        for zs, f in d.bands:
            if z >= zs:
                fil = f
        return self.colours[fil]

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(26, 28, 33))
        d = self.d
        if d is None:
            p.end()
            return
        w, h = self.width(), self.height()
        gap = 12
        line = p.fontMetrics().height()
        side = QRectF(gap, line + 8, 0.42 * w - 1.5 * gap, h - 2 * line - 16)
        top = QRectF(side.right() + gap, line + 8, w - side.right() - 2 * gap, h - 2 * line - 16)
        font = QFont(self.font())
        p.setFont(font)
        p.setPen(QColor(154, 163, 173))
        p.drawText(QRectF(side.left(), 3, side.width(), line), Qt.AlignLeft, "From the side")
        p.drawText(QRectF(top.left(), 3, top.width(), line), Qt.AlignLeft, "Layers from above")
        self._side(p, side)
        self._top(p, top)
        p.end()

    def _side(self, p: QPainter, a: QRectF):
        d = self.d
        z, rmax, rmin = d.profile_z, d.profile_max, d.profile_min
        s = min(a.width() / (2.0 * max(rmax.max(), 1.0)), a.height() / max(d.H, 1.0)) * 0.96
        cx, base = a.center().x(), a.bottom()

        def pt(x, zz):
            return QPointF(cx + x * s, base - zz * s)

        # the filled outline: one piece per run of a colour (thin strips for a gradient spool)
        rows = len(z)
        step = max(1, rows // 220)
        idx = list(range(0, rows - 1, step)) + [rows - 1]
        runs, start = [], 0
        for k in range(1, len(idx)):
            zm = 0.5 * (z[idx[k - 1]] + z[idx[k]])
            col = self.colour_at(zm)
            if k == 1:
                runs.append([idx[0], idx[1], col])
            elif d.gradient or col != runs[-1][2]:
                runs.append([idx[k - 1], idx[k], col])
            else:
                runs[-1][1] = idx[k]
        p.setPen(Qt.NoPen)
        p.setRenderHint(QPainter.Antialiasing, False)       # no hairline seams between the pieces
        for j0, j1, col in runs:
            js = [j for j in idx if j0 <= j <= j1]
            p.setBrush(_qcolor(col))
            p.drawPolygon(QPolygonF([pt(rmax[j], z[j]) for j in js] + [pt(-rmax[j], z[j]) for j in reversed(js)]))
        p.setRenderHint(QPainter.Antialiasing, True)
        # the narrowest radius at each height, inside: how deep the shape and patterns go
        p.setPen(QPen(QColor(20, 22, 26, 150), 1.0, Qt.DashLine))
        p.setBrush(Qt.NoBrush)
        for sign in (-1, 1):
            p.drawPolyline(QPolygonF([pt(sign * r, zz) for r, zz in zip(rmin[::step], z[::step])]))
        # the printed wall: solid bottom
        p.setPen(QPen(QColor(255, 255, 255, 70), 1.0))
        p.drawLine(pt(-rmax[0], d.zb), pt(rmax[0], d.zb))
        # where it was softened, and anything still leaning too far
        lim = d.p.max_overhang + 0.3
        bad = np.nonzero(d.band_lean > lim)[0]
        if len(bad):
            zb = (z[np.minimum(bad, len(z) - 1)] if d.rows is None
                  else np.array([d.rows[min(b, len(d.rows) - 1)][0] for b in bad]))
            p.setPen(QPen(QColor(235, 60, 50), 2.0))
            x = a.right() - 3
            for zz in zb:
                p.drawLine(QPointF(x - 6, base - zz * s), QPointF(x, base - zz * s))
        if d.softened > 0.05 and d.rows is None:
            moved = np.abs(d.R - d.R_design).max(axis=1) > 0.05
            p.setPen(QPen(QColor(240, 163, 86, 200), 2.0))
            x = a.left() + 3
            for zz in z[moved][::max(1, step)]:
                p.drawLine(QPointF(x, base - zz * s), QPointF(x + 6, base - zz * s))
        p.setPen(QColor(120, 128, 138))
        p.drawText(QRectF(a.left() - 6, a.bottom() + 4, a.width() + 12, p.fontMetrics().height()),
                   Qt.AlignHCenter, f"{d.H:.0f} mm tall, Ø {d.widest:.0f} mm")

    def _top(self, p: QPainter, a: QRectF):
        d = self.d
        half = 0.5 * max(d.size[0], d.size[1], 1.0)
        s = min(a.width(), a.height()) / (2.0 * half) * 0.95
        c = a.center()
        p.setBrush(Qt.NoBrush)
        n = len(self.slices)
        for k, (z, seg) in enumerate(self.slices):
            if not len(seg):
                continue
            col = _qcolor(self.colour_at(z), 120 + int(135 * k / max(n - 1, 1)))
            p.setPen(QPen(col, 2.2 if k == n - 1 else 1.2))
            xy = seg[:, :, :2] * (s, -s) + (c.x(), c.y())
            p.drawLines([QLineF(x0, y0, x1, y1) for (x0, y0), (x1, y1) in xy.tolist()])
        p.setPen(QPen(QColor(154, 163, 173, 120), 1))
        p.drawLine(QPointF(c.x() - 4, c.y()), QPointF(c.x() + 4, c.y()))
        p.drawLine(QPointF(c.x(), c.y() - 4), QPointF(c.x(), c.y() + 4))
