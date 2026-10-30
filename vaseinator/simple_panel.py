"""Simple mode: a handful of choices made from pictures, for anyone.

How big, the shape from above, the shape from the side, the twist, a pattern
and a colour - then one big button to save the vase for printing. Everything
else lives in Advanced. Each picture sets a few settings at once; whichever
picture matches the vase as it is now is lit. A mask or helmet is sized by the
head it fits instead.
"""

from __future__ import annotations

import os
import sys

import numpy as np
from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QGridLayout, QHBoxLayout, QLabel, QPushButton,
                               QScrollArea, QSizePolicy, QSlider, QToolButton, QVBoxLayout, QWidget)

from .choices import (COLOURS, MANY_COLOURS, NO_PATTERN, PATTERNS, SHAPES_FROM_ABOVE,  # noqa: F401
                      pattern_of, twist_words)
from .params import CIRCLE, EVENLY, ONE_COLOUR, OWN, POLYGON, SAME
from .shapes import PALETTES, PROFILES, pchip, shape_table
from .spinbox import DoubleSpinBox

ACCENT = QColor(240, 163, 86)
INK = QColor(225, 230, 236)
TILE = 52                                         # picture size on the buttons

def asset(*parts) -> str | None:
    """A file in assets/, whether running from the source or the one-file app."""
    here = os.path.dirname(os.path.abspath(__file__))
    for root in (os.path.join(here, ".."), getattr(sys, "_MEIPASS", here)):
        path = os.path.join(root, "assets", *parts)
        if os.path.exists(path):
            return path
    return None


# ------------------------------------------------------------------ pictures
def _canvas(w=TILE, h=TILE):
    pm = QPixmap(w, h)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    return pm, p


def shape_icon(settings: dict) -> QIcon:
    """The shape from above, filled."""
    kind = settings.get("shape1", CIRCLE)
    r = shape_table(kind, settings.get("count1", 5), settings.get("depth1", 0.0), settings.get("sharp1", 0.5))
    a = np.arange(len(r)) * (2 * np.pi / len(r)) + np.radians(settings.get("turn1", 0.0))
    pm, p = _canvas()
    s = 0.44 * TILE
    pts = [QPointF(TILE / 2 + s * rr * np.cos(t), TILE / 2 - s * rr * np.sin(t)) for rr, t in zip(r[::4], a[::4])]
    p.setPen(QPen(ACCENT.darker(160), 1.5))
    p.setBrush(ACCENT)
    p.drawPolygon(QPolygonF(pts))
    p.end()
    return QIcon(pm)


def profile_icon(points, colour: QColor = ACCENT) -> QIcon:
    """The shape from the side: the outline, mirrored, filled."""
    pts = np.asarray(points, dtype=float)
    hs = np.linspace(0.0, 1.0, 40)
    d = np.clip(pchip(pts[:, 0], pts[:, 1], hs), 0.05, None)
    d = d / d.max()
    pm, p = _canvas()
    top, bottom, half = 4.0, TILE - 4.0, 0.36 * TILE
    ys = bottom - hs * (bottom - top)
    left = [QPointF(TILE / 2 - half * w, y) for w, y in zip(d, ys)]
    right = [QPointF(TILE / 2 + half * w, y) for w, y in zip(d[::-1], ys[::-1])]
    p.setPen(QPen(colour.darker(160), 1.5))
    p.setBrush(colour)
    p.drawPolygon(QPolygonF(left + right))
    p.end()
    return QIcon(pm)


