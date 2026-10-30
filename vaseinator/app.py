"""Vaseinator - main window."""

from __future__ import annotations

import math
import os
import random
import sys
import time

import numpy as np
from PySide6.QtCore import QSettings, QSize, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import (QAction, QColor, QDesktopServices, QFontDatabase, QIcon, QKeySequence, QPainter,
                           QPalette, QPen, QPixmap, QSurfaceFormat)
from PySide6.QtWidgets import (QApplication, QCheckBox, QColorDialog, QComboBox, QDialog, QDialogButtonBox,
                               QDoubleSpinBox, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QLabel,
                               QLineEdit, QMainWindow, QMenu, QMessageBox, QPlainTextEdit, QPushButton,
                               QScrollArea, QSlider, QSpinBox, QSplitter, QStackedWidget, QStyle,
                               QTextBrowser, QToolButton, QVBoxLayout, QWidget)

from . import sections, slicers
from .curves import CurveEditor
from .expr import EXAMPLES
from .geometry import HEAD_SCALED, VaseDesign, duration, fit_head
from .outline_editor import CLOSE_UP_FROM, OutlineEditor, OutlineWindow
from .params import (DRAWN, FILAMENTS, ONE_COLOUR, OWN_PROFILE, POLYGON, REAL_VASE, VaseParams, colour_style_of,
                     load_design, save_design)
from .plots import ShapePlots
from .report import ABOUT, APP_NAME, DRAWING_HELP, PRINTING_HELP, function_help, info_html, print_steps
from .settings import (COLOUR_STYLES, REAL_COLOUR_STYLES, REMEMBERED, SPEC, TEXT_KEYS, change as apply_change,
                       outline_from_shape, wanted)
from .presets import GALLERY, gallery_design, outline, palette, plain_design, slug, surprise
from .simple_panel import GalleryDialog, SimplePanel, asset, profile_icon
from .spinbox import ComboBox, DoubleSpinBox, Slider, SpinBox
from .shapes import PALETTES, SHAPE_LABELS
from .stl import write_stl
from .threemf import write_3mf
from .viewer import Viewer3D, spin_transform

FILE_EXT = ".vase"
KOFI_URL = "https://ko-fi.com/rickapps"
VASE, SECTION, OVERHANGS, PRINT_LAYOUT = 0, 1, 2, 3
VIEW_NAMES = ("Vase", "Section", "Overhangs", "Print layout")
SPIN_SPEED = 30.0          # degrees a second, on the turntable



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
    app = QApplication.instance()
    ink = app.palette().color(QPalette.WindowText) if app is not None else QColor(225, 230, 236)
    pen = QPen(ink, 5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
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
    elif kind == "coffee":
        p.drawRoundedRect(QRectF(14, 26, 30, 26), 5, 5)              # cup
        p.drawArc(QRectF(36, 30, 16, 16), -90 * 16, 180 * 16)        # handle, ends on the cup
        pen.setColor(QColor(240, 163, 86))
        p.setPen(pen)
        for x in (21, 29, 37):                                       # steam
            p.drawLine(QPointF(x, 10), QPointF(x, 20))
    p.end()
    return QIcon(pm)


def make_app_icon() -> QIcon:
    here = os.path.dirname(os.path.abspath(__file__))
    for cand in (os.path.join(here, "..", "assets", "icon.png"),
                 os.path.join(getattr(sys, "_MEIPASS", here), "assets", "icon.png")):
        if os.path.exists(cand):
            return QIcon(cand)
    return QIcon()


class FunctionHelp(QDialog):
    """What a formula can use, with examples to try."""

    def __init__(self, parent, insert):
        super().__init__(parent)
        self.setWindowTitle("Your own function")
        self.resize(640, 560)
        text = QTextBrowser()
        text.setHtml(function_help())
        box = QVBoxLayout(self)
        box.addWidget(text)
        row = QHBoxLayout()
        row.addWidget(QLabel("Try an example:"))
        pick = ComboBox()
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


class PrintSteps(QDialog):
    """After Save for printing: where the file is, and plain steps to print it."""
    open_slicer = Signal()

    def __init__(self, parent, d, path, parts: int, slicer):
        super().__init__(parent)
        self.setWindowTitle("How to print it")
        where = slicers.slicer_name(slicer) if slicer else "your slicer"
        text = QLabel(print_steps(d, path, parts, where))
        text.setWordWrap(True)
        text.setTextInteractionFlags(Qt.TextSelectableByMouse)
        box = QVBoxLayout(self)
        box.addWidget(text)
        row = QHBoxLayout()
        if slicer:
            go = QPushButton(f"Open in {where}")
            go.setObjectName("saveButton")
            go.setMinimumHeight(36)
            go.clicked.connect(lambda: (self.open_slicer.emit(), self.accept()))
            row.addWidget(go)
        show = QPushButton("Show the file")
        show.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(path))))
        row.addWidget(show)
        done = QPushButton("Close")
        done.clicked.connect(self.accept)
        row.addWidget(done)
        box.addLayout(row)
        self.resize(560, 320)


