"""Self-tests: closed watertight meshes, no overhangs, one loop per layer, and the files.

Run:  .venv\\Scripts\\python -m tests.test_vase
"""

import json
import math
import os
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
import zipfile

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vaseinator import sections  # noqa: E402
from vaseinator.expr import ExprError, compile_expression  # noqa: E402
from vaseinator.geometry import (TOLERANCE, VORONOI_LONGEST, VaseDesign, edge_check, face_normals, fit_head,  # noqa: E402
                                 lean_angles, mesh_volume)
from vaseinator import hollow  # noqa: E402
from vaseinator.params import (ALMOND_EYES, BANDS, CHIN_MOUTH, CIRCLE, DIAMOND, DRAWN, ELLIPSE, EVENLY,  # noqa: E402
                               FAKE_VASE, FLOWER, GEAR, GRADIENT, GRILLE_MOUTH, NO_HOLES, ONE_COLOUR, OPEN_MOUTH, OWN,
                               POLYGON, RAISED_NOSE, REAL_VASE, ROUND, ROUND_EYES, SAME, SLOTS, STAR, STRIPES, SWING,
                               VORONOI, VaseParams, load_design, save_design)
from vaseinator.presets import GALLERY, PRINTER_KEYS, gallery_design, plain_design, surprise  # noqa: E402
from vaseinator.shapes import PROFILES, pchip, shape_table  # noqa: E402
from vaseinator.stl import read_stl, write_stl  # noqa: E402
from vaseinator.threemf import read_3mf, write_3mf  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def plain(**changes) -> VaseParams:
    """A plain round vase, changed as given."""
    base = dict(shape1=CIRCLE, twist=0.0, rib_count=0, ring_count=0, bump_around=0, organic_depth=0.0,
                colour_style=ONE_COLOUR)
    return VaseParams(**{**base, **changes})


def designs():
    """Every ready-made vase, a dozen surprises, and some hard cases."""
    out = [(t, gallery_design(t)) for t, _, _ in GALLERY]
    out += [(f"surprise {s}", surprise(VaseParams(), s)) for s in range(1, 13)]
    out += [
        ("fast twisted gear", VaseParams(shape1=GEAR, count1=12, depth1=0.15, sharp1=0.7, twist=540,
                                         twist_style=EVENLY)),
        ("deep sharp star", VaseParams(shape1=STAR, count1=6, depth1=0.6, sharp1=1.0, twist=300)),
        ("square to circle", VaseParams(shape1=POLYGON, count1=4, sharp1=0.0, shape2=CIRCLE, twist=90)),
        ("bottle shoulder", plain(silhouette=[[0.0, 100.0], [0.5, 100.0], [0.55, 30.0], [1.0, 30.0]])),
        ("flared lip", plain(silhouette=[[0.0, 60.0], [0.9, 60.0], [1.0, 120.0]])),
        ("tiny", plain(height=12.0, silhouette=[[0.0, 8.0], [1.0, 8.0]])),
        ("drawn claw, twisted, ribbed", plain(shape1=DRAWN, drawn1=sections.CLAW, repeat1=1, twist=200,
                                              rib_count=18, rib_depth=1.2)),
        ("drawn heart to five lobes", plain(shape1=DRAWN, drawn1=sections.OUTLINES[-1][1], repeat1=1, shape2=DRAWN,
                                            twist=60)),
    ]
    return out


def thinnest_wall(d: VaseDesign) -> float:
    """The narrowest wall between two holes, along any row of the pot (mm)."""
    zs, Os, Is, fs, kb, kr, _ = d.pot_rows
    seg, along, L = hollow.row_lengths(Os)
    best = np.inf
    for j in range(len(zs)):
        hole = fs[j] > 0
        if hole.all() or not hole.any():
            continue
        i = np.nonzero(hole != np.roll(hole, -1))[0]
        at = along[j][i] + seg[j][i] * fs[j][i] / (fs[j][i] - np.roll(fs[j], -1)[i])
        order = np.argsort(at)
        at, leaving = at[order], hole[i][order]
        for k in np.nonzero(leaving)[0]:                       # a hole ends: the wall runs to the next one
            best = min(best, (at[(k + 1) % len(at)] - at[k]) % L[j])
    return best


def layer_loops(d: VaseDesign, z: float) -> int:
    """How many separate closed loops the wall makes at height z (a spiral vase needs exactly one)."""
    seg = d.contour(z)
    if not len(seg):
        return 0
    pts = np.round(seg.reshape(-1, 3)[:, :2], 4)
    _, inv = np.unique(pts, axis=0, return_inverse=True)
    edges = inv.reshape(-1, 2)
    edges = edges[edges[:, 0] != edges[:, 1]]      # a slice through a corner leaves zero-length pieces
    inv = np.unique(edges, return_inverse=True)[1]
    edges = inv.reshape(-1, 2)
    n = int(inv.max()) + 1
    if not (np.bincount(edges.ravel(), minlength=n) == 2).all():
        return -1                                    # an open end, or a crossing: not a simple loop
    parent = np.arange(n)

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for a, b in edges:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb
    return len({find(a) for a in range(n)})


