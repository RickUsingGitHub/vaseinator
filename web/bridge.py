"""The web page's Python: the same vaseinator package as the desktop app, run in the browser by Pyodide.

The page's workers call these functions with settings as JSON text and get JSON text back - and, for a
built vase, its mesh as raw bytes the page draws with three.js. The settings, the rules for which are shown
and what a change brings with it, the panel's report and the help are the desktop app's own.
"""

from __future__ import annotations

import base64
import io
import json
import math
import os
import re
import tempfile

import numpy as np

from vaseinator import __version__, sections
from vaseinator.choices import COLOURS, MANY_COLOURS, NO_PATTERN, PATTERNS, SHAPES_FROM_ABOVE, pattern_of, twist_words
from vaseinator.expr import EXAMPLES
from vaseinator.geometry import TOLERANCE, VaseDesign, fit_head
from vaseinator.params import (CIRCLE, DRAWN, EVENLY, FAKE_VASE, FILE_FORMAT, FILE_VERSION, ONE_COLOUR, OWN,
                               OWN_PROFILE, POLYGON, REAL_VASE, SAME, VaseParams)
from vaseinator.presets import GALLERY, PRINTER_KEYS, gallery_design, plain_design, slug, surprise
from vaseinator.report import ABOUT, DRAWING_HELP, PRINTING_HELP, function_help, info_html, print_steps
from vaseinator.settings import COLOUR_STYLES, LIVE_KEYS, REAL_COLOUR_STYLES, SPEC, TEXT_KEYS, change, wanted
from vaseinator.shapes import PALETTES, PROFILES, SHAPE_LABELS, pchip, shape_table
from vaseinator.stl import write_stl
from vaseinator.threemf import write_3mf

SLICES = 14                   # layers drawn in the from-above picture, as the desktop app draws them


def _report(d, errors, warnings) -> str:
    """The desktop app's report, without its own style sheet: the page styles it."""
    return re.sub(r"^<style>.*?</style>", "", info_html(d, errors, warnings), flags=re.S)


def _params(text: str) -> VaseParams:
    return VaseParams.from_dict(json.loads(text))


def _dump(p: VaseParams) -> str:
    return json.dumps(p.to_dict())


def _shown(p: VaseParams) -> list:
    return [row[0] for _, rows in SPEC for row in rows if wanted(p, row[0])]


# ------------------------------------------------------------------ the choices
def _spec():
    """Every setting, by group, as the Advanced panel lists them."""
    groups = []
    for title, items in SPEC:
        rows = []
        for key, label, kind, lo, hi, step, extra, tip in items:
            row = dict(key=key, label=label, kind=kind, tip=tip, extra=extra)
            if kind == "choice":
                row["choices"] = [[v, t] for v, t in lo]
            elif kind == "curve":
                row["curve"] = lo
            else:
                row.update(lo=lo, hi=hi, step=step)
            rows.append(row)
        groups.append(dict(title=title, rows=rows))
    return groups


def start() -> str:
    """Everything the page needs: the gallery, the choices and pictures, every setting, the help."""
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
        many_colours=[dict(name=n, palette=pal, settings=s, colours=list(palettes[pal]))
                      for n, pal, s in MANY_COLOURS],
        palettes=[dict(name=n, colours=list(c)) for n, c in PALETTES],
        printer_keys=list(PRINTER_KEYS),
        spec=_spec(), live_keys=sorted(LIVE_KEYS), text_keys=sorted(TEXT_KEYS),
        colour_styles=[[v, t] for v, t in COLOUR_STYLES],
        real_colour_styles=[[v, t] for v, t in REAL_COLOUR_STYLES],
        outlines=[dict(name=n, points=[list(q) for q in pts], repeat=r) for n, pts, r in sections.OUTLINES],
        examples=[[n, f] for n, f in EXAMPLES],
        shape_labels={str(k): list(v) for k, v in SHAPE_LABELS.items()},
        help=dict(printing=PRINTING_HELP, drawing=DRAWING_HELP, about=ABOUT, function=function_help()),
        constants=dict(SAME=SAME, CIRCLE=CIRCLE, POLYGON=POLYGON, DRAWN=DRAWN, OWN=OWN, OWN_PROFILE=OWN_PROFILE,
                       EVENLY=EVENLY, REAL_VASE=REAL_VASE, FAKE_VASE=FAKE_VASE, ONE_COLOUR=ONE_COLOUR),
        defaults=VaseParams().to_dict(),
        plain=plain_design().to_dict(),
    ))


def shown(text: str) -> str:
    """Which settings the Advanced panel shows for this design."""
    return json.dumps(_shown(_params(text)))


def apply(text: str, key: str, value: str) -> str:
    """One change, as the panel makes it, with what follows from it (the desktop app's own rules)."""
    p = _params(text)
    touched, message = change(p, key, json.loads(value))
    p = VaseParams.from_dict(p.to_dict())
    return json.dumps(dict(params=p.to_dict(), touched=touched, message=message, shown=_shown(p)))


def design_of(title: str, keep: str) -> str:
    """A ready-made design (or the plain cylinder), with the printer settings of ``keep``."""
    k = _params(keep)
    return _dump(plain_design(k) if title == "Plain cylinder" else gallery_design(title, keep=k))


def surprise_me(keep: str, seed: int) -> str:
    return _dump(surprise(_params(keep), int(seed)))


def fit(text: str, head_mm: float) -> str:
    """The design scaled to fit a head this many mm round."""
    return _dump(fit_head(_params(text), float(head_mm)))


def trace(pixels: str, width: int, height: int) -> str:
    """Control points tracing the outline drawn in a picture: its RGBA pixels, base64."""
    rgba = np.frombuffer(base64.b64decode(pixels), dtype=np.uint8).reshape(int(height), int(width), 4)
    return json.dumps(sections.trace_rgba(rgba))


