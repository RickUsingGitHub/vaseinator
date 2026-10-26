"""Vaseinator - main window."""

from __future__ import annotations

import math
import os
import random
import sys
import time

import numpy as np
from PySide6.QtCore import QSettings, QSize, Qt, QTimer
from PySide6.QtGui import (QAction, QColor, QFontDatabase, QIcon, QKeySequence, QPainter, QPalette, QPen,
                           QPixmap, QSurfaceFormat)
from PySide6.QtWidgets import (QApplication, QCheckBox, QColorDialog, QComboBox, QDialog, QDialogButtonBox,
                               QDoubleSpinBox, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QLabel,
                               QLineEdit, QMainWindow, QMenu, QMessageBox, QPlainTextEdit, QPushButton,
                               QScrollArea, QSizePolicy, QSlider, QSpinBox, QSplitter, QStyle, QTextBrowser,
                               QToolButton, QVBoxLayout, QWidget)

from . import __version__
from .curves import CurveEditor
from .expr import EXAMPLES, FUNCTION_HELP, VARIABLES
from .geometry import VaseDesign, duration
from .params import (BANDS, CIRCLE, EASE, EVENLY, FILAMENTS, GLOSSY, GRADIENT, MATTE, ONE_COLOUR, OWN,
                     OWN_PROFILE, POLYGON, SAME, SHAPES, SILK, SLOW_DOWN, SPEED_UP, STRIPES, SWING, TRANSLUCENT,
                     VaseParams, load_design, save_design)
from .plots import ShapePlots
from .presets import GALLERY, gallery_design, outline, palette, surprise
from .shapes import (PALETTES, PROFILES, SHAPE_LABELS, SHAPE_NAMES, change, progress, sample_points, strength,
                     strength_names, style_names)
from .stl import write_stl
from .threemf import TemplateError, read_template, spiral_settings, write_3mf, write_project_3mf
from .viewer import Viewer3D, spin_transform

APP_NAME = "Vaseinator"
FILE_EXT = ".vase"
VASE, SECTION, OVERHANGS, PRINT_LAYOUT = 0, 1, 2, 3
VIEW_NAMES = ("Vase", "Section", "Overhangs", "Print layout")
SPIN_SPEED = 30.0          # degrees a second, on the turntable

PROFILE_CHOICES = [(i, name) for i, (name, _) in enumerate(PROFILES)] + [(OWN_PROFILE, "Your own (drawn below)")]
SHAPE_CHOICES = [(k, SHAPE_NAMES[k]) for k in SHAPES]
TWIST_STYLES = list(style_names().items())
MORPH_STYLES = [(EVENLY, "Evenly"), (EASE, "Eases in and out"), (SLOW_DOWN, "Mostly near the bottom"),
                (SPEED_UP, "Mostly near the top"), (SWING, "Back and forth"), (OWN, "Your own curve")]
STRENGTHS = list(strength_names().items())
COLOUR_STYLES = [(ONE_COLOUR, "One colour"), (BANDS, "Bands up the vase"), (STRIPES, "Stripes"),
                 (GRADIENT, "Gradient spool")]
LOOKS = [(MATTE, "Matte"), (SILK, "Silk"), (GLOSSY, "Glossy"), (TRANSLUCENT, "Translucent")]
USED = [(2, "Two"), (3, "Three"), (4, "Four")]


def _shape(k: int) -> tuple:
    """The settings of the bottom (1) or top (2) cross-section."""
    first = k == 1
    return [
        (f"shape{k}", "Cross-section" if first else "Turns into", "choice",
         SHAPE_CHOICES if first else [(SAME, "Stays the same")] + SHAPE_CHOICES, None, None, "",
         "The shape of the vase seen from above, at the bottom." if first else
         "A second shape that the first one turns into on the way up - or the same shape all the way."),
        (f"count{k}", "Sides", "int", 1, 99, 1, "", "How many sides, points, petals or teeth."),
        (f"depth{k}", "Depth", "pct", 0.0, 90.0, 1.0, " %",
         "How far in the shape cuts between its points or petals, as a share of the radius."),
        (f"sharp{k}", "Sharpness", "pct", 0.0, 100.0, 5.0, " %",
         "Polygon: how round the corners are. Star: from soft waves to sharp points.\n"
         "Flower: from fat round petals to narrow ones. Gear: how wide the teeth are."),
        (f"turn{k}", "Turned", "float", -180.0, 180.0, 5.0, "°", "Turn the shape round the axis."),
    ]


# (key, label, kind, min, max, step, suffix/special, tooltip)
SPEC = [
    ("Size", [
        ("height", "Height", "float", 5.0, 1000.0, 5.0, " mm", "Height of the vase, from the bed to the rim."),
        ("widest", "Widest", "widest", 4.0, 1000.0, 5.0, " mm",
         "Diameter at the widest point of the outline. Changing it scales the whole outline;\n"
         "shapes and patterns add to it."),
        ("profile", "Outline", "choice", PROFILE_CHOICES, None, None, "",
         "The shape of the vase from the side. Pick one to start from, then drag its points\n"
         "in the curve below (Detailed) to make it your own."),
        ("silhouette", "", "curve", dict(lo=0.0, hi=140.0, unit=" mm", mirror=True, height=170, floor=4.0,
                                          grow=True, decimals=0), None, None, "",
         "The outline: diameter at each height. Drag the points; double-click to add one,\n"
         "right-click to take one away. The curve through them never overshoots."),
    ]),
    ("Shape", _shape(1) + _shape(2) + [
        ("morph", "Change happens", "choice", MORPH_STYLES, None, None, "",
         "How the first shape turns into the second on the way up. Back and forth changes\n"
         "smoothly to the second shape and back again, as many times as you like."),
        ("morph_swings", "Changes", "int", 1, 40, 1, "",
         "How many times the shape changes on the way up, back and forth.\n"
         "3: bottom shape → top shape → bottom shape → top shape."),
        ("morph_curve", "", "curve", dict(lo=0.0, hi=1.0, unit="", height=110, decimals=2), None, None, "",
         "How far the shape has changed at each height, from the bottom of the vase on the left to the\n"
         "top on the right: 0 (down) is the bottom shape, 1 (up) the top one. Drag a point down to\n"
         "go back towards the bottom shape; double-click to add points for a wave."),
    ]),
    ("Spin", [
        ("twist", "Twist", "float", -3600.0, 3600.0, 15.0, "°",
         "How far the shape turns round from the bottom to the top. A back-and-forth twist\n"
         "swings this far each way."),
        ("twist_style", "Twist goes", "choice", TWIST_STYLES, None, None, "",
         "How the turning is spread up the vase: evenly, easing in and out, speeding up,\n"
         "slowing down, swinging back and forth, or along your own curve."),
        ("swings", "Swings", "int", 1, 40, 1, "", "How many times a back-and-forth twist changes direction."),
        ("twist_curve", "", "curve", dict(lo=-180.0, hi=180.0, unit="°", height=110, grow=True, decimals=0),
         None, None, "", "How far the shape has turned at each height, in degrees."),
        ("lattice", "Both ways", "bool", None, None, None, "",
         "Twist the shape both ways at once and keep whichever sticks out further: the\n"
         "ridges cross, making a lattice. Try a polygon or a star."),
    ]),
    ("Surface", [
        ("rib_count", "Ribs", "int", 0, 400, 1, "|None", "Ribs running up the vase."),
        ("rib_depth", "Rib depth", "float", -10.0, 10.0, 0.1, " mm",
         "How far the ribs stand out (+), or how deep they cut in as grooves (-)."),
        ("rib_sharp", "Rib shape", "pct", 0.0, 100.0, 5.0, " %", "0 %: smooth flutes. 100 %: narrow ridges."),
        ("rib_lean", "Ribs spiral", "float", -7200.0, 7200.0, 15.0, "°",
         "The ribs wind this far round the vase on the way up, on top of any twist."),
        ("rib_cross", "Ribs cross", "bool", None, None, None, "",
         "A second set of ribs winds the other way: diamond knurling."),
        ("ring_count", "Rings", "int", 0, 400, 1, "|None", "Rings round the vase, evenly up it."),
        ("ring_depth", "Ring depth", "float", -10.0, 10.0, 0.1, " mm", "How far the rings stand out (+) or cut in (-)."),
        ("ring_sharp", "Ring shape", "pct", 0.0, 100.0, 5.0, " %", "0 %: gentle waves. 100 %: narrow beads."),
        ("bump_around", "Bumps around", "int", 0, 200, 1, "|None", "Bumps in staggered rows: how many round the vase."),
        ("bump_up", "Bumps up", "int", 1, 200, 1, "", "... and how many rows up it."),
        ("bump_depth", "Bump depth", "float", -10.0, 10.0, 0.1, " mm", "How far the bumps stand out (+) or dimple in (-)."),
        ("organic_depth", "Organic", "float", 0.0, 20.0, 0.1, " mm|None",
         "Smooth random lumps all over: how far they go in and out."),
        ("organic_scale", "Lump size", "float", 3.0, 300.0, 1.0, " mm", "The size of one lump."),
        ("organic_seed", "Lump pattern", "seed", 0, 99999, 1, "", "Another number, another pattern of lumps."),
        ("texture_twist", "Turn with the twist", "bool", None, None, None, "",
         "The patterns turn with the shape's twist. Off: they stay square to the bed."),
        ("strength", "Strength", "choice", STRENGTHS, None, None, "", "How strong the patterns are on the way up."),
        ("strength_curve", "", "curve", dict(lo=0.0, hi=1.5, unit="×", height=100, decimals=2), None, None, "",
         "How strong the patterns are at each height (1 = as set)."),
        ("fade_foot", "Plain foot", "float", 0.0, 200.0, 0.5, " mm|None",
         "The patterns fade out over this much at the bottom, for a clean foot."),
        ("fade_rim", "Plain rim", "float", 0.0, 200.0, 0.5, " mm|None",
         "The patterns fade out over this much at the top, for a clean rim."),
    ]),
    ("Low-poly", [
        ("facets", "Flat facets", "bool", None, None, None, "",
         "Make the whole vase from flat triangles, like a cut gem. The shape and patterns\n"
         "are sampled at the corners of the facets."),
        ("facets_around", "Facets around", "int", 3, 400, 1, "", "How many facets round the vase."),
        ("facets_up", "Facets up", "int", 1, 400, 1, "", "How many rows of facets up the vase."),
        ("facet_rough", "Rough cut", "pct", 0.0, 100.0, 5.0, " %", "Move the corners about for a rougher, hand-cut look."),
        ("facet_seed", "Cut pattern", "seed", 0, 99999, 1, "", "Another number, another rough cut."),
    ]),
    ("Your own function", [
        ("expression", "", "expr", None, None, None, "",
         "A formula added to the radius, in mm. Variables: theta (angle round, radians),\n"
         "phi (the angle turning with the twist), z (height, mm), h (0 at the bottom, 1 at\n"
         "the top), r (the radius so far) and H (the height). Help lists the functions."),
    ]),
    ("Colours", [
        ("palette", "Palette", "palette", None, None, None, "", "Set all four filament colours from a palette."),
        ("color1", "Filament 1", "color", None, None, None, "",
         "Colour of filament 1. Load the same colour in slot 1 of the slicer."),
        ("color2", "Filament 2", "color", None, None, None, "", "Colour of filament 2."),
        ("color3", "Filament 3", "color", None, None, None, "", "Colour of filament 3."),
        ("color4", "Filament 4", "color", None, None, None, "", "Colour of filament 4."),
        ("colour_style", "Colours", "choice", COLOUR_STYLES, None, None, "",
         "One colour; bands of colour up the vase; thin stripes; or a gradient spool (one\n"
         "filament that changes colour along its length - shown as it will come out, by\n"
         "how much filament each height uses).\n"
         "Bands and stripes change filament at a layer: the panel lists each change."),
        ("colours_used", "Filaments", "choice", USED, None, None, "", "How many filaments the colours go through, from 1."),
        ("band_count", "Bands", "int", 2, 64, 1, "", "How many bands of colour, bottom to top."),
        ("band_spacing", "Band sizes", "slider", -1.0, 1.0, 0.01, "",
         "Even bands in the middle; slide left for thicker bands at the bottom, right for\n"
         "thicker bands at the top."),
        ("stripe_height", "Stripe height", "float", 0.2, 500.0, 1.0, " mm", "Height of each stripe."),
        ("gradient_length", "Colour cycle", "float", 0.1, 1000.0, 0.5, " m",
         "Metres of filament for one full cycle of the gradient spool's colours\n"
         "(see the spool's label; often 5 to 20 m)."),
        ("look", "Looks like", "choice", LOOKS, None, None, "", "How the filament looks in the 3D view."),
    ]),
    ("Printing", [
        ("slicer_template", "Slicer settings", "template", None, None, None, "",
         "A project you saved in Flash Studio (or OrcaSlicer or Bambu Studio) for your printer and\n"
         "filaments - File ▸ Save Project there. Export 3MF then writes a project on those settings,\n"
         "with spiral vase mode on and the colour bands as filament (tool) changes at their layers:\n"
         "open it in the slicer with File ▸ Open, ready to slice. Remembered for every design.\n"
         "Without one, Export 3MF writes the shape only."),
        ("max_overhang", "Steepest overhang", "float", 10.0, 70.0, 1.0, "°",
         "How far the wall may lean from upright, out or in. A spiral wall is one line wide,\n"
         "so it leans on the line beneath it either way. 45° prints on almost any printer."),
        ("soften", "Soften to fit", "bool", None, None, None, "",
         "Soften any part that leans more than that until it prints without supports. The\n"
         "panel says how far the surface was moved. Off: the Overhangs view shows the\n"
         "faces that would need support in red."),
        ("line_width", "Line width", "float", 0.2, 2.5, 0.02, " mm",
         "The slicer's spiral (outer wall) line width: the wall's thickness. 0.6 to 0.8 mm on\n"
         "a 0.4 mm nozzle makes a stronger wall that holds water better."),
        ("layer_height", "Layer height", "float", 0.04, 1.0, 0.02, " mm", "The layer height you will slice with."),
        ("bottom", "Solid bottom", "float", 0.2, 20.0, 0.2, " mm",
         "The solid floor the slicer prints first. Set the slicer's bottom layers to match:\n"
         "the panel gives the number."),
        ("printer_height", "Printer height", "float", 20.0, 2000.0, 5.0, " mm", "The tallest part the printer can make."),
        ("bed_x", "Bed width", "float", 30.0, 2000.0, 5.0, " mm", "Width of the printer bed."),
        ("bed_y", "Bed depth", "float", 30.0, 2000.0, 5.0, " mm", "Depth of the printer bed."),
        ("speed", "Print speed", "float", 5.0, 1000.0, 5.0, " mm/s", "The spiral wall's speed, for the print time."),
        ("max_flow", "Max flow", "float", 1.0, 200.0, 1.0, " mm³/s",
         "The most plastic the hot end can melt: it caps the speed of a wide line."),
        ("filament_d", "Filament", "float", 1.0, 3.5, 0.05, " mm", "Filament diameter."),
        ("density", "Density", "float", 0.5, 3.0, 0.01, " g/cm³", "PLA 1.24, PETG 1.27, ABS 1.04, TPU 1.21."),
        ("facet_size", "Mesh detail", "float", 0.15, 5.0, 0.05, " mm",
         "Spacing of the points on the surface: smaller is smoother but slower, and a bigger\n"
         "file. Shapes and patterns get enough points of their own."),
    ]),
]

