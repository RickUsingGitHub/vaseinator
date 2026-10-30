"""Finding the slicer programs on this computer, to open a saved vase in one."""

from __future__ import annotations

import glob
import os

from PySide6.QtCore import QProcess

# (name, where it is usually installed, under Program Files or the user's own Programs folder)
KNOWN = [
    ("Flash Studio", r"Flashforge\Flash Studio*\flash studio.exe"),
    ("Orca Slicer", r"OrcaSlicer\orca-slicer.exe"),
    ("Bambu Studio", r"Bambu Studio\bambu-studio.exe"),
    ("PrusaSlicer", r"Prusa3D\PrusaSlicer\prusa-slicer.exe"),
    ("UltiMaker Cura", r"UltiMaker Cura *\UltiMaker-Cura.exe"),
    ("Creality Print", r"Creality\Creality Print*\CrealityPrint.exe"),
    ("Elegoo Slicer", r"ElegooSlicer\elegoo-slicer.exe"),
    ("Anycubic Slicer Next", r"AnycubicSlicerNext\AnycubicSlicerNext.exe"),
]


def _roots():
    for var in ("ProgramFiles", "ProgramFiles(x86)", "ProgramW6432"):
        if os.environ.get(var):
            yield os.environ[var]
    if os.environ.get("LOCALAPPDATA"):
        yield os.path.join(os.environ["LOCALAPPDATA"], "Programs")


def find_slicers() -> list[tuple[str, str]]:
    """The slicers installed here, as (name, program path), each once."""
    found, seen = [], set()
    for name, pattern in KNOWN:
        for root in _roots():
            for path in sorted(glob.glob(os.path.join(root, pattern)), reverse=True):    # the newest first
                key = os.path.normcase(os.path.abspath(path))
                if key not in seen:
                    seen.add(key)
                    found.append((name, path))
                    break
    return found


def slicer_name(path: str) -> str:
    for name, pattern in KNOWN:
        if os.path.basename(path).lower() == os.path.basename(pattern).lower():
            return name
    return os.path.splitext(os.path.basename(path))[0]


def open_in(program: str, file: str) -> bool:
    """Start the slicer with the file; True if it started."""
    return bool(program and os.path.exists(program)
                and QProcess.startDetached(program, [os.path.abspath(file)], os.path.dirname(program))[0])
