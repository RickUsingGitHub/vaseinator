"""A small editor for a curve up the height of the vase: drag points, add and remove them.

Height runs up the editor, as it does on the vase, and the value runs across.
The outline's editor is drawn mirrored, so it looks like the vase from the side.
"""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import QSizePolicy, QWidget

from .shapes import pchip

POINT_R = 5.0
HIT = 9.0
GAP = 0.02                      # the closest two points may come in height


class CurveEditor(QWidget):
    changed = Signal(list)      # while a point is being dragged
    finished = Signal(list)     # a drag ended, or a point was added or taken away

    def __init__(self, lo: float, hi: float, unit: str = "", mirror: bool = False, height: int = 110,
                 floor: float | None = None, grow: bool = False, decimals: int = 0, parent=None):
        super().__init__(parent)
        self.lo, self.hi = float(lo), float(hi)
        self.base = (self.lo, self.hi)
        self.unit = unit
        self.mirror = mirror
        self.floor = floor              # the smallest value a point may take
        self.grow = grow                # the range grows to fit the points
        self.decimals = decimals
        self.points: list[list[float]] = [[0.0, 0.0], [1.0, 0.0]]
        self.drag = None
        self.hover = None
        self.accent = QColor(240, 163, 86)
        self.fill = QColor(240, 163, 86, 46)
        self.setMinimumHeight(height)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMouseTracking(True)
        self.setToolTip("Drag the points. Double-click to add one; right-click a point to take it away.\n"
                        "Up the editor is up the vase.")

    # ------------------------------------------------------------- data
    def set_points(self, points):
        self.points = [list(map(float, p)) for p in points]
        self._fit_range()
        self.update()

    def _fit_range(self):
        if not self.grow:
            return
        vals = [v for _, v in self.points]
        lo, hi = self.base
        if self.mirror:
            hi = max(hi, max(vals) * 1.15)
        else:
            span = max(abs(min(vals)), abs(max(vals)), max(abs(lo), abs(hi)) * 0.25) * 1.2
            lo, hi = (-span, span) if min(lo, min(vals)) < 0 else (min(lo, 0.0), max(hi, span))
        self.lo, self.hi = lo, hi

    # ---------------------------------------------------------- mapping
    def _area(self) -> QRectF:
        caption = self.fontMetrics().height() + 4          # room for the range underneath
        return QRectF(8, 8, max(self.width() - 16, 10), max(self.height() - 10 - caption, 10))

    def _xy(self, h, v):
        a = self._area()
        y = a.bottom() - h * a.height()
        if self.mirror:
            x = a.center().x() + 0.5 * v / max(self.hi, 1e-9) * (0.5 * a.width()) * 2
        else:
            x = a.left() + (v - self.lo) / max(self.hi - self.lo, 1e-9) * a.width()
        return QPointF(x, y)

    def _value(self, pos: QPointF):
        a = self._area()
        h = min(max((a.bottom() - pos.y()) / a.height(), 0.0), 1.0)
        if self.mirror:
            v = abs(pos.x() - a.center().x()) / (0.5 * a.width()) * self.hi
        else:
            v = self.lo + (pos.x() - a.left()) / a.width() * (self.hi - self.lo)
            v = min(max(v, self.lo), self.hi)
        if self.floor is not None:
            v = max(v, self.floor)
        return h, v

    def _hit(self, pos: QPointF):
        best, best_d = None, HIT
        for i, (h, v) in enumerate(self.points):
            p = self._xy(h, v)
            for q in ([p, QPointF(2 * self._area().center().x() - p.x(), p.y())] if self.mirror else [p]):
                d = (q - pos).manhattanLength()
                if d < best_d:
                    best, best_d = i, d
        return best

    # ------------------------------------------------------------ paint
    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        a = self._area()
        p.fillRect(self.rect(), QColor(26, 28, 33))
        p.setPen(QPen(QColor(59, 64, 73), 1))
        p.drawRect(a)
        grid = QPen(QColor(44, 48, 56), 1, Qt.DotLine)
        p.setPen(grid)
        for k in (0.25, 0.5, 0.75):
            p.drawLine(QPointF(a.left(), a.bottom() - k * a.height()), QPointF(a.right(), a.bottom() - k * a.height()))
        if not self.mirror and self.lo < 0 < self.hi:
            x0 = self._xy(0, 0.0).x()
            p.setPen(QPen(QColor(80, 86, 96), 1))
            p.drawLine(QPointF(x0, a.top()), QPointF(x0, a.bottom()))

        pts = np.array(self.points)
        hs = np.linspace(0.0, 1.0, 120)
        vs = pchip(pts[:, 0], pts[:, 1], hs)
        line = [self._xy(h, v) for h, v in zip(hs, vs)]
        if self.mirror:
            cx = a.center().x()
            left = [QPointF(2 * cx - q.x(), q.y()) for q in reversed(line)]
            shape = QPolygonF(line + left)
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(self.fill))
            p.drawPolygon(shape)
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(self.accent, 1.6))
            for side in (line, left):
                path = QPainterPath(side[0])
                for q in side[1:]:
                    path.lineTo(q)
                p.drawPath(path)
        else:
            path = QPainterPath(line[0])
            for q in line[1:]:
                path.lineTo(q)
            p.setPen(QPen(self.accent, 1.6))
            p.drawPath(path)

        for i, (h, v) in enumerate(self.points):
            q = self._xy(h, v)
            on = i == self.drag or i == self.hover
            p.setPen(QPen(QColor(20, 22, 26), 1))
            p.setBrush(QColor(255, 255, 255) if on else self.accent)
            p.drawEllipse(q, POINT_R + (1 if on else 0), POINT_R + (1 if on else 0))
        font = QFont(self.font())
        font.setPointSizeF(max(font.pointSizeF() - 1.0, 7.0))
        p.setFont(font)
        p.setPen(QColor(154, 163, 173))
        under = QRectF(a.left(), a.bottom() + 2, a.width(), p.fontMetrics().height())
        p.drawText(under, Qt.AlignLeft | Qt.AlignVCenter, "↑ up the vase")
        p.drawText(under, Qt.AlignRight | Qt.AlignVCenter,
                   f"{self._fmt(self.lo if not self.mirror else 0)} … {self._fmt(self.hi)}{self.unit}")
        k = self.drag if self.drag is not None else self.hover
        if k is not None:
            h, v = self.points[k]
            q = self._xy(h, v)
            text = f"{self._fmt(v)}{self.unit} at {h * 100:.0f}%"
            p.setPen(QColor(235, 238, 242))
            r = QRectF(q.x() + 8, q.y() - 4 - p.fontMetrics().height(), 170, p.fontMetrics().height())
            if r.right() > a.right():
                r.moveRight(q.x() - 8)
            p.drawText(r, Qt.AlignLeft | Qt.AlignVCenter if r.left() > q.x() else Qt.AlignRight | Qt.AlignVCenter,
                       text)
        p.end()

    def _fmt(self, v):
        return f"{v:.{self.decimals}f}"

    # ------------------------------------------------------------ mouse
    def mousePressEvent(self, ev):
        i = self._hit(ev.position())
        if ev.button() == Qt.RightButton:
            if i is not None and 0 < i < len(self.points) - 1:
                del self.points[i]
                self.hover = None
                self.update()
                self.finished.emit(self._copy())
            return
        if ev.button() == Qt.LeftButton and i is not None:
            self.drag = i
            self.update()

    def mouseMoveEvent(self, ev):
        if self.drag is None:
            i = self._hit(ev.position())
            if i != self.hover:
                self.hover = i
                self.update()
            return
        h, v = self._value(ev.position())
        i = self.drag
        if i == 0:
            h = 0.0
        elif i == len(self.points) - 1:
            h = 1.0
        else:
            h = min(max(h, self.points[i - 1][0] + GAP), self.points[i + 1][0] - GAP)
        self.points[i] = [h, v]
        self.update()
        self.changed.emit(self._copy())

    def mouseReleaseEvent(self, ev):
        if self.drag is not None:
            self.drag = None
            self._fit_range()
            self.update()
            self.finished.emit(self._copy())

    def mouseDoubleClickEvent(self, ev):
        if self._hit(ev.position()) is not None:
            return
        h, v = self._value(ev.position())
        if any(abs(h - q[0]) < GAP for q in self.points):
            return
        self.points.append([h, v])
        self.points.sort(key=lambda q: q[0])
        self.update()
        self.finished.emit(self._copy())

    def leaveEvent(self, ev):
        self.hover = None
        self.update()

    def _copy(self):
        return [[round(h, 4), round(v, 3)] for h, v in self.points]
