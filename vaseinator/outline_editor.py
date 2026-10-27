"""The cross-section editor: draw any outline with smooth spline points and sharp cusps.

The middle of the editor is the axis of the vase, and the dashed circle is the
widest the vase gets (the outline is scaled so its furthest point touches it).
With *Repeat around* above 1 the points drawn are one piece - one lobe, say -
and the rest are copies turned round the axis, shown fainter. With many
repeats the editor shows one of them close up, turned to point upwards.

``OutlineWindow`` is the same editor filling a window, where the wheel zooms
and a right or middle drag moves the view.
"""

from __future__ import annotations

import math

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QMenu, QPushButton, QSizePolicy, QSpinBox, QToolButton,
                               QVBoxLayout, QWidget)

from . import sections
from .params import MAX_REPEAT

HIT = 10.0
REACH = 1.35            # how far from the axis a point may go, in widest radii
CLOSE_UP_FROM = 8       # with more repeats than this, the editor starts close up on one
PER = 24                # points drawn along each side of the spline


class OutlineEditor(QWidget):
    changed = Signal(list)      # while a point is being dragged
    finished = Signal(list)     # a drag ended, or a point was added, sharpened, smoothed or taken away
    view_changed = Signal()     # switched between the whole outline and one repeat close up

    def __init__(self, parent=None, big: bool = False):
        super().__init__(parent)
        self.points: list[list] = [[1.0, 0.0, False], [-0.5, 0.87, False], [-0.5, -0.87, False]]
        self.repeat = 1
        self.big = big              # filling a window: the wheel zooms, a right or middle drag moves the view
        self.choice = None          # one repeat close up: None follows Repeat around, or as chosen
        self.view = None            # (cx, cy, pixels per unit, turn) - fitted again when None
        self.by_hand = False        # zoomed or moved with the mouse: kept as it is
        self.drag = None
        self.hover = None
        self.inside = False
        self.pan = None
        self._cache = None
        self._bg = None
        self.accent = QColor(240, 163, 86)
        if big:
            self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        else:
            self.setMinimumHeight(300)
            self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.ClickFocus)
        self.setToolTip("Drag the points. Double-click the line to add a point; double-click a point to make it\n"
                        "sharp (a cusp) or smooth again; right-click a point for more. The middle is the vase's\n"
                        "axis; the dashed circle is its widest." +
                        ("\nThe wheel zooms; drag with the right or middle button to move; F fits it again."
                         if big else ""))

    # ------------------------------------------------------------- data
    def set_outline(self, points, repeat: int):
        repeat = max(int(repeat), 1)
        if repeat != self.repeat:
            self.choice = None
            self.view, self.by_hand = None, False
        self.points = [[float(x), float(y), bool(c)] for x, y, c in points]
        self.repeat = repeat
        if self.view is not None and not self.by_hand and self.close_up() and not self._all_seen():
            self.view = None
        self.update()
        self.view_changed.emit()

    def _copy(self):
        return [[round(x, 4), round(y, 4), bool(c)] for x, y, c in self.points]

    # ------------------------------------------------------------- view
    def close_up(self) -> bool:
        """Showing one repeat close up, rather than the whole outline."""
        if self.repeat < 2:
            return False
        return self.choice if self.choice is not None else self.repeat > CLOSE_UP_FROM

    def set_close_up(self, on: bool):
        if bool(on) != self.close_up():
            self.choice = bool(on)
            self.fit()

    def fit(self):
        self.view, self.by_hand = None, False
        self.update()
        self.view_changed.emit()

    def _piece(self):
        """The drawn piece's angles (unwound along it) and distances from the axis."""
        P = np.array([q[:2] for q in self.points], dtype=float)
        return np.unwrap(np.arctan2(P[:, 1], P[:, 0])), np.hypot(P[:, 0], P[:, 1])

    def _fit(self):
        w, h = max(self.width(), 1), max(self.height(), 1)
        if not self.close_up():
            return 0.0, 0.0, 0.42 * min(w, h), 0.0
        n = self.repeat
        a, r = self._piece()
        mid = 0.5 * (a.min() + a.max())
        half = min(max(0.5 * (a.max() - a.min()), math.pi / n) + 0.6 * math.pi / n, math.pi)
        r_in = max(min(float(r.min()), 0.97) - 0.05, 0.0)
        r_out = max(float(r.max()), 1.0) + 0.05
        ang = 0.5 * math.pi + np.linspace(-half, half, 61)              # turned to point straight up
        ring = np.concatenate([np.stack([rr * np.cos(ang), rr * np.sin(ang)], 1) for rr in (r_in, r_out)])
        lo, hi = ring.min(0), ring.max(0)
        s = 0.92 * min(w / max(hi[0] - lo[0], 1e-9), h / max(hi[1] - lo[1], 1e-9))
        return 0.5 * (lo[0] + hi[0]), 0.5 * (lo[1] + hi[1]), s, 0.5 * math.pi - mid

    def _view(self):
        if self.view is None:
            self.view = self._fit()
        return self.view

    def _xf(self):
        cx, cy, s, turn = self._view()
        return cx, cy, s, math.cos(turn), math.sin(turn)

    def _to(self, x, y):
        cx, cy, s, c, sn = self._xf()
        return QPointF(self.width() / 2 + (x * c - y * sn - cx) * s, self.height() / 2 - (x * sn + y * c - cy) * s)

    def _screen(self, P) -> np.ndarray:
        cx, cy, s, c, sn = self._xf()
        return np.stack([self.width() / 2 + (P[:, 0] * c - P[:, 1] * sn - cx) * s,
                         self.height() / 2 - (P[:, 0] * sn + P[:, 1] * c - cy) * s], 1)

    def _from(self, pos: QPointF):
        cx, cy, s, c, sn = self._xf()
        xr = cx + (pos.x() - self.width() / 2) / s
        yr = cy + (self.height() / 2 - pos.y()) / s
        x, y = xr * c + yr * sn, -xr * sn + yr * c
        r = math.hypot(x, y)
        if r > REACH:
            x, y = x * REACH / r, y * REACH / r
        return x, y

    def _all_seen(self) -> bool:
        S = self._screen(np.array([q[:2] for q in self.points], dtype=float))
        return bool(((S[:, 0] >= 0) & (S[:, 0] <= self.width()) & (S[:, 1] >= 0) & (S[:, 1] <= self.height())).all())

    def _hit(self, pos: QPointF):
        best, best_d = None, HIT
        for i, (x, y, _) in enumerate(self.points):
            d = (self._to(x, y) - pos).manhattanLength()
            if d < best_d:
                best, best_d = i, d
        return best

    # ------------------------------------------------------------ paint
    def _loop(self):
        """The outline (all its copies) and whether it crosses itself - worked out once per change."""
        key = (tuple(tuple(q) for q in self.points), self.repeat)
        if self._cache is None or self._cache[0] != key:
            try:
                loop = sections.spline(self.points, self.repeat, per=PER)
                crossed = bool(sections.piece_crossings(loop, PER * len(self.points)))
            except ValueError:
                loop, crossed = None, False
            self._cache = (key, loop, crossed)
        return self._cache[1], self._cache[2]

    @staticmethod
    def _thin(S, gap: float = 2.5) -> np.ndarray:
        """Which screen points to keep for about one every ``gap`` pixels along the line."""
        if len(S) < 3:
            return np.ones(len(S), dtype=bool)
        along = np.concatenate([[0.0], np.cumsum(np.hypot(*np.diff(S, axis=0).T))])
        keep = np.concatenate([[True], np.diff(np.floor(along / gap)) > 0])
        keep[-1] = True
        return keep

    def _shapes(self, loop):
        """The loop on screen: a polygon to fill, thinned out off screen, and the runs of it on screen to stroke.

        Close up, most of a many-times-repeated outline lies far off screen; drawing only what shows, at
        about one point every few pixels, keeps dragging a point quick.
        """
        S = self._screen(loop)
        w, h = self.width(), self.height()
        m = 60
        near = (S[:, 0] > -m) & (S[:, 0] < w + m) & (S[:, 1] > -m) & (S[:, 1] < h + m)
        edge = near != np.roll(near, 1)
        keep = (near & self._thin(S, 6.0)) | edge | np.roll(edge, -1) | (np.arange(len(S)) % 32 == 0)
        fill = QPolygonF([QPointF(x, y) for x, y in S[keep].tolist()])
        if self.repeat < 2:
            return fill, (self._runs(S), [])
        # the drawn piece and a copy either side drawn smooth; further copies in plain lines, much quicker
        i, m = np.arange(len(S)), PER * len(self.points)
        piece = (i < 2 * m) | (i >= len(S) - m)
        return fill, (self._runs(S, only=piece), self._runs(S, only=~piece))

    def _runs(self, S, closed=True, only=None) -> list:
        """The stretches of a line of screen points that show (of those ``only`` picks), each with a point
        either side so it runs off the edge."""
        w, h, m = self.width(), self.height(), 60
        near = (S[:, 0] > -m) & (S[:, 0] < w + m) & (S[:, 1] > -m) & (S[:, 1] < h + m)
        if only is not None:
            near &= only
            if not near.any():
                return []
        if not closed:
            near[0] = near[-1] = near[0] and near[-1] and near.all()
        shown = near | np.roll(near, 1) | np.roll(near, -1)
        if shown.all():
            return [QPolygonF([QPointF(x, y) for x, y in S[self._thin(S)].tolist()])]
        starts = np.nonzero(shown & ~np.roll(shown, 1))[0]
        ends = np.nonzero(shown & ~np.roll(shown, -1))[0]
        runs = []
        for a in starts:
            b = ends[ends >= a][0] if (ends >= a).any() else ends[0] + len(S)
            R = S[np.arange(a, b + 1) % len(S)]
            runs.append(QPolygonF([QPointF(x, y) for x, y in R[self._thin(R)].tolist()]))
        return runs

    def _background(self, close: bool, crossed: bool, loop):
        """Everything but the points to drag - the grid, the widest circle, the outline - kept as a picture
        while only the points change (the mouse passing over them)."""
        w, h = self.width(), self.height()
        busy = self.drag is not None
        key = (self._cache[0] if self._cache else None, self._view(), w, h, close, busy)
        if self._bg is not None and self._bg[0] == key:
            return self._bg[1]
        dpr = self.devicePixelRatioF()
        size = (max(int(w * dpr), 1), max(int(h * dpr), 1))
        pm = self._bg[1] if self._bg is not None and (self._bg[1].width(), self._bg[1].height()) == size else None
        if pm is None:
            pm = QPixmap(*size)
            pm.setDevicePixelRatio(dpr)
        pm.fill(QColor(26, 28, 33))
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        cx, cy, s, c, sn = self._xf()
        # a grid square to the screen, a line every 28 pixels or more
        step = next((g for g in (0.002, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5) if g * s >= 28), 1.0)
        p.setPen(QPen(QColor(35, 38, 45), 0))
        for k in range(math.ceil((cx - w / 2 / s) / step), math.floor((cx + w / 2 / s) / step) + 1):
            x = w / 2 + (k * step - cx) * s
            p.drawLine(QPointF(x, 0), QPointF(x, h))
        for k in range(math.ceil((cy - h / 2 / s) / step), math.floor((cy + h / 2 / s) / step) + 1):
            y = h / 2 - (k * step - cy) * s
            p.drawLine(QPointF(0, y), QPointF(w, y))
        # the widest circle (the part that shows), and where each repeat begins
        t = np.linspace(0.0, 2 * math.pi, 2881)
        p.setPen(QPen(QColor(90, 96, 108), 1, Qt.DashLine))
        p.setBrush(Qt.NoBrush)
        for run in self._runs(self._screen(np.stack([np.cos(t), np.sin(t)], 1)), closed=False):
            p.drawPolyline(run)
        n = self.repeat
        if n > 1 and (close or n <= 24):
            a, _ = self._piece()
            mid = 0.5 * (a.min() + a.max())
            p.setPen(QPen(QColor(52, 57, 66), 0))
            o = self._to(0.0, 0.0)
            for k in range(n):
                b = mid + math.pi * (2 * k + 1) / n
                p.drawLine(o, self._to(1.3 * math.cos(b), 1.3 * math.sin(b)))
        p.setPen(QPen(QColor(120, 128, 138), 1))
        o = self._to(0.0, 0.0)
        p.drawLine(QPointF(o.x() - 5, o.y()), QPointF(o.x() + 5, o.y()))
        p.drawLine(QPointF(o.x(), o.y() - 5), QPointF(o.x(), o.y() + 5))
        if loop is not None:
            fill, (runs, rest) = self._shapes(loop)
            line = QColor(235, 60, 50) if crossed else QColor(self.accent)
            p.setRenderHint(QPainter.Antialiasing, False)    # a faint fill: no need, and much quicker
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(QColor(line.red(), line.green(), line.blue(), 40)))
            p.drawPolygon(fill)
            p.setBrush(Qt.NoBrush)
            line.setAlpha(170)
            p.setPen(QPen(line, 0))                          # one pixel: the quick way to draw a line
            for run in rest:
                p.drawPolyline(run)
            # a great deal on screen while a point is dragged: plain lines, smoothed again when it is let go
            p.setRenderHint(QPainter.Antialiasing, not (busy and sum(r.size() for r in runs) > 6000))
            line.setAlpha(255)
            p.setPen(QPen(line, 1.8))
            for run in runs:
                p.drawPolyline(run)
        p.end()
        self._bg = (key, pm)
        return pm

    def paintEvent(self, ev):
        close = self.close_up()
        w, h = self.width(), self.height()
        loop, crossed = self._loop()
        bg = self._background(close, crossed, loop)
        p = QPainter(self)
        p.drawPixmap(0, 0, bg)
        p.setRenderHint(QPainter.Antialiasing)
        n = self.repeat
        # the copies' points, faint (the nearest few when close up), then the drawn ones to drag
        if n > 1 and (close or n <= 24):
            copies = [1, 2, 3, n - 1, n - 2, n - 3] if close else range(1, n)
            P = np.array([q[:2] for q in self.points], dtype=float)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(240, 163, 86, 70))
            for k in sorted({k % n for k in copies} - {0}):
                a = 2 * math.pi * k / n
                R = P @ np.array([[math.cos(a), math.sin(a)], [-math.sin(a), math.cos(a)]])
                for x, y in self._screen(R).tolist():
                    p.drawEllipse(QPointF(x, y), 2.5, 2.5)
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
            p.drawText(QRectF(6, 4, w - 12, fh), Qt.AlignLeft, "The outline crosses itself")
        elif close:
            p.setPen(QColor(150, 158, 168))
            p.drawText(QRectF(6, 4, w - 12, fh), Qt.AlignLeft, f"One of {n} repeats, close up")
        if self.inside and self.drag is None and self.pan is None:
            p.setPen(QColor(120, 128, 138))
            tip = "double-click: add a point · on a point: sharp / smooth"
            if self.big:
                tip += " · wheel: zoom · right-drag: move · F: fit"
            p.drawText(QRectF(6, h - fh - 4, w - 12, fh), Qt.AlignLeft, tip)
        p.setPen(QColor(110, 118, 128))
        p.drawText(QRectF(6, 4, w - 12, fh), Qt.AlignRight, "widest ⌒")
        p.end()

    def resizeEvent(self, ev):
        if not self.by_hand:
            self.view = None
        super().resizeEvent(ev)

    # ------------------------------------------------------------ mouse
    def mousePressEvent(self, ev):
        pos = ev.position()
        i = self._hit(pos)
        if ev.button() == Qt.RightButton and i is not None:
            self._menu(i, ev.globalPosition().toPoint())
            return
        if self.big and (ev.button() == Qt.MiddleButton or ev.button() == Qt.RightButton):
            self.pan = (pos, self._view())
            self.setCursor(Qt.ClosedHandCursor)
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
        if self.pan is not None:
            start, (cx, cy, s, turn) = self.pan
            d = ev.position() - start
            self.view, self.by_hand = (cx - d.x() / s, cy + d.y() / s, s, turn), True
            self.update()
            return
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
        if self.pan is not None:
            self.pan = None
            self.unsetCursor()
            self.update()
            return
        if self.drag is not None:
            self.drag = None
            self.update()
            self.finished.emit(self._copy())

    def mouseDoubleClickEvent(self, ev):
        if ev.button() != Qt.LeftButton:
            return
        i = self._hit(ev.position())
        if i is not None:
            self._toggle(i)
            return
        x, y = self._from(ev.position())
        # on whichever copy is nearest: the point goes into the drawn piece, turned back to it
        best = None
        for k in range(self.repeat):
            a = -2 * math.pi * k / self.repeat
            xk, yk = x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a)
            side, dist = self._nearest_side(xk, yk)
            if best is None or dist < best[0]:
                best = (dist, side, xk, yk)
        _, side, xk, yk = best
        self.points.insert(side + 1, [xk, yk, False])
        self.update()
        self.finished.emit(self._copy())

    def wheelEvent(self, ev):
        if not self.big:                                   # in the settings panel the wheel scrolls the panel
            ev.ignore()
            return
        cx, cy, s, turn = self._view()
        s2 = min(max(s * 1.0015 ** ev.angleDelta().y(), 20.0), 2e6)
        pos = ev.position()
        xr, yr = cx + (pos.x() - self.width() / 2) / s, cy + (self.height() / 2 - pos.y()) / s
        self.view = (xr - (pos.x() - self.width() / 2) / s2, yr - (self.height() / 2 - pos.y()) / s2, s2, turn)
        self.by_hand = True
        self.update()

    def keyPressEvent(self, ev):
        if ev.key() in (Qt.Key_Delete, Qt.Key_Backspace) and self.hover is not None:
            self._delete(self.hover)
        elif ev.key() in (Qt.Key_F, Qt.Key_Home):
            self.fit()
        else:
            super().keyPressEvent(ev)

    def enterEvent(self, ev):
        self.inside = True
        self.update()

    def leaveEvent(self, ev):
        self.inside = False
        self.hover = None
        self.update()

    def _nearest_side(self, x, y):
        """The point after which a new point at (x, y) belongs - the nearest side of the chain - and how far."""
        P = np.array([pt[:2] for pt in self.points])
        nxt = np.roll(P, -1, axis=0)
        if self.repeat > 1:                                   # the last point joins the next copy's first
            a = 2 * math.pi / self.repeat
            nxt[-1] = P[0] @ np.array([[math.cos(a), math.sin(a)], [-math.sin(a), math.cos(a)]])
        q = np.array([x, y])
        d = nxt - P
        t = np.clip(np.einsum("ij,ij->i", q - P, d) / np.maximum(np.einsum("ij,ij->i", d, d), 1e-12), 0, 1)
        dist = np.linalg.norm(P + d * t[:, None] - q, axis=1)
        i = int(np.argmin(dist))
        return i, float(dist[i])