class MainWindow(QMainWindow):
    def __init__(self, settings: QSettings | None = None):
        super().__init__()
        self.settings = settings or QSettings("Vaseinator", "Vaseinator")
        if self.settings.value("big_text", False, type=bool) or self.settings.value("light_theme", False, type=bool):
            apply_theme(QApplication.instance(), light=self.settings.value("light_theme", False, type=bool),
                        scale=1.3 if self.settings.value("big_text", False, type=bool) else 1.0)
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
        self.outline_menus = {}        # Start from, for each drawn cross-section
        self.close_up_buttons = {}
        self.outline_windows = {}      # the cross-section editors opened full window
        self.slider_notes = {}
        self.history: list[dict] = []
        self.future: list[dict] = []
        self.spin_angle = 0.0
        self.spinning = self.settings.value("spin", True, type=bool)
        self.printing = None          # the print animation: its start time
        self._last_full_ms = 0.0
        self._note = ""                    # said with the next "Built in ..." message
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
        self.detail_btn = QPushButton("Advanced")
        self.simple_btn.setToolTip("A few choices made from pictures: size, shape, twist, pattern and colour.")
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

        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Name"))
        self.name_edit = QLineEdit(self.params.name)
        self.name_edit.setToolTip("Design name - used for exported file names.")
        self.name_edit.textChanged.connect(self._on_name)
        name_row.addWidget(self.name_edit)
        dice = self.dice_btn = QToolButton()
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
        # Simple: a few choices made from pictures; Advanced: every setting
        self.simple = SimplePanel()
        self.simple.param.connect(lambda k, v: self._on_param(k, v))
        self.simple.live.connect(lambda k, v: self._on_param(k, v, live=True))
        self.simple.changes.connect(self.apply_changes)
        self.simple.choose_design.connect(self.choose_design)
        self.simple.surprise.connect(lambda: self.surprise_me())
        self.simple.draw_own.connect(self.draw_own_shape)
        self.simple.save.connect(self.save_for_printing)
        self.simple.advanced.connect(lambda: self.set_simple_mode(False))
        simple_scroll = QScrollArea()
        simple_scroll.setWidget(self.simple)
        simple_scroll.setWidgetResizable(True)
        simple_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.panels = QStackedWidget()
        self.panels.addWidget(simple_scroll)
        self.panels.addWidget(scroll)
        self.panels.setCurrentIndex(0 if self.simple_mode else 1)
        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(8, 8, 0, 0)
        lv.setSpacing(6)
        lv.addLayout(mode_row)
        lv.addWidget(self.panels, 1)
        left.setMinimumWidth(370)
        left.setMaximumWidth(480)

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
        main.addWidget(left)
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
            s = DoubleSpinBox()
            s.setDecimals(1)
            s.setRange(lo, hi)
            s.setSingleStep(step)
            s.setSuffix(extra)
            s.setKeyboardTracking(False)
            s.setValue(self._widest())
            s.valueChanged.connect(lambda v: self._on_param("widest", float(v)))
            self.widgets[key] = s
            return s
        if kind == "head":                        # not a setting of its own: it scales the design to fit
            s = DoubleSpinBox()
            s.setDecimals(1)
            s.setRange(lo, hi)
            s.setSingleStep(step)
            s.setSuffix(extra)
            s.setKeyboardTracking(False)
            s.setValue(57.0)
            s.valueChanged.connect(lambda v: self._on_param("head", float(v)))
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
        if kind == "outline":                     # a drawn cross-section, and where to start one from
            k = key[-1]
            box = QWidget()
            vl = QVBoxLayout(box)
            vl.setContentsMargins(0, 0, 0, 0)
            vl.setSpacing(4)
            ed = OutlineEditor()
            ed.set_outline(getattr(self.params, key), getattr(self.params, f"repeat{k}"))
            ed.changed.connect(lambda pts, kk=int(k), e=ed: self._outline_edited(kk, pts, e, live=True))
            ed.finished.connect(lambda pts, kk=int(k), e=ed: self._outline_edited(kk, pts, e))
            start = QToolButton()
            start.setText("Start from")
            start.setPopupMode(QToolButton.InstantPopup)
            m = QMenu(start)
            for name, pts, repeat in sections.OUTLINES:
                m.addAction(name).triggered.connect(
                    lambda _=False, kk=k, pp=pts, rr=repeat: self._use_outline(kk, pp, rr))
            m.addSeparator()
            m.addAction("Trace a picture…").triggered.connect(lambda _=False, kk=k: self._trace_outline(kk))
            start.setMenu(m)
            start.setToolTip("Start again from a ready-made outline, or trace one from a picture: dark lines "
                             "drawn round a shape on a light or see-through ground.")
            close = QToolButton()
            close.setText("Close up")
            close.setCheckable(True)
            close.setToolTip("Show one repeat close up, turned to point upwards - or the whole outline.\n"
                             f"Above {CLOSE_UP_FROM} repeats it starts close up.")
            close.toggled.connect(ed.set_close_up)
            ed.view_changed.connect(lambda kk=int(k): self._show_close_up(kk))
            big = QToolButton()
            big.setText("Full window…")
            big.setToolTip("Draw it in a window of its own, as big as the screen: the wheel zooms, a right-drag "
                           "moves it.")
            big.clicked.connect(lambda _=False, kk=int(k): self._open_outline_window(kk))
            self.outline_menus[int(k)] = m
            self.close_up_buttons[int(k)] = close
            buttons = QHBoxLayout()
            buttons.setContentsMargins(0, 0, 0, 0)
            buttons.addWidget(start)
            buttons.addWidget(close)
            buttons.addWidget(big)
            buttons.addStretch(1)
            vl.addWidget(ed)
            vl.addLayout(buttons)
            self.widgets[key] = ed
            return box
        val = getattr(self.params, key)
        if kind == "float":
            suffix, _, special = extra.partition("|")
            s = DoubleSpinBox()
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
            s = SpinBox()
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
            s = DoubleSpinBox()
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
            w = ComboBox()
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
            s = Slider(Qt.Horizontal)
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
            elif key in ("palette", "head"):            # the head size follows the design once it is built
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
            elif isinstance(w, OutlineEditor):
                w.set_outline(getattr(self.params, key), getattr(self.params, f"repeat{key[-1]}"))
            w.blockSignals(False)
        for k in (1, 2):
            self._push_outline(k)
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
        # a real spiral vase prints one filament: only the colour styles that need no change of filament
        real = p.vase_mode == REAL_VASE
        styles = REAL_COLOUR_STYLES if real else COLOUR_STYLES
        combo = self.widgets["colour_style"]
        combo.blockSignals(True)
        if [(combo.itemData(i), combo.itemText(i)) for i in range(combo.count())] != styles:
            combo.clear()
            for value, text in styles:
                combo.addItem(text, value)
        combo.setCurrentIndex(max(0, combo.findData(colour_style_of(p))))
        combo.blockSignals(False)
        self.labels["color1"].setText("Colour" if colour_style_of(p) == ONE_COLOUR else "Filament 1")
        s = p.band_spacing
        self.slider_notes["band_spacing"].setText(
            "Even" if abs(s) < 0.05 else ("Thicker towards the top" if s > 0 else "Thicker towards the bottom"))
        for k, win in self.outline_windows.items():          # a shape no longer drawn has nothing to draw
            if win.isVisible() and getattr(p, f"shape{k}") != DRAWN:
                win.close()
        if hasattr(self, "simple"):
            titles = {slug(t): t for t, _, _ in GALLERY}
            titles["plain_cylinder"] = "Plain cylinder"
            self.simple.refresh(p, self._widest(), titles.get(p.name, ""))
        self._apply_mode()

    def _wanted(self, key) -> bool:
        return wanted(self.params, key)

    def _apply_mode(self):
        for key, (form, field) in self._rows.items():
            form.setRowVisible(field, self._wanted(key))
        for box, keys in self._groups:
            box.setVisible(any(self._wanted(k) for k in keys))

    def set_simple_mode(self, simple: bool, remember: bool = True):
        self.simple_mode = simple
        (self.simple_btn if simple else self.detail_btn).setChecked(True)
        self.panels.setCurrentIndex(0 if simple else 1)
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
        self.a_plain = act("New plain cylinder", self.use_plain, None, "Ctrl+Shift+N",
                           "Start from a plain cylinder, 200 mm across and 200 mm tall, with everything else off - "
                           "ready for your own function or a drawn cross-section")
        self.a_open = act("Open…", self.open_design, QStyle.SP_DialogOpenButton, "Ctrl+O", "Open a saved vase design")
        self.a_save = act("Save", self.save_design, QStyle.SP_DialogSaveButton, "Ctrl+S", "Save the design")
        self.a_save_as = act("Save As…", lambda: self.save_design(as_new=True), None, "Ctrl+Shift+S")
        self.a_exp_stl = act("Export STL…", self.export_stl, glyph_icon("export"), "Ctrl+E",
                             "The vase as one solid, watertight STL, for spiral vase mode")
        self.a_exp_3mf = act("Export 3MF…", self.export_3mf, None, "Ctrl+Shift+E",
                             "The vase as a 3MF, in the middle of the bed, set to its first filament")
        self.a_snap = act("Save picture…", self.save_snapshot, glyph_icon("picture"), "Ctrl+P",
                          "Save the 3D view as a PNG image")
        self.a_print = act("Save for printing…", self.save_for_printing, glyph_icon("export"), "Ctrl+Shift+P",
                           "Save the vase for your printer's slicer, with how to print it")
        self.a_slicer = act("Open in slicer", lambda: self.open_in_slicer(), None, "Ctrl+L",
                            "Open the vase saved for printing in your slicer")
        self.a_pick_slicer = act("Choose slicer program…", lambda: self.choose_slicer(), None, None,
                                 "Which program Open in slicer uses")
        self.a_gallery = act("Choose a design…", self.choose_design, glyph_icon("gallery"), "Ctrl+G",
                             "Pictures of every ready-made vase, and a plain cylinder to start from")
        self.a_big = act("Bigger text", lambda on: self._set_look(big=on), None, "Ctrl+=",
                         "Make all the writing bigger")
        self.a_light = act("Light theme", lambda on: self._set_look(light=on), None, None,
                           "Dark writing on a light background")
        for a, key in ((self.a_big, "big_text"), (self.a_light, "light_theme")):
            a.setCheckable(True)
            a.setChecked(self.settings.value(key, False, type=bool))
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
        self.a_drawing = act("Drawing a cross-section…", self.drawing_help)

        tb.addAction(self.a_new)
        tb.addAction(self.a_open)
        tb.addAction(self.a_save)
        tb.addSeparator()
        tb.addAction(self.a_print)
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
        gal_btn = self.gal_btn = QToolButton()
        gal_btn.setText("Gallery")
        gal_btn.setIcon(glyph_icon("gallery"))
        gal_btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        gal_btn.setToolTip("Pictures of every ready-made vase to start from (Ctrl+G)")
        gal_btn.clicked.connect(self.choose_design)
        self.gallery_menu = QMenu(self)
        self.gallery_menu.addAction(self.a_gallery)
        self.gallery_menu.addSeparator()
        self.gallery_menu.addAction(self.a_plain)
        self.gallery_menu.addSeparator()
        for title, about, _ in GALLERY:
            a = self.gallery_menu.addAction(title)
            a.setToolTip(about)
            a.setStatusTip(about)
            a.triggered.connect(lambda _=False, t=title: self.use_gallery(t))
        self.gallery_menu.setToolTipsVisible(True)
        tb.addWidget(gal_btn)
        tb.addSeparator()
        tb.addAction(self.a_undo)
        tb.addAction(self.a_redo)

        mb = self.menuBar()
        fm = mb.addMenu("&File")
        for a in (self.a_new, self.a_plain, self.a_open, self.a_save, self.a_save_as, None, self.a_print,
                  self.a_slicer, self.a_pick_slicer, None, self.a_exp_stl, self.a_exp_3mf, self.a_snap, None,
                  self.a_quit):
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
        vm.addSeparator()
        vm.addAction(self.a_big)
        vm.addAction(self.a_light)
        hm = mb.addMenu("&Help")
        hm.addAction(self.a_printing)
        hm.addAction(self.a_function)
        hm.addAction(self.a_drawing)
        hm.addSeparator()
        hm.addAction(self.a_about)

        # A coffee cup after Help, for anyone who would like to chip in.
        self.a_kofi = QAction(glyph_icon("coffee"), "", self)
        self.a_kofi.setToolTip("Vaseinator is free — buy me a coffee")
        self.a_kofi.setStatusTip("Vaseinator is free — buy me a coffee")
        self.a_kofi.triggered.connect(lambda: QDesktopServices.openUrl(QUrl(KOFI_URL)))
        mb.addAction(self.a_kofi)
        self._update_undo()

    # ============================================================ params
    def _on_param(self, key, value, live=False):
        if key == "head":
            self._set_head(value)
            return
        touched, message = apply_change(self.params, key, value)
        for k in touched:
            self._set_widget(k)
        if message:
            self.statusBar().showMessage(message, 8000)
        if key in REMEMBERED:
            self.settings.setValue(f"default_{key}", float(value))
        self._sync_widgets()
        self._dirty = True
        self._update_title()
        self._schedule(live=live, text=key in TEXT_KEYS)

    def _set_head(self, cm: float):
        """Scale the design to fit a head ``cm`` round."""
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            fitted = fit_head(self.params, 10.0 * cm)
        finally:
            QApplication.restoreOverrideCursor()
        self.apply_changes({k: getattr(fitted, k) for k in ("silhouette",) + HEAD_SCALED})
        self.statusBar().showMessage(f"Sized for a head {cm:g} cm round — Ctrl+Z to go back", 6000)

    def _show_head(self, d: VaseDesign):
        """The head the design fits, in the head size boxes."""
        cm = round(d.head_fit / 10.0, 1)
        w = self.widgets["head"]
        w.blockSignals(True)
        w.setValue(cm)
        w.blockSignals(False)
        self.simple.show_head(cm)

    def _set_widget(self, key):
        w = self.widgets[key]
        w.blockSignals(True)
        if key == "widest":
            w.setValue(self._widest())
        elif isinstance(w, CurveEditor):
            w.set_points(getattr(self.params, key))
        elif isinstance(w, OutlineEditor):
            w.blockSignals(False)
            self._push_outline(int(key[-1]))
        elif isinstance(w, QComboBox):
            w.setCurrentIndex(max(0, w.findData(getattr(self.params, key))))
        elif isinstance(w, QSpinBox):
            w.setValue(int(getattr(self.params, key)))
            if key in ("repeat1", "repeat2"):
                self._push_outline(int(key[-1]))
        w.blockSignals(False)

    # ----------------------------------------------------- drawn outlines
    def _outline_edited(self, k: int, pts, source, live=False):
        """An editor changed drawn outline k: the vase follows, and so does the other editor."""
        self._on_param(f"drawn{k}", pts, live=live)
        self._push_outline(k, source)

    def _push_outline(self, k: int, source=None):
        """Show drawn outline k in its editors - the one in the panel and any full window - but the one it came
        from."""
        p = self.params
        pts, repeat = getattr(p, f"drawn{k}"), getattr(p, f"repeat{k}")
        ed = self.widgets.get(f"drawn{k}")
        if ed is not None and ed is not source:
            ed.set_outline(pts, repeat)
        win = self.outline_windows.get(k)
        if win is not None and win.editor is not source:
            win.set_outline(pts, repeat)

    def _show_close_up(self, k: int):
        ed, b = self.widgets[f"drawn{k}"], self.close_up_buttons[k]
        b.blockSignals(True)
        b.setEnabled(ed.repeat > 1)
        b.setChecked(ed.close_up())
        b.blockSignals(False)

    def _open_outline_window(self, k: int):
        """The cross-section editor in a window of its own, as big as the screen."""
        win = self.outline_windows.get(k)
        if win is None:
            title = "Draw the cross-section" if k == 1 else "Draw the cross-section it turns into"
            win = OutlineWindow(self, f"{title} — {APP_NAME}", self.outline_menus[k])
            win.editor.changed.connect(lambda pts, kk=k, e=win.editor: self._outline_edited(kk, pts, e, live=True))
            win.editor.finished.connect(lambda pts, kk=k, e=win.editor: self._outline_edited(kk, pts, e))
            win.repeat_changed.connect(lambda v, kk=k: self._on_param(f"repeat{kk}", int(v)))
            self.outline_windows[k] = win
        win.set_outline(getattr(self.params, f"drawn{k}"), getattr(self.params, f"repeat{k}"))
        win.showMaximized()
        win.raise_()
        win.activateWindow()

    def _outline_from_shape(self, k: int):
        outline_from_shape(self.params, k)
        self._set_widget(f"repeat{k}")
        self._set_widget(f"drawn{k}")

    def _use_outline(self, k: int, pts, repeat: int):
        """Start drawn outline k again from given control points."""
        setattr(self.params, f"repeat{k}", int(repeat))
        self._set_widget(f"repeat{k}")
        self._on_param(f"drawn{k}", [list(q) for q in pts])
        self._set_widget(f"drawn{k}")

    def _trace_outline(self, k: int):
        start = self.settings.value("picture_dir", self._last_dir())
        path, _ = QFileDialog.getOpenFileName(QApplication.activeWindow() or self, "Trace a picture", start,
                                              "Pictures (*.png *.jpg *.jpeg *.bmp *.gif *.webp);;All files (*)")
        if not path:
            return
        self.settings.setValue("picture_dir", os.path.dirname(path))
        try:
            pts = sections.trace_picture(path)
        except (ValueError, OSError) as exc:
            QMessageBox.warning(self, "Can't trace that picture",
                                f"{os.path.basename(path)}: {exc}. Draw the outline as one closed dark line on a "
                                "light or see-through ground.")
            return
        self._note = (f"Traced {os.path.basename(path)}: {len(pts)} points, "
                      f"{sum(q[2] for q in pts)} sharp corners. ")
        self._use_outline(k, pts, 1)

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

    def apply_changes(self, changes: dict, live=False):
        """Several settings at once - a picture picked in Simple mode."""
        p = self.params
        for key, value in changes.items():
            setattr(p, key, value)
        if "profile" in changes and p.profile != OWN_PROFILE:
            p.silhouette = outline(p.profile, self._widest())
        self._dirty = True
        self._refresh_widgets()
        self._schedule(live=live)

    def choose_design(self):
        """Every ready-made vase as a picture to click."""
        def entry(title, about, p, picture):
            pts = np.asarray(p.silhouette, dtype=float)
            return title, about, asset("gallery", picture), profile_icon(pts, QColor(p.color1))
        entries = [entry("Plain cylinder", "200 mm across and 200 mm tall, with everything else off: a blank "
                         "start for your own shape or function", plain_design(), "plain_cylinder.png")]
        entries += [entry(t, about, gallery_design(t), slug(t) + ".png") for t, about, _ in GALLERY]
        dlg = GalleryDialog(self, entries)
        if dlg.exec() == QDialog.Accepted and dlg.chosen:
            if dlg.chosen == "Plain cylinder":
                self.use_plain()
            else:
                self.use_gallery(dlg.chosen)

    def draw_own_shape(self):
        """Draw the shape from above, in a window of its own, starting from the shape it is."""
        if self.params.shape1 != DRAWN:
            self._on_param("shape1", DRAWN)
            self._flush()
        self._open_outline_window(1)

    def _set_look(self, big=None, light=None):
        """Bigger text, and the light or dark theme - remembered for next time."""
        if big is not None:
            self.settings.setValue("big_text", bool(big))
        if light is not None:
            self.settings.setValue("light_theme", bool(light))
        apply_theme(QApplication.instance(), light=self.settings.value("light_theme", False, type=bool),
                    scale=1.3 if self.settings.value("big_text", False, type=bool) else 1.0)
        # the line icons are drawn in the theme's ink: draw them again
        for a, kind in ((self.a_exp_stl, "export"), (self.a_print, "export"), (self.a_snap, "picture"),
                        (self.a_surprise, "dice"), (self.a_undo, "undo"), (self.a_redo, "redo"),
                        (self.a_gallery, "gallery"), (self.a_kofi, "coffee")):
            a.setIcon(glyph_icon(kind))
        self.gal_btn.setIcon(glyph_icon("gallery"))
        self.dice_btn.setIcon(glyph_icon("dice"))

    def use_plain(self):
        """A blank start: the plain cylinder, keeping the printer settings."""
        self._flush()
        self.params = plain_design(keep=self.params)
        self._dirty = True
        self._refresh_widgets()
        self.regenerate()
        self.statusBar().showMessage("Plain cylinder, 200 mm across and 200 mm tall - type your own function, or "
                                     "choose Drawn as the cross-section; Ctrl+Z to go back", 12000)

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
        self._show_head(d)
        dt = (time.perf_counter() - t0) * 1000
        if not draft:
            self._last_full_ms = dt
            self._show_info(d, [], d.warnings)
            note, self._note = self._note, ""
            self.statusBar().showMessage(f"{note}Built in {dt:.0f} ms — {d.triangles:,} triangles",
                                         10000 if note else 6000)

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
        self.info.setHtml(info_html(d, errors, warnings))


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
            write_stl(path, *d.print_mesh(), base)
        except OSError as exc:
            QMessageBox.critical(self, "Export failed", str(exc))
            return
        self._remember_dir(path)
        if d.p.vase_mode == REAL_VASE:
            how = "slice it with spiral vase mode on"
        else:
            how = ("the hollow pot: slice it with your usual settings (an STL has no colours: Export 3MF has the "
                   "bands as parts)")
        self.statusBar().showMessage(
            f"Exported {os.path.basename(path)} ({d.triangles:,} triangles, watertight) to "
            f"{os.path.dirname(path)} — {how}", 12000)

    def band_parts(self, d):
        """The vase for write_3mf: a part per colour band, set to its filament."""
        colors = d.p.colors()
        parts = d.print_parts()
        many = len(parts) > 1
        return [(f"{self._safe_name()} band {k + 1}" if many else self._safe_name(), verts, faces, fil, colors[fil])
                for k, (fil, verts, faces) in enumerate(parts)]

    def export_3mf(self):
        """The vase for the slicer: one solid for a real spiral vase, a part per colour band for a fake one."""
        d = self._current_design()
        if d is None:
            return
        p = d.p
        base = self._safe_name()
        path, _ = QFileDialog.getSaveFileName(self, "Export 3MF", os.path.join(self._last_dir(), base + ".3mf"),
                                              "3MF files (*.3mf)")
        if not path:
            return
        if not path.lower().endswith(".3mf"):
            path += ".3mf"
        parts = self.band_parts(d)
        try:
            write_3mf(path, base, parts, (p.bed_x / 2.0, p.bed_y / 2.0, 0.0))
        except OSError as exc:
            QMessageBox.critical(self, "Export failed", str(exc))
            return
        self._remember_dir(path)
        if p.vase_mode == REAL_VASE:
            how = "turn on spiral vase"
        else:
            how = "leave spiral vase off and print with your usual settings"
        if len(parts) > 1:
            fils = ", ".join(str(f) for f in sorted({f for _, _, _, f, _ in parts}))
            what = f"{len(parts)} bands set to filaments {fils}"
        else:
            what = "the vase, one part"
        self.statusBar().showMessage(
            f"Exported {os.path.basename(path)}: {what} — in Flash Studio use File ▸ Import (Ctrl+I), then {how}",
            15000)

    def save_for_printing(self):
        """The one button Simple mode needs: the vase as a 3MF for the slicer, and plain steps to print it."""
        d = self._current_design()
        if d is None:
            return
        base = self._safe_name()
        path, _ = QFileDialog.getSaveFileName(self, "Save for printing", os.path.join(self._last_dir(), base + ".3mf"),
                                              "3MF files, for the slicer (*.3mf)")
        if not path:
            return
        if not path.lower().endswith(".3mf"):
            path += ".3mf"
        parts = self.band_parts(d)
        try:
            write_3mf(path, base, parts, (d.p.bed_x / 2.0, d.p.bed_y / 2.0, 0.0))
        except OSError as exc:
            QMessageBox.critical(self, "Couldn't save it", str(exc))
            return
        self._remember_dir(path)
        self.print_file = path
        self.statusBar().showMessage(f"Saved {os.path.basename(path)} for printing, in {os.path.dirname(path)}",
                                     12000)
        self.steps = PrintSteps(self, d, path, len(parts), self._slicer(ask=False))
        self.steps.open_slicer.connect(lambda: self.open_in_slicer(path))
        self.steps.show()

    def _slicer(self, ask=True):
        """The slicer program to open a vase in: the one chosen before, else the first one installed."""
        path = self.settings.value("slicer", "", type=str)
        if path and os.path.exists(path):
            return path
        found = slicers.find_slicers()
        if found:
            self.settings.setValue("slicer", found[0][1])
            return found[0][1]
        return self.choose_slicer() if ask else None

    def choose_slicer(self):
        found = slicers.find_slicers()
        start = os.path.dirname(found[0][1]) if found else os.environ.get("ProgramFiles", os.path.expanduser("~"))
        path, _ = QFileDialog.getOpenFileName(QApplication.activeWindow() or self, "Choose your slicer program",
                                              start, "Programs (*.exe);;All files (*)")
        if not path:
            return None
        self.settings.setValue("slicer", path)
        self.statusBar().showMessage(f"Open in slicer will use {slicers.slicer_name(path)}", 8000)
        return path

    def open_in_slicer(self, path=None):
        """Open the vase saved for printing in the slicer (saving it first if it hasn't been)."""
        path = path or getattr(self, "print_file", None)
        if not path or not os.path.exists(path):
            self.save_for_printing()
            return
        program = self._slicer()
        if not program:
            return
        if slicers.open_in(program, path):
            self.statusBar().showMessage(f"Opening {os.path.basename(path)} in {slicers.slicer_name(program)}…",
                                         10000)
        else:
            QMessageBox.warning(self, "Couldn't open the slicer",
                                f"{program} didn't start. Choose your slicer program in the File menu, or open "
                                f"{path} in it yourself.")

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
        QApplication.clipboard().setText(self.design.colour_plan())
        self.statusBar().showMessage("Colour changes copied to the clipboard", 6000)

    def printing_help(self):
        QMessageBox.information(self, "Printing it watertight", PRINTING_HELP)

    def drawing_help(self):
        QMessageBox.information(self, "Drawing a cross-section", DRAWING_HELP)

    def about(self):
        QMessageBox.about(self, f"About {APP_NAME}", ABOUT)

    def closeEvent(self, ev):
        if not self._confirm_discard():
            ev.ignore()
            return
        self.settings.setValue("geometry", self.saveGeometry())
        super().closeEvent(ev)