# ------------------------------------------------------------------ building it
def _gradient(colours, phase):
    """The blend the 3D view uses for a gradient spool, for each phase."""
    ring = np.asarray(colours, dtype=float)
    n = len(ring)
    ph = np.mod(phase, 1.0) * n
    k = np.floor(ph).astype(int) % n
    t = ph - np.floor(ph)
    t = t * t * (3.0 - 2.0 * t)
    return ring[k] * (1.0 - t)[:, None] + ring[(k + 1) % n] * t[:, None]


def _colours(d: VaseDesign, z: np.ndarray) -> np.ndarray:
    """The colour of each height, as the desktop app's 3D view shows it: bands, or a gradient spool."""
    cols = d.p.colors()
    if d.gradient:
        return _gradient([cols[k] for k in d.gradient_fils], d.colour_phase(z))
    starts = np.array([b[0] for b in d.bands])
    band_cols = np.array([cols[f] for _, f in d.bands], dtype=float)
    idx = np.clip(np.searchsorted(starts, z, side="right") - 1, 0, len(starts) - 1)
    return band_cols[idx]


def _plots(d: VaseDesign) -> dict:
    """What the side and from-above pictures under the 3D view draw, as the desktop app draws them."""
    z = np.asarray(d.profile_z, dtype=float)
    step = max(1, len(z) // 400)
    keep = np.unique(np.concatenate([np.arange(0, len(z), step), [len(z) - 1]]))
    lim = d.p.max_overhang + TOLERANCE
    bad = np.nonzero(d.band_lean > lim)[0]
    bad_z = (z[np.minimum(bad, len(z) - 1)] if d.rows is None
             else np.array([d.rows[min(b, len(d.rows) - 1)][0] for b in bad]))
    moved = z[d.row_moved > 0.05] if d.softened > 0.05 and d.row_moved is not None else np.zeros(0)
    heights = [min(max(d.H * k / SLICES, 0.02), d.H - 0.02) for k in range(SLICES + 1)]
    slices = [np.round(d.contour(zc)[:, :, :2], 2).reshape(-1).tolist() for zc in heights]
    return dict(z=np.round(z[keep], 3).tolist(), rmax=np.round(d.profile_max[keep], 3).tolist(),
                rmin=np.round(d.profile_min[keep], 3).tolist(), colours=np.round(_colours(d, z[keep]), 4).tolist(),
                zb=float(d.zb), bad=np.round(bad_z, 2).tolist(), moved=np.round(moved[::step], 2).tolist(),
                slices=slices, slice_colours=np.round(_colours(d, np.array(heights)), 4).tolist(),
                half=0.5 * float(max(d.size[0], d.size[1], 1.0)), height=float(d.H), widest=float(d.widest))


def build(text: str, draft: bool):
    """Build the vase. Returns (what the page shows about it, as JSON; positions; triangles; colours; each
    corner's steepest lean) - the last four as raw float32 / uint32 bytes."""
    p = _params(text)
    d = VaseDesign(p, draft=bool(draft))
    meta = dict(errors=d.errors, warnings=d.warnings)
    if d.errors:
        meta["report"] = _report(None, d.errors, d.warnings)
        return json.dumps(meta), b"", b"", b"", b""
    verts = np.asarray(d.shell_verts, dtype=np.float64)
    faces = np.asarray(d.shell_faces, dtype=np.int64)
    lean = np.full(len(verts), -1.0)
    np.maximum.at(lean, faces.ravel(), np.repeat(np.asarray(d.shell_lean, dtype=float), 3))
    fz, fa = np.asarray(d.filament_z, dtype=float), np.asarray(d.filament_at, dtype=float)
    pick = np.unique(np.linspace(0, len(fz) - 1, min(len(fz), 300)).astype(int))
    meta.update(
        info=d.info(), notes=d.notes, draft=bool(draft), height=float(d.H), size=[float(s) for s in d.size],
        widest=float(max(v for _, v in p.silhouette)), head=round(float(d.head_fit) / 10.0, 1),
        worn=bool(d.p.worn), pattern=pattern_of(d.p),
        twist_words=twist_words(d.p.twist) if d.p.twist_style != OWN else "Your own curve",
        ok=bool(d.worst <= d.p.max_overhang + TOLERANCE), look=int(d.p.look), normal=bool(d.normal),
        triangles=int(len(faces)), bed=[float(d.p.bed_x), float(d.p.bed_y), float(d.p.printer_height)],
        limit=float(d.p.max_overhang), report=_report(d, [], d.warnings), plan=d.colour_plan(), plots=_plots(d),
        printing=dict(z=np.round(fz[pick], 3).tolist(), at=np.round(fa[pick], 2).tolist(), layers=int(d.layers),
                      seconds=float(d.seconds), grams=float(d.grams)))
    colours = _colours(d, verts[:, 2]).astype(np.float32)
    return (json.dumps(meta), verts.astype(np.float32).tobytes(), faces.astype(np.uint32).tobytes(),
            colours.tobytes(), lean.astype(np.float32).tobytes())


# ------------------------------------------------------------------ files
def _name(p: VaseParams) -> str:
    name = "".join(ch if ch.isalnum() or ch in "-_ " else "_" for ch in p.name).strip()
    return name or "vase"


def export_3mf(text: str):
    """The vase for the slicer, as the desktop app's Save for printing makes it: a part per band of colour.
    Returns (the file, the steps to print it, as HTML)."""
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
        data = fh.read()
    steps = print_steps(d, f"your downloads/{base}.3mf", len(parts))
    return data, steps.replace(" (the button below, or File ▸ Import)", " (File ▸ Import)")


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