SIMPLE_KEYS = {"height", "widest", "profile", "shape1", "count1", "depth1", "sharp1", "shape2", "count2",
               "morph", "morph_swings", "twist",
               "twist_style", "lattice", "rib_count", "rib_depth", "ring_count", "ring_depth", "bump_around",
               "organic_depth", "facets", "palette", "color1", "color2", "color3", "color4", "colour_style",
               "colours_used", "band_count", "look", "slicer_template", "max_overhang", "soften", "line_width",
               "layer_height"}
REMEMBERED = ("line_width", "layer_height", "bottom", "printer_height", "bed_x", "bed_y", "speed", "max_flow",
              "filament_d", "density", "max_overhang")
LIVE_KEYS = {"band_spacing"}            # sliders: follow the hand with quick draft builds
TEXT_KEYS = {"expression"}


def swatch(color: str, size: int = 14) -> QIcon:
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setPen(QPen(QColor(20, 22, 26), 1))
    p.setBrush(QColor(color))
    p.drawRect(0, 0, size - 1, size - 1)
    p.end()
    return QIcon(pm)


def palette_icon(colours) -> QIcon:
    pm = QPixmap(56, 14)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    for k, c in enumerate(colours):
        p.setPen(QPen(QColor(20, 22, 26), 1))
        p.setBrush(QColor(c))
        p.drawRect(k * 14, 0, 13, 13)
    p.end()
    return QIcon(pm)


def glyph_icon(kind: str) -> QIcon:
    """Small light line icons that read well on the dark theme."""
    from PySide6.QtCore import QPointF, QRectF

    pm = QPixmap(64, 64)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor(225, 230, 236), 5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)
    if kind == "export":
        p.drawLine(QPointF(32, 8), QPointF(32, 40))
        p.drawPolyline([QPointF(19, 28), QPointF(32, 41), QPointF(45, 28)])
        p.drawPolyline([QPointF(10, 40), QPointF(10, 54), QPointF(54, 54), QPointF(54, 40)])
    elif kind == "picture":
        p.drawRoundedRect(QRectF(8, 14, 48, 38), 4, 4)
        pen.setColor(QColor(240, 163, 86))
        p.setPen(pen)
        p.drawPolyline([QPointF(14, 44), QPointF(26, 30), QPointF(34, 38), QPointF(42, 26), QPointF(50, 38)])
    elif kind == "dice":
        p.drawRoundedRect(QRectF(10, 10, 44, 44), 9, 9)
        p.setBrush(QColor(240, 163, 86))
        p.setPen(Qt.NoPen)
        for x, y in ((22, 22), (42, 22), (32, 32), (22, 42), (42, 42)):
            p.drawEllipse(QPointF(x, y), 4.5, 4.5)
    elif kind == "gallery":
        pen.setColor(QColor(240, 163, 86))
        p.setPen(pen)
        p.drawPolyline([QPointF(20, 8), QPointF(20, 16), QPointF(12, 34), QPointF(16, 56), QPointF(48, 56),
                        QPointF(52, 34), QPointF(44, 16), QPointF(44, 8)])
        p.drawLine(QPointF(16, 8), QPointF(48, 8))
    elif kind in ("undo", "redo"):
        sx = 1 if kind == "undo" else -1
        cx = 32
        p.drawArc(QRectF(14, 18, 36, 32), (0 if sx > 0 else 180) * 16, (180 if sx > 0 else -180) * 16)
        tip = QPointF(cx - sx * 18, 34)
        p.drawPolyline([QPointF(tip.x() - sx * 7, 25), tip, QPointF(tip.x() + sx * 9, 28)])
    p.end()
    return QIcon(pm)


def make_app_icon() -> QIcon:
    here = os.path.dirname(os.path.abspath(__file__))
    for cand in (os.path.join(here, "..", "assets", "icon.png"),
                 os.path.join(getattr(sys, "_MEIPASS", here), "assets", "icon.png")):
        if os.path.exists(cand):
            return QIcon(cand)
    return QIcon()


class ElidedButton(QPushButton):
    """A button whose text is shortened in the middle to fit, however narrow the panel gets."""

    def __init__(self):
        super().__init__()
        self.full = ""
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)

    def set_full_text(self, text: str):
        self.full = text
        self._fit()

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self._fit()

    def _fit(self):
        self.setText(self.fontMetrics().elidedText(self.full, Qt.ElideMiddle, max(self.width() - 18, 40)))


