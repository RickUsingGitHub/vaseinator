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

from vaseinator.expr import ExprError, compile_expression  # noqa: E402
from vaseinator.geometry import (TOLERANCE, VaseDesign, edge_check, face_normals, lean_angles,  # noqa: E402
                                 mesh_volume)
from vaseinator.params import (BANDS, CIRCLE, EVENLY, FAKE_VASE, GEAR, GRADIENT, ONE_COLOUR, OWN, POLYGON,
                               REAL_VASE, SAME, STAR,  # noqa: E402
                               STRIPES, SWING, VaseParams, load_design, save_design)
from vaseinator.presets import GALLERY, gallery_design, surprise  # noqa: E402
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
    ]
    return out


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
            assert layer_loops(d, z) == 1, f"{name}: the layer at {z:.1f} mm is not one closed loop"


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
    # it holds the inside of a 0.6 mm wall above a 1.2 mm floor
    holds = math.pi * (r - 0.6) ** 2 * (H - 1.2) / 1000.0
    assert abs(d.capacity - holds) / holds < 0.01, (d.capacity, holds)


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
