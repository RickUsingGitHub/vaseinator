"""Drive the main window without a person: edits, curves, undo, the gallery, the views and the exports.

Run:  .venv\\Scripts\\python -m tests.test_app
"""

import os
import sys
import tempfile

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QPoint, QPointF, QSettings, Qt  # noqa: E402
from PySide6.QtGui import QColor, QImage, QPainter, QPalette, QPen, QPolygonF, QWheelEvent  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QDialog, QFileDialog, QLabel, QMessageBox, QPushButton  # noqa: E402

from vaseinator import app as appmod  # noqa: E402
from vaseinator import sections  # noqa: E402
from vaseinator.presets import GALLERY, slug  # noqa: E402
from vaseinator.simple_panel import PATTERNS, SHAPES_FROM_ABOVE, asset  # noqa: E402
from vaseinator.geometry import edge_check  # noqa: E402
from vaseinator.params import (BANDS, CIRCLE, DRAWN, FAKE_VASE, FLOWER, GRADIENT, NO_HOLES, ONE_COLOUR, OWN,  # noqa: E402
                               VORONOI, ALMOND_EYES, CHIN_MOUTH,
                               OWN_PROFILE, POLYGON, REAL_VASE, SAME, STAR, SWING, VaseParams, load_design)
from vaseinator.stl import read_stl  # noqa: E402
from vaseinator.threemf import read_3mf  # noqa: E402


