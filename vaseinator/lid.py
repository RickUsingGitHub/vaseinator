"""A lid for a tissue box cover's open end, printed on its own - after the cover, if wanted.

It is a flat plate, the shape of the cover's rim, that the cover stands on, with springy tabs standing up from
it just inside the wall. Each tab has a small bump on its outside: pushed in, the tabs bend in a little and
press on the wall, so the lid stays on when the cover is picked up, and a pull tab at one end takes it off
again to change the tissues. It is made from the cover's own design - the wall where each tab presses is
measured - so it fits a cover already printed. Nothing here needs Qt.
"""

from __future__ import annotations

import math

import numpy as np

from . import hollow, sections
from .geometry import edge_check, mesh_volume
from .params import LID_FIRM, LID_GENTLE, LID_SNUG

LID_PLATE = 1.6               # how thick the plate is (mm)
LID_FRAME = 12.0              # an open lid: how wide its frame is, in from the edge
LID_TAB_TALL = 11.0           # how far the tabs stand up from the plate, at least
LID_TAB_WIDE = 10.0           # ... how wide each is, along the wall
LID_TAB_THICK = 1.0           # ... and how thick: springy, not stiff (the slicer makes it two thin lines)
LID_BUMP_AT = 8.5             # how high the bump on each tab is, on a plain wall: high enough for the tab to bend
LID_BUMP_LOW, LID_BUMP_HIGH = 8.0, 13.0     # ... and the heights it may move to, to sit where the wall suits it
LID_GAP = 0.3                 # between a tab and the wall where the wall comes nearest it
LID_SINK = 0.3                # how far the tabs go down into the plate, to be one with it
LID_PULL = 9.0                # how far the pull tab sticks out past the rim
LID_PULL_WIDE = 26.0          # ... and how wide it is
LID_GRIP = {LID_GENTLE: 0.25, LID_SNUG: 0.35, LID_FIRM: 0.5}    # how far each tab's bump presses into the wall
GRIP_WORDS = {LID_GENTLE: "gently", LID_SNUG: "snugly", LID_FIRM: "firmly"}


def _anticlockwise(loop):
    x, y = loop[:, 0], loop[:, 1]
    area = 0.5 * float(np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y))
    return loop if area > 0 else loop[::-1]


def _dense(loop, step: float = 1.0):
    """The loop with points added along its sides, none further apart than step (mm)."""
    nxt = np.roll(loop, -1, axis=0)
    n = np.maximum(np.ceil(np.linalg.norm(nxt - loop, axis=1) / step).astype(int), 1)
    t = np.concatenate([np.arange(k) / k for k in n])
    i = np.repeat(np.arange(len(loop)), n)
    return loop[i] + t[:, None] * (nxt[i] - loop[i])


def _reach(loop, U, V, vs):
    """How far out a loop goes in the direction U at each of the places vs across it (along V): the furthest
    of its crossings there."""
    a, b = loop @ U, np.roll(loop, -1, axis=0) @ U
    va, vb = loop @ V, np.roll(loop, -1, axis=0) @ V
    vs = np.asarray(vs, dtype=float)[:, None]
    cross = (np.minimum(va, vb) <= vs) & (np.maximum(va, vb) >= vs) & (va != vb)
    t = (vs - va) / np.where(va != vb, vb - va, 1.0)
    u = np.where(cross, a + t * (b - a), -np.inf)
    return u.max(axis=1)


def _prism(profile, U, V, v0: float, v1: float, z0: float):
    """A closed solid: the profile (n, 2) of (out along U, up) points, anticlockwise, made into a bar from
    v0 to v1 along V, standing at z0. Its caps are fans from the profile's first point."""
    n = len(profile)
    ends = []
    for v in (v0, v1):
        xy = profile[:, :1] * U + v * V
        ends.append(np.column_stack([xy, z0 + profile[:, 1]]))
    verts = np.concatenate(ends)
    cap = np.array([[0, k, k + 1] for k in range(1, n - 1)])
    k = np.arange(n)
    side = np.concatenate([np.stack([k, (k + 1) % n, n + (k + 1) % n], 1), np.stack([k, n + (k + 1) % n, n + k], 1)])
    faces = np.concatenate([cap[:, ::-1], cap + n, side])
    if mesh_volume(verts, faces) < 0:
        faces = faces[:, ::-1]
    return verts, faces