def pattern_icon(name: str) -> QIcon:
    """A little vase body with the pattern drawn on it."""
    pm, p = _canvas()
    body = QRectF(10, 4, TILE - 20, TILE - 8)
    path = QPainterPath()
    path.addRoundedRect(body, 6, 6)
    p.setPen(QPen(ACCENT.darker(160), 1.5))
    p.setBrush(ACCENT)
    p.drawPath(path)
    p.setClipPath(path)
    pen = QPen(ACCENT.darker(185), 2.2, Qt.SolidLine, Qt.RoundCap)
    p.setPen(pen)
    l, r, t, b = body.left(), body.right(), body.top(), body.bottom()
    if name == "Ribs":
        for x in np.linspace(l + 4, r - 4, 6):
            p.drawLine(QPointF(x, t), QPointF(x, b))
    elif name in ("Spiral ribs", "Diamonds"):
        for x in np.linspace(l - 30, r + 4, 9):
            p.drawLine(QPointF(x, b), QPointF(x + 26, t))
            if name == "Diamonds":
                p.drawLine(QPointF(x, t), QPointF(x + 26, b))
    elif name == "Rings":
        for y in np.linspace(t + 5, b - 5, 6):
            p.drawLine(QPointF(l, y), QPointF(r, y))
    elif name == "Bumps":
        p.setPen(Qt.NoPen)
        p.setBrush(ACCENT.darker(150))
        for row, y in enumerate(np.linspace(t + 6, b - 6, 6)):
            for x in np.linspace(l + 5 + (row % 2) * 3, r - 5, 4):
                p.drawEllipse(QPointF(x, y), 2.2, 2.2)
    elif name == "Lumpy":
        p.setPen(Qt.NoPen)
        p.setBrush(ACCENT.darker(135))
        for x, y, rr in ((18, 12, 5), (31, 18, 6), (21, 30, 7), (34, 37, 5), (17, 44, 4)):
            p.drawEllipse(QPointF(x, y), rr, rr)
    elif name in ("Voronoi holes", "Round holes"):         # holes right through: cut out of the picture
        p.setCompositionMode(QPainter.CompositionMode_Clear)
        p.setPen(Qt.NoPen)
        p.setBrush(Qt.black)
        if name == "Round holes":
            for row, y in enumerate(np.linspace(t + 7, b - 7, 4)):
                for x in np.linspace(l + 6 + (row % 2) * 4, r - 6, 3):
                    p.drawEllipse(QPointF(x, y), 3.0, 3.0)
        else:
            cells = [[(14, 8), (22, 6), (25, 13), (19, 18), (13, 15)], [(28, 9), (35, 7), (38, 15), (31, 19)],
                     [(13, 22), (21, 22), (23, 30), (15, 33)], [(27, 24), (36, 22), (38, 31), (29, 33)],
                     [(15, 38), (24, 37), (25, 45), (14, 46)], [(29, 38), (37, 37), (36, 46), (28, 45)]]
            for cell in cells:
                p.drawPolygon(QPolygonF([QPointF(x, y) for x, y in cell]))
        p.setCompositionMode(QPainter.CompositionMode_SourceOver)
    elif name == "Gem":
        pen.setWidth(1)
        p.setPen(QPen(ACCENT.darker(185), 1.3))
        for y in np.linspace(t, b, 5):
            p.drawLine(QPointF(l, y), QPointF(r, y))
        for k, y in enumerate(np.linspace(t, b, 5)[:-1]):
            for x in np.linspace(l - 8 + 4 * (k % 2), r, 4):
                p.drawLine(QPointF(x, y), QPointF(x + 8, y + (b - t) / 4))
    p.end()
    return QIcon(pm)


def colour_icon(colours) -> QIcon:
    """A round swatch: one colour, or bands of several."""
    pm, p = _canvas(40, 40)
    path = QPainterPath()
    path.addEllipse(QRectF(3, 3, 34, 34))
    p.setClipPath(path)
    n = len(colours)
    for k, c in enumerate(colours):
        p.fillRect(QRectF(0, 40 - 40 * (k + 1) / n, 40, 40 / n + 0.5), QColor(c))
    p.setClipping(False)
    p.setPen(QPen(QColor(20, 22, 26), 1.5))
    p.setBrush(Qt.NoBrush)
    p.drawEllipse(QRectF(3, 3, 34, 34))
    p.end()
    return QIcon(pm)


