"""Draw a picture of each ready-made vase for Choose a design: assets/gallery/<name>.png.

    .venv\\Scripts\\python tools\\make_thumbnails.py

The window opens on the second screen, if there is one, draws each vase in the
3D view and keeps the middle of it, the vase filling the picture.
"""

import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import numpy as np  # noqa: E402
from PySide6.QtCore import QSettings, Qt  # noqa: E402
from PySide6.QtGui import QImage  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from vaseinator import app as appmod  # noqa: E402
from vaseinator.presets import GALLERY, slug  # noqa: E402

W, H = 150, 190          # the picture, as Choose a design shows it


def vase_box(img: QImage):
    """Where the vase is: pixels unlike the background of their own row (the background is a vertical
    gradient), in the middle of the view."""
    img = img.convertToFormat(QImage.Format_RGB32)
    w, h = img.width(), img.height()
    a = np.frombuffer(img.constBits(), np.uint8).reshape(h, img.bytesPerLine() // 4, 4)[:, :w, :3].astype(int)
    diff = np.abs(a - a[:, 3:4, :]).sum(axis=2) > 24
    diff[:20] = diff[-20:] = False
    diff[:, : w // 5] = diff[:, 4 * w // 5:] = False
    ys, xs = np.nonzero(diff)
    return xs.min(), ys.min(), xs.max(), ys.max()


def picture(win) -> QImage:
    win.show_view(appmod.VASE)
    QApplication.processEvents()
    win.viewer.repaint()
    img = win.viewer.grabFramebuffer()
    img.setDevicePixelRatio(1.0)
    x0, y0, x1, y1 = vase_box(img)
    # a margin round the vase, at the picture's own shape
    cx, cy = 0.5 * (x0 + x1), 0.5 * (y0 + y1)
    side = max((x1 - x0) * 1.12 / W, (y1 - y0) * 1.12 / H)
    crop = img.copy(int(cx - side * W / 2), int(cy - side * H / 2), int(side * W), int(side * H))
    return crop.scaled(W, H, Qt.KeepAspectRatio, Qt.SmoothTransformation)


def main():
    app = QApplication(sys.argv)
    appmod.apply_dark_theme(app)
    settings = QSettings(os.path.join(tempfile.mkdtemp(), "thumbs.ini"), QSettings.IniFormat)
    settings.setValue("spin", False)
    win = appmod.MainWindow(settings)
    appmod.place_for_testing(win, sys.argv)
    out = os.path.join(ROOT, "assets", "gallery")
    os.makedirs(out, exist_ok=True)
    jobs = [("plain_cylinder", win.use_plain)] + [(slug(t), lambda t=t: win.use_gallery(t)) for t, _, _ in GALLERY]
    for name, load in jobs:
        load()
        win._flush()
        picture(win).save(os.path.join(out, name + ".png"))
        print("wrote", name + ".png")
    win._dirty = False
    win.close()


if __name__ == "__main__":
    main()
