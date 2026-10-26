"""Drive the main window without a person: edits, curves, undo, the gallery, the views and the exports.

Run:  .venv\\Scripts\\python -m tests.test_app
"""

import os
import sys
import tempfile

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QPoint, QSettings, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox  # noqa: E402

from vaseinator import app as appmod  # noqa: E402
from vaseinator.geometry import edge_check  # noqa: E402
from vaseinator.params import CIRCLE, GRADIENT, OWN, OWN_PROFILE, POLYGON, STAR, SWING, load_design  # noqa: E402
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
          and win._wanted("twist_curve") is not win.simple_mode)

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
    check("the exported STL is watertight", edge_check(faces)[0] and len(faces) == win.design.triangles)
    win.export_3mf()
    name, v3, f3, fil, pos = read_3mf(out["3mf"])
    check("the 3MF sits in the middle of the bed", pos == (win.params.bed_x / 2, win.params.bed_y / 2, 0.0)
          and len(f3) == win.design.triangles)
    win.copy_colour_plan()
    check("the colour plan goes to the clipboard", "Vaseinator" in QApplication.clipboard().text())

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