# ------------------------------------------------------------------ widgets
class PictureChoice(QWidget):
    """A grid of picture buttons, at most one of them lit."""
    picked = Signal(int)

    def __init__(self, items, columns: int, icon: QSize = QSize(TILE, TILE), text: bool = True):
        super().__init__()
        grid = QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(6)
        self.buttons = []
        for i, (name, ic, tip) in enumerate(items):
            b = QToolButton()
            b.setObjectName("pictureButton")
            b.setCheckable(True)
            b.setIcon(ic)
            b.setIconSize(icon)
            if text:
                b.setText(name)
                b.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
            b.setToolTip(tip or name)
            b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            b.clicked.connect(lambda _=False, k=i: self._click(k))
            grid.addWidget(b, i // columns, i % columns)
            self.buttons.append(b)

    def _click(self, k):
        self.light(k)
        self.picked.emit(k)

    def light(self, k):
        for i, b in enumerate(self.buttons):
            b.setChecked(i == k)


def _title(text: str) -> QLabel:
    """A section's title: bold and bigger, set by the theme so it grows with Bigger text."""
    lab = QLabel(text)
    lab.setObjectName("simpleTitle")
    return lab


class SimplePanel(QWidget):
    """The Simple settings: pictures and a few numbers. It asks the window to make each change."""
    param = Signal(str, object)          # one setting: (key, value)
    live = Signal(str, object)           # ... while a slider is being dragged
    changes = Signal(dict)               # several settings at once
    choose_design = Signal()
    surprise = Signal()
    draw_own = Signal()
    save = Signal()
    advanced = Signal()

    def __init__(self):
        super().__init__()
        v = QVBoxLayout(self)
        v.setContentsMargins(4, 4, 4, 4)
        v.setSpacing(8)

        # the design: its name, pick another, or a surprise
        self.name = _title("")
        self.name.setWordWrap(True)
        v.addWidget(self.name)
        row = QHBoxLayout()
        pick = QPushButton("Choose a design…")
        pick.setObjectName("bigButton")
        pick.setToolTip("Pictures of every ready-made vase, and a plain cylinder to start from")
        pick.clicked.connect(self.choose_design)
        dice = QPushButton("Surprise me")
        dice.setObjectName("bigButton")
        dice.setToolTip("A new random vase that still prints")
        dice.clicked.connect(self.surprise)
        row.addWidget(pick, 3)
        row.addWidget(dice, 2)
        v.addLayout(row)

        # how big: tall and wide - or, for a mask or helmet, the head it fits
        v.addWidget(_title("How big"))
        self.size_row = QWidget()
        size = QGridLayout(self.size_row)
        size.setContentsMargins(0, 0, 0, 0)
        self.tall, self.wide = DoubleSpinBox(), DoubleSpinBox()
        for box, key, lo in ((self.tall, "height", 2.0), (self.wide, "widest", 1.0)):
            box.setDecimals(1)
            box.setRange(lo, 100.0)
            box.setSingleStep(1.0)
            box.setSuffix(" cm")
            box.setKeyboardTracking(False)
            box.setMinimumHeight(30)
            box.valueChanged.connect(lambda val, k=key: self.param.emit(k, round(float(val) * 10.0, 1)))
        self.tall.setToolTip("How tall the vase is, from the table to the rim")
        self.wide.setToolTip("How wide it is at its widest; the whole shape grows or shrinks with it")
        size.addWidget(QLabel("Tall"), 0, 0)
        size.addWidget(self.tall, 0, 1)
        size.addWidget(QLabel("Wide"), 0, 2)
        size.addWidget(self.wide, 0, 3)
        size.setColumnStretch(1, 1)
        size.setColumnStretch(3, 1)
        v.addWidget(self.size_row)
        self.head_row = QWidget()
        head = QHBoxLayout(self.head_row)
        head.setContentsMargins(0, 0, 0, 0)
        self.head = DoubleSpinBox()
        self.head.setDecimals(1)
        self.head.setRange(30.0, 90.0)
        self.head.setSingleStep(0.5)
        self.head.setSuffix(" cm round")
        self.head.setKeyboardTracking(False)
        self.head.setMinimumHeight(30)
        self.head.setToolTip("Measure round the head, above the eyebrows and ears, as for a hat (an adult: about "
                             "54 to 60 cm).\nThe whole mask or helmet grows or shrinks to fit, with a centimetre "
                             "to spare.")
        self.head.valueChanged.connect(lambda val: self.param.emit("head", float(val)))
        head.addWidget(QLabel("Head size"))
        head.addWidget(self.head, 1)
        v.addWidget(self.head_row)

        # the shape from above, and your own
        v.addWidget(_title("Shape from above"))
        self.above = PictureChoice([(n, shape_icon(s), None) for n, s in SHAPES_FROM_ABOVE], 4)
        self.above.picked.connect(lambda k: self.changes.emit(
            {"shape2": SAME, "turn1": 0.0, **SHAPES_FROM_ABOVE[k][1]}))
        v.addWidget(self.above)
        own = QPushButton("Draw my own shape…")
        own.setToolTip("Draw the shape from above yourself, in a big window")
        own.clicked.connect(self.draw_own)
        v.addWidget(own)

        # the shape from the side
        self.side_title = _title("Shape from the side")
        v.addWidget(self.side_title)
        names = [n.split(" (")[0] for n, _ in PROFILES]
        self.side = PictureChoice([(n, profile_icon(pts), full) for n, (full, pts) in zip(names, PROFILES)], 4)
        self.side.picked.connect(lambda k: self.param.emit("profile", k))
        v.addWidget(self.side)

        # the twist
        v.addWidget(_title("Twist"))
        trow = QHBoxLayout()
        self.twist = QSlider(Qt.Horizontal)
        self.twist.setRange(0, 24)                 # 15 degrees a step, up to two whole turns
        self.twist.setPageStep(6)
        self.twist.setToolTip("How far the shape turns from the bottom to the top")
        self.twist_label = QLabel()
        self.twist_label.setMinimumWidth(150)
        self.twist.valueChanged.connect(self._twisting)
        self.twist.sliderReleased.connect(lambda: self._twist_done())
        trow.addWidget(self.twist, 1)
        trow.addWidget(self.twist_label)
        v.addLayout(trow)

        # a pattern
        v.addWidget(_title("Pattern"))
        self.pattern = PictureChoice([(n, pattern_icon(n), None) for n, _ in PATTERNS], 4)
        self.pattern.picked.connect(lambda k: self.changes.emit({**NO_PATTERN, **PATTERNS[k][1]}))
        v.addWidget(self.pattern)

        # a colour
        v.addWidget(_title("Colour"))
        pals = dict(PALETTES)
        items = [(n, colour_icon([c]), n) for n, c in COLOURS]
        items += [(n, colour_icon(pals[pal][:3]), f"{n} of colour ({pal})") for n, pal, _ in MANY_COLOURS]
        self.colour = PictureChoice(items, 7, QSize(32, 32), text=False)
        self.colour.picked.connect(self._colour)
        v.addWidget(self.colour)

        # save it, or go further
        save = QPushButton("Save for printing…")
        save.setObjectName("saveButton")
        save.setToolTip("Save the vase as a file for your printer's slicer, with how to print it")
        save.setMinimumHeight(48)
        save.clicked.connect(self.save)
        v.addSpacing(6)
        v.addWidget(save)
        more = QPushButton("More settings (Advanced)…")
        more.setFlat(True)
        more.setToolTip("Every setting: curves, patterns, colours, printing")
        more.clicked.connect(self.advanced)
        v.addWidget(more)
        v.addStretch(1)
        self._twist_style = EVENLY

    # ---------------------------------------------------------- choices
    def _twisting(self, step):
        deg = 15.0 * step
        self.twist_label.setText(twist_words(deg))
        if self.twist.isSliderDown():
            self.live.emit("twist", deg)
        else:
            self._twist_done()

    def _twist_done(self):
        deg = 15.0 * self.twist.value()
        change = {"twist": deg}
        if self._twist_style == OWN:                   # a twist drawn by hand: back to an even one
            change["twist_style"] = EVENLY
        self.changes.emit(change)

    def show_head(self, cm: float):
        """The head the design fits, as built."""
        self.head.blockSignals(True)
        self.head.setValue(cm)
        self.head.blockSignals(False)

    def _colour(self, k):
        if k < len(COLOURS):
            self.changes.emit(dict(colour_style=ONE_COLOUR, color1=COLOURS[k][1]))
        else:
            name, pal, change = MANY_COLOURS[k - len(COLOURS)]
            cols = dict(PALETTES)[pal]
            self.changes.emit({**change, **{f"color{i + 1}": c for i, c in enumerate(cols)}})

    # ---------------------------------------------------------- showing the vase as it is
    def refresh(self, p, widest: float, title: str = ""):
        """Show the settings of ``p``: its title, the numbers, and light the pictures that match it."""
        name = p.name.replace("_", " ").strip()
        self.name.setText(title or (name[:1].upper() + name[1:]) or "Your vase")
        # a mask or helmet: sized by the head, its shape from the side its own
        self.head_row.setVisible(p.worn)
        for w in (self.size_row, self.side_title, self.side):
            w.setVisible(not p.worn)
        for box, mm in ((self.tall, p.height), (self.wide, widest)):
            box.blockSignals(True)
            box.setValue(round(mm / 10.0, 1))
            box.blockSignals(False)
        # the same kind of shape; polygons by their number of sides too
        self.above.light(next((i for i, (_, s) in enumerate(SHAPES_FROM_ABOVE)
                               if p.shape2 == SAME and p.shape1 == s["shape1"]
                               and (p.shape1 != POLYGON or p.count1 == s["count1"])), None))
        self.side.light(p.profile if 0 <= p.profile < len(PROFILES) else None)
        self._twist_style = p.twist_style
        self.twist.blockSignals(True)
        self.twist.setValue(int(round(min(max(p.twist, 0.0), 360.0) / 15.0)))
        self.twist.blockSignals(False)
        self.twist_label.setText(twist_words(p.twist) if p.twist_style != OWN else "Your own curve")
        self.pattern.light(pattern_of(p))
        if p.colour_style == ONE_COLOUR:
            self.colour.light(next((i for i, (_, c) in enumerate(COLOURS) if c.lower() == p.color1.lower()), None))
        else:
            self.colour.light(next((len(COLOURS) + i for i, (_, _, ch) in enumerate(MANY_COLOURS)
                                    if ch["colour_style"] == p.colour_style), None))


class GalleryDialog(QDialog):
    """Every ready-made vase as a picture to click, with a plain cylinder first."""

    def __init__(self, parent, entries):
        """entries: [(title, about, picture path or None, fallback icon)]"""
        super().__init__(parent)
        self.setWindowTitle("Choose a design")
        self.chosen = None
        inner = QWidget()
        grid = QGridLayout(inner)
        grid.setSpacing(10)
        columns = 5
        for i, (title, about, path, fallback) in enumerate(entries):
            b = QToolButton()
            b.setObjectName("pictureButton")
            b.setText(title)
            b.setToolTip(about)
            b.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
            b.setIcon(QIcon(path) if path else fallback)
            b.setIconSize(QSize(150, 190))
            b.setMinimumWidth(176)
            b.clicked.connect(lambda _=False, t=title: self._choose(t))
            grid.addWidget(b, i // columns, i % columns)
        scroll = QScrollArea()
        scroll.setWidget(inner)
        scroll.setWidgetResizable(True)
        box = QVBoxLayout(self)
        box.addWidget(QLabel("Click a vase to start from it. Your printer settings are kept, and "
                             "Undo takes you back."))
        box.addWidget(scroll, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.Cancel)
        buttons.rejected.connect(self.reject)
        box.addWidget(buttons)
        self.resize(1000, 760)

    def _choose(self, title):
        self.chosen = title
        self.accept()