class FunctionHelp(QDialog):
    """What a formula can use, with examples to try."""

    def __init__(self, parent, insert):
        super().__init__(parent)
        self.setWindowTitle("Your own function")
        self.resize(640, 560)
        text = QTextBrowser()
        rows = "".join(f"<tr><td><code>{k}</code></td><td>{v}</td></tr>" for k, v in VARIABLES.items())
        funcs = "".join(f"<tr><td><code>{k}</code></td><td>{v}</td></tr>" for k, v in FUNCTION_HELP)
        text.setHtml(
            "<style>td{padding:2px 8px;vertical-align:top;} code{color:#f0a356;}</style>"
            "<p>Type a formula in millimetres; it is <b>added to the radius</b> everywhere on the vase. "
            "The vase is still softened afterwards, so even a wild formula prints without supports.</p>"
            f"<h4>Variables</h4><table>{rows}<tr><td><code>pi tau e</code></td><td>the constants</td></tr></table>"
            f"<h4>Functions</h4><table>{funcs}</table>"
            "<h4>Tips</h4><ul>"
            "<li>Use whole numbers with the angle - <code>sin(5*theta)</code> - so the pattern meets itself "
            "round the back.</li>"
            "<li><code>phi</code> turns with the twist, so <code>sin(8*phi)</code> makes ribs that twist "
            "with the shape.</li>"
            "<li>For seamless noise, feed it the angle as a circle: "
            "<code>noise(4*cos(theta), 4*sin(theta), z/15)</code>.</li>"
            "<li><code>h</code> runs 0 to 1 up the vase, so <code>sin(pi*h)</code> is 0 at the ends and 1 in "
            "the middle - good for fading things in and out.</li></ul>")
        box = QVBoxLayout(self)
        box.addWidget(text)
        row = QHBoxLayout()
        row.addWidget(QLabel("Try an example:"))
        pick = QComboBox()
        for name, formula in EXAMPLES:
            pick.addItem(name, formula)
        row.addWidget(pick, 1)
        use = QPushButton("Use it")
        use.clicked.connect(lambda: (insert(pick.currentData()), self.accept()))
        row.addWidget(use)
        box.addLayout(row)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        box.addWidget(buttons)


