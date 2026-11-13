"""A lid for a tissue box cover's open end, printed on its own - after the cover, if wanted.

A thin-walled cover is stiff only by its corners: the middle of a side or an end bows out at a touch, so a
catch there lets go as soon as a box of tissues leans on the lid. This lid holds on where the cover is stiff,
with nothing that has to bend to hold:

* The cover has four short **rails** inside its long sides, by the corners (see geometry.rails). The lid has four
  rigid **hooks**. It is laid on the rim a little way along from where it belongs - the hooks go in beside the
  rails - and slid along, like a battery cover: each hook's claw slides in behind its rail. The claws' undersides
  rise a little towards their leading ends, so the lid is drawn tight against the rim as it comes home.
* The hooks stand on a **fence** along each long side, which keeps the plate stiff under the box of tissues; a
  lower fence across the far end is the **stop** that says the lid is home.
* By the pull tab, the plate's end bar is a flat spring - printed flat, the strong way - with a ridge on it, the
  **latch**: it springs up inside the cover's end as the lid comes home, and the lid can't slide back. Lifting the
  tab bends the bar away, and the lid slides out.

It is made from the cover's own design - the wall where each part goes is measured. Nothing here needs Qt.
"""

from __future__ import annotations

import math

import numpy as np

from . import hollow, sections
from .geometry import (RAIL_END, RAIL_IN, box_outline, edge_check, mesh_volume, rail_heights, rail_lean,
                       rail_places)
from .params import LID_FIRM, LID_GENTLE, LID_SNUG

LID_PLATE = 1.6               # how thick the plate is (mm)
LID_FRAME = 12.0              # an open lid: how wide its frame is, in from the edge
LID_SLIDE = RAIL_IN - RAIL_END    # how far the lid slides along the cover to lock
LID_HOOK_IN = 1.0             # how far each hook stops short of its rail's ends
LID_POST = 2.4                # how thick each hook's post is
LID_POST_GAP = 0.3            # between a post and the face of its rail
LID_TIP_GAP = 0.35            # between a claw's tip and the wall
LID_CLAW = 1.6                # how thick each claw is at its tip, at the least
LID_TAPER = 0.5               # how much higher each claw's underside is at its leading end: the lid is drawn tight
#                               against the rim over the last of its slide
LID_GRIP = {LID_GENTLE: 0.15, LID_SNUG: 0.0, LID_FIRM: -0.15}   # between a claw and its rail when the lid is home:
#                               less than nothing squeezes them together
GRIP_WORDS = {LID_GENTLE: "gently", LID_SNUG: "snugly", LID_FIRM: "firmly"}
LID_FENCE = 2.0               # the fence along each long side: how thick
LID_FENCE_TALL = 5.0          # ... how tall
LID_FENCE_BACK = 0.1          # ... and how far back it stands from the hooks' posts
LID_STOP_TALL = 2.0           # the stop across the far end: how tall - low, to pass over the box as the lid slides
LID_STOP_GAP = 0.15           # ... and how far from the cover's end it stops the lid
LID_LATCH_TALL = 1.8          # the latch's ridge, by the pull tab: how tall
LID_LATCH_FLAT = 0.6          # ... the flat on its top
LID_LATCH_RAMP = 3.0          # ... how long the slope the cover's rim rides up as the lid slides on
LID_LATCH_GAP = 0.35          # ... how far inside the cover's end it springs up
LID_LATCH_LONG = 30.0         # ... and how long it is, across the end - or 0.3 of the end, if that is less
LID_BAR_SHORT = 0.8           # the latch's bar stops this far short of the box of tissues, which mustn't lean on it
LID_END_MIN = 45.0            # the straight part of an end must be this long for the latch's bar to bend
LID_SINK = 0.3                # how far everything on the plate goes down into it, to be one with it
LID_PULL = 9.0                # how far the pull tab sticks out past the rim
LID_PULL_WIDE = 26.0          # ... and how wide it is


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


def _loft(first, last, U, V, v0: float, v1: float, z0: float):
    """A closed solid: a bar from v0 to v1 along V, standing at z0, whose section is the profile ``first`` (n, 2)
    of (out along U, up) points at v0 and ``last`` at v1 - each anticlockwise, with as many points. Its caps are
    fans from each profile's first point."""
    n = len(first)
    ends = []
    for profile, v in ((first, v0), (last, v1)):
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


def _prism(profile, U, V, v0: float, v1: float, z0: float):
    """A closed solid: the profile (n, 2) of (out along U, up) points, anticlockwise, made into a bar from
    v0 to v1 along V, standing at z0."""
    profile = np.asarray(profile, dtype=float)
    return _loft(profile, profile, U, V, v0, v1, z0)