class Lid:
    """The lid for a tissue box cover's design ``d`` (a VaseDesign, built in full): verts, faces - flat on the
    bed, the tabs up, as it prints and as it goes on - and its sums."""

    def __init__(self, d):
        p = d.p
        self.errors: list[str] = []
        self.notes: list[str] = []
        self.verts = self.faces = None
        self.tabs, self.closed = 0, False
        if not p.box or d.pot_rows is None or d.errors:
            self.errors.append("A lid is made for a tissue box cover.")
            return
        zs, Os, Is, fs, _, _, swell = d.pot_rows
        Is = Is - sections.normals(Is) * swell[..., None]        # the wall inside, swollen round any holes
        H = float(zs[-1])
        # the cover is turned over to go on: seen from above, its rim as the lid meets it is mirrored
        def used(loop):
            return _anticlockwise(np.asarray(loop, dtype=float) * [1.0, -1.0])

        rim = _dense(used(Os[-1]))
        grip = LID_GRIP.get(p.lid_grip, LID_GRIP[LID_SNUG])
        t = LID_TAB_THICK
        top = LID_PLATE
        # the pull tab, on the end of the long way
        X, Y = np.abs(rim).max(axis=0)
        U = np.array([1.0, 0.0]) if X >= Y else np.array([0.0, 1.0])
        V = np.array([-U[1], U[0]])
        outline = self._pull_tab(rim, U, V)
        parts = [self._plate(outline, rim if p.lid_open else None)]
        # the tabs: two a side, a quarter of the way in from each end, where the side is straight
        heights = H - zs                                          # how far above the rim each row is, the cover on
        holed = heights[(fs > 0).any(axis=1)]
        high = min(LID_BUMP_HIGH, float(holed.min()) - 3.0) if len(holed) else LID_BUMP_HIGH
        if high < 4.0:
            self.errors.append("The holes come too near the rim for a lid's tabs to hold on: make the plain rim "
                               "wider (Advanced ▸ Holes and openings ▸ Plain rim).")
            return
        low = min(LID_BUMP_LOW, high)
        near = np.nonzero(heights <= LID_BUMP_HIGH + 8.0)[0]
        rows = np.arange(max(near.min() - 1, 0), len(zs))         # and the row just beyond the tallest tab
        inner = [used(Is[k]) for k in rows]
        worst = 0.0
        for U in (np.array([1.0, 0.0]), np.array([-1.0, 0.0]), np.array([0.0, 1.0]), np.array([0.0, -1.0])):
            V = np.array([-U[1], U[0]])
            u, v = rim @ U, rim @ V
            flat = v[u >= u.max() - 0.05]
            lo, hi = float(flat.min()), float(flat.max())
            half = 0.5 * LID_TAB_WIDE
            if hi - lo >= 4.0 * LID_TAB_WIDE:
                places = [lo + 0.25 * (hi - lo), lo + 0.75 * (hi - lo)]
            elif hi - lo >= LID_TAB_WIDE + 2.0:
                places = [0.5 * (lo + hi)]
            else:
                continue
            for c in places:
                across = np.linspace(c - half, c + half, 9)
                # how near the wall comes, over the tab's width, at each row's height above the rim
                wall = np.array([_reach(loop, U, V, across).min() for loop in inner])
                h = heights[rows]
                order = np.argsort(h)
                h, wall = h[order], wall[order]

                def nearest(a, b):
                    s = np.concatenate([[a, b], h[(h > a) & (h < b)]])
                    return float(np.interp(s, h, wall).min())

                # the bump goes where the wall is straight up, or leans out above it - just past a ring that
                # comes in, so it clicks in behind it - not where the wall leans in and would push the lid back
                # out; on a plain wall, at LID_BUMP_AT
                ss = np.arange(low, high + 1e-9, 0.25)
                lean = (np.interp(ss + 0.8, h, wall) - np.interp(ss - 1.0, h, wall)) / 1.8
                bump = float(ss[np.argmax(np.round(np.minimum(lean, 0.1), 2) - 0.002 * np.abs(ss - LID_BUMP_AT))])
                flat_top = 0.8
                e, tall = 1.0, LID_TAB_TALL
                for _ in range(3):                                # out to the wall, and the grip beyond
                    tall = max(bump + flat_top + max(2.0 * e, 1.5), LID_TAB_TALL)
                    face = nearest(0.0, tall) - LID_GAP           # the tab's outside, clear of the wall all the way up
                    e = nearest(bump, bump + flat_top) + grip - face    # where it touches
                worst = max(worst, e)
                profile = np.array([[face - t, -LID_SINK], [face, -LID_SINK], [face, bump - e], [face + e, bump],
                                    [face + e, bump + flat_top], [face, tall], [face - t, tall],
                                    [face - t, bump]])
                parts.append(_prism(profile[[7, 0, 1, 2, 3, 4, 5, 6]], U, V, c - half, c + half, top))
                self.tabs += 1
        if not self.tabs:
            self.errors.append("The cover is too small for a lid's tabs.")
            return
        if worst > 2.5:
            self.notes.append("The wall goes in and out near the rim, so the tabs' bumps stand out a long way: "
                              "the lid may be stiff to push on.")
        verts, faces, n = [], [], 0
        for v_, f_ in parts:
            verts.append(v_)
            faces.append(f_ + n)
            n += len(v_)
        self.verts, self.faces = np.concatenate(verts), np.concatenate(faces)
        self.closed = edge_check(self.faces)[0]
        self.open = bool(p.lid_open)
        self.grip = GRIP_WORDS.get(p.lid_grip, GRIP_WORDS[LID_SNUG])
        self.size = self.verts.max(0) - self.verts.min(0)
        if self.size[0] > p.bed_x or self.size[1] > p.bed_y:
            self.notes.append(f"It is {self.size[0]:.0f} × {self.size[1]:.0f} mm across: bigger than the bed "
                              f"({p.bed_x:.0f} × {p.bed_y:.0f} mm). Turn it corner to corner in the slicer.")
        vol = mesh_volume(self.verts, self.faces)
        self.grams = vol / 1000.0 * p.density
        speed = min(p.speed, p.max_flow / max(p.line_width * p.layer_height, 1e-6))
        self.seconds = vol / (p.line_width * p.layer_height) / max(speed, 0.1) + 120.0
        self.p = p

    @staticmethod
    def _pull_tab(rim, U, V):
        """The rim's outline with a tab sticking out of the middle of its end at U, to pull the lid off by."""
        u, v = rim @ U, rim @ V
        w = 0.5 * LID_PULL_WIDE
        on = (u > 0) & (np.abs(v) < w)
        if not on.any():
            return rim
        k = np.argmin(u)                                          # start round from the far end
        rim, u, v, on = (np.roll(a, -k, axis=0) for a in (rim, u, v, on))
        idx = np.nonzero(on)[0]
        i0, i1 = int(idx.min()), int(idx.max())
        out = float(u[idx].max()) + LID_PULL
        r = min(5.0, w)
        a = np.linspace(-0.5 * math.pi, 0.0, 9)
        b = np.linspace(0.0, 0.5 * math.pi, 9)
        path = ([(u[i0], -w)] + [(out - r + r * math.cos(t), -w + r + r * math.sin(t)) for t in a]
                + [(out - r + r * math.cos(t), w - r + r * math.sin(t)) for t in b] + [(u[i1], w)])
        tab = np.array([pu * U + pv * V for pu, pv in path])
        return np.concatenate([rim[:i0], tab, rim[i1 + 1:]])

    @staticmethod
    def _plate(outline, rim=None):
        """The flat plate: the outline, LID_PLATE thick - with the middle open, a frame LID_FRAME wide, if the
        rim is given."""
        n = len(outline)
        if rim is None:
            ring = np.arange(n)
            k = np.arange(n)
            nxt = (k + 1) % n
            verts = np.concatenate([np.column_stack([outline, np.zeros(n)]),
                                    np.column_stack([outline, np.full(n, LID_PLATE)]),
                                    [[0.0, 0.0, 0.0], [0.0, 0.0, LID_PLATE]]])
            faces = np.concatenate([np.stack([np.full(n, 2 * n), nxt, k], 1),               # underneath
                                    np.stack([np.full(n, 2 * n + 1), n + k, n + nxt], 1),   # on top
                                    np.stack([k, nxt, n + nxt], 1), np.stack([k, n + nxt, n + k], 1)])
            return verts, faces
        hole = _anticlockwise(sections.inset(rim, LID_FRAME))
        m = len(hole)
        loops = np.concatenate([outline, hole])
        verts = np.concatenate([np.column_stack([loops, np.zeros(n + m)]),
                                np.column_stack([loops, np.full(n + m, LID_PLATE)])])
        top = hollow.zip_rings(np.arange(n), outline, np.arange(n, n + m), hole)
        k, j = np.arange(n), np.arange(m)
        side = n + m
        faces = np.concatenate([top + side, top[:, ::-1],
                                np.stack([k, (k + 1) % n, side + (k + 1) % n], 1),
                                np.stack([k, side + (k + 1) % n, side + k], 1),
                                np.stack([n + j, side + n + (j + 1) % m, n + (j + 1) % m], 1),
                                np.stack([n + j, side + n + j, side + n + (j + 1) % m], 1)])
        return verts, faces

    def info(self) -> str:
        """A line about it, for the panel and the steps."""
        return (f"{self.size[0]:.0f} × {self.size[1]:.0f} mm, {'a frame open in the middle' if self.open else 'solid'},"
                f" with {self.tabs} tabs that hold it on {self.grip}")
