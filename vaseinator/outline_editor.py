"""The cross-section editor: draw any outline with smooth spline points and sharp cusps.

The middle of the editor is the axis of the vase, and the dashed circle is the
widest the vase gets (the outline is scaled so its furthest point touches it).
With *Repeat around* above 1 the points drawn are one piece - one lobe, say -
and the rest are copies turned round the axis, shown fainter.
"""

from __future__ import annotations

import math

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import QMenu, QSizePolicy, QWidget

from . import sections

HIT = 10.0
REACH = 1.35            # how far from the axis a point may go, in widest radii


class OutlineEditor(QWidget):
    changed = Signal(list)      # while a point is being dragged
    finished = Signal(list)     # a drag ended, or a point was added, sharpened, smoothed or taken away

    def __init__(self, parent=None):
        super().__init__(parent)
        self.points: list[list] = [[1.0, 0.0, False], [-0.5, 0.87, False], [-0.5, -0.87, False]]
        self.repeat = 1
        self.drag = None
        self.hover = None
        self.inside = False
        self.accent = QColor(240, 163, 86)
        self.setMinimumHeight(300)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.ClickFocus)
        self.setToolTip("Drag the points. Double-click the line to add a point; double-click a point to make it\n"
                        "sharp (a cusp) or smooth again; right-click a point for more. The middle is the vase's\n"
                        "axis; the dashed circle is its widest.")

    # ------------------------------------------------------------- data
    def set_outline(self, points, repeat: int):
        self.points = [[float(x), float(y), bool(c)] for x, y, c in points]
        self.repeat = max(int(repeat), 1)
        self.update()

    def _copy(self):
        return [[round(x, 4), round(y, 4), bool(c)] for x, y, c in self.points]

    # ---------------------------------------------------------- mapping
    def _scale(self):
        return 0.42 * min(self.width(), self.height())

    def _to(self, x, y):
        s = self._scale()
        return QPointF(self.width() / 2 + x * s, self.height() / 2 - y * s)

    def _from(self, pos: QPointF):
        s = self._scale()
        x, y = (pos.x() - self.width() / 2) / s, (self.height() / 2 - pos.y()) / s
        r = math.hypot(x, y)
        if r > REACH:
            x, y = x * REACH / r, y * REACH / r
        return x, y

    def _hit(self, pos: QPointF):
        best, best_d = None, HIT
        for i, (x, y, _) in enumerate(self.points):
            d = (self._to(x, y) - pos).manhattanLength()
            if d < best_d:
                best, best_d = i, d
        return best

    # ------------------------------------------------------------ paint
    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(26, 28, 33))
        s = self._scale()
        c = QPointF(self.width() / 2, self.height() / 2)
        p.setPen(QPen(QColor(44, 48, 56), 1, Qt.DotLine))
        for k in range(-5, 6):
            p.drawLine(self._to(k * 0.25, -1.3), self._to(k * 0.25, 1.3))
            p.drawLine(self._to(-1.3, k * 0.25), self._to(1.3, k * 0.25))
        p.setPen(QPen(QColor(90, 96, 108), 1, Qt.DashLine))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(c, s, s)
        if self.repeat > 1:                                   # where each repeat begins
            p.setPen(QPen(QColor(52, 57, 66), 1))
            for k in range(self.repeat):
                a = math.pi * (2 * k + 1) / self.repeat
                p.drawLine(c, self._to(1.3 * math.cos(a), 1.3 * math.sin(a)))
        p.setPen(QPen(QColor(120, 128, 138), 1))
        p.drawLine(QPointF(c.x() - 5, c.y()), QPointF(c.x() + 5, c.y()))
        p.drawLine(QPointF(c.x(), c.y() - 5), QPointF(c.x(), c.y() + 5))

        crossed = False
        try:
            loop = sections.spline(self.points, self.repeat, per=24)
            crossed = bool(sections.crossings(loop, limit=1200))
        except ValueError:
            loop = None
        if loop is not None:
            poly = QPolygonF([self._to(x, y) for x, y in loop])
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(QColor(235, 60, 50, 40) if crossed else QColor(240, 163, 86, 40)))
            p.drawPolygon(poly)
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(QColor(235, 60, 50) if crossed else self.accent, 1.8))
            p.drawPolygon(poly)
        # the copies' points, faint, then the drawn ones to drag
        if self.repeat > 1:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(240, 163, 86, 70))
            for k in range(1, self.repeat):
                a = 2 * math.pi * k / self.repeat
                ca, sa = math.cos(a), math.sin(a)
                for x, y, _ in self.points:
                    p.drawEllipse(self._to(x * ca - y * sa, x * sa + y * ca), 2.5, 2.5)
        for i, (x, y, cusp) in enumerate(self.points):
            q = self._to(x, y)
            on = i in (self.drag, self.hover)
            p.setPen(QPen(QColor(20, 22, 26), 1))
            p.setBrush(QColor(255, 255, 255) if on else self.accent)
            r = 6.0 if on else 5.0
            if cusp:                                          # a cusp is a diamond, a smooth point round
                p.drawPolygon(QPolygonF([QPointF(q.x(), q.y() - r - 1), QPointF(q.x() + r + 1, q.y()),
                                         QPointF(q.x(), q.y() + r + 1), QPointF(q.x() - r - 1, q.y())]))
            else:
                p.drawEllipse(q, r, r)
        font = QFont(self.font())
        font.setPointSizeF(max(font.pointSizeF() - 1.0, 7.0))
        p.setFont(font)
        fh = p.fontMetrics().height()
        if crossed:
            p.setPen(QColor(255, 120, 110))
            p.drawText(QRectF(6, 4, self.width() - 12, fh), Qt.AlignLeft, "The outline crosses itself")
        elif self.inside and self.drag is None:
            p.setPen(QColor(120, 128, 138))
            p.drawText(QRectF(6, self.height() - fh - 4, self.width() - 12, fh), Qt.AlignLeft,
                       "double-click: add a point · on a point: sharp / smooth")
        p.setPen(QColor(110, 118, 128))
        p.drawText(QRectF(6, 4, self.width() - 12, fh), Qt.AlignRight, "widest ⌒")
        p.end()

    # ------------------------------------------------------------ mouse
    def mousePressEvent(self, ev):
        i = self._hit(ev.position())
        if ev.button() == Qt.RightButton and i is not None:
            self._menu(i, ev.globalPosition().toPoint())
            return
        if ev.button() == Qt.LeftButton and i is not None:
            self.drag = i
            self.update()

    def _menu(self, i, where):
        m = QMenu(self)
        cusp = self.points[i][2]
        m.addAction("Smooth point" if cusp else "Sharp corner (cusp)").triggered.connect(lambda: self._toggle(i))
        delete = m.addAction("Take this point away")
        delete.setEnabled(len(self.points) > 3)
        delete.triggered.connect(lambda: self._delete(i))
        m.exec(where)

    def _toggle(self, i):
        self.points[i][2] = not self.points[i][2]
        self.update()
        self.finished.emit(self._copy())

    def _delete(self, i):
        if len(self.points) > 3:
            del self.points[i]
            self.hover = None
            self.update()
            self.finished.emit(self._copy())

    def mouseMoveEvent(self, ev):
        if self.drag is None:
            i = self._hit(ev.position())
            if i != self.hover:
                self.hover = i
                self.update()
            return
        x, y = self._from(ev.position())
        self.points[self.drag][:2] = [x, y]
        self.update()
        self.changed.emit(self._copy())

    def mouseReleaseEvent(self, ev):
        if self.drag is not None:
            self.drag = None
            self.update()
            self.finished.emit(self._copy())

    def mouseDoubleClickEvent(self, ev):
        i = self._hit(ev.position())
        if i is not None:
            self._toggle(i)
            return
        x, y = self._from(ev.position())
        self.points.insert(self._nearest_side(x, y) + 1, [x, y, False])
        self.update()
        self.finished.emit(self._copy())

    def keyPressEvent(self, ev):
        if ev.key() in (Qt.Key_Delete, Qt.Key_Backspace) and self.hover is not None:
            self._delete(self.hover)
        else:
            super().keyPressEvent(ev)

    def enterEvent(self, ev):
        self.inside = True
        self.update()

    def leaveEvent(self, ev):
        self.inside = False
        self.hover = None
        self.update()

    def _nearest_side(self, x, y) -> int:
        """Index of the point after which a new point at (x, y) belongs: the nearest side of the chain."""
        P = np.array([pt[:2] for pt in self.points])
        nxt = np.roll(P, -1, axis=0)
        if self.repeat > 1:                                   # the last point joins the next copy's first
            a = 2 * math.pi / self.repeat
            nxt[-1] = P[0] @ np.array([[math.cos(a), math.sin(a)], [-math.sin(a), math.cos(a)]])
        q = np.array([x, y])
        d = nxt - P
        t = np.clip(np.einsum("ij,ij->i", q - P, d) / np.maximum(np.einsum("ij,ij->i", d, d), 1e-12), 0, 1)
        dist = np.linalg.norm(P + d * t[:, None] - q, axis=1)
        return int(np.argmin(dist))
