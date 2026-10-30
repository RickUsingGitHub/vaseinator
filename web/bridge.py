"""The web page's Python: the same vaseinator package as the desktop app, run in the browser by Pyodide.

The page's worker calls these functions with settings as JSON text and gets JSON text back - and, for a
built vase, its mesh as raw bytes the page draws with three.js.
"""

from __future__ import annotations

import io
import json
import math
import os
import tempfile

import numpy as np

from vaseinator import __version__
from vaseinator.choices import COLOURS, MANY_COLOURS, NO_PATTERN, PATTERNS, SHAPES_FROM_ABOVE, pattern_of, twist_words
from vaseinator.geometry import TOLERANCE, VaseDesign, fit_head
from vaseinator.params import (CIRCLE, EVENLY, FAKE_VASE, FILE_FORMAT, FILE_VERSION, GRADIENT, ONE_COLOUR, OWN,
                               POLYGON, REAL_VASE, SAME, VaseParams)
from vaseinator.presets import GALLERY, PRINTER_KEYS, gallery_design, plain_design, slug, surprise
from vaseinator.shapes import PALETTES, PROFILES, pchip, shape_table
from vaseinator.stl import write_stl
from vaseinator.threemf import write_3mf


def _params(text: str) -> VaseParams:
    return VaseParams.from_dict(json.loads(text))


def _dump(p: VaseParams) -> str:
    return json.dumps(p.to_dict())