# ---------------------------------------------------------------- the tests
def test_every_design_is_closed_and_printable():
    for name, p in designs():
        d = VaseDesign(p)
        assert not d.errors, (name, d.errors)
        closed, bad = edge_check(d.faces)
        assert closed, f"{name}: the solid has {bad} open or doubled edges"
        assert edge_check(d.shell_faces)[0], f"{name}: the shown shell is not closed"
        assert mesh_volume(d.verts, d.faces) > 0, f"{name}: the faces point inwards"
        assert d.worst <= p.max_overhang + TOLERANCE, f"{name}: leans {d.worst:.2f}° (limit {p.max_overhang})"
        # flat on the bed: the lowest point is the base, and the base is flat at z = 0
        assert abs(d.verts[:, 2].min()) < 1e-9 and abs(d.verts[:, 2].max() - d.H) < 1e-9, name
        down = d.faces[d.side:d.side + (len(d.faces) - d.side) // 2]
        assert np.allclose(d.verts[down][:, :, 2], 0.0), f"{name}: the base is not flat"
        for z in np.linspace(0.3, d.H - 0.3, 9) + 0.0123:
            loops = layer_loops(d, z)
            if d.holes_open:                          # holes cut a layer into pieces: each one still closed
                assert loops >= 1, f"{name}: the layer at {z:.1f} mm is not closed"
            else:
                assert loops == 1, f"{name}: the layer at {z:.1f} mm is not one closed loop"
        if d.normal:                                  # what a normal print exports: the hollow pot, closed
            assert edge_check(d.print_mesh()[1])[0] and len(d.print_mesh()[1]) == d.triangles, name


def test_the_shape_can_change_back_and_forth():
    """Circle, pentagon, circle, pentagon - by Back and forth, or by an own curve shaped like a wave."""
    def roundness(d, h):
        row = d.R[int(round(h * d.M))]
        return row.min() / row.max()

    pentagon = math.cos(math.pi / 5)
    base = dict(shape1=CIRCLE, shape2=POLYGON, count2=5, sharp2=0.0, twist=0.0,
                silhouette=[[0.0, 80.0], [1.0, 80.0]])
    for p in (VaseParams(**base, morph=SWING, morph_swings=3),
              VaseParams(**base, morph=OWN, morph_curve=[[0, 0], [1 / 3, 1], [2 / 3, 0], [1, 1]])):
        d = VaseDesign(p)
        for h, want in ((0.0, 1.0), (1 / 3, pentagon), (2 / 3, 1.0), (1.0, pentagon)):
            assert abs(roundness(d, h) - want) < 0.02, (p.morph, h, roundness(d, h), want)
        assert d.closed and d.worst <= p.max_overhang + TOLERANCE


def test_overhangs_are_found_without_softening():
    p = plain(ring_count=6, ring_depth=6.0, ring_sharp=0.6, soften=False)
    d = VaseDesign(p)
    assert d.worst > p.max_overhang + 5, d.worst
    assert any("leans" in w for w in d.warnings)
    # ... and softened away with it
    p.soften = True
    d = VaseDesign(p)
    assert d.worst <= p.max_overhang + TOLERANCE and d.softened > 0.5


def test_the_lean_is_measured_right():
    # a cone whose wall leans 30° out: every wall face leans 30°
    H, r0 = 100.0, 30.0
    r1 = r0 + H * math.tan(math.radians(30.0))
    d = VaseDesign(plain(height=H, silhouette=[[0.0, 2 * r0], [1.0, 2 * r1]], soften=False))
    lean = lean_angles(d.verts, d.faces[:d.side])
    assert abs(lean.min() - 30.0) < 0.2 and abs(lean.max() - 30.0) < 0.2, (lean.min(), lean.max())
    # leaning in counts the same: a spiral wall rests on one line either way
    d = VaseDesign(plain(height=H, silhouette=[[0.0, 2 * r1], [1.0, 2 * r0]], soften=False))
    assert abs(d.worst - 30.0) < 0.2


def test_softening_keeps_a_steep_limit_tight():
    for limit in (25.0, 35.0, 55.0):
        p = VaseParams(max_overhang=limit, shape1=STAR, count1=5, depth1=0.4, sharp1=0.8, twist=360)
        d = VaseDesign(p)
        assert d.worst <= limit + TOLERANCE, (limit, d.worst)


def test_a_cylinder_has_the_right_volume():
    r, H = 40.0, 100.0
    d = VaseDesign(plain(height=H, silhouette=[[0.0, 2 * r], [1.0, 2 * r]], facet_size=0.5))
    want = math.pi * r * r * H
    assert abs(mesh_volume(d.verts, d.faces) - want) / want < 0.002
    # printed normally, it holds the inside of two 0.6 mm walls above a 1.2 mm floor
    assert abs(d.wall - 1.2) < 1e-9
    holds = math.pi * (r - 1.2) ** 2 * (H - 1.2) / 1000.0
    assert abs(d.capacity - holds) / holds < 0.01, (d.capacity, holds)
    # seamless, inside one 0.6 mm line
    d = VaseDesign(plain(height=H, silhouette=[[0.0, 2 * r], [1.0, 2 * r]], facet_size=0.5, vase_mode=REAL_VASE))
    holds = math.pi * (r - 0.6) ** 2 * (H - 1.2) / 1000.0
    assert abs(d.capacity - holds) / holds < 0.01, (d.capacity, holds)


def test_the_plain_start_is_a_plain_cylinder():
    """A blank start: 200 mm across and 200 mm tall, everything else off, the printer kept."""
    keep = VaseParams(line_width=0.8, layer_height=0.28, bed_x=300.0, walls=3)
    p = plain_design(keep)
    assert all(getattr(p, k) == getattr(keep, k) for k in PRINTER_KEYS)
    d = VaseDesign(p)
    assert not d.errors and not d.warnings and d.closed
    assert abs(d.H - 200.0) < 1e-9 and abs(d.widest - 200.0) < 0.01 and d.worst < 0.01 and d.softened == 0.0
    side = d.verts[d.faces[:d.side].ravel()]
    assert np.allclose(np.hypot(side[:, 0], side[:, 1]), 100.0, atol=1e-6)       # round, straight, no pattern
    assert not d.gradient and len(d.bands) == 1 and p.expression == "" and p.vase_mode == FAKE_VASE
    # ready for your own function
    p.expression = "2 * sin(8*theta)"
    d = VaseDesign(p)
    side = d.verts[d.faces[:d.side].ravel()]
    r = np.hypot(side[:, 0], side[:, 1])
    assert d.closed and abs(r.max() - 102.0) < 0.05 and abs(r.min() - 98.0) < 0.05


def test_a_normal_print_is_the_hollow_pot():
    """A normal print exports the pot as it prints - wall, floor and rim - so the slicer needs no special
    settings; seamless exports the solid for spiral vase mode."""
    r, H = 40.0, 100.0
    d = VaseDesign(plain(height=H, silhouette=[[0.0, 2 * r], [1.0, 2 * r]], facet_size=0.5, walls=2, line_width=0.6))
    verts, faces = d.print_mesh()
    assert d.normal and edge_check(faces)[0] and mesh_volume(verts, faces) > 0
    want = math.pi * r * r * H - math.pi * (r - 1.2) ** 2 * (H - 1.2)           # the plastic: wall and floor
    assert abs(mesh_volume(verts, faces) - want) / want < 0.01, (mesh_volume(verts, faces), want)
    assert abs(d.grams - want / 1000.0 * d.p.density) < 0.02 * d.grams
    seamless = VaseDesign(plain(height=H, silhouette=[[0.0, 2 * r], [1.0, 2 * r]], vase_mode=REAL_VASE))
    v2, f2 = seamless.print_mesh()
    assert not seamless.normal and np.array_equal(f2, seamless.faces)
    assert abs(mesh_volume(v2, f2) - math.pi * r * r * H) / (math.pi * r * r * H) < 0.002
    # colour bands of the pot: closed parts that together are the pot
    d = VaseDesign(plain(colour_style=BANDS, band_count=4, colours_used=2))
    parts = d.print_parts()
    assert len(parts) == 4 and all(edge_check(f)[0] for _, _, f in parts)
    whole = mesh_volume(*d.print_mesh())
    assert abs(sum(mesh_volume(v, f) for _, v, f in parts) - whole) < 1e-6 * whole


def test_holes_print_without_supports():
    """Every pattern of holes, on round and drawn shapes, twisting or not: a closed pot whose holes' tops
    lean no more than the limit, but for a short bridge at their very points - and Voronoi holes, ovals with
    round tops, that leave every wall between them as thick as set, and can swell round their edges."""
    cases = [plain(holes=VORONOI), plain(holes=VORONOI, hole_jitter=0.0, twist=360.0),
             plain(holes=ROUND, twist=720.0), plain(holes=DIAMOND, open_bottom=True),
             plain(holes=SLOTS, hole_size=10.0, hole_strut=2.0),
             plain(holes=VORONOI, hole_size=8.0, hole_strut=2.0, shape1=STAR, count1=6, depth1=0.3, twist=90.0),
             plain(holes=ROUND, shape1=DRAWN, drawn1=sections.CLAW, repeat1=1, twist=90.0)]
    for p in cases:
        d = VaseDesign(p)
        verts, faces = d.print_mesh()
        assert not d.errors and d.holes_open and edge_check(faces)[0], p.holes
        assert d.worst <= p.max_overhang + TOLERANCE, (p.holes, d.worst)
        longest = VORONOI_LONGEST + 0.5 if p.holes == VORONOI else 8.0   # Voronoi ovals' round tops bridge further
        assert 0.0 <= d.bridge < longest and 0.15 < d.hole_share < 0.7, (d.bridge, d.hole_share)
        assert d.capacity == 0.0 and d.info()["Holds"].startswith("nothing")
        assert max(layer_loops(d, z) for z in np.linspace(0.3 * d.H, 0.7 * d.H, 5)) > 1
        parts = d.print_parts()
        assert all(edge_check(f)[0] for _, _, f in parts)
        whole = mesh_volume(verts, faces)
        assert abs(sum(mesh_volume(v, f) for _, v, f in parts) - whole) < 1e-6 * whole
    # Voronoi holes are rounded, pointed inside their own cells: no wall between them is cut thinner than set
    for p in (plain(holes=VORONOI), plain(holes=VORONOI, hole_jitter=0.0), gallery_design("Voronoi Lamp")):
        d = VaseDesign(p)
        assert thinnest_wall(d) >= 0.9 * p.hole_strut, (thinnest_wall(d), p.hole_strut)
    # rounded edges: the wall swells round the holes, the pot still closed, printable, and heavier
    flat = VaseDesign(plain(holes=VORONOI, hole_swell=0.0))
    d = VaseDesign(plain(holes=VORONOI, hole_swell=1.5))
    swollen = d.pot_rows[6]
    assert edge_check(d.print_mesh()[1])[0] and d.worst <= p.max_overhang + TOLERANCE
    assert 1.2 < swollen.max() <= 1.5 and np.all(swollen[d.pot_rows[3] > 0] == 0.0)
    assert d.grams > 1.3 * flat.grams and "edges rounded" in d.info()["Holes"]
    # every hole side the overhang check sees leans out over its hole no more than the limit
    d = VaseDesign(plain(holes=ROUND))
    over = np.degrees(np.arcsin(np.clip(-face_normals(d.shell_verts, d.shell_faces)[:, 2], 0, 1)))
    assert over[d.shell_kind == hollow.SIDE].max() <= d.p.max_overhang + TOLERANCE
    # no room for holes is said; seamless can't have holes, so it is printed normally, and said
    d = VaseDesign(plain(holes=VORONOI, height=40.0, hole_foot=20.0, hole_rim=20.0))
    assert not d.holes_open and any("no room for the holes" in n for n in d.notes)
    d = VaseDesign(plain(holes=VORONOI, vase_mode=REAL_VASE))
    assert d.normal and d.holes_open and any("normal print" in n for n in d.notes)
    # open at the bottom: no floor, nothing held, the pot still closed
    d = VaseDesign(plain(open_bottom=True))
    verts, faces = d.print_mesh()
    bottom = verts[faces][np.all(np.abs(verts[faces][:, :, 2]) < 1e-9, axis=1)]
    assert edge_check(faces)[0] and len(bottom) and np.hypot(bottom[..., 0], bottom[..., 1]).min() > 20.0
    assert d.info()["Holds"] == "nothing: it is open at the bottom" and d.bottom_layers == 0


def test_masks_and_helmets():
    """A closed top comes to a point over a small ceiling; a wall part way round leaves a gap at the back; a
    face's eyes, mouth and strap slots are holes with pointed tops, its nose stands out; and a design sized
    for a head fits it. All of it closed, and printable without supports."""
    limit = 45.0 + TOLERANCE
    # a closed top: a point, a small ceiling under it, holding nothing; seamless, the solid comes to a point
    for p in (plain(closed_top=True, open_bottom=True), plain(closed_top=True),
              plain(closed_top=True, shape1=DRAWN, drawn1=sections.CLAW, repeat1=1),
              plain(closed_top=True, open_bottom=True, rib_count=6, rib_depth=2.0, colour_style=BANDS, band_count=3,
                    colours_used=3)):
        d = VaseDesign(p)
        verts, faces = d.print_mesh()
        top = verts[verts[:, 2] > d.H - 1e-6]
        assert not d.errors and edge_check(faces)[0] and d.worst <= limit, (d.errors, d.worst)
        assert np.hypot(top[:, 0], top[:, 1]).max() < 3.0 and 0.0 < d.ceiling < 10.0, d.ceiling
        assert d.capacity == 0.0 and d.info()["Top"].startswith("closed in a point")
        parts = d.print_parts()
        whole = mesh_volume(verts, faces)
        assert all(edge_check(f)[0] for _, _, f in parts)
        assert abs(sum(mesh_volume(v, f) for _, v, f in parts) - whole) < 1e-6 * whole
    d = VaseDesign(plain(closed_top=True, vase_mode=REAL_VASE))
    assert not d.normal and d.closed and d.worst <= limit and d.info()["Top"].startswith("comes in to a point")
    # part way round: nothing behind the axis past the ends, nothing held; a closed top needs it all round
    d = VaseDesign(plain(around=200.0, open_bottom=True))
    verts, faces = d.print_mesh()
    back = np.degrees(np.abs(np.arctan2(verts[:, 0], -verts[:, 1])))       # degrees round from the front (-y)
    assert edge_check(faces)[0] and 99.0 < back.max() < 101.5, back.max()
    assert d.info()["Holds"] == "nothing: it goes only part way round" and d.size[1] < 0.6 * d.size[0]
    d = VaseDesign(plain(around=200.0, closed_top=True))
    assert not d.p.closed_top and any("all the way round" in n for n in d.notes)
    # a face: holes with pointed tops, a nose that stands out, a seamless vase printed normally to have them
    face = dict(eyes=ALMOND_EYES, nose=RAISED_NOSE, mouth=GRILLE_MOUTH, mouth_smile=8.0, straps=True,
                open_bottom=True, around=200.0)
    for extra in ({}, dict(eyes=ROUND_EYES, mouth=OPEN_MOUTH), dict(mouth=CHIN_MOUTH, around=360.0),
                  dict(shape1=ELLIPSE, depth1=0.2, turn1=90.0, holes=VORONOI, hole_size=10.0, hole_strut=2.2)):
        p = plain(**{**face, **extra})
        d = VaseDesign(p)
        verts, faces = d.print_mesh()
        assert edge_check(faces)[0] and d.worst <= limit and d.holes_open and d.bridge < 8.0, (extra, d.worst)
        over = np.degrees(np.arcsin(np.clip(-face_normals(d.shell_verts, d.shell_faces)[:, 2], 0, 1)))
        assert over[d.shell_kind == hollow.SIDE].max() <= limit
        assert layer_loops(d, p.eye_up) > 1 and "Face" in d.info()
    plain_front = VaseDesign(plain()).R[:, 3 * VaseDesign(plain()).N // 4]
    d = VaseDesign(plain(nose=RAISED_NOSE))
    front = d.R[:, 3 * d.N // 4]
    j = int(np.argmin(np.abs(d.z - d.p.nose_up)))
    assert front[j] - plain_front[j] > 0.7 * d.p.nose_depth and np.allclose(front[:j // 2], plain_front[:j // 2])
    d = VaseDesign(plain(eyes=ALMOND_EYES, vase_mode=REAL_VASE))
    assert d.normal and d.holes_open and any("normal print" in n for n in d.notes)
    # sized for a head: the inside fits, the face grows with it; the masks and helmet fit 57 cm as they come
    p = plain(**face, worn=True)
    q = fit_head(p, 520.0)
    d = VaseDesign(q)
    k = q.height / p.height
    assert abs(d.head_fit - 520.0) < 1.0 and abs(q.eye_up - k * p.eye_up) < 0.05 and abs(q.silhouette[0][1] - k * p.silhouette[0][1]) < 0.05
    assert d.info()["Fits a head"].startswith("up to 52.0 cm")
    for title in ("Theatre Mask", "Lace Masquerade", "Robot Mask", "Norman Helmet"):
        d = VaseDesign(gallery_design(title))
        assert abs(d.head_fit - 570.0) < 3.0 and d.p.worn and d.H < 220.0, (title, d.head_fit, d.H)


def test_the_web_version():
    """The web page's Python - the bridge and the package's modules that need no Qt, as tools/build_web.py puts
    them together - runs without Qt: it starts, builds a mask, fits it to a head, and makes the slicer's file."""
    import subprocess
    out = tempfile.mkdtemp()
    subprocess.run([sys.executable, os.path.join(ROOT, "tools", "build_web.py"), out], check=True, capture_output=True)
    for name in ("index.html", "app.js", "view.js", "curves.js", "outline.js", "plots.js", "worker.js", "style.css",
                 "gallery/theatre_mask.png", "py/files.json", "py/vaseinator/settings.py"):
        assert os.path.exists(os.path.join(out, name)), name
    code = r"""
import json, sys
sys.modules["PySide6"] = None                    # as in the browser: no Qt at all
sys.path.insert(0, sys.argv[1])
import bridge
s = json.loads(bridge.start())
keep = json.dumps(s["defaults"])
mask = bridge.design_of("Theatre Mask", keep)
meta, pos, tri, col, lean = bridge.build(mask, True)
m = json.loads(meta)
assert not m["errors"] and m["head"] == 57.0 and len(pos) == len(col) == 3 * len(lean) and len(tri) % 12 == 0, m["errors"]
assert json.loads(bridge.fit(mask, 520.0))["eye_up"] < json.loads(mask)["eye_up"]
data, steps = bridge.export_3mf(bridge.design_of("Plain cylinder", keep))
assert data[:2] == b"PK" and "No supports" in steps
assert json.loads(bridge.open_vase(bridge.save_vase(mask)))["name"] == "theatre_mask"
# the Advanced panel: every setting, and the desktop app's own rules for a change
assert [g["title"] for g in s["spec"]][0] == "Size" and "eye_tilt" in json.loads(bridge.shown(mask))
r = json.loads(bridge.apply(keep, "twist_style", "5"))
assert r["touched"] == ["twist_curve"] and r["params"]["twist_style"] == 5
r = json.loads(bridge.apply(keep, "shape1", "7"))
assert r["params"]["shape1"] == 7 and len(r["params"]["drawn1"]) >= 3 and "repeat1" in r["shown"]
r = json.loads(bridge.apply(json.dumps(dict(s["defaults"], vase_mode=0)), "holes", "1"))
assert r["params"]["vase_mode"] == 1 and "normal print" in r["message"]
assert "<style>" not in m["report"] and "Steepest overhang" in m["report"] and len(m["plots"]["slices"]) == 15
# tracing a picture: a dark square on white
import base64
import numpy as np
img = np.full((60, 80, 4), 255, np.uint8)
img[10:50, 20:60, :3] = 0
assert len(json.loads(bridge.trace(base64.b64encode(img.tobytes()).decode(), 80, 60))) >= 4
print("ok", len(s["gallery"]))
"""
    r = subprocess.run([sys.executable, "-I", "-c", code, os.path.join(out, "py")], capture_output=True, text=True)
    assert r.returncode == 0 and r.stdout.startswith(f"ok {len(GALLERY)}"), r.stderr[-2000:]


def test_low_poly_facets_are_flat():
    p = VaseParams(facets=True, facets_around=10, facets_up=6, facet_rough=0.4)
    d = VaseDesign(p)
    assert edge_check(d.faces)[0]
    assert d.side == 2 * 10 * 6                      # two triangles for each facet position
    assert d.worst <= p.max_overhang + TOLERANCE


def test_stl_round_trip():
    d = VaseDesign(gallery_design("Spiral Ribs"))
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "v.stl")
        write_stl(path, d.verts, d.faces, "v")
        assert os.path.getsize(path) == 84 + 50 * len(d.faces)
        verts, faces = read_stl(path)
    assert len(faces) == len(d.faces)
    assert edge_check(faces)[0], "the STL as written is not watertight"
    assert abs(mesh_volume(verts, faces) - mesh_volume(d.verts, d.faces)) < 1e-3 * mesh_volume(d.verts, d.faces)


def test_3mf_round_trip():
    d = VaseDesign(gallery_design("Gem Facets"))
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "v.3mf")
        write_3mf(path, "gem", [("gem", d.verts, d.faces, 2, (0.5, 0.2, 0.8))], (128.0, 128.0, 0.0))
        [(name, v, f, fil, pos)] = read_3mf(path)
    assert name == "gem" and fil == 2 and pos == (128.0, 128.0, 0.0)
    assert np.array_equal(f, d.faces) and np.allclose(v, d.verts, atol=1e-4)


def test_colour_bands_as_parts():
    """Each band its own closed part, set to its filament, together filling the vase exactly once."""
    for p in (gallery_design("Tulip Bloom"), gallery_design("Gear Tower"),
              VaseParams(**{**gallery_design("Gem Facets").to_dict(), "vase_mode": FAKE_VASE,
                            "colour_style": BANDS, "band_count": 3, "colours_used": 3})):
        d = VaseDesign(p)
        parts = d.band_parts()
        assert [f for f, _, _ in parts] == [f for _, f in d.bands], p.name
        whole = mesh_volume(d.verts, d.faces)
        assert abs(sum(mesh_volume(v, f) for _, v, f in parts) - whole) < 0.002 * whole, p.name
        tops = [z for z, _ in d.bands[1:]] + [d.H]
        for (fil, v, f), (lo, _), hi in zip(parts, d.bands, tops):
            assert edge_check(f)[0], (p.name, fil)
            assert abs(v[:, 2].min() - lo) < 1e-9 and abs(v[:, 2].max() - hi) < 1e-9
            wall = np.abs(face_normals(v, f)[:, 2]) < 0.999
            assert lean_angles(v, f[wall]).max() <= p.max_overhang + TOLERANCE + 0.5, p.name
    # one colour: the vase as it is, in one part
    d = VaseDesign(plain())
    [(fil, v, f)] = d.band_parts()
    assert fil == 1 and abs(mesh_volume(v, f) - mesh_volume(d.verts, d.faces)) < 1e-6 * mesh_volume(d.verts, d.faces)
    with tempfile.TemporaryDirectory() as tmp:
        p = VaseParams(vase_mode=FAKE_VASE, colour_style=BANDS, band_count=3, colours_used=3)
        d = VaseDesign(p)
        colours = p.colors()
        write_3mf(os.path.join(tmp, "b.3mf"), "b", [(f"band {k}", v, f, fil, colours[fil])
                                                     for k, (fil, v, f) in enumerate(d.band_parts())])
        back = read_3mf(os.path.join(tmp, "b.3mf"))
    assert [b[3] for b in back] == [1, 2, 3] and all(edge_check(b[2])[0] for b in back)


def test_real_and_fake_spiral_vases():
    """A real spiral vase is one filament in one line; a fake one has its bands, and walls."""
    real = VaseDesign(VaseParams(vase_mode=REAL_VASE, colour_style=BANDS, band_count=3, colours_used=3))
    assert real.bands == [(0.0, 1)] and len(real.band_parts()) == 1     # bands can't be printed in spiral mode
    real_gradient = VaseDesign(VaseParams(vase_mode=REAL_VASE, colour_style=GRADIENT, colours_used=3))
    assert real_gradient.gradient                                       # a gradient spool is still one filament
    fake = VaseDesign(VaseParams(vase_mode=FAKE_VASE, colour_style=BANDS, band_count=3, colours_used=3, walls=2))
    assert [f for _, f in fake.bands] == [1, 2, 3] and len(fake.band_parts()) == 3
    # two walls of 0.6 mm: a wall 1.2 mm thick, inside the same outside, so it holds less and weighs more
    assert abs(fake.wall - 1.2) < 1e-9 and abs(real.wall - 0.6) < 1e-9
    assert fake.capacity < real.capacity and fake.grams > 1.8 * real.grams
    assert np.allclose(fake.verts, real.verts)                          # the same solid either way


def test_drawn_outlines():
    """Any outline, drawn with spline points and cusps: it goes through its points, and a round one is a cylinder."""
    pts = [[1.0, 0.0, False], [0.0, 0.7, True], [-0.8, 0.0, False], [0.0, -0.7, False]]
    loop = sections.spline(pts, per=16)
    assert np.allclose(loop[::16], np.array(pts)[:, :2])
    # a motif repeated round the axis: the same area as the built-in flower it came from
    table = shape_table(FLOWER, 5, 0.3, 0.5)
    motif = sections.motif_from_table(table, 5)
    a_motif = sections.area(sections.normalised(sections.spline(motif, 5)))
    a_table = sections.area(sections.normalised(sections.from_table(table)))
    assert abs(a_motif / a_table - 1) < 0.03, (a_motif, a_table)
    # a drawn circle holds what the built-in circle does
    circle = sections.OUTLINES[0][1]
    drawn = VaseDesign(plain(shape1=DRAWN, drawn1=circle, repeat1=1))
    round_ = VaseDesign(plain())
    assert drawn.free and not round_.free
    assert abs(drawn.capacity / round_.capacity - 1) < 0.01, (drawn.capacity, round_.capacity)
    # an outline that crosses itself is refused, with where
    bow = [[1, 0, False], [-1, 1, False], [-1, -1, False], [1, 1, False], [0.2, -1.2, False]]
    bad = VaseDesign(plain(shape1=DRAWN, drawn1=bow, repeat1=1))
    assert bad.errors and "crosses itself" in bad.errors[0]
    # a picture traced: a filled five-pointed star gives five sharp points
    yy, xx = np.mgrid[0:300, 0:400]
    ang = np.arctan2(150 - yy, xx - 200)
    rad = np.hypot(xx - 200, yy - 150)
    star = rad < 55 + 65 * np.abs(((ang * 5 / (2 * np.pi)) % 1) * 2 - 1) ** 3
    traced = sections.trace_mask(star)
    assert sum(c for _, _, c in traced) >= 5 and not sections.crossings(sections.spline(traced))
    # drawn outlines print as colour bands too, each band a closed part
    fake = VaseDesign(plain(shape1=DRAWN, drawn1=sections.OUTLINES[1][1], repeat1=5, vase_mode=FAKE_VASE,
                            colour_style=BANDS, band_count=3, colours_used=3))
    parts = fake.band_parts()
    assert len(parts) == 3 and all(edge_check(f)[0] for _, _, f in parts)
    # saved and opened, the outline is the same
    path = os.path.join(tempfile.mkdtemp(), "drawn.vase")
    save_design(path, fake.p)
    back = load_design(path)
    assert back.drawn1 == fake.p.drawn1 and back.repeat1 == 5


def test_many_repeats():
    """A piece repeated up to a hundred times: narrowed to fit, checked quickly, built and filled."""
    five = sections.OUTLINES[1][1]
    hundred = sections.respace(five, 5, 100)
    back = sections.respace(hundred, 100, 5)
    a = [np.unwrap(np.arctan2([q[1] for q in pts], [q[0] for q in pts])) for pts in (five, back)]
    assert np.allclose(np.diff(a[0]), np.diff(a[1]), atol=1e-3)            # there and back: the same piece
    assert np.allclose([math.hypot(q[0], q[1]) for q in five], [math.hypot(q[0], q[1]) for q in hundred], atol=1e-3)
    # the quick check on the drawn piece finds what the full check finds
    for pts, n in ((hundred, 100), (five, 5), (five, 8), (sections.CLAW, 1), (sections.CLAW, 3)):
        loop = sections.spline(pts, n, per=16)
        assert bool(sections.piece_crossings(loop, 16 * len(pts))) == bool(sections.crossings(loop, limit=10 ** 6)), n
    assert sections.piece_crossings(sections.spline(five, 8, per=16), 16 * len(five))    # too wide for 8: crosses
    # filling a loop of thousands of points: every side once, no more triangles than it needs, the same area
    loop = sections.resample(sections.normalised(sections.spline(hundred, 100)), 4000)
    T = sections.triangulate(loop)
    assert len(T) == len(loop) - 2
    sides = np.sort(np.concatenate([T[:, [0, 1]], T[:, [1, 2]], T[:, [2, 0]]]), axis=1)
    edges, uses = np.unique(sides, axis=0, return_counts=True)
    outline = {(min(i, (i + 1) % 4000), max(i, (i + 1) % 4000)) for i in range(4000)}
    assert all((u == 1) == (tuple(e) in outline) for e, u in zip(edges, uses)) and uses.max() == 2
    A, B, C = loop[T[:, 0]], loop[T[:, 1]], loop[T[:, 2]]
    cut = 0.5 * ((B[:, 0] - A[:, 0]) * (C[:, 1] - A[:, 1]) - (B[:, 1] - A[:, 1]) * (C[:, 0] - A[:, 0]))
    assert cut.min() > -1e-12 and abs(cut.sum() - sections.area(loop)) < 1e-9
    # and the vase: closed, one loop a layer, within the limit, in a few seconds
    t0 = time.perf_counter()
    d = VaseDesign(plain(shape1=DRAWN, drawn1=hundred, repeat1=100, twist=60))
    assert time.perf_counter() - t0 < 15
    assert not d.errors and d.closed and d.worst <= d.p.max_overhang + TOLERANCE
    assert d.N >= 22 * 100
    for z in (5.3, 61.7, 140.2):
        assert layer_loops(d, z) == 1


def test_designs_save_and_open():
    p = gallery_design("Star to Moon")
    p.expression = "0.5*sin(3*theta)"
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "x.vase")
        save_design(path, p)
        assert load_design(path).to_dict() == p.to_dict()
    # a damaged file keeps what it can
    q = VaseParams.from_dict({"height": "tall", "shape1": 42, "depth1": 7, "silhouette": [[0, -5], [1, 3]],
                              "twist_curve": "nonsense", "color2": "blue", "rib_count": 12})
    fresh = VaseParams()
    assert q.height == fresh.height and q.shape1 == fresh.shape1 and q.depth1 == 0.9
    assert q.silhouette == fresh.silhouette and q.twist_curve == fresh.twist_curve
    assert q.color2 == fresh.color2 and q.rib_count == 12
    for name in os.listdir(os.path.join(ROOT, "examples")):
        if name.endswith(".vase"):
            d = VaseDesign(load_design(os.path.join(ROOT, "examples", name)))
            assert not d.errors and d.closed, name


def test_your_own_function_is_safe():
    for bad in ("__import__('os')", "open('x')", "theta.real", "(lambda: 1)()", "'text'", "x + 1",
                "[1, 2]", "sin(theta, out=theta)", "globals()", "a if theta else b", "1 and 2"):
        try:
            compile_expression(bad)
        except ExprError:
            continue
        raise AssertionError(f"accepted: {bad}")
    t0 = time.perf_counter()
    fn = compile_expression("9**9**9")
    try:
        fn(theta=np.zeros(3))
        raise AssertionError("a huge power went through")
    except ExprError:
        pass
    assert time.perf_counter() - t0 < 1.0
    fn = compile_expression("1/(theta - theta)")
    try:
        fn(theta=np.ones(3))
        raise AssertionError("dividing by zero went through")
    except ExprError:
        pass
    fn = compile_expression("2*sin(3*theta) + noise(z, h, 0.5) + where(z > 5, 1, 0)")
    v = fn(theta=np.linspace(0, 6, 7), z=np.linspace(0, 10, 7), h=np.linspace(0, 1, 7))
    assert v.shape == (7,) and np.isfinite(v).all()
    # a function that doesn't meet itself round the back is pointed out
    d = VaseDesign(plain(expression="0.4*theta"))
    assert any("meet itself" in w for w in d.warnings)
    d = VaseDesign(plain(expression="0.4*sin(4*theta)"))
    assert not any("meet itself" in w for w in d.warnings)
    d = VaseDesign(plain(expression="sin(theta"))
    assert d.errors


def test_a_function_over_several_lines_is_one_formula():
    """Lines are read as one formula, notes after # dropped; a line that doesn't carry on is pointed out."""
    env = dict(theta=np.linspace(0, 6, 7), z=np.linspace(0, 90, 7), h=np.linspace(0, 1, 7))
    want = compile_expression("1.5 * sin(6*theta + 4*pi*h) + 0.5 * cos(3*theta) - 2*h")(**env)
    for text in ("1.5 * sin(6*theta + 4*pi*h)\n+ 0.5 * cos(3*theta)\n- 2*h",
                 "1.5 * sin(6*theta\n          + 4*pi*h)\n+ 0.5 * cos(3*theta) - 2*h\n\n",
                 "\n  1.5 * sin(6*theta + 4*pi*h)   # waves\n+ 0.5 * cos(3*theta)        # lobes\n- 2*h  # narrower",
                 "1.5 * sin(6*theta + 4*pi*h) +\r\n0.5 * cos(3*theta) -\r\n2*h"):
        assert np.allclose(compile_expression(text)(**env), want), text
    assert compile_expression("# only a note\n\n") is None
    for text, says in (("sin(theta)\ncos(theta)", "start line 2 with + - * or /"),
                       ("2*h\n+ 0.5*cos(3*theta\n+ 1", "a ( is never closed (line 2"),
                       ("2*h\n+ 3*", "stops part way"),
                       ("sin(theta))", "a ) has no ("),
                       ("2*h\n+ 3 * * h", "line 2, near character 7")):
        try:
            compile_expression(text)
        except ExprError as exc:
            assert says in str(exc), (text, str(exc))
            continue
        raise AssertionError(f"accepted: {text!r}")
    # and the vase is built from it, as from the one line
    one = VaseDesign(plain(expression="1.5 * sin(6*theta) + 2*h"))
    two = VaseDesign(plain(expression="1.5 * sin(6*theta)   # waves\n+ 2*h"))
    assert not two.errors and np.allclose(one.verts, two.verts)


def test_colour_changes_land_on_layers():
    p = plain(height=100.0, vase_mode=FAKE_VASE, colour_style=BANDS, band_count=4, colours_used=2, layer_height=0.2)
    d = VaseDesign(p)
    assert [f for _, f in d.bands] == [1, 2, 1, 2]
    for z, _ in d.bands:
        assert abs(z / 0.2 - round(z / 0.2)) < 1e-9
    assert [(layer, round(z, 2), f) for layer, z, f in d.colour_changes()] == [
        (126, 25.2, 2), (251, 50.2, 1), (376, 75.2, 2)]
    d = VaseDesign(plain(height=100.0, vase_mode=FAKE_VASE, colour_style=STRIPES, stripe_height=10.0, colours_used=3))
    assert len(d.bands) == 10 and [f for _, f in d.bands][:4] == [1, 2, 3, 1]
    d = VaseDesign(plain(vase_mode=FAKE_VASE, colour_style=BANDS, band_count=3, colours_used=1))
    assert len(d.bands) == 1                       # one filament: no changes at all
    assert "change to filament" not in d.colour_plan()


def test_shapes_and_curves():
    for kind in (CIRCLE, POLYGON, STAR, GEAR):
        for count, depth, sharp in ((3, 0.3, 0.0), (8, 0.5, 1.0), (40, 0.1, 0.5)):
            t = shape_table(kind, count, depth, sharp)
            assert abs(t.max() - 1.0) < 1e-12 and t.min() > 0.0
    t = shape_table(POLYGON, 6, 0.0, 0.0)          # a sharp hexagon: flat sides at cos(30°)
    assert abs(t.min() - math.cos(math.pi / 6)) < 2e-3
    # the outline curve never overshoots its points
    x = np.array([0.0, 0.3, 0.6, 1.0])
    y = np.array([60.0, 100.0, 40.0, 70.0])
    v = pchip(x, y, np.linspace(0, 1, 501))
    assert v.max() <= 100.0 + 1e-9 and v.min() >= 40.0 - 1e-9
    assert np.allclose(pchip(x, y, x), y)
    assert len(PROFILES) >= 10


def test_surprises_respect_the_printer():
    small = VaseParams(printer_height=120.0, bed_x=120.0, bed_y=120.0)
    for seed in range(20):
        p = surprise(small, seed)
        d = VaseDesign(p)
        assert not d.errors, (seed, d.errors)
        assert d.H <= 120.0 and p.soften
        assert d.worst <= p.max_overhang + TOLERANCE, (seed, d.worst)


def main():
    tests = [(k, v) for k, v in globals().items() if k.startswith("test_") and callable(v)]
    failed = 0
    for name, fn in tests:
        t0 = time.perf_counter()
        try:
            fn()
        except AssertionError as exc:
            failed += 1
            print(f"FAIL  {name}: {exc}")
            continue
        print(f"ok    {name}  ({time.perf_counter() - t0:.1f} s)")
    print(f"\n{len(tests) - failed} of {len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