def main():
    qapp = QApplication.instance() or QApplication(sys.argv)
    appmod.apply_dark_theme(qapp)
    tmp = tempfile.mkdtemp()
    settings = QSettings(os.path.join(tmp, "test.ini"), QSettings.IniFormat)
    win = appmod.MainWindow(settings)
    appmod.place_for_testing(win, sys.argv)          # on the second screen, out of the way
    qapp.processEvents()
    checks = []

    def check(what, ok):
        checks.append((what, bool(ok)))
        print(("ok    " if ok else "FAIL  ") + what)

    def settle():
        win._flush()
        qapp.processEvents()

    d0 = win.design
    check("the default vase builds, closed", d0 is not None and d0.closed)

    # ordinary edits, as the widgets make them
    win.widgets["height"].setValue(150.0)
    settle()
    check("height follows the spin box", abs(win.design.H - 150.0) < 1e-9)
    win.widgets["widest"].setValue(80.0)
    settle()
    check("Widest scales the outline", abs(max(d for _, d in win.params.silhouette) - 80.0) < 1e-6
          and abs(win.design.widest - 80.0) < 1.0)
    win.widgets["shape1"].setCurrentIndex(win.widgets["shape1"].findData(STAR))
    settle()
    check("the shape's settings are named for it", win.labels["count1"].text() == "Points")
    win.widgets["twist_style"].setCurrentIndex(win.widgets["twist_style"].findData(OWN))
    settle()
    check("an own twist curve starts from the twist as it was",
          win.params.twist_style == OWN and abs(win.params.twist_curve[-1][1] - 150.0) < 1e-6
          and win._wanted("twist_curve"))

    # a curve dragged: live draft builds, then a full one
    win.set_simple_mode(False, remember=False)
    ed = win.widgets["silhouette"]
    pts = [list(p) for p in win.params.silhouette]
    pts[1][1] += 10.0
    ed.changed.emit(pts)
    win.draft_timer.timeout.emit()
    qapp.processEvents()
    check("dragging the outline builds a quick draft", win.design.draft)
    ed.finished.emit(pts)
    settle()
    check("... then the full vase, and the outline is now your own",
          not win.design.draft and win.params.profile == OWN_PROFILE and win.design.closed)

    # undo and redo
    before = win.params.to_dict()
    win.widgets["rib_count"].setValue(24)
    settle()
    win.undo()
    check("undo takes the ribs away again", win.params.to_dict() == before)
    win.redo()
    check("redo puts them back", win.params.rib_count == 24)

    # the gallery and Surprise me keep the printer
    win.widgets["line_width"].setValue(0.8)
    settle()
    # a plain start, for your own function or cross-section: there in Simple mode too
    before = win.params.to_dict()
    win.set_simple_mode(True, remember=False)
    win.a_plain.trigger()
    check("New plain cylinder: 200 mm across and tall, everything off, the printer kept",
          win.params.name == "plain_cylinder" and abs(win.design.H - 200) < 1e-9 and abs(win.design.widest - 200) < 0.01
          and win.design.worst < 0.01 and win.params.line_width == 0.8 and win.params.twist == 0
          and win.params.shape1 == CIRCLE and win.params.rib_count == 0 and win.params.expression == "")
    check("... and Your own function is there in Simple mode", win._wanted("expression")
          and win.a_plain in win.gallery_menu.actions())
    win.widgets["expression"].setPlainText("2 * sin(8*theta)")
    settle()
    check("... and a function typed in shapes it", win.design.closed and abs(win.design.widest - 204) < 0.2)
    win.widgets["shape1"].setCurrentIndex(win.widgets["shape1"].findData(DRAWN))
    settle()
    check("... and Drawn starts from a circle", win.params.repeat1 == 1 and len(win.params.drawn1) == 8
          and win.design.closed)
    win.undo()
    win.undo()
    win.undo()
    check("... and it can all be undone", win.params.to_dict() == before)
    win.set_simple_mode(False, remember=False)
    win.use_gallery("Ocean Ripple")
    check("a gallery vase keeps the line width", win.params.line_width == 0.8 and win.params.name == "ocean_ripple")
    check("... and is a gradient", win.design.gradient and win.params.colour_style == GRADIENT)
    win.surprise_me(1234)
    check("Surprise me makes a closed vase within the overhang limit",
          win.design.closed and win.design.worst <= win.params.max_overhang + 0.3 and win.params.line_width == 0.8)
    win.params.twist_style = SWING
    win.undo()
    check("... and can be undone", win.params.name == "ocean_ripple")

    # the shape changing back and forth, then an own curve dragged down with the mouse
    def choose(key, value):
        w = win.widgets[key]
        w.setCurrentIndex(w.findData(value))
        settle()

    choose("shape1", CIRCLE)
    choose("shape2", POLYGON)
    win.widgets["count2"].setValue(5)
    choose("morph", SWING)
    check("Back and forth asks how many changes", win._wanted("morph_swings") and win.params.morph_swings == 3)
    choose("morph", OWN)
    values = [round(v, 2) for _, v in win.params.morph_curve]
    check("... and an own curve starts as the same wave", values[::2] == [0.0, 1.0, 0.0, 1.0])
    ed = win.widgets["morph_curve"]
    ed.ensurePolished()
    qapp.processEvents()
    h, v = win.params.morph_curve[2]                          # the first peak: the pentagon
    start = ed._xy(h, v).toPoint()
    end = start + QPoint(0, int(0.8 * ed._area().height()))
    QTest.mousePress(ed, Qt.LeftButton, Qt.NoModifier, start)
    QTest.mouseMove(ed, end)
    QTest.mouseRelease(ed, Qt.LeftButton, Qt.NoModifier, end)
    settle()
    h2, v2 = win.params.morph_curve[2]
    check("dragging a point of the curve down lessens it, at the same height",
          v2 < 0.3 and abs(h2 - h) < 0.01 and win.design.closed)

    # every view, spinning, and the print animation
    for i in range(4):
        win.show_view(i)
        qapp.processEvents()
        win.viewer.repaint()
    check("all four views draw", win.viewer._gl_error is None)
    win.print_btn.setChecked(True)
    win.printing -= 0.5 * win._print_length()
    win._anim_tick()
    v = win.viewer
    check("half way through printing, the vase is cut and the nozzle's loop drawn",
          v.cut_z is not None and 0 < v.cut_z < win.design.H and v.lines is not None)
    win.print_btn.setChecked(False)
    check("stopping clears the cut", v.cut_z is None and v.lines is None)

    # saving and exporting, with the file dialogs answered
    out = {"vase": os.path.join(tmp, "x.vase"), "stl": os.path.join(tmp, "x_vase.stl"),
           "3mf": os.path.join(tmp, "x.3mf"), "png": os.path.join(tmp, "x.png")}
    QFileDialog.getSaveFileName = staticmethod(
        lambda *a, **k: (out[next(e for e in out if a[2].lower().endswith(e) or e in a[1].lower())], ""))
    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Discard)
    win.save_design(as_new=True)
    check("save writes a design that opens the same", load_design(out["vase"]).to_dict() == win.params.to_dict())
    win.export_stl()
    verts, faces = read_stl(out["stl"])
    check("the exported STL is watertight", edge_check(faces)[0] and len(faces) == win.design.triangles
          and len(faces) == len(win.design.print_mesh()[1]))
    win.export_3mf()
    [(name, v3, f3, fil, pos)] = read_3mf(out["3mf"])
    check("a one-colour 3MF is the whole vase, in the middle of the bed, asking nothing",
          pos == (win.params.bed_x / 2, win.params.bed_y / 2, 0.0) and len(f3) == win.design.triangles)
    # Real / Fake: a real spiral vase offers one colour; a fake one bands, walls and colour parts
    choose("vase_mode", REAL_VASE)
    styles = [win.widgets["colour_style"].itemData(i) for i in range(win.widgets["colour_style"].count())]
    check("a real spiral vase offers one colour or a gradient spool, and no walls",
          styles == [ONE_COLOUR, GRADIENT] and not win._wanted("walls") and not win._wanted("band_count"))
    choose("vase_mode", FAKE_VASE)
    choose("colour_style", BANDS)
    win.widgets["band_count"].setValue(3)
    choose("colours_used", 3)
    check("a fake one offers bands and stripes, and walls", win.widgets["colour_style"].count() == 4
          and win._wanted("walls") and win._wanted("band_count") and "walls" in win.info.toPlainText())
    win.export_3mf()
    parts = read_3mf(out["3mf"])
    check("... and its 3MF is a part per band, set to filaments 1, 2 and 3, each closed",
          [p[3] for p in parts] == [1, 2, 3] and all(edge_check(p[2])[0] for p in parts)
          and "spiral vase off" in win.statusBar().currentMessage())
    choose("vase_mode", REAL_VASE)
    win.export_3mf()
    check("switched back to real, the same design exports as one solid, for spiral vase mode",
          len(read_3mf(out["3mf"])) == 1 and "turn on spiral vase" in win.statusBar().currentMessage()
          and win.params.colour_style == BANDS)
    choose("vase_mode", FAKE_VASE)
    check("... and switching to fake again brings its bands back", len(win.design.bands) == 3)
    win.copy_colour_plan()
    check("the colour plan goes to the clipboard", "Vaseinator" in QApplication.clipboard().text())

    # a drawn cross-section: from the shape it was, edited, repeated, traced from a picture
    choose("vase_mode", REAL_VASE)
    choose("shape1", FLOWER)
    win.widgets["count1"].setValue(5)
    choose("shape2", SAME)
    choose("shape1", DRAWN)
    oed = win.widgets["drawn1"]
    check("a flower turned into a drawn outline is one petal, repeated five times",
          win.params.repeat1 == 5 and oed.repeat == 5 and oed.points == [[x, y, bool(c)] for x, y, c in win.params.drawn1]
          and win._wanted("drawn1") and not win._wanted("count1") and win.design.closed and win.design.free)
    pts = [list(q) for q in win.params.drawn1]
    pts[len(pts) // 2][0] *= 1.15
    oed.finished.emit(pts)
    settle()
    check("dragging a point of the outline changes the vase", win.params.drawn1 == pts and win.design.closed)
    win.widgets["repeat1"].setValue(3)
    settle()
    check("Repeat around shows in the editor", oed.repeat == 3 and win.design.closed)
    # with the mouse: drag a point out, double-click it sharp, double-click the line for a new point
    oed.ensurePolished()
    qapp.processEvents()
    i = max(range(len(oed.points)), key=lambda j: oed.points[j][0])     # the point furthest out to the right
    x0, y0, sharp0 = oed.points[i]
    at = oed._to(x0, y0).toPoint()
    QTest.mousePress(oed, Qt.LeftButton, Qt.NoModifier, at)
    QTest.mouseMove(oed, at + QPoint(-20, 0))
    QTest.mouseRelease(oed, Qt.LeftButton, Qt.NoModifier, at + QPoint(-20, 0))
    settle()
    check("dragging a point in the editor with the mouse moves it", win.params.drawn1[i][0] < x0 - 0.05)
    at = oed._to(*win.params.drawn1[i][:2]).toPoint()
    QTest.mouseDClick(oed, Qt.LeftButton, Qt.NoModifier, at)
    settle()
    check("... double-clicking it makes it sharp", win.params.drawn1[i][2] != sharp0)
    n = len(win.params.drawn1)
    loop = sections.spline(win.params.drawn1, 3, per=24)
    mid = oed._to(*loop[12]).toPoint()                                 # on the line, half way to the next point
    QTest.mouseDClick(oed, Qt.LeftButton, Qt.NoModifier, mid + QPoint(0, 1))
    settle()
    check("... and double-clicking the line adds a point", len(win.params.drawn1) == n + 1 and win.design.closed)

    # a hundred repeats: the piece narrows to fit, shown close up, and in a window of its own
    before = np.array([q[:2] for q in win.params.drawn1])
    win.widgets["repeat1"].setValue(100)
    settle()
    after = np.array([q[:2] for q in win.params.drawn1])
    spread = [np.ptp(np.unwrap(np.arctan2(P[:, 1], P[:, 0]))) for P in (before, after)]
    check("Repeat around 100: the piece narrows to fit, as deep as before, and the vase builds",
          win.params.repeat1 == 100 and abs(spread[1] - spread[0] * 3 / 100) < 1e-3
          and np.allclose(np.hypot(*before.T), np.hypot(*after.T), atol=1e-3)
          and win.design.closed and "drawn bottom outline crosses itself" not in win.info.toPlainText())
    check("... and the editor shows one repeat close up", oed.close_up() and win.close_up_buttons[1].isChecked())
    win._open_outline_window(1)
    qapp.processEvents()
    big = win.outline_windows[1]
    bed = big.editor
    check("Full window opens the editor on its own, bigger, showing the same",
          big.isVisible() and bed.repeat == 100 and big.repeat.value() == 100 and bed.points == oed.points
          and bed.width() > oed.width() and bed.close_up())
    spot = QPointF(bed.width() * 0.5, bed.height() * 0.4)
    held = bed._from(spot)
    s0 = bed._view()[2]
    QApplication.sendEvent(bed, QWheelEvent(spot, bed.mapToGlobal(spot), QPoint(), QPoint(0, 240), Qt.NoButton,
                                            Qt.NoModifier, Qt.NoScrollPhase, False))
    check("the wheel zooms in about the mouse", bed._view()[2] > 1.3 * s0
          and (bed._to(*held) - spot).manhattanLength() < 1.0)
    j = max(range(len(bed.points)), key=lambda q: np.hypot(*bed.points[q][:2]))       # the tip of the lobe
    tip = list(win.params.drawn1[j])
    at = bed._to(*bed.points[j][:2]).toPoint()
    QTest.mousePress(bed, Qt.LeftButton, Qt.NoModifier, at)
    QTest.mouseMove(bed, at + QPoint(0, 25))
    QTest.mouseRelease(bed, Qt.LeftButton, Qt.NoModifier, at + QPoint(0, 25))
    settle()
    check("dragging a point in the full window changes the vase, and the editor in the panel",
          win.params.drawn1[j] != tip and oed.points == [[x, y, bool(c)] for x, y, c in win.params.drawn1]
          and win.design.closed)
    big.repeat.setValue(6)
    settle()
    check("its Repeat around changes the vase and the panel, and shows the whole outline again",
          win.params.repeat1 == 6 and win.widgets["repeat1"].value() == 6 and oed.repeat == 6
          and not bed.close_up() and not oed.close_up() and win.design.closed)
    big.close()
    win.widgets["repeat1"].setValue(3)
    settle()
    choose("shape2", DRAWN)
    check("a top shape that was the same starts as a copy of the bottom one",
          win.params.drawn2 == win.params.drawn1 and win.params.repeat2 == 3)
    choose("shape2", SAME)
    oed.finished.emit([[1, 0, False], [-1, 1, False], [-1, -1, False], [1, 1, False], [0.2, -1.2, False]])
    settle()
    check("an outline that crosses itself is reported, not built", "crosses itself" in win.info.toPlainText())
    claw = next(q for name, q, n in sections.OUTLINES if name == "Claw")
    win._use_outline(1, claw, 1)
    settle()
    check("Start from: the claw builds, closed and printable", win.params.repeat1 == 1
          and win.design.closed and win.design.worst <= win.params.max_overhang + 0.3 and oed.repeat == 1)
    pic = QImage(400, 300, QImage.Format_RGB32)
    pic.fill(QColor("white"))
    painter = QPainter(pic)
    painter.setPen(QPen(QColor("black"), 6))
    painter.drawPolygon(QPolygonF([QPointF(200 + r * np.cos(a), 150 - r * np.sin(a)) for a, r in
                                   zip(np.linspace(0, 2 * np.pi, 10, endpoint=False), [120, 55] * 5)]))
    painter.end()
    pic.save(os.path.join(tmp, "star.png"))
    QFileDialog.getOpenFileName = staticmethod(lambda *a, **k: (os.path.join(tmp, "star.png"), ""))
    win._trace_outline(1)
    settle()
    check("a traced star has its five sharp points, and builds",
          sum(q[2] for q in win.params.drawn1) >= 5 and win.design.closed and "Traced" in win.statusBar().currentMessage())
    win.save_design(as_new=True)
    check("a drawn outline saves and opens the same", load_design(out["vase"]).drawn1 == win.params.drawn1)
    win.export_stl()
    verts, faces = read_stl(out["stl"])
    check("... and its STL is watertight", edge_check(faces)[0] and len(faces) == win.design.triangles)
    win._open_outline_window(1)
    qapp.processEvents()
    choose("shape1", CIRCLE)
    check("the full window closes when the shape is no longer drawn", not win.outline_windows[1].isVisible())

    # Simple mode, for anyone: a few pictures, and one button to save it for printing
    win.use_plain()
    settle()
    win.set_simple_mode(True, remember=False)
    sp = win.simple
    check("Simple shows the picture panel, Advanced every setting, and a vase prints normally unless asked",
          win.panels.currentIndex() == 0 and win.detail_btn.text() == "Advanced"
          and VaseParams().vase_mode == FAKE_VASE and sp.name.text() == "Plain cylinder")
    star = [n for n, _ in SHAPES_FROM_ABOVE].index("Star")
    sp.above.buttons[star].click()
    settle()
    check("the Star picture makes it a five-pointed star, the same all the way up",
          win.params.shape1 == STAR and win.params.count1 == 5 and win.params.shape2 == SAME
          and win.design.closed and sp.above.buttons[star].isChecked())
    sp.side.buttons[5].click()                                    # Bulb
    settle()
    check("a picture from the side gives it that outline", win.params.profile == 5
          and sp.side.buttons[5].isChecked() and win.design.closed)
    sp.wide.setValue(12.0)
    sp.tall.setValue(15.0)
    settle()
    check("Tall and Wide, in centimetres, size it", abs(win.design.widest - 120.0) < 1.0
          and abs(win.design.H - 150.0) < 1e-6)
    sp.twist.setValue(6)
    settle()
    check("the twist slider turns it a quarter turn", win.params.twist == 90.0
          and sp.twist_label.text() == "A quarter turn")
    ribs = [n for n, _ in PATTERNS].index("Ribs")
    sp.pattern.buttons[ribs].click()
    settle()
    check("a pattern picture puts on ribs, and nothing else", win.params.rib_count == 24
          and win.params.ring_count == 0 and win.params.bump_around == 0 and sp.pattern.buttons[ribs].isChecked())
    sp.colour.buttons[3].click()                                  # red
    settle()
    check("a colour makes it that colour", win.params.colour_style == ONE_COLOUR
          and win.params.color1.lower() == "#d62828" and sp.colour.buttons[3].isChecked())
    win.undo()
    check("Undo takes back one picture at a time", win.params.color1.lower() != "#d62828"
          and win.params.rib_count == 24)
    check("every design has its picture in the gallery",
          all(asset("gallery", slug(t) + ".png") for t, _, _ in GALLERY) and asset("gallery", "plain_cylinder.png"))
    appmod.GalleryDialog.exec = lambda self: (setattr(self, "chosen", "Claw Shell"), QDialog.Accepted)[1]
    sp.choose_design.emit()
    settle()
    check("Choose a design starts from the picture picked", win.params.name == "claw_shell"
          and sp.name.text() == "Claw Shell")
    win.use_plain()
    settle()
    sp.draw_own.emit()
    qapp.processEvents()
    check("Draw my own shape opens the big drawing window, starting as the shape it was",
          win.params.shape1 == DRAWN and win.params.repeat1 == 1 and win.outline_windows[1].isVisible())
    win.outline_windows[1].close()
    opened = []
    appmod.slicers.open_in = lambda program, file: opened.append((program, file)) or True
    win.settings.setValue("slicer", sys.executable)               # a program that exists; it isn't started
    os.remove(out["3mf"])
    sp.save.emit()
    qapp.processEvents()
    words = " ".join(lab.text() for lab in win.steps.findChildren(QLabel))
    check("Save for printing writes the 3MF and says how to print it", os.path.exists(out["3mf"])
          and win.steps.isVisible() and "No supports" in words and "usual settings" in words
          and "Spiral vase off" in words)
    go = next(b for b in win.steps.findChildren(QPushButton) if b.text().startswith("Open in"))
    go.click()
    qapp.processEvents()
    check("... and Open in opens it in the slicer", opened and opened[-1][1] == out["3mf"])
    # holes: a picture in Simple mode; their settings in Advanced; never seamless
    holes = [n for n, _ in PATTERNS].index("Voronoi holes")
    win.params.vase_mode = REAL_VASE
    sp.pattern.buttons[holes].click()
    settle()
    check("the Voronoi holes picture cuts holes through a normal print, and says so",
          win.params.holes == VORONOI and win.params.vase_mode == FAKE_VASE and win.design.holes_open
          and win.design.closed and sp.pattern.buttons[holes].isChecked()
          and "it has holes" in win.info.toPlainText())
    win.set_simple_mode(False, remember=False)
    check("... Advanced shows the holes' settings", win._wanted("hole_size") and win._wanted("hole_jitter"))
    choose("vase_mode", REAL_VASE)
    choose("holes", NO_HOLES)
    win.widgets["open_bottom"].setChecked(True)
    settle()
    check("an open bottom makes it a normal print, holding nothing", win.params.vase_mode == FAKE_VASE
          and "open at the bottom" in win.info.toPlainText())
    win.widgets["open_bottom"].setChecked(False)
    choose("holes", VORONOI)
    choose("colour_style", BANDS)
    win.export_3mf()
    parts = read_3mf(out["3mf"])
    check("... and a vase with holes and bands exports as closed hollow parts", len(parts) == len(win.design.bands)
          and all(edge_check(part[2])[0] for part in parts))
    choose("holes", NO_HOLES)
    # masks and helmets: sized by the head they fit, in Simple mode; the face's settings in Advanced
    win.use_gallery("Theatre Mask")
    win.set_simple_mode(True, remember=False)
    settle()
    check("a mask shows the head it fits in Simple mode, instead of Tall and Wide",
          sp.head_row.isVisibleTo(sp) and not sp.size_row.isVisibleTo(sp) and not sp.side.isVisibleTo(sp)
          and abs(sp.head.value() - 57.0) < 0.15 and "Fits a head" in win.info.toPlainText())
    sp.head.setValue(52.0)
    settle()
    check("... and a head size fits it to that head, face and all", abs(win.design.head_fit - 520.0) < 2.0
          and abs(sp.head.value() - 52.0) < 0.15 and win.params.eye_up < 115.0 and win.design.closed)
    win.undo()
    check("... which Undo takes back", abs(sp.head.value() - 57.0) < 0.15 and win.params.eye_up > 120.0)
    win.set_simple_mode(False, remember=False)
    check("Advanced shows the face's settings in use", win._wanted("head") and win._wanted("eye_tilt")
          and win._wanted("nose_depth") and win._wanted("mouth_smile"))
    choose("mouth", CHIN_MOUTH)
    check("... and only those", not win._wanted("mouth_slots") and not win._wanted("mouth_height")
          and win.design.closed and "open down to the chin" in win.info.toPlainText())
    win.use_plain()
    choose("vase_mode", REAL_VASE)
    choose("eyes", ALMOND_EYES)
    check("eyes on a seamless vase make it a normal print", win.params.vase_mode == FAKE_VASE
          and win.design.holes_open and not win._wanted("head"))
    win.widgets["closed_top"].setChecked(True)
    settle()
    check("a closed top comes to a point", "closed in a point" in win.info.toPlainText() and win.design.closed)
    win.widgets["closed_top"].setChecked(False)
    win.widgets["around"].setValue(200.0)
    settle()
    check("... and a wall part way round leaves the back open", "200° of the way round" in win.info.toPlainText()
          and win.design.closed)
    win.use_plain()
    win.set_simple_mode(True, remember=False)
    settle()
    check("a vase shows Tall and Wide again", sp.size_row.isVisibleTo(sp) and not sp.head_row.isVisibleTo(sp))
    pt = QApplication.font().pointSizeF()
    win.a_big.trigger()
    qapp.processEvents()
    check("Bigger text makes the writing bigger", QApplication.font().pointSizeF() > 1.25 * pt)
    win.a_big.trigger()
    win.a_light.trigger()
    qapp.processEvents()
    check("... the light theme is light", QApplication.palette().color(QPalette.Window).lightness() > 200)
    win.a_light.trigger()
    qapp.processEvents()
    check("... and both go back", abs(QApplication.font().pointSizeF() - pt) < 0.01
          and QApplication.palette().color(QPalette.Window).lightness() < 80)
    win.set_simple_mode(False, remember=False)

    # a broken function is reported, not crashed on
    win.widgets["expression"].setPlainText("sin(theta")
    settle()
    check("a broken function is reported in the panel", "Your own function" in win.info.toPlainText())
    win.widgets["expression"].setPlainText("")
    settle()
    win._dirty = False
    win.close()
    failed = [w for w, ok in checks if not ok]
    print(f"\n{len(checks) - len(failed)} of {len(checks)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    np.seterr(all="ignore")
    sys.exit(main())