# ------------------------------------------------------------------ the choices
def start() -> str:
    """Everything the page needs to draw its pictures: the gallery, the choices, the defaults."""
    def above(settings):
        r = shape_table(settings.get("shape1", CIRCLE), settings.get("count1", 5), settings.get("depth1", 0.0),
                        settings.get("sharp1", 0.5))
        a = np.arange(len(r)) * (2 * math.pi / len(r)) + math.radians(settings.get("turn1", 0.0))
        step = max(len(r) // 160, 1)
        return [[round(float(rr * math.cos(t)), 4), round(float(rr * math.sin(t)), 4)]
                for rr, t in zip(r[::step], a[::step])]

    def side(points):
        pts = np.asarray(points, dtype=float)
        hs = np.linspace(0.0, 1.0, 40)
        d = np.clip(pchip(pts[:, 0], pts[:, 1], hs), 0.05, None)
        return [round(float(v), 4) for v in d / d.max()]

    palettes = dict(PALETTES)
    return json.dumps(dict(
        version=__version__,
        gallery=[dict(title=t, about=about, slug=slug(t), worn=bool(ch.get("worn", False)))
                 for t, about, ch in GALLERY],
        shapes=[dict(name=n, settings=s, outline=above(s)) for n, s in SHAPES_FROM_ABOVE],
        profiles=[dict(name=full.split(" (")[0], full=full, widths=side(pts), points=[list(q) for q in pts])
                  for full, pts in PROFILES],
        patterns=[dict(name=n, settings=s) for n, s in PATTERNS],
        no_pattern=NO_PATTERN,
        colours=[dict(name=n, colour=c) for n, c in COLOURS],
        many_colours=[dict(name=n, palette=pal, settings=s, colours=list(palettes[pal])) for n, pal, s in MANY_COLOURS],
        printer_keys=list(PRINTER_KEYS),
        constants=dict(SAME=SAME, CIRCLE=CIRCLE, POLYGON=POLYGON, OWN=OWN, EVENLY=EVENLY, REAL_VASE=REAL_VASE,
                       FAKE_VASE=FAKE_VASE, ONE_COLOUR=ONE_COLOUR),
        defaults=VaseParams().to_dict(),
        plain=plain_design().to_dict(),
    ))


def design_of(title: str, keep: str) -> str:
    """A ready-made design (or the plain cylinder), with the printer settings of ``keep``."""
    k = _params(keep)
    return _dump(plain_design(k) if title == "Plain cylinder" else gallery_design(title, keep=k))


def surprise_me(keep: str, seed: int) -> str:
    return _dump(surprise(_params(keep), int(seed)))


def fit(text: str, head_mm: float) -> str:
    """The design scaled to fit a head this many mm round."""
    return _dump(fit_head(_params(text), float(head_mm)))


# ------------------------------------------------------------------ building it
def _colours(d: VaseDesign, z: np.ndarray) -> np.ndarray:
    """The colour of each height, as the desktop app's 3D view shows it: bands, or a gradient spool."""
    cols = d.p.colors()
    if d.gradient:
        ring = np.array([cols[k] for k in d.gradient_fils], dtype=float)
        n = len(ring)
        ph = np.mod(d.colour_phase(z), 1.0) * n
        k = np.floor(ph).astype(int) % n
        t = ph - np.floor(ph)
        t = t * t * (3.0 - 2.0 * t)
        return ring[k] * (1.0 - t)[:, None] + ring[(k + 1) % n] * t[:, None]
    starts = np.array([b[0] for b in d.bands])
    band_cols = np.array([cols[f] for _, f in d.bands], dtype=float)
    idx = np.clip(np.searchsorted(starts, z, side="right") - 1, 0, len(starts) - 1)
    return band_cols[idx]


def build(text: str, draft: bool):
    """Build the vase. Returns (what the panel shows, as JSON; positions; triangles; colours) - the last
    three as raw float32 / uint32 bytes."""
    p = _params(text)
    d = VaseDesign(p, draft=bool(draft))
    meta = dict(errors=d.errors, warnings=d.warnings)
    if d.errors:
        return json.dumps(meta), b"", b"", b""
    verts = np.asarray(d.shell_verts, dtype=np.float64)
    faces = np.asarray(d.shell_faces, dtype=np.uint32)
    widest = max(v for _, v in p.silhouette)
    meta.update(
        info=d.info(), notes=d.notes, draft=bool(draft), height=float(d.H), size=[float(s) for s in d.size],
        widest=float(widest), head=round(float(d.head_fit) / 10.0, 1), worn=bool(d.p.worn),
        pattern=pattern_of(d.p), twist_words=twist_words(d.p.twist) if d.p.twist_style != OWN else "Your own curve",
        ok=bool(d.worst <= d.p.max_overhang + TOLERANCE), look=int(d.p.look), normal=bool(d.normal),
        triangles=int(len(faces)), bed=[float(d.p.bed_x), float(d.p.bed_y), float(d.p.printer_height)],
        params=d.p.to_dict(), steps=_steps(d))
    colours = _colours(d, verts[:, 2]).astype(np.float32)
    return json.dumps(meta), verts.astype(np.float32).tobytes(), faces.tobytes(), colours.tobytes()


def _steps(d: VaseDesign) -> list:
    """Plain steps to print it, as Save for printing gives them."""
    p = d.p
    if p.vase_mode == REAL_VASE:
        settings = (f"turn on <b>Spiral vase</b> (Spiralize), with <b>{d.bottom_layers} bottom layers</b> and the "
                    f"outer wall <b>{p.line_width:g} mm</b> wide")
    else:
        settings = ("leave <b>Spiral vase off</b> and use your <b>usual settings</b>: the wall is in the model, "
                    f"{d.wall:.1f} mm thick, so there is nothing to change")
    fils = sorted({f for _, f in d.bands})
    steps = ["Open it in your slicer (File ▸ Import in Flash Studio, OrcaSlicer, Bambu Studio or PrusaSlicer).",
             f"In the print settings: {settings}.",
             f"<b>No supports</b> - none are needed: nothing leans more than {d.worst:.0f}°."]
    if p.worn or p.around < 360.0 or p.open_bottom:
        steps.append("Add a <b>brim</b>: it stands on a thin edge" + (", a mask on its chin" if p.around < 360.0
                                                                     else "") + ".")
    if p.straps:
        steps.append("When it is done, thread an <b>elastic strap</b> through the slots at the sides.")
    if len(fils) > 1 and p.vase_mode != REAL_VASE and p.colour_style != GRADIENT:
        steps.append(f"It comes as parts, one for each band of colour, already set to filaments "
                     f"{', '.join(str(k) for k in fils)}: load those colours in those slots, or change them in "
                     "the slicer.")
    else:
        steps.append("Load the filament you want.")
    hours = int(round(d.seconds / 60.0))
    took = f"{hours // 60} h {hours % 60:02d} min" if hours >= 60 else f"{max(hours, 1)} min"
    steps.append(f"Slice it and print. It takes about <b>{took}</b> and <b>{d.grams:.0f} g</b> of filament.")
    return steps


# ------------------------------------------------------------------ files
def _name(p: VaseParams) -> str:
    name = "".join(ch if ch.isalnum() or ch in "-_ " else "_" for ch in p.name).strip()
    return name or "vase"


def export_3mf(text: str) -> bytes:
    """The vase for the slicer, as the desktop app's Save for printing makes it: a part per band of colour."""
    p = _params(text)
    d = VaseDesign(p)
    if d.errors:
        raise ValueError("; ".join(d.errors))
    colors = d.p.colors()
    parts = d.print_parts()
    base = _name(p)
    many = len(parts) > 1
    named = [(f"{base} band {k + 1}" if many else base, v, f, fil, colors[fil]) for k, (fil, v, f) in enumerate(parts)]
    path = os.path.join(tempfile.gettempdir(), "vase.3mf")
    write_3mf(path, base, named, (p.bed_x / 2.0, p.bed_y / 2.0, 0.0))
    with open(path, "rb") as fh:
        return fh.read()


def export_stl(text: str) -> bytes:
    p = _params(text)
    d = VaseDesign(p)
    if d.errors:
        raise ValueError("; ".join(d.errors))
    path = os.path.join(tempfile.gettempdir(), "vase.stl")
    write_stl(path, *d.print_mesh(), _name(p))
    with open(path, "rb") as fh:
        return fh.read()


def save_vase(text: str) -> str:
    """A .vase design file, the same as the desktop app saves."""
    return json.dumps({"format": FILE_FORMAT, "version": FILE_VERSION, "params": _params(text).to_dict()}, indent=2)


def open_vase(text: str) -> str:
    """The settings from a .vase design file, made safe."""
    data = json.load(io.StringIO(text))
    if data.get("format") != FILE_FORMAT:
        raise ValueError("That is not a Vaseinator design file.")
    return _dump(VaseParams.from_dict(data.get("params", {})))
