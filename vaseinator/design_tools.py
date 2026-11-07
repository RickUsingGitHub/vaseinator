"""Desktop controls for the shared portable design tools."""

import json

from PySide6.QtCore import Qt, QSize, QByteArray
from PySide6.QtGui import QIcon, QPixmap, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QCheckBox,
    QTabWidget,
    QWidget,
    QListWidget,
    QListWidgetItem,
    QInputDialog,
    QFileDialog,
    QMessageBox,
)

from .workspace import LOCKS, comparison, calibration_parts, CALIBRATION_HELP, thumbnail
from .params import VaseParams
from .threemf import write_3mf


def show_comparison(win):
    win._flush()
    d = win._current_design()
    if d is None:
        return
    data = comparison(d)
    dlg = QDialog(win)
    dlg.setWindowTitle("Original and softened")
    dlg.resize(700, 500)
    layout = QVBoxLayout(dlg)
    label = QLabel(data["text"])
    label.setWordWrap(True)
    layout.addWidget(label)
    svg = QSvgWidget()
    svg.load(QByteArray(data["svg"].encode()))
    layout.addWidget(svg)
    dlg.exec()


def save_calibration(win):
    path, _ = QFileDialog.getSaveFileName(
        win, "Save clearance samples", "clearance_samples.3mf", "3MF (*.3mf)"
    )
    if not path:
        return
    if not path.lower().endswith(".3mf"):
        path += ".3mf"
    try:
        write_3mf(
            path,
            "Clearance samples",
            calibration_parts(),
            (win.params.bed_x / 2, win.params.bed_y / 2, 0),
        )
    except OSError as exc:
        QMessageBox.warning(win, "Could not save samples", str(exc))
        return
    QMessageBox.information(win, "How to use the samples", CALIBRATION_HELP)


class DesignTools(QDialog):
    def __init__(self, win):
        super().__init__(win)
        self.win = win
        self.setWindowTitle("Design library and profiles")
        self.resize(760, 620)
        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                "Keep these when using Surprise me (printer settings are always kept):"
            )
        )
        row = QHBoxLayout()
        self.lock_boxes = {}
        for name in LOCKS:
            box = QCheckBox(name)
            box.setChecked(name in win.workspace.data["locks"])
            row.addWidget(box)
            self.lock_boxes[name] = box
            box.toggled.connect(lambda on, n=name: self.lock(n, on))
        layout.addLayout(row)
        note = QLabel(
            "Library and recovery stay on this computer. Export a library backup to transfer it to the web app. Recovery keeps the last 30 settled designs. Thumbnails are silhouette sketches."
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        tabs = QTabWidget()
        layout.addWidget(tabs)
        self.lists = {}
        for category, title in [
            ("designs", "My designs"),
            ("profiles", "Printer and material profiles"),
            ("recovery", "Recovery"),
        ]:
            page = QWidget()
            box = QVBoxLayout(page)
            entries = QListWidget()
            entries.setIconSize(QSize(80, 80))
            box.addWidget(entries)
            self.lists[category] = entries
            buttons = QHBoxLayout()
            box.addLayout(buttons)

            def button(text, callback):
                b = QPushButton(text)
                b.clicked.connect(callback)
                buttons.addWidget(b)

            if category == "designs":
                button("Save current variant", lambda: self.save("designs"))
                button("Favourite", lambda: self.selected("designs", "favorite"))
            if category == "profiles":
                button("Save printer", lambda: self.save("profiles", "printer"))
                button("Save material", lambda: self.save("profiles", "material"))
            button(
                "Restore / apply",
                lambda _=False, c=category: self.selected(c, "restore"),
            )
            button("Remove", lambda _=False, c=category: self.selected(c, "delete"))
            tabs.addTab(page, title)
        row = QHBoxLayout()
        layout.addLayout(row)
        for text, fn in [
            ("Export library backup", self.export_file),
            ("Import library", self.import_file),
            ("Close", self.accept),
        ]:
            b = QPushButton(text)
            b.clicked.connect(fn)
            row.addWidget(b)
        self.refresh()

    def lock(self, name, on):
        locks = set(self.win.workspace.data["locks"])
        locks.add(name) if on else locks.discard(name)
        self.win.workspace.command("locks", self.win.params, {"locks": list(locks)})
        self.win._save_workspace()

    def refresh(self):
        for name, box in self.lock_boxes.items():
            box.blockSignals(True)
            box.setChecked(name in self.win.workspace.data["locks"])
            box.blockSignals(False)
        for category, widget in self.lists.items():
            widget.clear()
            for e in sorted(
                self.win.workspace.data[category],
                key=lambda e: (e["favorite"], e["created"]),
                reverse=True,
            ):
                text = (
                    ("★ " if e["favorite"] else "") + e["name"] + " — " + e["created"]
                )
                if category == "profiles":
                    text = e["kind"].title() + ": " + text
                item = QListWidgetItem(text)
                item.setData(Qt.UserRole, e["id"])
                if category == "designs":
                    renderer = QSvgRenderer(
                        QByteArray(
                            thumbnail(VaseParams.from_dict(e["params"])).encode()
                        )
                    )
                    pix = QPixmap(80, 80)
                    pix.fill(Qt.transparent)
                    painter = QPainter(pix)
                    renderer.render(painter)
                    painter.end()
                    item.setIcon(QIcon(pix))
                widget.addItem(item)

    def save(self, category, kind="printer"):
        name, ok = QInputDialog.getText(
            self,
            "Save variant" if category == "designs" else "Save profile",
            "Name:",
            text=self.win.params.name,
        )
        if ok and name.strip():
            self.run("save", dict(category=category, name=name, kind=kind))

    def selected(self, category, op):
        item = self.lists[category].currentItem()
        if item is None:
            return
        if (
            op == "delete"
            and QMessageBox.question(self, "Remove entry", "Remove this saved entry?")
            != QMessageBox.Yes
        ):
            return
        self.run(op, dict(category=category, id=item.data(Qt.UserRole)))

    def run(self, op, payload):
        try:
            self.win._flush()
            result = self.win.workspace.command(op, self.win.params, payload)
            if result["params"]:
                if payload.get("category") != "profiles":
                    self.win.current_file = None
                self.win._restore(result["params"])
            self.win._save_workspace()
            self.refresh()
        except (ValueError, KeyError, StopIteration) as exc:
            QMessageBox.warning(self, "Design tools", str(exc))

    def export_file(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export library", "vaseinator-library.json", "JSON (*.json)"
        )
        if path:
            try:
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(self.win.workspace.dumps())
            except OSError as exc:
                QMessageBox.warning(self, "Export failed", str(exc))

    def import_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import library", "", "JSON (*.json)"
        )
        if path:
            try:
                with open(path, encoding="utf-8") as fh:
                    data = json.load(fh)
                self.run("import", data)
            except (ValueError, OSError) as exc:
                QMessageBox.warning(self, "Import failed", str(exc))