# ============================================================== bootstrap
def apply_dark_theme(app: QApplication):
    apply_theme(app, light=False)


def apply_theme(app: QApplication, light: bool = False, scale: float = 1.0):
    """The look: dark (the usual) or light, and the writing at its own size or bigger."""
    app.setStyle("Fusion")
    base = app.property("vaseinator_base_pt")
    if base is None:
        base = app.font().pointSizeF()
        app.setProperty("vaseinator_base_pt", base)
    font = app.font()
    font.setPointSizeF(base * scale)
    app.setFont(font)
    title = f"QLabel#simpleTitle {{ font-weight: 700; font-size: {base * scale * 1.25:.1f}pt; }}"
    if light:
        _light_theme(app)
        app.setStyleSheet(app.styleSheet() + title)
        return
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
        QToolButton#pictureButton { border: 1px solid #3b4049; border-radius: 6px; padding: 4px;
                                    background: #2a2d33; }
        QToolButton#pictureButton:hover { border-color: #6b7380; }
        QToolButton#pictureButton:checked { border: 2px solid #f0a356; background: #3a332b; }
        QPushButton#bigButton { padding: 8px 10px; font-weight: 600; }
        QPushButton#saveButton { background: #f0a356; color: #1a1c21; font-weight: 700; border-radius: 6px;
                                 border: 1px solid #f0a356; }
        QPushButton#saveButton:hover { background: #f5b878; }
        QLabel#simpleTitle { color: #f0a356; }
    """ + title)


def _light_theme(app: QApplication):
    pal = QPalette()
    c = QColor
    pal.setColor(QPalette.Window, c(238, 240, 243))
    pal.setColor(QPalette.WindowText, c(28, 30, 34))
    pal.setColor(QPalette.Base, c(255, 255, 255))
    pal.setColor(QPalette.AlternateBase, c(232, 235, 239))
    pal.setColor(QPalette.ToolTipBase, c(255, 255, 238))
    pal.setColor(QPalette.ToolTipText, c(20, 20, 20))
    pal.setColor(QPalette.Text, c(28, 30, 34))
    pal.setColor(QPalette.Button, c(226, 229, 234))
    pal.setColor(QPalette.ButtonText, c(28, 30, 34))
    pal.setColor(QPalette.BrightText, c(200, 30, 30))
    pal.setColor(QPalette.Highlight, c(56, 132, 214))
    pal.setColor(QPalette.HighlightedText, c(255, 255, 255))
    pal.setColor(QPalette.Link, c(20, 100, 200))
    pal.setColor(QPalette.PlaceholderText, c(120, 125, 135))
    for role in (QPalette.Text, QPalette.ButtonText, QPalette.WindowText):
        pal.setColor(QPalette.Disabled, role, c(150, 154, 162))
    app.setPalette(pal)
    app.setStyleSheet("""
        QGroupBox { font-weight: 600; border: 1px solid #c4c9d1; border-radius: 6px;
                    margin-top: 12px; padding-top: 4px; }
        QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; color: #b45f12; }
        QTextBrowser { border: none; }
        QToolBar { border: none; spacing: 4px; padding: 3px; }
        QSplitter::handle { background: #d5d9df; }
        QPushButton#modeButton { border: 1px solid #c4c9d1; padding: 4px 12px; background: #e6e8ec; }
        QPushButton#modeButton:checked { background: #3884d6; color: white; border-color: #3884d6; }
        QToolButton#pictureButton { border: 1px solid #c4c9d1; border-radius: 6px; padding: 4px;
                                    background: #f6f7f9; }
        QToolButton#pictureButton:hover { border-color: #8c939e; }
        QToolButton#pictureButton:checked { border: 2px solid #e08a2c; background: #fcefe0; }
        QPushButton#bigButton { padding: 8px 10px; font-weight: 600; }
        QPushButton#saveButton { background: #e08a2c; color: white; font-weight: 700; border-radius: 6px;
                                 border: 1px solid #e08a2c; }
        QPushButton#saveButton:hover { background: #ea9b44; }
        QLabel#simpleTitle { color: #b45f12; }
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
            write_3mf(os.path.join(out_dir, "t.3mf"), "t", win.band_parts(d), (d.p.bed_x / 2, d.p.bed_y / 2, 0.0))

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
