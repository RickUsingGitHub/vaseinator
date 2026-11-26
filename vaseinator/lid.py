"""A lid for a tissue box cover's open end, printed on its own - after the cover, if wanted.

A thin-walled cover is stiff only by its corners, and a ledge inside a cover printed upside down has to slope -
so a lid that hangs on ledges pushes the walls apart under a box of tissues and lets go. This lid hangs on flat
faces instead, and loads the walls only along themselves, the way they are strong. It goes in like a bayonet:

* The cover has four **catches** inside its long sides, by the corners (see geometry.catches): a **tooth**, a
  **pocket** under a short **bridge**, and a **stop**. The bridge is printed as a bridge, so its underside is flat.
* The lid is a flat plate a little way up inside the rim, with four **ears** on its long edges. It is laid in
  short of home, pushed in past the teeth and slid along: its ears pass under the teeth and spring up into the
  pockets, onto the bridges' flat undersides, against the stops. Then the teeth stop it sliding back unless it is
  pushed in again first - and the box of tissues' weight pushes the other way.
* Four **springs** - tongues cut in the plate, printed flat, the strong way, each with a post on its end - press
  on the box of tissues and push the lid out onto the bridges whichever way up the cover is.
* Nothing else stands on the plate - nothing beside the box of tissues to catch on it as the lid is pushed in -
  but an **arrow** on its end bar, pointing the way it slides to lock.

It is made from the cover's own design - the wall inside its rim is measured. Nothing here needs Qt.
"""

from __future__ import annotations

import math

import numpy as np

from . import hollow, sections
from .geometry import (CATCH_GAP, CATCH_IN, CATCH_LIP, CATCH_PLAIN, CATCH_PLAY, CATCH_SLIDE, LID_PLATE, box_outline,
                       catch_dip, catch_places, edge_check, lid_room, mesh_volume)
from .params import LID_FIRM, LID_GENTLE, LID_SNUG

LID_SLIDE = CATCH_SLIDE       # how far the lid slides along the cover to lock
LID_RING = 4.0                # the plate's rim, all round: how wide
LID_FRAME = 12.0              # an open lid: how wide its frame is, in from the edge; and every lid's end bars
LID_SLIT = 1.0                # how wide the slits round the springs are
LID_SPRING_WIDE = LID_FRAME - LID_RING - LID_SLIT      # each spring: a tongue this wide, beside the rim
LID_SPRING_LONG = 40.0        # ... this long, from the end bar it grows from - or less, on a short lid
LID_SPRING_SHORT = 20.0       # ... and no shorter, or it would be too stiff to push in
LID_POST = 5.0                # the post on each spring's end: this wide each way
LID_PRESS = {LID_GENTLE: 0.8, LID_SNUG: 1.5, LID_FIRM: 2.2}    # how far each post reaches past the box of tissues'
#                               bottom when the lid is home, the box as tall as it is set: the springs bend that far
GRIP_WORDS = {LID_GENTLE: "gently", LID_SNUG: "snugly", LID_FIRM: "firmly"}
LID_ARROW = 0.6               # the arrow on the end bar: how tall


def _anticlockwise(loop):
    x, y = loop[:, 0], loop[:, 1]
    area = 0.5 * float(np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y))
    return loop if area > 0 else loop[::-1]


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


def _slab(loop, z0: float, z1: float):
    """A closed solid: the loop (n, 2), anticlockwise round its middle (which it can see all of), from z0 up to
    z1."""
    loop = _anticlockwise(np.asarray(loop, dtype=float))
    n = len(loop)
    k = np.arange(n)
    nxt = (k + 1) % n
    mid = loop.mean(axis=0)
    verts = np.concatenate([np.column_stack([loop, np.full(n, z0)]), np.column_stack([loop, np.full(n, z1)]),
                            [[mid[0], mid[1], z0], [mid[0], mid[1], z1]]])
    faces = np.concatenate([np.stack([np.full(n, 2 * n), nxt, k], 1),               # underneath
                            np.stack([np.full(n, 2 * n + 1), n + k, n + nxt], 1),   # on top
                            np.stack([k, nxt, n + nxt], 1), np.stack([k, n + nxt, n + k], 1)])
    return verts, faces


