"""Desktop feature controls; runs without a display using QT_QPA_PLATFORM=offscreen."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QSettings
from PySide6.QtGui import QFontDatabase, QFont
from PySide6.QtWidgets import QApplication, QCheckBox, QMessageBox
from vaseinator.app import MainWindow
from vaseinator.design_tools import DesignTools, save_calibration
from vaseinator.threemf import read_3mf


class DesktopToolsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        font = Path("C:/Windows/Fonts/segoeui.ttf")
        if font.exists():
            ident = QFontDatabase.addApplicationFont(str(font))
            families = QFontDatabase.applicationFontFamilies(ident)
            if families:
                cls.app.setFont(QFont(families[0], 10))

    def test_library_profile_recovery_and_samples(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings = QSettings(str(Path(tmp) / "test.ini"), QSettings.IniFormat)
            win = MainWindow(settings)
            win.params.facet_size = 2
            dialog = DesignTools(win)
            dialog.show()
            self.app.processEvents()
            colour = next(
                c for c in dialog.findChildren(QCheckBox) if c.text() == "Colours"
            )
            colour.setChecked(True)
            self.assertIn("Colours", win.workspace.data["locks"])
            dialog.run("save", dict(category="designs", name="Variant"))
            entry = win.workspace.data["designs"][0]
            dialog.run("favorite", {"id": entry["id"]})
            self.assertTrue(entry["favorite"])
            win.params.line_width = 0.8
            dialog.run(
                "save", dict(category="profiles", name="Printer", kind="printer")
            )
            profile = win.workspace.data["profiles"][0]
            win.params.line_width = 0.4
            dialog.run("restore", dict(category="profiles", id=profile["id"]))
            self.assertEqual(win.params.line_width, 0.8)
            win.current_file = "old.vase"
            dialog.run("restore", dict(category="designs", id=entry["id"]))
            self.assertIsNone(win.current_file)
            self.assertEqual(win.params.line_width, entry["params"]["line_width"])
            self.assertTrue(win.workspace.data["recovery"])
            self.assertEqual(
                json.loads(settings.value("workspace")), win.workspace.data
            )
            path = str(Path(tmp) / "samples.3mf")
            with (
                patch(
                    "vaseinator.design_tools.QFileDialog.getSaveFileName",
                    return_value=(path, ""),
                ),
                patch.object(QMessageBox, "information"),
            ):
                save_calibration(win)
            self.assertEqual(len(read_3mf(path)), 10)
            dialog.grab().save("work-temp/desktop-library.png")
            dialog.close()
            win._dirty = False
            win.close()


if __name__ == "__main__":
    unittest.main()