def _slab(loop, z0: float, z1: float):
    """A closed solid: the loop (n, 2), anticlockwise round the middle, from z0 up to z1."""
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
    bed, the hooks up, as it prints and as it goes on, in the place it is in when it is home - and its sums.
    ``along`` is the way to the pull tab's end (x, y): the lid goes on ``slide`` mm that way from home, and slides
    back to lock."""

    def __init__(self, d):
        p = d.p
        self.errors: list[str] = []
        self.notes: list[str] = []
        self.verts = self.faces = None
        self.hooks = self.latches = 0
        self.closed = False
        self.slide = LID_SLIDE
        if not p.box or d.pot_rows is None or d.errors:
            self.errors.append("A lid is made for a tissue box cover.")
            return
        places = rail_places(p)
        a, b, c = box_outline(p)
        side, end = a - c, b - c                  # half the straight part of each long side, and of each end
        if places is None:
            self.errors.append("The cover is too short for a lid: its hooks need long sides with more that is "
                               "straight. Make the box longer, or the corners less round.")
            return
        if 2.0 * end < LID_END_MIN:
            self.errors.append("The cover's ends are too round for a lid: its latch needs an end with "
                               f"{LID_END_MIN:g} mm that is straight. Make the corners less round.")
            return
        zs, Os, Is, fs, _, _, swell = d.pot_rows
        Is = Is - sections.normals(Is) * swell[..., None]        # the wall inside, swollen round any holes
        H = float(zs[-1])
        # the cover is turned over to go on: seen from above, its rim as the lid meets it is mirrored
        def used(loop):
            return _anticlockwise(np.asarray(loop, dtype=float) * [1.0, -1.0])

        rim = _dense(used(Os[-1]))
        grip = LID_GRIP.get(p.lid_grip, LID_GRIP[LID_SNUG])
        top = LID_PLATE
        X, Y = np.abs(rim).max(axis=0)
        T = np.array([1.0, 0.0]) if X >= Y else np.array([0.0, 1.0])     # the long way, to the pull tab's end
        V = np.array([-T[1], T[0]])
        self.along = T
        h0, h1, h2 = rail_heights(p)
        slope = math.tan(math.radians(rail_lean(p)))             # out, for each mm up a rail's sloping side
        tall = h2 + LID_TAPER + LID_CLAW + 1.0                   # as tall as a hook may come to
        heights = H - zs                                          # how far above the rim each row is, the cover on
        rows = np.arange(max(int(np.nonzero(heights <= tall + 6.0)[0].min()) - 1, 0), len(zs))
        inner = [used(Is[k]) for k in rows]
        order = np.argsort(heights[rows])
        h = heights[rows][order]

        def wall(O, A, lo, hi):
            """How near the wall comes, going out along O, at each row's height above the rim - anywhere from
            lo to hi along A."""
            at = np.linspace(lo, hi, max(int(math.ceil((hi - lo) / 0.8)) + 1, 3))
            return np.array([_reach(loop, O, A, at).min() for loop in inner])[order]

        def nearest(w, lo, hi):
            s = np.concatenate([[lo, hi], h[(h > lo) & (h < hi)]])
            return float(np.interp(s, h, w).min())

        # the plate: the rim's outline with the pull tab; a frame, its bar at the tab's end narrow - the latch's
        # spring, which the box of tissues mustn't lean on; solid, a panel fills the frame but for a slit there
        bar = min(max(a - 0.5 * max(p.box_length, p.box_width) - LID_BAR_SHORT, 4.0), LID_FRAME - 2.0)

        def towards_tab(loop, by):
            return loop + np.where((loop @ T > 0.0)[:, None], by * T, 0.0)

        hole = towards_tab(_anticlockwise(sections.inset(rim, LID_FRAME)), LID_FRAME - bar)
        parts = [self._plate(self._pull_tab(rim, T, V), hole)]
        if not p.lid_open:
            panel = towards_tab(_anticlockwise(sections.inset(rim, LID_FRAME - 0.5)), LID_FRAME - bar - 1.5)
            parts.append(_slab(panel, 0.0, LID_PLATE))

        # the hooks: one behind each rail when the lid is home. Each is measured where it stands, where it goes
        # in, and all the way between
        start, to = places
        homes = [(start + LID_HOOK_IN, to - LID_HOOK_IN), (-(to - LID_HOOK_IN), -(start + LID_HOOK_IN))]
        fits = []
        for O in (V, -V):
            for u0, u1 in homes:
                home = wall(O, T, u0, u1)
                rail = nearest(home, h0, h1)                      # the face of the rail
                plain = min(nearest(wall(O, T, u0 + LID_SLIDE, u1 + LID_SLIDE), 0.0, tall),
                            nearest(wall(O, T, u0, u1 + LID_SLIDE), h2 + 0.3, tall))
                fits.append([O, u0, u1, home, rail - LID_POST_GAP, plain - LID_TIP_GAP])
        # every hook the same shape: as deep a claw as the shallowest
        depth = min(tip - post for *_, post, tip in fits)
        if depth < 0.6:
            self.errors.append("The wall inside the cover goes in and out too much by its rim for a lid's hooks.")
            return
        for fit in fits:
            O, u0, u1, home, post, _ = fit
            # where the rail's sloping side comes out to the claw's tip, as measured
            hs = np.linspace(h1, h2 + 0.5, 80)
            ws = np.interp(hs, h, home)
            fit.append(float(hs[np.argmax(ws >= post + depth)]) if (ws >= post + depth).any()
                       else h1 + (depth - LID_POST_GAP) / slope)
        crown = max(fit[6] for fit in fits) + LID_TAPER + max(grip, 0.0) + LID_CLAW      # every hook as tall
        posts = {1: [], -1: []}
        for O, u0, u1, home, post, _, catch in fits:
            def profile(gap):
                # from the claw's root round: its tip, the top, the back of the post, down into the plate
                return np.array([[post, catch - depth / slope + gap], [post + depth, catch + gap],
                                 [post + depth, crown], [post - LID_POST, crown],
                                 [post - LID_POST, -LID_SINK], [post, -LID_SINK]])

            # the leading end, towards the far end of the lid, is the higher: the claw tightens as it slides home
            parts.append(_loft(profile(grip + LID_TAPER), profile(grip), O, T, u0, u1, top))
            posts[1 if O @ V > 0 else -1].append(post)
            self.hooks += 1

        # the fences, one along each long side between its hooks and past them: they keep the plate stiff under
        # the box of tissues. Each stops short of the tab's end by the slide, to go in clear of the corner
        f0, f1 = -side + 2.0, side - LID_SLIDE - 1.5
        for O in (V, -V):
            face = min(nearest(wall(O, T, f0, f1 + LID_SLIDE), 0.0, LID_FENCE_TALL + 0.3) - LID_POST_GAP,
                       min(posts[1 if O @ V > 0 else -1])) - LID_FENCE_BACK
            parts.append(_prism([[face - LID_FENCE, -LID_SINK + 0.05], [face, -LID_SINK + 0.05],
                                 [face, LID_FENCE_TALL], [face - LID_FENCE, LID_FENCE_TALL]], O, T, f0, f1, top))
        # the stop, across the far end: it meets the inside of the cover's end when the lid is home
        s1 = end - 2.0
        face = nearest(wall(-T, V, -s1, s1), 0.0, LID_STOP_TALL + 0.3) - LID_STOP_GAP
        parts.append(_prism([[face - LID_FENCE, -LID_SINK + 0.05], [face, -LID_SINK + 0.05],
                             [face, LID_STOP_TALL], [face - LID_FENCE, LID_STOP_TALL]], -T, V, -s1, s1, top))
        # the latch, on the bar at the tab's end: a ridge that springs up just inside the cover's end. The rim
        # rides up its slope as the lid slides on; its upright side then faces the wall
        r1 = 0.5 * min(LID_LATCH_LONG, 0.6 * end)
        face = nearest(wall(T, V, -r1, r1), 0.0, LID_LATCH_TALL + 0.3) - LID_LATCH_GAP
        reach = (LID_LATCH_TALL + LID_SINK) / LID_LATCH_TALL
        room = face - (float((rim @ T).max()) - bar) - 0.2 - LID_LATCH_FLAT     # on the bar, all of it
        ramp = min(LID_LATCH_RAMP * reach, room)
        if ramp < 1.0:
            self.errors.append("There is too little room inside the cover's end for a lid's latch.")
            return
        parts.append(_prism([[face - LID_LATCH_FLAT - ramp, -LID_SINK], [face, -LID_SINK], [face, LID_LATCH_TALL],
                             [face - LID_LATCH_FLAT, LID_LATCH_TALL]], T, V, -r1, r1, top))
        self.latches = 1
        if 2.0 * (b - LID_FRAME) < 70.0:                          # the bar, from one long side of the frame to the other
            self.notes.append("The cover's end is short, so the latch's bar is stiff: lift the pull tab firmly, "
                              "and no further than it takes.")

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
    def _plate(outline, hole):
        """The flat plate, LID_PLATE thick: a frame, from the outline in to the hole (each anticlockwise round
        the middle)."""
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
                f" with {self.hooks} hooks that slide in behind the cover's rails and fit them {self.grip}, and a "
                "latch by the pull tab")