class Lid:
    """The lid for a tissue box cover's design ``d`` (a VaseDesign, built in full): verts, faces - flat on the
    bed, the springs up, as it prints and as it is when the cover is on, in the place it is in when it is home,
    its underside CATCH_LIP above the rim - and its sums. ``along`` is the way it slides to lock (x, y): it is laid
    in ``slide`` mm short of home that way, pushed in ``dip`` mm, and slid home."""

    def __init__(self, d):
        p = d.p
        self.errors: list[str] = []
        self.notes: list[str] = []
        self.verts = self.faces = None
        self.ears = self.springs = 0
        self.closed = False
        self.slide = LID_SLIDE
        if not p.box or d.pot_rows is None or d.errors:
            self.errors.append("A lid is made for a tissue box cover.")
            return
        places = catch_places(p)
        if places is None or d.catch_wall is None:
            self.errors.append("The cover is too short for a lid: its catches need long sides with more that is "
                               "straight. Make the box longer, or the corners less round.")
            return
        a, b, c = box_outline(p)
        wall = p.line_width * max(int(p.walls), 1)
        zs, Os, Is, fs, _, _, swell = d.pot_rows
        Is = Is - sections.normals(Is) * swell[..., None]        # the wall inside, swollen round any holes
        H = float(zs[-1])
        X, Y = np.abs(Is[-1]).max(axis=0)
        U = np.array([1.0, 0.0]) if X >= Y else np.array([0.0, 1.0])     # the cover's long way
        # the cover is turned over to go on: seen from above, its inside as the lid meets it is mirrored
        T = U * [1.0, -1.0]                       # the long way, as the lid sees it: the same places along it
        V = np.array([-T[1], T[0]])
        self.along = T
        self.dip = catch_dip(p)

        def at(u, v):
            return np.outer(u, T) + np.outer(v, V) if np.ndim(u) else u * T + v * V

        def rounded(u0, u1, w, r, n=10):
            """A rectangle from u0 to u1 along T and w each side of the middle across it, its corners rounded r."""
            r = max(min(r, w - 0.01, 0.5 * (u1 - u0) - 0.01), 0.0)
            n = n if r > 0.05 else 1                  # a square corner: one point
            pts = []
            for cu, cv, a0 in ((u1 - r, -w + r, -90.0), (u1 - r, w - r, 0.0), (u0 + r, w - r, 90.0),
                               (u0 + r, -w + r, 180.0)):
                t = np.radians(np.linspace(a0, a0 + 90.0, n))
                pts.append(at(cu + r * np.cos(t), cv + r * np.sin(t)))
            return _anticlockwise(np.concatenate(pts))

        def rect(u0, u1, v0, v1):
            v0, v1 = min(v0, v1), max(v0, v1)
            return _anticlockwise(np.array([at(u0, v0), at(u1, v0), at(u1, v1), at(u0, v1)]))

        # the plate's outline: in from the long sides' inner faces clear of the catches; at each end, in from the
        # end's inside - measured, nearest at any height the lid passes - and short of the - end by the slide
        rows = np.nonzero(H - zs <= CATCH_PLAIN)[0]
        inner = [Is[k] * [1.0, -1.0] for k in rows]
        across = np.linspace(-(b - c - 1.0), b - c - 1.0, 25)
        u1 = min(float(_reach(loop, T, V, across).min()) for loop in inner) - CATCH_GAP
        u0 = -(min(float(_reach(loop, -T, V, across).min()) for loop in inner) - CATCH_GAP) + LID_SLIDE
        w = d.catch_wall - CATCH_IN - CATCH_GAP           # half the plate's width
        r = max(c - wall - CATCH_GAP, 1.0)
        outline = rounded(u0, u1, w, r)
        if w < LID_FRAME + LID_SLIT + 4.0:
            self.errors.append("The cover is too narrow for a lid.")
            return
        # the springs: tongues along the long sides, growing from the end bars towards the middle
        long = min(LID_SPRING_LONG, 0.5 * ((u1 - u0) - 2.0 * LID_FRAME - 2.0 * LID_SLIT - 10.0))
        if long < LID_SPRING_SHORT:
            self.errors.append("The cover is too short for a lid: its springs need longer sides. Make the box "
                               "longer.")
            return
        press = LID_PRESS.get(p.lid_grip, LID_PRESS[LID_SNUG])
        post = lid_room(p) - CATCH_LIP - LID_PLATE + press        # the posts reach the box of tissues, and press it
        tips = (u0 + LID_FRAME + long, u1 - LID_FRAME - long)     # each spring's free end, from the - end and the +
        s_out, s_in = w - LID_RING - LID_SLIT, w - LID_FRAME      # each spring's sides, across from the middle

        parts = [self._ring(outline, rounded(u0 + LID_RING, u1 - LID_RING, w - LID_RING, r - LID_RING))]
        bar = rounded(u0 + LID_RING - 1.0, u1 - LID_RING + 1.0, w - LID_RING + 1.0, r - LID_RING + 1.0)
        parts.append(_slab(self._clip(bar, T, u1 - LID_FRAME), 0.0, LID_PLATE))         # the end bars
        parts.append(_slab(self._clip(bar, -T, -(u0 + LID_FRAME)), 0.0, LID_PLATE))
        for s in (1.0, -1.0):
            for g0, g1, tip in ((u0 + LID_FRAME - 1.0, tips[0], tips[0]), (tips[1], u1 - LID_FRAME + 1.0, tips[1])):
                parts.append(_slab(rect(g0, g1, s * s_in, s * s_out), 0.0, LID_PLATE))
                q = tip + (LID_SLIT if tip == tips[1] else -LID_SLIT - LID_POST)   # the post, by the free end
                v_mid = s * 0.5 * (s_in + s_out)
                parts.append(_slab(rect(q, q + LID_POST, v_mid - 0.5 * LID_POST, v_mid + 0.5 * LID_POST),
                                   LID_PLATE, LID_PLATE + post))
                self.springs += 1
            # between the springs' free ends, the frame is whole
            reach_in = s_in - (0.0 if p.lid_open else LID_SLIT + 1.0)
            parts.append(_slab(rect(tips[0] + LID_SLIT, tips[1] - LID_SLIT, s * reach_in, s * (w - LID_RING + 1.0)),
                               0.0, LID_PLATE))
            # the ears, one under each catch's bridge
            for t0, t1, s0, s1 in places:
                parts.append(_slab(rect(t1 + CATCH_PLAY, s0 - CATCH_PLAY, s * (w - LID_RING + 0.5),
                                        s * (d.catch_wall - CATCH_GAP)), 0.0, LID_PLATE))
                self.ears += 1
        if not p.lid_open:                        # solid: a panel between the springs, joined to the end bars
            panel = self._clip(self._clip(bar, V, -(s_in - LID_SLIT)), -V, -(s_in - LID_SLIT))
            parts.append(_slab(panel, 0.0, LID_PLATE))
        # the arrow on the + end bar, the way it slides to lock
        m = u1 - LID_RING - 0.5 * (LID_FRAME - LID_RING)
        parts.append(_slab(rect(m - 4.0, m + 0.5, -1.2, 1.2), LID_PLATE, LID_PLATE + LID_ARROW))
        parts.append(_slab(np.array([at(m, -3.5), at(m + 3.5, 0.0), at(m, 3.5)]), LID_PLATE, LID_PLATE + LID_ARROW))

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
        # the plastic: the parts overlap a little where they join, so it is a shade less than their sum
        vol = sum(mesh_volume(v_, f_) for v_, f_ in parts) * 0.97
        self.grams = vol / 1000.0 * p.density
        speed = min(p.speed, p.max_flow / max(p.line_width * p.layer_height, 1e-6))
        self.seconds = vol / (p.line_width * p.layer_height) / max(speed, 0.1) + 120.0
        self.p = p

    @staticmethod
    def _clip(loop, n, d: float):
        """The part of the loop where p·n >= d (a straight cut)."""
        out = []
        k = len(loop)
        for i in range(k):
            a, b = loop[i], loop[(i + 1) % k]
            da, db = a @ n - d, b @ n - d
            if da >= 0:
                out.append(a)
            if (da >= 0) != (db >= 0):
                out.append(a + (b - a) * (da / (da - db)))
        return np.array(out)

    @staticmethod
    def _ring(outline, hole):
        """The flat plate's rim, LID_PLATE thick: from the outline in to the hole (each anticlockwise round the
        middle)."""
        n, m = len(outline), len(hole)
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
                f" with {self.ears} ears that slide in under the cover's catches and {self.springs} springs that "
                f"hold it shut {self.grip}")