class OutlineWindow(QDialog):
    """The cross-section editor filling a window, with room to place the points exactly."""
    repeat_changed = Signal(int)

    def __init__(self, parent, title: str, start_menu: QMenu):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setWindowFlags((self.windowFlags() | Qt.WindowMinMaxButtonsHint) & ~Qt.WindowContextHelpButtonHint)
        self.editor = OutlineEditor(big=True)
        start = QToolButton()
        start.setText("Start from")
        start.setPopupMode(QToolButton.InstantPopup)
        start.setMenu(start_menu)
        self.repeat = QSpinBox()
        self.repeat.setRange(1, MAX_REPEAT)
        self.repeat.setKeyboardTracking(False)
        self.repeat.setToolTip("Draw one piece - one lobe, one petal - and repeat it this many times round the axis.")
        self.close_up = QToolButton()
        self.close_up.setText("One repeat close up")
        self.close_up.setCheckable(True)
        self.close_up.setToolTip("Show one repeat close up, turned to point upwards, or the whole outline.")
        fit = QPushButton("Fit")
        fit.setToolTip("Show it all again after zooming (F)")
        done = QPushButton("Done")
        done.setAutoDefault(False)
        fit.setAutoDefault(False)
        bar = QHBoxLayout()
        bar.addWidget(start)
        bar.addSpacing(12)
        bar.addWidget(QLabel("Repeat around"))
        bar.addWidget(self.repeat)
        bar.addWidget(self.close_up)
        bar.addWidget(fit)
        bar.addStretch(1)
        bar.addWidget(done)
        box = QVBoxLayout(self)
        box.addLayout(bar)
        box.addWidget(self.editor, 1)
        self.repeat.valueChanged.connect(self.repeat_changed)
        self.close_up.toggled.connect(self.editor.set_close_up)
        self.editor.view_changed.connect(self._show_view)
        fit.clicked.connect(self.editor.fit)
        done.clicked.connect(self.close)
        self.resize(1100, 850)

    def set_outline(self, points, repeat: int):
        self.repeat.blockSignals(True)
        self.repeat.setValue(int(repeat))
        self.repeat.blockSignals(False)
        self.editor.set_outline(points, repeat)

    def _show_view(self):
        self.close_up.blockSignals(True)
        self.close_up.setEnabled(self.editor.repeat > 1)
        self.close_up.setChecked(self.editor.close_up())
        self.close_up.blockSignals(False)