class MainWindow(QMainWindow):
    def __init__(self, settings: QSettings | None = None):
        super().__init__()
        self.settings = settings or QSettings("Vaseinator", "Vaseinator")
        self.simple_mode = self.settings.value("simple_mode", True, type=bool)
        self.params = self._fresh_params()
        self.design: VaseDesign | None = None
        self.current_file = None
        self.view = VASE
        self._free_camera = False
        self._fitted = None
        self._dirty = False
        self.widgets = {}
        self.labels = {}
        self.slider_notes = {}
        self.history: list[dict] = []
        self.future: list[dict] = []
        self.spin_angle = 0.0
        self.spinning = self.settings.value("spin", True, type=bool)
        self.template_path = str(self.settings.value("slicer_template", "") or "")
        self._load_template(self.template_path)          # a slicer project to build 3MFs on
        self.printing = None          # the print animation: its start time
        self._last_full_ms = 0.0
        self._last_tick = time.perf_counter()

        self.regen_timer = QTimer(self)
        self.regen_timer.setSingleShot(True)
        self.regen_timer.timeout.connect(self.regenerate)
        self.draft_timer = QTimer(self)
        self.draft_timer.setSingleShot(True)
        self.draft_timer.timeout.connect(lambda: self.regenerate(draft=True))
        self.anim_timer = QTimer(self)
        self.anim_timer.setInterval(16)
        self.anim_timer.timeout.connect(self._anim_tick)

        self.setWindowIcon(make_app_icon())
        self._build_ui()
        self._build_actions()
        self.resize(1480, 940)
        geo = self.settings.value("geometry")
        if geo is not None:
            self.restoreGeometry(geo)
        self.regenerate()
        self._update_anim()

    # ================================================================== UI
    def _build_ui(self):
        panel = QWidget()
        pl = QVBoxLayout(panel)
        pl.setContentsMargins(8, 8, 8, 8)
        pl.setSpacing(8)

        mode_row = QHBoxLayout()
        mode_row.setSpacing(0)
        self.simple_btn = QPushButton("Simple")
        self.detail_btn = QPushButton("Detailed")
        self.simple_btn.setToolTip("The essentials: size, shape, spin, patterns and colours.")
        self.detail_btn.setToolTip("Every setting, with curves to draw how things change up the vase.")
        for b in (self.simple_btn, self.detail_btn):
            b.setCheckable(True)
            b.setAutoExclusive(True)
            b.setMinimumHeight(28)
            b.setObjectName("modeButton")
            mode_row.addWidget(b)
        (self.simple_btn if self.simple_mode else self.detail_btn).setChecked(True)
        self.simple_btn.clicked.connect(lambda: self.set_simple_mode(True))
        self.detail_btn.clicked.connect(lambda: self.set_simple_mode(False))
        pl.addLayout(mode_row)

        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Name"))
        self.name_edit = QLineEdit(self.params.name)
        self.name_edit.setToolTip("Design name - used for exported file names.")
        self.name_edit.textChanged.connect(self._on_name)
        name_row.addWidget(self.name_edit)
        dice = QToolButton()
        dice.setIcon(glyph_icon("dice"))
        dice.setToolTip("Surprise me: a new random vase that still prints (Ctrl+R)")
        dice.clicked.connect(self.surprise_me)
        name_row.addWidget(dice)
        pl.addLayout(name_row)

        self._rows = {}
        self._groups = []
        for title, items in SPEC:
            box = QGroupBox(title)
            form = QFormLayout(box)
            form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
            form.setContentsMargins(8, 12, 8, 8)
            form.setHorizontalSpacing(10)
            form.setVerticalSpacing(5)
            for key, label, kind, lo, hi, step, extra, tip in items:
                w = self._make_widget(key, kind, lo, hi, step, extra)
                if tip:
                    w.setToolTip(tip)
                if label:
                    lab = QLabel(label)
                    if tip:
                        lab.setToolTip(tip)
                    self.labels[key] = lab
                    form.addRow(lab, w)
                else:
                    form.addRow(w)
                self._rows[key] = (form, w)
            self._groups.append((box, [it[0] for it in items]))
            pl.addWidget(box)
        pl.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidget(panel)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setMinimumWidth(350)
        scroll.setMaximumWidth(460)

        self.viewer = Viewer3D()
        self.viewer.dragged.connect(self._on_dragged)
        self.viewer.reset_requested.connect(lambda: self.show_view(self.view))
        self.viewer.resized.connect(self._on_resized)
        self.plots = ShapePlots()
        self.info = QTextBrowser()
        self.info.setOpenExternalLinks(False)
        self.info.setMinimumWidth(280)

        bottom = QSplitter(Qt.Horizontal)
        bottom.addWidget(self.plots)
        bottom.addWidget(self.info)
        bottom.setStretchFactor(0, 3)
        bottom.setStretchFactor(1, 2)
        bottom.setSizes([560, 500])

        right = QSplitter(Qt.Vertical)
        right.addWidget(self._make_view_bar())
        right.addWidget(self.viewer)
        right.addWidget(bottom)
        right.setStretchFactor(1, 3)
        right.setStretchFactor(2, 2)
        right.setSizes([36, 560, 300])
        right.setCollapsible(0, False)
        right.handle(1).setEnabled(False)

        main = QSplitter(Qt.Horizontal)
        main.addWidget(scroll)
        main.addWidget(right)
        main.setStretchFactor(1, 1)
        main.setSizes([380, 1100])
        self.setCentralWidget(main)
        self.statusBar().showMessage("Ready")
        self._refresh_widgets()

    def _make_view_bar(self):
        bar = QWidget()
        bar.setMaximumHeight(40)
        h = QHBoxLayout(bar)
        h.setContentsMargins(6, 4, 6, 4)
        h.addWidget(QLabel("Show"))
        row = QHBoxLayout()
        row.setSpacing(0)
        self.view_btns = []
        tips = ("The vase as it will look (Ctrl+1)",
                "Cut in half through the middle: the single printed wall and the solid bottom (Ctrl+2)",
                "How far each part of the wall leans: green is easy, orange near the limit, red needs "
                "support (Ctrl+3)",
                "On the printer bed, inside the space the printer can reach (Ctrl+4)")
        for idx, text in enumerate(VIEW_NAMES):
            b = QPushButton(text)
            b.setCheckable(True)
            b.setAutoExclusive(True)
            b.setMinimumHeight(28)
            b.setObjectName("modeButton")
            b.setToolTip(tips[idx])
            b.clicked.connect(lambda _=False, i=idx: self.show_view(i))
            row.addWidget(b)
            self.view_btns.append(b)
        self.view_btns[self.view].setChecked(True)
        h.addLayout(row)
        h.addSpacing(10)
        self.spin_btn = QPushButton("⟳ Spin")
        self.spin_btn.setCheckable(True)
        self.spin_btn.setChecked(self.spinning)
        self.spin_btn.setObjectName("modeButton")
        self.spin_btn.setMinimumHeight(28)
        self.spin_btn.setToolTip("Turn the vase slowly on a turntable (S)")
        self.spin_btn.toggled.connect(self.set_spin)
        h.addWidget(self.spin_btn)
        self.print_btn = QPushButton("▶ Watch it print")
        self.print_btn.setCheckable(True)
        self.print_btn.setObjectName("modeButton")
        self.print_btn.setMinimumHeight(28)
        self.print_btn.setToolTip("Build the vase up as the printer would, keeping to the real print time "
                                  "(wide layers take longer) (F5)")
        self.print_btn.toggled.connect(self.set_printing)
        h.addWidget(self.print_btn)
        h.addSpacing(10)
        self.hint = QLabel("Drag to turn · wheel to zoom")
        self.hint.setStyleSheet("color: #9aa3ad;")
        h.addWidget(self.hint)
        h.addStretch(1)
        fit = QToolButton()
        fit.setText("Reset view")
        fit.setToolTip("Back to the chosen view (double-click the 3D view, or press F)")
        fit.clicked.connect(lambda: self.show_view(self.view))
        h.addWidget(fit)
        return bar

    def _make_widget(self, key, kind, lo, hi, step, extra):
        def row(*parts):
            box = QWidget()
            hl = QHBoxLayout(box)
            hl.setContentsMargins(0, 0, 0, 0)
            hl.setSpacing(6)
            for part in parts:
                hl.addWidget(part, 0 if isinstance(part, QToolButton) else 1)
            return box

        if kind == "widest":
            s = QDoubleSpinBox()
            s.setDecimals(1)
            s.setRange(lo, hi)
            s.setSingleStep(step)
            s.setSuffix(extra)
            s.setKeyboardTracking(False)
            s.setValue(self._widest())
            s.valueChanged.connect(lambda v: self._on_param("widest", float(v)))
            self.widgets[key] = s
            return s
        if kind == "palette":
            b = QToolButton()
            b.setText("Choose a palette")
            b.setPopupMode(QToolButton.InstantPopup)
            b.setToolButtonStyle(Qt.ToolButtonTextOnly)
            m = QMenu(b)
            for name, cols in PALETTES:
                a = m.addAction(palette_icon(cols), name)
                a.triggered.connect(lambda _=False, n=name: self._apply_palette(n))
            b.setMenu(m)
            b.setMinimumHeight(24)
            self.widgets[key] = b
            return b
        if kind == "template":                    # a slicer project to take the printer's settings from
            b = ElidedButton()
            b.setMinimumHeight(24)
            b.clicked.connect(self._pick_template)
            clear = QToolButton()
            clear.setText("✕")
            clear.setToolTip("Forget these settings: Export 3MF writes the shape only")
            clear.clicked.connect(lambda: self._set_template(""))
            self.template_clear = clear
            self.widgets[key] = b
            return row(b, clear)
        val = getattr(self.params, key)
        if kind == "float":
            suffix, _, special = extra.partition("|")
            s = QDoubleSpinBox()
            s.setDecimals(2)
            s.setRange(lo, hi)
            s.setSingleStep(step)
            s.setSuffix(suffix)
            if special:
                s.setSpecialValueText(special)
            s.setValue(val)
            s.setKeyboardTracking(False)
            s.valueChanged.connect(lambda v, k=key: self._on_param(k, float(v)))
            s.setMinimumWidth(110)
            w = s
        elif kind == "int" or kind == "seed":
            suffix, _, special = extra.partition("|")
            s = QSpinBox()
            s.setRange(int(lo), int(hi))
            s.setSingleStep(int(step))
            s.setSuffix(suffix)
            if special:
                s.setSpecialValueText(special)
            s.setValue(int(val))
            s.setKeyboardTracking(False)
            s.valueChanged.connect(lambda v, k=key: self._on_param(k, int(v)))
            self.widgets[key] = s
            if kind == "seed":
                roll = QToolButton()
                roll.setIcon(glyph_icon("dice"))
                roll.setToolTip("Another one")
                roll.clicked.connect(lambda _=False, ss=s: ss.setValue(random.randint(0, 99999)))
                return row(s, roll)
            return s
        elif kind == "pct":
            s = QDoubleSpinBox()
            s.setDecimals(0)
            s.setRange(lo, hi)
            s.setSingleStep(step)
            s.setSuffix(extra)
            s.setValue(100.0 * val)
            s.setKeyboardTracking(False)
            s.valueChanged.connect(lambda v, k=key: self._on_param(k, float(v) / 100.0))
            w = s
        elif kind == "bool":
            w = QCheckBox()
            w.setChecked(val)
            w.toggled.connect(lambda v, k=key: self._on_param(k, bool(v)))
        elif kind == "choice":
            w = QComboBox()
            for value, label in lo:
                w.addItem(label, value)
            w.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
            w.setMinimumContentsLength(12)
            w.setCurrentIndex(max(0, w.findData(val)))
            w.currentIndexChanged.connect(lambda i, k=key, ww=w: self._on_param(k, ww.itemData(i)))
        elif kind == "color":
            w = QPushButton()
            w.setMinimumHeight(24)
            w.clicked.connect(lambda _=False, k=key: self._pick_color(k))
        elif kind == "slider":
            box = QWidget()
            vl = QVBoxLayout(box)
            vl.setContentsMargins(0, 0, 0, 0)
            vl.setSpacing(1)
            s = QSlider(Qt.Horizontal)
            s.setRange(int(round(lo * 100)), int(round(hi * 100)))
            s.setPageStep(10)
            s.setTickInterval(100)
            s.setTickPosition(QSlider.TicksBelow)
            s.setValue(int(round(val * 100)))
            s.valueChanged.connect(lambda v, k=key: self._on_param(k, v / 100.0, live=True))
            s.sliderReleased.connect(lambda: self._on_param(key, s.value() / 100.0))
            self.slider_notes[key] = QLabel()
            self.slider_notes[key].setStyleSheet("color: #9aa3ad;")
            vl.addWidget(s)
            vl.addWidget(self.slider_notes[key])
            self.widgets[key] = s
            return box
        elif kind == "curve":
            w = CurveEditor(**lo)
            w.set_points(val)
            w.changed.connect(lambda pts, k=key: self._on_param(k, pts, live=True))
            w.finished.connect(lambda pts, k=key: self._on_param(k, pts))
        elif kind == "expr":
            box = QWidget()
            vl = QVBoxLayout(box)
            vl.setContentsMargins(0, 0, 0, 0)
            vl.setSpacing(4)
            t = QPlainTextEdit(val)
            mono = QFontDatabase.systemFont(QFontDatabase.FixedFont)
            t.setFont(mono)
            t.setPlaceholderText("e.g. 1.5 * sin(6*theta + 4*pi*h)")
            t.setTabChangesFocus(True)
            t.setFixedHeight(54)
            t.textChanged.connect(lambda k=key, tt=t: self._on_param(k, tt.toPlainText()))
            self.widgets[key] = t
            ex = QToolButton()
            ex.setText("Examples")
            ex.setPopupMode(QToolButton.InstantPopup)
            m = QMenu(ex)
            for name, formula in EXAMPLES:
                a = m.addAction(f"{name}:  {formula}")
                a.triggered.connect(lambda _=False, f=formula: self._set_expression(f))
            m.addSeparator()
            m.addAction("Clear").triggered.connect(lambda: self._set_expression(""))
            ex.setMenu(m)
            helpb = QToolButton()
            helpb.setText("Help…")
            helpb.clicked.connect(self.function_help)
            buttons = QHBoxLayout()
            buttons.setContentsMargins(0, 0, 0, 0)
            buttons.addWidget(ex)
            buttons.addWidget(helpb)
            buttons.addStretch(1)
            vl.addWidget(t)
            vl.addLayout(buttons)
            return box
        else:
            raise ValueError(kind)
        self.widgets[key] = w
        return w

    def _widest(self) -> float:
        return max(d for _, d in self.params.silhouette)

    def _refresh_widgets(self):
        """Push self.params into the widgets without triggering updates."""
        for key, w in self.widgets.items():
            w.blockSignals(True)
            if key == "widest":
                w.setValue(self._widest())
            elif key in ("palette", "slicer_template"):
                pass
            elif isinstance(w, QComboBox):
                w.setCurrentIndex(max(0, w.findData(getattr(self.params, key))))
            elif isinstance(w, QCheckBox):
                w.setChecked(bool(getattr(self.params, key)))
            elif isinstance(w, QPlainTextEdit):
                if w.toPlainText() != getattr(self.params, key):
                    w.setPlainText(getattr(self.params, key))
            elif isinstance(w, QSpinBox):
                w.setValue(int(getattr(self.params, key)))
            elif isinstance(w, QDoubleSpinBox):
                v = getattr(self.params, key)
                w.setValue(100.0 * v if w.suffix() == " %" else v)
            elif isinstance(w, QSlider):
                w.setValue(int(round(getattr(self.params, key) * 100)))
            elif isinstance(w, CurveEditor):
                w.set_points(getattr(self.params, key))
            w.blockSignals(False)
        self.name_edit.blockSignals(True)
        self.name_edit.setText(self.params.name)
        self.name_edit.blockSignals(False)
        self._update_title()
        self._sync_widgets()

    def _fresh_params(self) -> VaseParams:
        """Default design, using the printer settings remembered from last time."""
        p = VaseParams()
        # a first run borrows the printer from Maze Tube Designer or Lenticular Sign Maker
        others = (QSettings("MazeTube", "MazeTubeDesigner"), QSettings("LenticularSign", "LenticularSignMaker"))
        for key in REMEMBERED:
            for v in (self.settings.value(f"default_{key}"),) + tuple(o.value(f"default_{key}") for o in others):
                try:
                    if v is not None:
                        setattr(p, key, float(v))
                        break
                except (TypeError, ValueError):
                    pass
        return p

    def _sync_widgets(self):
        """Colour swatches, labels and greyed-out settings that follow other settings."""
        p = self.params
        for k in FILAMENTS:
            color = getattr(p, f"color{k}")
            btn = self.widgets[f"color{k}"]
            dark = QColor(color).lightnessF() < 0.55
            btn.setText(color.upper())
            btn.setStyleSheet(f"background: {color}; color: {'white' if dark else 'black'}; "
                              f"border: 1px solid #3b4049; border-radius: 3px;")
        for k in (1, 2):
            kind = getattr(p, f"shape{k}")
            names = SHAPE_LABELS.get(kind, (None, None, None))
            for key, name in zip((f"count{k}", f"depth{k}", f"sharp{k}"), names):
                if name:
                    self.labels[key].setText(name)
            self.widgets[f"count{k}"].setMinimum(3 if kind == POLYGON else 1)
        b = self.widgets["slicer_template"]
        if self.template is not None:
            text = f"{self.template['printer']} · {os.path.basename(self.template_path)}"
        elif self.template_path:
            text = "Not readable - choose again…"
        else:
            text = "Choose a saved project…"
        b.set_full_text(text)
        b.setToolTip(self.template_path or "No slicer settings chosen: Export 3MF writes the shape only")
        self.template_clear.setEnabled(bool(self.template_path))
        s = p.band_spacing
        self.slider_notes["band_spacing"].setText(
            "Even" if abs(s) < 0.05 else ("Thicker towards the top" if s > 0 else "Thicker towards the bottom"))
        self._apply_mode()

    def _wanted(self, key) -> bool:
        """Whether a setting's row is shown: only what the current choices use."""
        p = self.params
        twisting = p.twist_style == OWN or abs(p.twist) > 1e-9
        patterns = p.rib_count > 0 or p.ring_count > 0 or p.bump_around > 0 or p.organic_depth > 0
        show = True
        if key[:-1] in ("count", "depth", "sharp") and key[-1] in "12":
            k = int(key[-1])
            kind = getattr(p, f"shape{k}")
            idx = ("count", "depth", "sharp").index(key[:-1])
            show = kind != SAME and SHAPE_LABELS.get(kind, (None,) * 3)[idx] is not None
        elif key in ("turn1", "turn2"):
            show = getattr(p, f"shape{key[-1]}") not in (CIRCLE, SAME)
        elif key == "morph":
            show = p.shape2 != SAME
        elif key == "morph_swings":
            show = p.shape2 != SAME and p.morph == SWING
        elif key == "morph_curve":
            show = p.shape2 != SAME and p.morph == OWN
        elif key == "twist":
            show = p.twist_style != OWN
        elif key == "swings":
            show = p.twist_style == SWING
        elif key == "twist_curve":
            show = p.twist_style == OWN
        elif key == "lattice":
            show = twisting
        elif key.startswith("rib_") and key != "rib_count":
            show = p.rib_count > 0 and (key != "rib_cross" or p.rib_lean != 0)
        elif key.startswith("ring_") and key != "ring_count":
            show = p.ring_count > 0
        elif key in ("bump_up", "bump_depth"):
            show = p.bump_around > 0
        elif key in ("organic_scale", "organic_seed"):
            show = p.organic_depth > 0
        elif key == "texture_twist":
            show = patterns and twisting
        elif key in ("strength", "fade_foot", "fade_rim"):
            show = patterns
        elif key == "strength_curve":
            show = patterns and p.strength == OWN
        elif key.startswith("facet") and key != "facets" and key != "facet_size":
            show = p.facets
        elif key == "colours_used":
            show = p.colour_style != ONE_COLOUR
        elif key in ("band_count", "band_spacing"):
            show = p.colour_style == BANDS
        elif key == "stripe_height":
            show = p.colour_style == STRIPES
        elif key == "gradient_length":
            show = p.colour_style == GRADIENT
        elif key.startswith("color") and key[-1] in "1234":
            show = int(key[-1]) <= (1 if p.colour_style == ONE_COLOUR else p.colours_used)
        if not show:
            return False
        if key in ("silhouette",):
            return not self.simple_mode
        return not self.simple_mode or key in SIMPLE_KEYS

    def _apply_mode(self):
        for key, (form, field) in self._rows.items():
            form.setRowVisible(field, self._wanted(key))
        for box, keys in self._groups:
            box.setVisible(any(self._wanted(k) for k in keys))

    def set_simple_mode(self, simple: bool, remember: bool = True):
        self.simple_mode = simple
        (self.simple_btn if simple else self.detail_btn).setChecked(True)
        if remember:
            self.settings.setValue("simple_mode", simple)
        self._apply_mode()

    def _pick_color(self, key):
        c = QColorDialog.getColor(QColor(getattr(self.params, key)), self, "Filament colour")
        if c.isValid():
            self._on_param(key, c.name().upper())

    def _apply_palette(self, name):
        for k, v in palette(name).items():
            setattr(self.params, k, v)
        self._on_param("color1", self.params.color1)

    def _set_expression(self, formula):
        self.widgets["expression"].setPlainText(formula)      # its textChanged updates the design

    def function_help(self):
        FunctionHelp(self, self._set_expression).exec()

    def _build_actions(self):
        st = self.style()
        tb = self.addToolBar("Main")
        tb.setMovable(False)
        tb.setIconSize(QSize(20, 20))
        tb.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)

        def act(text, slot, icon=None, shortcut=None, tip=None):
            a = QAction(text, self)
            if isinstance(icon, QIcon):
                a.setIcon(icon)
            elif icon is not None:
                a.setIcon(st.standardIcon(icon))
            if shortcut:
                a.setShortcut(QKeySequence(shortcut))
            if tip:
                a.setToolTip(tip)
                a.setStatusTip(tip)
            a.triggered.connect(slot)
            return a

        self.a_new = act("New", self.new_design, QStyle.SP_FileIcon, "Ctrl+N", "Start again from the default vase")
        self.a_open = act("Open…", self.open_design, QStyle.SP_DialogOpenButton, "Ctrl+O", "Open a saved vase design")
        self.a_save = act("Save", self.save_design, QStyle.SP_DialogSaveButton, "Ctrl+S", "Save the design")
        self.a_save_as = act("Save As…", lambda: self.save_design(as_new=True), None, "Ctrl+Shift+S")
        self.a_exp_stl = act("Export STL…", self.export_stl, glyph_icon("export"), "Ctrl+E",
                             "The vase as one solid, watertight STL, for spiral vase mode")
        self.a_exp_3mf = act("Export 3MF…", self.export_3mf, None, "Ctrl+Shift+E",
                             "The vase as a 3MF, in the middle of the bed, set to its first filament")
        self.a_snap = act("Save picture…", self.save_snapshot, glyph_icon("picture"), "Ctrl+P",
                          "Save the 3D view as a PNG image")
        self.a_quit = act("Exit", self.close, None, "Ctrl+Q")
        self.a_undo = act("Undo", self.undo, glyph_icon("undo"), "Ctrl+Z", "Undo the last change")
        self.a_redo = act("Redo", self.redo, glyph_icon("redo"), "Ctrl+Y", "Redo")
        self.a_redo.setShortcuts([QKeySequence("Ctrl+Y"), QKeySequence("Ctrl+Shift+Z")])
        self.a_surprise = act("Surprise me", self.surprise_me, glyph_icon("dice"), "Ctrl+R",
                              "A new random vase that still prints without supports")
        self.a_copy_plan = act("Copy colour changes", self.copy_colour_plan, None, "Ctrl+Shift+C",
                               "Copy the list of filament changes, to keep beside the slicer")
        self.a_about = act("About", self.about)
        self.a_printing = act("Printing it watertight…", self.printing_help)
        self.a_function = act("Your own function…", self.function_help)

        tb.addAction(self.a_new)
        tb.addAction(self.a_open)
        tb.addAction(self.a_save)
        tb.addSeparator()
        exp_btn = QToolButton()
        exp_btn.setDefaultAction(self.a_exp_stl)
        exp_btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        exp_btn.setPopupMode(QToolButton.MenuButtonPopup)
        m = QMenu(exp_btn)
        m.addAction(self.a_exp_stl)
        m.addAction(self.a_exp_3mf)
        exp_btn.setMenu(m)
        tb.addWidget(exp_btn)
        tb.addAction(self.a_snap)
        tb.addSeparator()
        tb.addAction(self.a_surprise)
        gal_btn = QToolButton()
        gal_btn.setText("Gallery")
        gal_btn.setIcon(glyph_icon("gallery"))
        gal_btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        gal_btn.setPopupMode(QToolButton.InstantPopup)
        gal_btn.setToolTip("Ready-made vases to start from")
        self.gallery_menu = QMenu(gal_btn)
        for title, about, _ in GALLERY:
            a = self.gallery_menu.addAction(title)
            a.setToolTip(about)
            a.setStatusTip(about)
            a.triggered.connect(lambda _=False, t=title: self.use_gallery(t))
        self.gallery_menu.setToolTipsVisible(True)
        gal_btn.setMenu(self.gallery_menu)
        tb.addWidget(gal_btn)
        tb.addSeparator()
        tb.addAction(self.a_undo)
        tb.addAction(self.a_redo)

        mb = self.menuBar()
        fm = mb.addMenu("&File")
        for a in (self.a_new, self.a_open, self.a_save, self.a_save_as, None, self.a_exp_stl, self.a_exp_3mf,
                  self.a_snap, None, self.a_quit):
            fm.addAction(a) if a is not None else fm.addSeparator()
        em = mb.addMenu("&Edit")
        for a in (self.a_undo, self.a_redo, None, self.a_surprise, None, self.a_copy_plan):
            em.addAction(a) if a is not None else em.addSeparator()
        dm = mb.addMenu("&Designs")
        dm.addActions(self.gallery_menu.actions())
        vm = mb.addMenu("&View")
        self.view_actions = []
        for i, name in enumerate(VIEW_NAMES):
            a = QAction(name, self)
            a.setShortcut(QKeySequence(f"Ctrl+{i + 1}"))
            a.triggered.connect(lambda _=False, i=i: self.show_view(i))
            vm.addAction(a)
            self.view_actions.append(a)
        vm.addSeparator()
        a = QAction("Spin", self)
        a.setShortcut(QKeySequence("S"))
        a.triggered.connect(self.spin_btn.toggle)
        vm.addAction(a)
        a = QAction("Watch it print", self)
        a.setShortcut(QKeySequence("F5"))
        a.triggered.connect(self.print_btn.toggle)
        vm.addAction(a)
        a = QAction("Reset view", self)
        a.setShortcut(QKeySequence("Ctrl+0"))
        a.triggered.connect(lambda: self.show_view(self.view))
        vm.addAction(a)
        hm = mb.addMenu("&Help")
        hm.addAction(self.a_printing)
        hm.addAction(self.a_function)
        hm.addSeparator()
        hm.addAction(self.a_about)
        self._update_undo()

    # ============================================================ params
    def _on_param(self, key, value, live=False):
        p = self.params
        if key == "widest":
            old = self._widest()
            if old > 0 and value > 0:
                p.silhouette = [[h, round(d * value / old, 3)] for h, d in p.silhouette]
                self._set_widget("silhouette")
        elif key == "profile":
            p.profile = value
            if value != OWN_PROFILE:
                p.silhouette = outline(value, self._widest())
                self._set_widget("silhouette")
        elif key == "silhouette":
            p.silhouette = value
            if p.profile != OWN_PROFILE:
                p.profile = OWN_PROFILE
                self._set_widget("profile")
            self._set_widget("widest")
        else:
            # an own curve starts from the curve as it was, a point at each peak of a back-and-forth
            if key == "twist_style" and value == OWN and p.twist_style != OWN:
                p.twist_curve = [[h, round(d, 1)] for h, d in sample_points(
                    lambda hs: p.twist * progress(p.twist_style, hs, swings=p.swings), p.twist_style, p.swings)]
                self._set_widget("twist_curve")
            elif key == "morph" and value == OWN and p.morph != OWN:
                p.morph_curve = [[h, round(m, 3)] for h, m in sample_points(
                    lambda hs: change(p.morph, hs, changes=p.morph_swings), p.morph, p.morph_swings)]
                self._set_widget("morph_curve")
            elif key == "strength" and value == OWN and p.strength != OWN:
                p.strength_curve = [[h, round(s, 3)] for h, s in sample_points(
                    lambda hs: strength(p.strength, hs), p.strength, 1)]
                self._set_widget("strength_curve")
            elif key == "colour_style" and value != ONE_COLOUR and p.colours_used < 2:
                p.colours_used = 3
                self._set_widget("colours_used")
            setattr(p, key, value)
        if key in REMEMBERED:
            self.settings.setValue(f"default_{key}", float(value))
        self._sync_widgets()
        self._dirty = True
        self._update_title()
        self._schedule(live=live, text=key in TEXT_KEYS)

    def _set_widget(self, key):
        w = self.widgets[key]
        w.blockSignals(True)
        if key == "widest":
            w.setValue(self._widest())
        elif isinstance(w, CurveEditor):
            w.set_points(getattr(self.params, key))
        elif isinstance(w, QComboBox):
            w.setCurrentIndex(max(0, w.findData(getattr(self.params, key))))
        w.blockSignals(False)

    def _schedule(self, live=False, text=False):
        """Rebuild after a pause; while something is being dragged, quick rough builds follow the hand."""
        if text:
            self.regen_timer.start(600)
            return
        slow = self._last_full_ms > 220
        if live or slow:
            self.draft_timer.start(15)
            self.regen_timer.start(450 if live else 300)
        else:
            self.regen_timer.start(120)

    def _on_name(self, text):
        self.params.name = text.strip() or "vase"
        self._dirty = True
        self._update_title()

    def _update_title(self):
        f = os.path.basename(self.current_file) if self.current_file else "unsaved"
        star = " •" if self._dirty else ""
        self.setWindowTitle(f"{APP_NAME} — {self.params.name} ({f}){star}")

    # ======================================================= undo / redo
    def _remember(self):
        d = self.params.to_dict()
        if not self.history or self.history[-1] != d:
            self.history.append(d)
            del self.history[:-200]
            self.future.clear()
        self._update_undo()

    def _update_undo(self):
        if hasattr(self, "a_undo"):
            self.a_undo.setEnabled(len(self.history) > 1)
            self.a_redo.setEnabled(bool(self.future))

    def _restore(self, d):
        self.params = VaseParams.from_dict(d)
        self._dirty = True
        self._refresh_widgets()
        self.regenerate()

    def _flush(self):
        """Build now if a change is still waiting."""
        if self.regen_timer.isActive() or self.draft_timer.isActive():
            self.regen_timer.stop()
            self.draft_timer.stop()
            self.regenerate()

    def undo(self):
        self._flush()
        if len(self.history) < 2:
            return
        self.future.append(self.history.pop())
        self._restore(self.history[-1])
        self._update_undo()

    def redo(self):
        self._flush()
        if not self.future:
            return
        d = self.future.pop()
        self.history.append(d)
        self._restore(d)
        self._update_undo()

    def surprise_me(self, seed=None):
        self._flush()
        seed = random.randint(1, 999_999) if seed is None or seed is False else int(seed)
        self.params = surprise(self.params, seed)
        self._dirty = True
        self._refresh_widgets()
        self.regenerate()
        self.statusBar().showMessage(f"Surprise #{seed}: {self.params.name.replace('_', ' ')} — Ctrl+Z to go "
                                     "back", 8000)

    def use_gallery(self, title):
        self._flush()
        self.params = gallery_design(title, keep=self.params)
        self._dirty = True
        self._refresh_widgets()
        self.regenerate()
        self.statusBar().showMessage(f"{title} — your printer settings are kept; Ctrl+Z to go back", 8000)

    # ============================================================ build
    def regenerate(self, draft=False):
        if not draft:
            self.draft_timer.stop()
        t0 = time.perf_counter()
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            d = VaseDesign(self.params.copy(), draft=draft)
        except Exception as exc:   # pragma: no cover - safety net for the GUI
            self._show_info(None, [f"Internal error: {exc}"], [])
            return
        finally:
            QApplication.restoreOverrideCursor()
        if not draft:
            self._remember()
        if d.errors:
            self._show_info(None, d.errors, d.warnings)
            self.statusBar().showMessage("This vase cannot be built - see the panel on the right")
            return
        self.design = d
        self._show_design(d)
        dt = (time.perf_counter() - t0) * 1000
        if not draft:
            self._last_full_ms = dt
            self._show_info(d, [], d.warnings)
            self.statusBar().showMessage(f"Built in {dt:.0f} ms — {d.triangles:,} triangles", 6000)

    def _show_design(self, d: VaseDesign):
        colors = d.p.colors()
        phase = d.colour_phase(d.shell_verts[:, 2]) if d.gradient else None
        self.viewer.set_mesh("vase", d.shell_verts, d.shell_faces, colors[d.bands[0][1]],
                             face_vals=d.shell_lean, vert_vals=phase, flat=d.rows is not None)
        self.viewer.set_section_source(d.shell_verts, d.shell_faces)
        self.viewer.set_bed(d.p.bed_x, d.p.bed_y, d.p.printer_height)
        self.plots.set_design(d, colors)
        self._apply_view()
        if self.printing is not None:
            self._anim_tick()

    def _show_info(self, d, errors, warnings):
        css = ("<style>td{padding:2px 6px;} .k{color:#9aa3ad;} .e{color:#ff6b6b;} "
               ".w{color:#f2c14e;} .ok{color:#6fdc8c;} h3{margin:4px 0 6px 0;}</style>")
        html = [css]
        if errors:
            html.append("<h3 class='e'>Cannot build this vase</h3><ul>")
            html += [f"<li class='e'>{e}</li>" for e in errors]
            html.append("</ul>")
        if d is not None:
            html.append("<h3>The vase</h3><table>")
            for k, v in d.info().items():
                cls = " class='ok'" if v.endswith("✓") else (" class='e'" if v.endswith("✗") else "")
                html.append(f"<tr><td class='k'>{k}</td><td{cls}>{v}</td></tr>")
            html.append("</table>")
            for note in d.notes:
                html.append(f"<p class='k'>ℹ {note}</p>")
        if warnings:
            html.append("<h3 class='w'>Warnings</h3><ul>")
            html += [f"<li class='w'>{w}</li>" for w in warnings]
            html.append("</ul>")
        if d is not None:
            p = d.p
            html.append("<h3>Colours</h3>")
            if d.gradient:
                cycles = d.metres / max(p.gradient_length, 0.05)
                html.append(f"<p class='k'>One gradient spool: about {cycles:.1f} colour cycles over the "
                            f"{d.metres:.1f} m this vase uses. The view shows where each colour lands.</p>")
            else:
                f0 = d.bands[0][1]
                html.append(f"<table><tr><td>Start</td><td>{self._chip(d, f0)} filament {f0}</td></tr>")
                for layer, ztop, fil in d.colour_changes(self._first_layer()):
                    html.append(f"<tr><td class='k'>Layer {layer} ({ztop:.2f} mm)</td>"
                                f"<td>{self._chip(d, fil)} change to filament {fil}</td></tr>")
                html.append("</table>")
                if len(d.bands) > 1 and self.template is not None and self.template["filaments"] > 1:
                    html.append(
                        f"<p class='k'><b>Export 3MF</b> puts these changes in for you: on the "
                        f"{self.template['printer']} each one parks a toolhead and picks up the next, which "
                        "heats up before the spiral carries on - a short pause, and a small seam.</p>")
                elif len(d.bands) > 1 and self.template is not None:
                    html.append(
                        "<p class='k'><b>Export 3MF</b> puts these changes in for you, as pauses to change "
                        "the filament by hand (the saved printer has one filament).</p>")
                elif len(d.bands) > 1:
                    html.append(
                        "<p class='k'>In the slicer's preview, add a filament change at each of these "
                        "layers on the layer slider (Edit ▸ Copy colour changes puts the list on the "
                        "clipboard) - or choose <b>Slicer settings</b> under Printing, and Export 3MF puts "
                        "them in for you. Each change pauses the spiral and leaves a small seam.</p>")
            if self.template is not None:
                html.append(
                    f"<h3>Slicing it</h3><p class='k'><b>Export 3MF</b> writes a project for the "
                    f"<b>{self.template['printer']}</b> on your saved settings, with spiral vase on, "
                    f"<b>{d.bottom_layers} bottom layers</b> at <b>{p.layer_height:g} mm</b>, 0 top layers, "
                    f"0% infill, 1 wall of <b>{p.line_width:g} mm</b> and supports off - none are needed: "
                    f"nothing leans more than {d.worst:.0f}°. Open it in Flash Studio with <b>File ▸ Open</b> "
                    "(not Import, which takes the shape only) and slice. For a watertight vase: a little extra "
                    "flow (103–105%) and 5–10 °C hotter than usual for strong layer bonds.</p>")
            html.append(
                f"<h3>{'Or by hand' if self.template is not None else 'Slicing it'}</h3>"
                "<p class='k'>Turn on <b>spiral vase</b> (Spiralize). "
                f"<b>{d.bottom_layers} bottom layers</b> at <b>{p.layer_height:g} mm</b>, 0 top layers, "
                f"0% infill, 1 wall, outer wall line width <b>{p.line_width:g} mm</b>. Supports off - "
                f"none are needed: nothing leans more than {d.worst:.0f}°. "
                f"For a watertight vase: a little extra flow (103–105%), 5–10 °C hotter than usual for "
                f"strong layer bonds, and a wide line. A brim helps a narrow foot stay put.</p>"
                "<p class='k'><b>Sturdier still:</b> slice the same STL normally with 2–3 walls, 0% infill "
                "and 0 top layers - the walls are then several lines thick.</p>")
        self.info.setHtml("".join(html))

    @staticmethod
    def _chip(d, fil):
        c = d.filament_of(fil)
        return f"<span style='background:{c}; color:{c};'>&nbsp;■■&nbsp;</span>"

    # ============================================================ view
    def show_view(self, idx):
        self.view = idx
        self._free_camera = False
        self._fitted = None
        self.view_btns[idx].setChecked(True)
        self._apply_view()

    def _apply_view(self):
        d, v = self.design, self.viewer
        if d is None:
            return
        p = d.p
        v.show_bed = self.view == PRINT_LAYOUT
        v.section = self.view == SECTION
        colors = p.colors()
        v.bands = [(z, colors[f]) for z, f in d.bands]
        v.gradient = [colors[f] for f in d.gradient_fils]
        v.colmode = 3 if self.view == OVERHANGS else (2 if d.gradient else 1)
        v.limit = p.max_overhang
        v.look = p.look
        if self.view == OVERHANGS:
            self.hint.setText(f"Green: easy · orange: near {p.max_overhang:g}° · red: over it, needs support")
        elif self.printing is None:
            self.hint.setText("Drag to turn · wheel to zoom · right-drag to move")
        size = (round(float(d.size[0]), 0), round(float(d.size[1]), 0), round(d.H, 0))
        if self._fitted != (self.view, size):
            r = 0.5 * math.hypot(d.size[0], d.size[1])
            reach = math.hypot(r, 0.5 * d.H)
            aspect = max(v.width(), 1) / max(v.height(), 1)
            fov = math.radians(v.fov) * min(1.0, aspect)
            v.target = np.array([0.0, 0.0, 0.5 * d.H])
            v.dist = reach / math.sin(fov / 2.0) * (1.75 if self.view == PRINT_LAYOUT else 1.12)
            self._fitted = (self.view, size)
            if not self._free_camera:
                v.yaw, v.pitch = {VASE: (-60.0, 14.0), SECTION: (-90.0, 8.0), OVERHANGS: (-60.0, 14.0),
                                  PRINT_LAYOUT: (-55.0, 32.0)}[self.view]
        v.set_model(spin_transform(self.spin_angle))
        v.update()

    def _on_dragged(self):
        self._free_camera = True

    def _on_resized(self):
        if not self._free_camera:
            self._fitted = None
            self._apply_view()

    # ------------------------------------------------- spin and printing
    def set_spin(self, on: bool):
        self.spinning = bool(on)
        self.settings.setValue("spin", self.spinning)
        self._update_anim()

    def set_printing(self, on: bool):
        if on and self.design is not None:
            self.printing = time.perf_counter()
        else:
            self.printing = None
            self.viewer.cut_z = None
            self.viewer.set_lines(None)
            self._apply_view()
        self._update_anim()

    def _update_anim(self):
        if self.spinning or self.printing is not None:
            self._last_tick = time.perf_counter()
            self.anim_timer.start()
        else:
            self.anim_timer.stop()

    def _print_length(self):
        d = self.design
        return float(np.clip(6.0 + d.H / 30.0, 6.0, 16.0))

    def _anim_tick(self):
        now = time.perf_counter()
        dt, self._last_tick = now - self._last_tick, now
        d, v = self.design, self.viewer
        if d is None:
            return
        if self.spinning:
            self.spin_angle = (self.spin_angle + SPIN_SPEED * min(dt, 0.1)) % 360.0
            v.set_model(spin_transform(self.spin_angle))
        if self.printing is not None:
            span = self._print_length()
            t = (now - self.printing) / span
            if t > 1.25:                                  # hold the finished vase a moment, then again
                self.printing = now
                t = 0.0
            t = min(t, 1.0)
            # the real print time: the filament used up to each height, at an even speed
            done = d.filament_at[-1] * t
            z = float(np.interp(done, d.filament_at, d.filament_z)) if d.filament_at[-1] > 0 else t * d.H
            z = min(max(z, 0.05), d.H)
            v.cut_z = z if t < 1.0 else None
            v.set_lines(d.contour(z) if t < 1.0 else None)
            layer = min(int(math.ceil(z / d.p.layer_height)), d.layers)
            self.hint.setText(f"Printing: layer {layer} of {d.layers} · {duration(d.seconds * t)} of "
                              f"{duration(d.seconds)}" if t < 1.0 else f"Done: {duration(d.seconds)}, "
                              f"{d.grams:.0f} g of filament")
        v.update()

    # ============================================================ files
    def _last_dir(self):
        return self.settings.value("last_dir", os.path.join(os.path.expanduser("~"), "Documents"))

    def _remember_dir(self, path):
        self.settings.setValue("last_dir", os.path.dirname(path))

    def _safe_name(self):
        name = "".join(ch if ch.isalnum() or ch in "-_ " else "_" for ch in self.params.name).strip()
        return name or "vase"

    def new_design(self):
        if not self._confirm_discard():
            return
        self.params = self._fresh_params()
        self.current_file = None
        self._dirty = False
        self._refresh_widgets()
        self.regenerate()

    def _confirm_discard(self):
        if not self._dirty:
            return True
        r = QMessageBox.question(self, "Unsaved changes", "Discard unsaved changes to the current design?",
                                 QMessageBox.Discard | QMessageBox.Cancel, QMessageBox.Cancel)
        return r == QMessageBox.Discard

    def open_design(self):
        if not self._confirm_discard():
            return
        path, _ = QFileDialog.getOpenFileName(self, "Open design", self._last_dir(),
                                              f"Vaseinator designs (*{FILE_EXT} *.json);;All files (*)")
        if path:
            self.load_file(path)

    def load_file(self, path):
        try:
            params = load_design(path)
        except Exception as exc:
            QMessageBox.critical(self, "Open failed", f"Could not open the design:\n{exc}")
            return
        self._remember_dir(path)
        self.params = params
        self.current_file = path
        self._dirty = False
        self._refresh_widgets()
        self.regenerate()
        self.statusBar().showMessage(f"Opened {path}", 6000)

    def save_design(self, as_new=False):
        path = self.current_file
        if as_new or not path:
            default = os.path.join(self._last_dir(), self._safe_name() + FILE_EXT)
            path, _ = QFileDialog.getSaveFileName(self, "Save design", default, f"Vaseinator designs (*{FILE_EXT})")
            if not path:
                return
            if not os.path.splitext(path)[1]:
                path += FILE_EXT
        try:
            save_design(path, self.params)
        except OSError as exc:
            QMessageBox.critical(self, "Save failed", str(exc))
            return
        self._remember_dir(path)
        self.current_file = path
        self._dirty = False
        self._update_title()
        self.statusBar().showMessage(f"Saved {path}", 6000)

    def _current_design(self):
        """The design to export, rebuilt in full first if a change is still waiting."""
        self._flush()
        d = self.design
        if d is not None and d.draft:
            self.regenerate()
            d = self.design
        if d is None or {**d.p.to_dict(), "name": ""} != {**self.params.to_dict(), "name": ""}:
            QMessageBox.warning(self, "Nothing to export", "The current settings do not make a vase.")
            return None
        if not d.closed:
            QMessageBox.warning(self, "Not exported", "The mesh is not closed, so it would not print as one "
                                "watertight wall. Please report this design.")
            return None
        return d

    def export_stl(self):
        d = self._current_design()
        if d is None:
            return
        base = self._safe_name()
        if not base.endswith("_vase"):
            base += "_vase"         # make it obvious this is a solid model for spiral vase mode
        path, _ = QFileDialog.getSaveFileName(self, "Export STL", os.path.join(self._last_dir(), base + ".stl"),
                                              "STL files (*.stl)")
        if not path:
            return
        if not path.lower().endswith(".stl"):
            path += ".stl"
        try:
            write_stl(path, d.verts, d.faces, base)
        except OSError as exc:
            QMessageBox.critical(self, "Export failed", str(exc))
            return
        self._remember_dir(path)
        self.statusBar().showMessage(
            f"Exported {os.path.basename(path)} ({d.triangles:,} triangles, watertight) to "
            f"{os.path.dirname(path)} — slice it with spiral vase mode on", 12000)

    def export_3mf(self):
        """A slicer project on the chosen settings (spiral vase on, the colour changes in), or the shape only."""
        d = self._current_design()
        if d is None:
            return
        if self.template is None:
            box = QMessageBox(self)
            box.setWindowTitle("Export 3MF")
            box.setIcon(QMessageBox.Question)
            box.setText("To carry the colour changes and the spiral vase settings, the 3MF is built on a "
                        "project you have saved in your slicer for your printer and filaments.")
            box.setInformativeText("In Flash Studio, set up any print for your printer and save it with File ▸ "
                                   "Save Project, then choose that file. It is remembered for every design.")
            choose = box.addButton("Choose a saved project…", QMessageBox.AcceptRole)
            shape = box.addButton("The shape only", QMessageBox.ActionRole)
            box.addButton(QMessageBox.Cancel)
            box.setDefaultButton(choose)
            box.exec()
            if box.clickedButton() is choose:
                self._pick_template()
                if self.template is None:
                    return
            elif box.clickedButton() is not shape:
                return
        p = d.p
        if self.template is not None:
            used = max(f for _, f in d.bands)
            if self.template["filaments"] > 1 and used > self.template["filaments"]:
                QMessageBox.warning(self, "Not exported", f"The colours use filament {used}, but "
                                    f"{self.template['printer']} has {self.template['filaments']} in the saved "
                                    "project. Use fewer filaments, or save a project with more.")
                return
        base = self._safe_name()
        path, _ = QFileDialog.getSaveFileName(self, "Export 3MF", os.path.join(self._last_dir(), base + ".3mf"),
                                              "3MF files (*.3mf)")
        if not path:
            return
        if not path.lower().endswith(".3mf"):
            path += ".3mf"
        fil = d.bands[0][1]
        middle = (p.bed_x / 2.0, p.bed_y / 2.0, 0.0)
        try:
            if self.template is not None:
                colours = {k: getattr(p, f"color{k}").upper() for k in FILAMENTS}
                changes = write_project_3mf(path, base, d.verts, d.faces, self.template,
                                            spiral_settings(d.bottom_layers, p.layer_height, p.line_width),
                                            d.bands, colours, middle)
            else:
                write_3mf(path, base, d.verts, d.faces, fil, p.colors()[fil], middle)
        except OSError as exc:
            QMessageBox.critical(self, "Export failed", str(exc))
            return
        self._remember_dir(path)
        if self.template is not None:
            n = len(changes)
            self.statusBar().showMessage(
                f"Exported {os.path.basename(path)}: a project for the {self.template['printer']}, spiral vase on, "
                f"{n} colour change{'' if n == 1 else 's'} — open it in Flash Studio with File ▸ Open (Ctrl+O), "
                "not Import", 15000)
        else:
            self.statusBar().showMessage(
                f"Exported {os.path.basename(path)} to {os.path.dirname(path)} — the shape only: load it with "
                "File ▸ Import (Ctrl+I) and turn on spiral vase", 12000)

    # ------------------------------------------------------------ slicer settings
    def _load_template(self, path):
        """The slicer settings in a saved project, or None (the reason in self.template_error)."""
        self.template, self.template_error = None, ""
        if path:
            try:
                self.template = read_template(path)
            except TemplateError as exc:
                self.template_error = str(exc)

    def _pick_template(self):
        start = os.path.dirname(self.template_path) if self.template_path else self._last_dir()
        path, _ = QFileDialog.getOpenFileName(self, "Choose a project you saved in your slicer", start,
                                              "3MF projects (*.3mf)")
        if path:
            self._set_template(path)

    def _set_template(self, path):
        old = self.template_path
        self._load_template(path)
        if path and self.template is None:
            QMessageBox.warning(self, "Can't use that file",
                                f"{os.path.basename(path)} can't give slicer settings: {self.template_error}")
            self._load_template(old)
            return
        self.template_path = path
        self.settings.setValue("slicer_template", path)
        self._sync_widgets()
        if self.design is not None:
            self._show_info(self.design, [], self.design.warnings)
        if self.template is not None:
            self.statusBar().showMessage(f"Slicer settings from {os.path.basename(path)}: {self.template['printer']}, "
                                         f"{self.template['filaments']} filaments", 8000)

    def _first_layer(self):
        """The first layer height in the chosen slicer settings, if there are any."""
        if self.template is None:
            return None
        try:
            return float(self.template["config"].get("initial_layer_print_height"))
        except (TypeError, ValueError):
            return None

    def save_snapshot(self):
        default = os.path.join(self._last_dir(), self._safe_name() + "_3d.png")
        path, _ = QFileDialog.getSaveFileName(self, "Save picture", default, "PNG image (*.png)")
        if not path:
            return
        if not path.lower().endswith(".png"):
            path += ".png"
        self.viewer.grabFramebuffer().save(path)
        self._remember_dir(path)
        self.statusBar().showMessage(f"Saved picture to {path}", 8000)

    def copy_colour_plan(self):
        self._flush()
        if self.design is None:
            return
        QApplication.clipboard().setText(self.design.colour_plan(self._first_layer()))
        self.statusBar().showMessage("Colour changes copied to the clipboard", 6000)

    def printing_help(self):
        QMessageBox.information(
            self, "Printing it watertight",
            "<h3>Spiral vase mode</h3>"
            "<p>The exported STL is <b>solid</b>: the slicer's spiral vase mode (Spiralize) prints only its "
            "outside, as one continuous line climbing round and round, on a solid bottom. Don't slice it "
            "normally with infill - it would print as a solid block.</p>"
            "<ul><li><b>Spiral vase / Spiralize</b> on; 1 wall; 0 top layers; 0% infill.</li>"
            "<li><b>Bottom layers</b>: the number in the panel, so the floor is as thick as set.</li>"
            "<li><b>Outer wall line width</b>: the app's line width. 0.6–0.8 mm on a 0.4 mm nozzle is much "
            "stronger and more watertight than 0.4 mm.</li>"
            "<li><b>No supports</b>: every part of the wall leans no more than the limit you set, either way, "
            "and the panel shows the steepest.</li></ul>"
            "<h3>To make sure it holds water</h3>"
            "<ul><li>A little extra flow (103–105%) and 5–10 °C hotter than usual bond the layers well.</li>"
            "<li>Slow down: 30–50 mm/s for the wall.</li>"
            "<li>PETG is more watertight than PLA. Silk PLA looks great but bonds a little less well.</li>"
            "<li>Test it in a sink first. A coat of clear epoxy or varnish inside seals any weep.</li>"
            "<li>Sturdier still: slice the same STL normally with 2–3 walls, 0% infill and 0 top layers.</li></ul>"
            "<h3>Colours</h3>"
            "<p>Bands and stripes change filament at the layers the panel lists. Choose <b>Slicer settings</b> "
            "under Printing - a project you saved in Flash Studio for your printer - and <b>Export 3MF</b> "
            "writes a project with spiral vase on and those changes already in: open it with File ▸ Open, not "
            "Import. On a printer with several toolheads, like the Creator 5 Pro, each change swaps the head; "
            "on one with a single filament it pauses for you to change it. Without slicer settings, add the "
            "changes on the slicer's layer slider yourself. A gradient spool needs nothing: the view shows "
            "where its colours will land.</p>")

    def about(self):
        QMessageBox.about(
            self, f"About {APP_NAME}",
            f"<h3>{APP_NAME} {__version__}</h3>"
            "<p>Designs vases for a 3D printer's spiral vase mode: one continuous wall, watertight, with no "
            "supports. Shape the outline, the cross-section and how it changes on the way up, spin it, cover "
            "it in patterns or your own formula, and colour it in bands, stripes or a gradient.</p>"
            "<p><b>3D view:</b> left-drag turn · right-drag / shift-drag pan · wheel zoom · double-click or F to "
            "go back to the chosen view · S spin · F5 watch it print.</p>"
            "<p>Exports are in millimetres, standing on the bed, ready to slice.</p>")

    def closeEvent(self, ev):
        if not self._confirm_discard():
            ev.ignore()
            return
        self.settings.setValue("geometry", self.saveGeometry())
        super().closeEvent(ev)


# ============================================================== bootstrap
def apply_dark_theme(app: QApplication):
    app.setStyle("Fusion")
    pal = QPalette()
    c = QColor
    pal.setColor(QPalette.Window, c(36, 39, 45))
    pal.setColor(QPalette.WindowText, c(222, 225, 230))
    pal.setColor(QPalette.Base, c(26, 28, 33))
    pal.setColor(QPalette.AlternateBase, c(44, 47, 54))
    pal.setColor(QPalette.ToolTipBase, c(52, 56, 64))
    pal.setColor(QPalette.ToolTipText, c(230, 230, 230))
    pal.setColor(QPalette.Text, c(222, 225, 230))
    pal.setColor(QPalette.Button, c(50, 54, 62))
    pal.setColor(QPalette.ButtonText, c(222, 225, 230))
    pal.setColor(QPalette.BrightText, c(255, 90, 90))
    pal.setColor(QPalette.Highlight, c(56, 132, 214))
    pal.setColor(QPalette.HighlightedText, c(255, 255, 255))
    pal.setColor(QPalette.Link, c(110, 180, 255))
    pal.setColor(QPalette.PlaceholderText, c(130, 135, 145))
    for role in (QPalette.Text, QPalette.ButtonText, QPalette.WindowText):
        pal.setColor(QPalette.Disabled, role, c(120, 124, 132))
    app.setPalette(pal)
    app.setStyleSheet("""
        QGroupBox { font-weight: 600; border: 1px solid #3b4049; border-radius: 6px;
                    margin-top: 12px; padding-top: 4px; }
        QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; color: #f0a356; }
        QTextBrowser { border: none; }
        QToolBar { border: none; spacing: 4px; padding: 3px; }
        QSplitter::handle { background: #2b2e34; }
        QPushButton#modeButton { border: 1px solid #3b4049; padding: 4px 12px; background: #2a2d33; }
        QPushButton#modeButton:checked { background: #3884d6; color: white; border-color: #3884d6; }
    """)


def place_for_testing(win: QMainWindow, argv):
    """Put a test run's window on another screen than the main one (the second, unless --screen N),
    so testing doesn't get in the way of whoever is at the computer.

    Windows places a new window itself, so the window is shown see-through,
    moved once it is up, and only then made visible.
    """
    from PySide6.QtCore import QRect

    screens = QApplication.screens()
    index = int(argv[argv.index("--screen") + 1]) if "--screen" in argv else (1 if len(screens) > 1 else 0)
    screen = screens[min(max(index, 0), len(screens) - 1)]
    g = screen.availableGeometry()
    win.setWindowOpacity(0.0)
    win.show()
    QApplication.processEvents()
    win.windowHandle().setScreen(screen)
    win.setGeometry(QRect(g.x() + 10, g.y() + 30, min(1480, g.width() - 20), min(940, g.height() - 40)))
    QApplication.processEvents()
    win.setWindowOpacity(1.0)


def main(argv=None):
    argv = list(sys.argv if argv is None else argv)
    fmt = QSurfaceFormat()
    fmt.setDepthBufferSize(24)
    fmt.setSamples(8)
    fmt.setVersion(2, 1)
    fmt.setProfile(QSurfaceFormat.CompatibilityProfile)
    QSurfaceFormat.setDefaultFormat(fmt)

    app = QApplication(argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName("Vaseinator")
    apply_dark_theme(app)
    settings = None
    if "--screenshot" in argv:          # a test run keeps its hands off the remembered settings
        import tempfile
        settings = QSettings(os.path.join(tempfile.gettempdir(), "Vaseinator-test.ini"), QSettings.IniFormat)
        settings.clear()
        settings.setValue("spin", False)
    win = MainWindow(settings)
    if "--screenshot" in argv:
        place_for_testing(win, argv)
    else:
        win.show()

    valued = ("--screenshot", "--view", "--export-test", "--yaw", "--pitch", "--zoom", "--gallery", "--surprise",
              "--print-at", "--spin", "--screen")
    files = [a for i, a in enumerate(argv) if i > 0 and not a.startswith("--")
             and argv[i - 1] not in valued and os.path.isfile(a)]
    if files:
        win.load_file(files[0])

    # developer hook: --screenshot out.png [--view N] [--gallery NAME] [--surprise SEED] [--yaw a]
    #                 [--pitch a] [--zoom k] [--print-at 0..1] [--spin deg] [--detailed] [--export-test DIR]
    #                 [--screen N]  (the window opens on the second screen, if there is one)  [--only-3d]
    if "--screenshot" in argv:
        out = argv[argv.index("--screenshot") + 1]
        win.set_simple_mode("--detailed" not in argv, remember=False)
        if "--gallery" in argv:
            win.use_gallery(argv[argv.index("--gallery") + 1])
        if "--surprise" in argv:
            win.surprise_me(int(argv[argv.index("--surprise") + 1]))
        if "--view" in argv:
            win.show_view(int(argv[argv.index("--view") + 1]))
        if "--export-test" in argv:
            out_dir = argv[argv.index("--export-test") + 1]
            d = win.design
            write_stl(os.path.join(out_dir, "t_vase.stl"), d.verts, d.faces, "t")
            write_3mf(os.path.join(out_dir, "t.3mf"), "t", d.verts, d.faces, d.bands[0][1],
                      d.p.colors()[d.bands[0][1]], (d.p.bed_x / 2, d.p.bed_y / 2, 0.0))

        def snap():
            win._fitted = None
            win._apply_view()
            if "--spin" in argv:
                win.spin_angle = float(argv[argv.index("--spin") + 1])
                win.viewer.set_model(spin_transform(win.spin_angle))
            for flag, attr in (("--yaw", "yaw"), ("--pitch", "pitch")):
                if flag in argv:
                    setattr(win.viewer, attr, float(argv[argv.index(flag) + 1]))
            if "--zoom" in argv:
                win.viewer.dist /= float(argv[argv.index("--zoom") + 1])
            if "--print-at" in argv:
                t = float(argv[argv.index("--print-at") + 1])
                d = win.design
                z = float(np.interp(d.filament_at[-1] * t, d.filament_at, d.filament_z))
                win.viewer.cut_z = z
                win.viewer.set_lines(d.contour(z))
                layer = int(math.ceil(z / d.p.layer_height))
                win.hint.setText(f"Printing: layer {layer} of {d.layers} · {duration(d.seconds * t)} of "
                                 f"{duration(d.seconds)}")
            win.viewer.repaint()
            (win.viewer.grabFramebuffer() if "--only-3d" in argv else win.grab()).save(out)
            win._dirty = False          # a test run has nothing to save: close without asking
            app.quit()
        QTimer.singleShot(2200, snap)

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
