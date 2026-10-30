"""The vase as a normal print makes it: a hollow pot, with holes cut right through its wall if you like.

The pot is built from rows of points round the vase - the outer face's and the
inner face's, at the same heights - on the grid the vase's surface is made on.
A hole pattern is a number at each grid point: how far inside a hole it is, in
mm, below nought in the wall. The wall is cut where that number is nought
(marching squares), the same on both faces, and a side face joins them round
each hole. Every cut is one vertex shared by the faces on either side of it,
so the pot stays closed and watertight.

Holes print without supports: going up the wall a hole may only close in as
fast as the overhang limit allows, so each one ends in a pointed top. The
same goes for a face's eyes, mouth and strap slots, and for the gap at the
back of a wall that goes only part way round - a mask.
"""

from __future__ import annotations

import math

import numpy as np

from . import sections
from .params import (ALMOND_EYES, CHIN_MOUTH, DIAMOND, GRILLE_MOUTH, NO_EYES, NO_HOLES, OPEN_MOUTH,
                     ROUND, SLOTS, VORONOI)

OUTER, INNER, SIDE, CAP, TIP = 0, 1, 2, 3, 4   # what each face of the pot is: TIP is the short bridge at the
                                               # very top of a hole, where it closes between two grid points
TALL = 1.3               # Voronoi cells this much taller than a honeycomb's: their oval holes stand upright
OVAL = 0.97              # a Voronoi hole's oval fills this much of the room its cell leaves it
TILT = 0.5               # ... and leans this share as far as its cell does


# ================================================================= the holes
def row_lengths(O):
    """For rows of points (K, N, 2): the distance to the next point (K, N), along from the first (K, N), and
    each row's length round (K,)."""
    seg = np.linalg.norm(np.roll(O, -1, axis=1) - O, axis=2)
    along = np.concatenate([np.zeros((len(O), 1)), np.cumsum(seg[:, :-1], axis=1)], axis=1)
    return seg, along, seg.sum(axis=1)


def _lattice(kind, size, strut, z_lo, z_hi, n_round):
    """Where the holes go: rows of centres, every other row half a step round, filling z_lo..z_hi.

    Returns (row pitch, the rows' heights, holes round). A Voronoi pattern also gets a row of solid
    cells below and above, so its edge cells close.
    """
    if kind == DIAMOND:
        pitch = 0.5 * size
    elif kind == SLOTS:                              # a slot, its pointed top, and the wall above it
        pitch = 2.0 * size + 1.5 * (size - strut) + strut
    else:
        pitch = size * math.sqrt(3.0) / 2.0 * (TALL if kind == VORONOI else 1.0)
    span = z_hi - z_lo
    first = 1 if kind != VORONOI else 0
    # each hole needs room for its pointed top above it; Voronoi cells stop at their solid neighbours
    reach = pitch if kind == SLOTS else {VORONOI: 0.5, ROUND: 1.0, DIAMOND: 1.0}[kind] * size
    rows = max(int((span - reach) // pitch) + first, 0)
    if rows == 0:
        return pitch, np.zeros(0), n_round
    used = (rows - 1) * pitch + reach
    zs = z_lo + 0.5 * (span - used) + 0.5 * reach * (kind != VORONOI) + pitch * np.arange(rows)
    if kind == VORONOI:
        zs = z_lo + 0.5 * (span - (rows - 1) * pitch) + pitch * np.arange(rows)
    return pitch, zs, n_round


def hole_field(kind, t, z, L, size, strut, jitter, seed, z_lo, z_hi, room=None, slope=0.85, bridge=10.0):
    """How far inside a hole each grid point is, in mm (below nought in the wall), and how wide a hole's top may
    be bridged at each point (mm: Voronoi's ovals; None for the other patterns, which come to points).

    t (K, N): the share of the way round of each grid point, 0..1 (turning with the shape when it twists);
    z (K,): the rows' heights; L (K,): their lengths round. Holes keep between z_lo and z_hi, and inside room
    (K, N) where it is given: above nought where a hole may go (clear of a face's holes, say). slope: how fast
    a hole's sides may close in going up (mm each side for each mm up); bridge: the widest top a Voronoi oval
    may close over.

    A Voronoi hole is an oval in its cell - as long, as wide and as tilted as the cell itself - kept a strut's
    width in from the cell's sides: the wall between the holes is thin where two cells meet and thick where
    three do, with no corners anywhere.
    """
    K, N = t.shape
    f = np.full((K, N), -1.0)
    spans = np.zeros((K, N)) if kind == VORONOI else None
    if kind == NO_HOLES or z_hi - z_lo < 0.5 * size:
        return f, spans
    band = (z >= z_lo - size) & (z <= z_hi + size)
    rows_in = np.nonzero(band)[0]
    if not len(rows_in):
        return f, spans
    n_round = max(int(round(float(np.mean(L[band])) / size)), 3)
    pitch, zs, n_round = _lattice(kind, size, strut, z_lo, z_hi, n_round)
    if not len(zs):
        return f, spans
    rng = np.random.default_rng(int(seed))
    solid_rows = kind == VORONOI
    if solid_rows:                                   # a row of solid cells either side
        zs = np.concatenate([[zs[0] - pitch], zs, [zs[-1] + pitch]])
    R = len(zs)
    stagger = 0.0 if kind == SLOTS else 0.5            # every other row half a step round; slots in columns
    tc = (np.arange(n_round)[None, :] + stagger * (np.arange(R)[:, None] % 2)) / n_round
    zc = np.broadcast_to(zs[:, None], (R, n_round)).copy()
    if kind == VORONOI and jitter > 0:
        tc = tc + rng.uniform(-0.5, 0.5, (R, n_round)) * jitter / n_round
        zc = zc + rng.uniform(-0.5, 0.5, (R, n_round)) * jitter * pitch
    hole_seed = np.ones((R, n_round), dtype=bool)
    if solid_rows:
        hole_seed[0] = hole_seed[-1] = False
    # the nearest centres of each grid point: its own lattice cell and the cells round it
    tt, zz, LL = t[rows_in], z[rows_in][:, None], L[rows_in][:, None]
    r0 = np.floor((zz - zs[0]) / pitch).astype(int)
    r0 = np.broadcast_to(r0, tt.shape)
    best = np.full(tt.shape + (2,), np.inf)
    best_hole = np.zeros(tt.shape, dtype=bool)
    best_dx, best_dz = np.zeros(tt.shape), np.zeros(tt.shape)       # from the nearest centre to the point
    best_cell = np.zeros(tt.shape, dtype=np.intp)
    reach_r = 2 if kind == VORONOI else 1
    for dr in range(-reach_r, reach_r + 1):
        r = r0 + dr
        ok = (r >= 0) & (r < R)
        rc = np.clip(r, 0, R - 1)
        c0 = np.floor(tt * n_round - stagger * (rc % 2)).astype(int)
        for dc in range(-2, 3):
            c = np.mod(c0 + dc, n_round)
            dt = np.mod(tt - tc[rc, c] + 0.5, 1.0) - 0.5
            dx = dt * LL
            dzz = zz - zc[rc, c]
            if kind == DIAMOND:
                sx = LL / n_round
                ax = np.maximum(0.5 * sx - 0.75 * strut, 0.3)
                az = max(pitch - 0.75 * strut, 0.3)
                d = (np.abs(dx) / ax + np.abs(dzz) / az - 1.0) * np.minimum(ax, az)
            elif kind == SLOTS:
                sx = LL / n_round
                w = np.maximum(sx - strut, 0.6)
                d = np.hypot(dx, np.maximum(np.abs(dzz) - size, 0.0)) - 0.5 * w
            else:
                d = np.hypot(dx, dzz)
            d = np.where(ok, d, np.inf)
            closer = d < best[..., 0]
            best[..., 1] = np.where(closer, best[..., 0], np.minimum(best[..., 1], d))
            best_hole = np.where(closer, hole_seed[rc, c], best_hole)
            best[..., 0] = np.where(closer, d, best[..., 0])
            if kind == VORONOI:
                best_dx = np.where(closer, dx, best_dx)
                best_dz = np.where(closer, dzz, best_dz)
                best_cell = np.where(closer, rc * n_round + c, best_cell)
    if kind == VORONOI:
        # how far in from the cell's sides: each is the line halfway to a neighbouring centre
        inside = np.full(tt.shape, np.inf)
        for dr in range(-reach_r, reach_r + 1):
            r = r0 + dr
            ok = (r >= 0) & (r < R)
            rc = np.clip(r, 0, R - 1)
            c0 = np.floor(tt * n_round - stagger * (rc % 2)).astype(int)
            for dc in range(-2, 3):
                c = np.mod(c0 + dc, n_round)
                dx = (np.mod(tt - tc[rc, c] + 0.5, 1.0) - 0.5) * LL
                dzz = zz - zc[rc, c]
                gap = np.hypot(best_dx - dx, best_dz - dzz)          # from this centre to the nearest
                side = (dx * dx + dzz * dzz - best_dx * best_dx - best_dz * best_dz) / (2.0 * np.maximum(gap, 1e-9))
                inside = np.where(ok & (gap > 1e-6), np.minimum(inside, side), inside)
        # the room for a hole: the cell, a strut's width in from its sides, clear of the plain foot and rim
        cell = np.minimum(inside - 0.5 * strut, np.minimum(zz - z_lo, z_hi - zz))
        if room is not None:
            cell = np.minimum(cell, room[rows_in])
        ovals, span = _ovals(cell, best_cell, best_dx, best_dz, slope, bridge)
        fr = np.where(best_hole, np.minimum(ovals, cell), -inside - 0.5 * strut)
        spans[rows_in] = np.where(best_hole, span, 0.0)
    elif kind == ROUND:
        sx = LL / n_round
        near = np.minimum(sx, np.hypot(0.5 * sx, pitch))     # the nearest neighbour's distance, this row
        fr = 0.5 * (near - strut) - best[..., 0]
    else:
        fr = -best[..., 0]
    fr = np.where(np.isfinite(fr), fr, -1.0)
    # never into the foot or the rim, nor out of the room given
    fr = np.minimum(fr, np.minimum(zz - z_lo, z_hi - zz))
    if room is not None:
        fr = np.minimum(fr, room[rows_in])
    f[rows_in] = fr
    return f, spans


def _ovals(cell, ids, dx, dz, slope, bridge):
    """Each Voronoi cell's oval, as a hole field (mm in from its edge), and the span its round top is bridged
    at, at each of its points.

    The oval is centred on the middle of the room the cell leaves for a hole, as long, as wide and as tilted as
    that room (the oval with the same spread of points), and as big as fits wholly inside it - so no oval is
    ever clipped flat by its cell, and the wall left round it is thin where it nears a side and thick in the
    corners. Its top closes over a bridge where its sides grow flatter than ``slope``; an oval whose bridge
    would be wider than ``bridge`` is made smaller. dx, dz: each point from its cell's centre (mm); ids: its
    cell; cell: how far inside the room it is."""
    use = cell > 0
    n = int(ids.max()) + 1
    out = np.full(cell.shape, -1.0)
    if not use.any():
        return out, np.zeros(cell.shape)
    w = use.astype(float)
    count = np.maximum(np.bincount(ids.ravel(), w.ravel(), n), 1.0)
    mx = np.bincount(ids.ravel(), (w * dx).ravel(), n) / count
    mz = np.bincount(ids.ravel(), (w * dz).ravel(), n) / count
    u, v = dx - mx[ids], dz - mz[ids]
    sxx = np.bincount(ids.ravel(), (w * u * u).ravel(), n) / count
    szz = np.bincount(ids.ravel(), (w * v * v).ravel(), n) / count
    sxz = np.bincount(ids.ravel(), (w * u * v).ravel(), n) / count
    # its axes: an even oval's points spread a quarter of its half-length squared along each
    spread = np.sqrt(0.25 * (sxx - szz) ** 2 + sxz ** 2)
    a = 2.0 * np.sqrt(np.maximum(0.5 * (sxx + szz) + spread, 1e-6))
    b = 2.0 * np.sqrt(np.maximum(0.5 * (sxx + szz) - spread, 1e-6))
    turn = 0.5 * np.arctan2(2.0 * sxz, sxx - szz)
    # leaning less than their cells: an upright oval's top needs the shortest bridge, so it can be bigger
    upright = np.where(sxx > szz, 0.0, 0.5 * math.pi)
    turn = upright + TILT * (np.mod(turn - upright + 0.5 * math.pi, math.pi) - 0.5 * math.pi)
    c, s = np.cos(turn)[ids], np.sin(turn)[ids]
    along, across = u * c + v * s, -u * s + v * c
    reach = np.hypot(along / a[ids], across / b[ids])         # 1 on that oval
    # as big as fits: shrunk to just inside the nearest point of the cell that has no room
    fits = np.full(n, np.inf)
    np.minimum.at(fits, ids[~use], reach[~use])
    scale = np.minimum(OVAL * np.where(np.isfinite(fits), fits, 1.0), 1.0)
    # the bridge its top needs: its width where, coming down from the top, its sides first lean no flatter
    # than the slope allows; bigger than allowed, the oval is made smaller to suit
    need = _top_span(a * scale, b * scale, turn, slope)
    smaller = np.minimum(bridge / np.maximum(need, 1e-9), 1.0)
    scale = scale * smaller
    span = need * smaller + 0.3
    return (scale[ids] - reach) * np.minimum(a, b)[ids], span[ids]


def _top_span(a, b, turn, slope, samples=240):
    """For ovals with half-lengths a and b, the a-axis turned ``turn`` from the row: how wide each is (along the
    row) where, coming down from its top, both its sides first close in by no more than ``slope`` for each mm
    up - the bridge its round top needs. A tilted oval's two sides lean differently: each is looked at."""
    c, s = np.cos(turn), np.sin(turn)
    # x along the row, y up: A x^2 + B x y + C y^2 = 1
    A = (c / a) ** 2 + (s / b) ** 2
    B = 2.0 * c * s * (1.0 / a ** 2 - 1.0 / b ** 2)
    C = (s / a) ** 2 + (c / b) ** 2
    top = np.sqrt(4.0 * A / np.maximum(4.0 * A * C - B * B, 1e-12))
    low = -top
    y = top[:, None] + (low - top)[:, None] * np.linspace(0.0, 1.0, samples)[None, :]   # from the top down
    root = np.sqrt(np.maximum((B[:, None] * y) ** 2 - 4.0 * A[:, None] * (C[:, None] * y * y - 1.0), 0.0))
    left = (-B[:, None] * y - root) / (2.0 * A[:, None])
    right = (-B[:, None] * y + root) / (2.0 * A[:, None])
    dy = np.maximum(2.0 * top[:, None] / (samples - 1), 1e-12)
    # going up, how fast each side moves in over the hole
    gentle = ((left[:, :-1] - left[:, 1:]) / dy <= slope) & ((right[:, 1:] - right[:, :-1]) / dy <= slope)
    first = np.where(gentle.any(axis=1), np.argmax(gentle, axis=1), samples - 2)
    return (right - left)[np.arange(len(a)), first]


# ================================================================ the face
def from_front(O, seg, along, L):
    """How far along each row each point is from the front of the vase (-y), in mm: + one way round, - the
    other. The front is where the row crosses straight in front of the axis (the outermost such place)."""
    K, N = O.shape[:2]
    ang = np.arctan2(O[..., 1], O[..., 0])
    d = np.mod(ang + 0.5 * math.pi + math.pi, 2 * math.pi) - math.pi         # how far round past the front
    nxt = np.roll(d, -1, axis=1)
    cross = (d <= 0) & (nxt > 0) & (nxt - d < math.pi)
    radius = np.where(cross, np.hypot(O[..., 0], O[..., 1]), -1.0)
    i = np.argmax(radius, axis=1)
    k = np.arange(K)
    u = np.where(cross[k, i], -d[k, i] / np.maximum(nxt[k, i] - d[k, i], 1e-12), 0.0)
    start = along[k, i] + u * seg[k, i]
    return np.mod(along - start[:, None] + 0.5 * L[:, None], L[:, None]) - 0.5 * L[:, None]


def _ellipse(x, y, a, b):
    return (1.0 - np.hypot(x / a, y / b)) * min(a, b)


def _almond(x, y, a, b):
    """A pointed oval, a wide and b high (half sizes): where two circles overlap."""
    rho = (a * a + b * b) / (2.0 * b)
    c = rho - b
    return rho - np.maximum(np.hypot(x, y - c), np.hypot(x, y + c))


def _slot(x, y, w, h):
    """An upright slot with round ends, w wide and h tall."""
    return 0.5 * w - np.hypot(x, np.maximum(np.abs(y) - max(0.5 * (h - w), 0.0), 0.0))


def openings(s, z, L, p):
    """The face's holes and the gap at the back, as a hole field (mm, below nought in the wall).

    s (K, N): how far along the row from the front each point is (mm); z (K,) the rows' heights; L (K,)
    their lengths round. The eyes, mouth and straps are placed in mm along the surface, mirrored either side
    of the front.
    """
    f = np.full(s.shape, -1.0)
    zz = np.broadcast_to(z[:, None], s.shape)
    if p.around < 360.0:                                   # part way round: a gap at the back
        f = np.maximum(f, np.abs(s) - 0.5 * L[:, None] * p.around / 360.0)
    if p.eyes != NO_EYES:
        a, b = 0.5 * p.eye_width, 0.5 * p.eye_height
        for side in (1.0, -1.0):
            x, y = s - side * 0.5 * p.eye_apart, zz - p.eye_up
            t = math.radians(p.eye_tilt) * side           # the outer corners raised
            xr, yr = x * math.cos(t) + y * math.sin(t), -x * math.sin(t) + y * math.cos(t)
            shape = _almond if p.eyes == ALMOND_EYES else _ellipse
            f = np.maximum(f, shape(xr, yr, a, b))
    if p.mouth == OPEN_MOUTH:
        f = np.maximum(f, _ellipse(s, zz - p.mouth_up, 0.5 * p.mouth_width, 0.5 * p.mouth_height))
    elif p.mouth == GRILLE_MOUTH:
        n = max(int(p.mouth_slots), 1)
        pitch = p.mouth_width / n
        w = max(0.5 * pitch, 1.5)
        for k in range(n):
            x = (k - 0.5 * (n - 1)) * pitch
            lift = p.mouth_smile * (x / max(0.5 * (p.mouth_width - pitch), 1e-6)) ** 2   # the corners turn up
            f = np.maximum(f, _slot(s - x, zz - p.mouth_up - lift, w, p.mouth_height))
    elif p.mouth == CHIN_MOUTH:                            # open from the bottom edge up to mouth_up
        w = p.mouth_width
        f = np.maximum(f, 0.5 * w - np.hypot(s, np.maximum(zz - (p.mouth_up - 0.5 * w), 0.0)))
    if p.straps:
        at = float(np.interp(p.strap_up, z, L))
        edge = 0.5 * at * min(p.around, 360.0) / 360.0
        x0 = edge - 12.0 if p.around < 360.0 else 0.25 * at       # near the edges, or at the sides
        for side in (1.0, -1.0):
            f = np.maximum(f, _slot(s - side * x0, zz - p.strap_up, 5.0, 18.0))
    return f


def nose(s, z, p, slope: float):
    """A raised nose, in mm out from the face: a ridge from between the eyes that grows to its tip, and under
    the tip a slope back to the face no steeper than ``slope`` (mm in for each mm down)."""
    zz = np.broadcast_to(np.asarray(z, dtype=float)[:, None], s.shape)
    u = (zz - p.nose_up) / max(p.nose_length, 1e-6)                 # 0 at the tip, 1 between the eyes
    depth = np.where(u >= 0.0, p.nose_depth * np.clip(1.0 - u, 0.0, 1.0) ** 1.1,
                     np.maximum(p.nose_depth + (zz - p.nose_up) * slope, 0.0))
    half = 0.5 * p.nose_width * np.where(u >= 0.0, 0.45 + 0.55 * np.clip(1.0 - u, 0.0, 1.0), 1.0)
    across = np.clip(1.0 - (s / half) ** 2, 0.0, 1.0) ** 1.5
    return depth * across


def pointed_tops(f, z, O, slope, bridge=None):
    """Every hole closes at its top no faster than ``slope`` (mm in, each side, for each mm up).

    Going up row by row, the wall over a hole may only reach in that far past the wall below it - measured
    from the point really below, so on a twisting vase, whose grid leans round with the shape, the holes'
    sides lean no further than their tops. Where a hole would close faster it is kept open, so its top comes
    to a point instead of a flat roof that would need support.

    bridge (K, N), mm: where a hole is already narrower than this it may close at once - the printer bridges
    the rest of its rounded top - so an oval keeps its round top.
    """
    f = f.copy()
    K, N = f.shape
    seg, along, L = row_lengths(O)
    # how far round the row below each point's column has moved on the way up: the point below a point is
    # its own column's point, slid along that row by this much
    tangent = np.roll(O, -1, axis=1) - np.roll(O, 1, axis=1)
    tangent /= np.maximum(np.linalg.norm(tangent, axis=2, keepdims=True), 1e-12)
    slide = np.einsum("kni,kni->kn", O[1:] - O[:-1], tangent[:-1])
    below = None                  # the row below, as seen from this one, its holes narrowed by one row's step
    for j in range(K):
        row = f[j] if below is None else np.maximum(f[j], below)     # open wherever a hole below still reaches
        hole = row > 0
        if hole.any() and not hole.all():
            # where the row crosses into and out of each hole, along it (mm), and how far each point is from
            # the nearest such edge: measured the same way in every row, the cut between rows runs straight
            # from edge to edge
            s = along[j]
            nxt = np.roll(row, -1)
            i = np.nonzero(hole != np.roll(hole, -1))[0]
            at = s[i] + seg[j][i] * row[i] / (row[i] - nxt[i])
            at = np.sort(np.concatenate([at - L[j], at, at + L[j]]))
            k = np.clip(np.searchsorted(at, s), 1, len(at) - 1)
            edge = np.minimum(s - at[k - 1], at[k] - s)
            row = np.where(hole, edge, -edge)
            if below is not None:                 # just above a closing hole, the wall goes on from its edges
                row = np.where(hole, row, np.maximum(row, below))
            if bridge is not None:                # narrow enough to bridge: free to close above
                narrow = hole & (at[k] - at[k - 1] < bridge[j])
        elif not hole.any() and below is not None:
            row = below                           # a hole closes under this row: its top rises from its edges
        f[j] = row
        if j + 1 < K:
            step = slope * (z[j + 1] - z[j])
            carry = row
            if bridge is not None and hole.any() and not hole.all():
                carry = np.where(narrow, -4.0 * step, row)
            if (carry > -4.0 * step).any():
                # this row, read at the points under the next row's, narrowed by a step
                ext = np.concatenate([along[j] - L[j], along[j], along[j] + L[j]])
                val = np.concatenate([carry, carry, carry])
                q = np.mod(along[j] + slide[j], L[j])
                below = np.interp(q, ext, val) - step
            else:
                below = None
    return f


# ================================================================== rounded edges
def hole_distance(f, z, cap):
    """How far each grid point is from the nearest hole (mm), up to cap - straight-line distance. Every row a
    hole crosses holds, where it is wall, how far along the row the nearest hole's edge is (see
    ``pointed_tops``); from those, across the rows within reach."""
    hole = f > 0
    row = np.where(hole.any(axis=1)[:, None], np.where(hole, 0.0, -f), cap) ** 2
    best = row.copy()
    for o in range(1, len(z)):                               # rows o apart, while any is near enough to matter
        rise = (z[o:] - z[:-o])[:, None] ** 2
        if float(rise.min()) >= cap * cap:
            break
        np.minimum(best[o:], row[:-o] + rise, out=best[o:])
        np.minimum(best[:-o], row[o:] + rise, out=best[:-o])
    return np.minimum(np.sqrt(best), cap)


def swell(f, z, amount, far, slope):
    """How far the wall swells out - and in, the same - round the holes (mm, each side): from nothing at a
    hole's edge it curves up (a quarter wave) to ``amount``, so each edge is rounded from outside to in, and
    fades away again past ``far`` mm from the nearest hole. Going up, the swell may only grow by ``slope`` mm
    for each mm - where the wall over a hole would bulge out faster than it may lean, it bulges less."""
    hole = f > 0
    radius = 1.6 * amount + 0.6                              # the rounding of each edge
    fade = 3.0 * radius + 4.0
    d = hole_distance(f, z, far + fade + 1.0)
    rise = np.sin(0.5 * math.pi * np.clip(d / radius, 0.0, 1.0))
    t = np.clip((d - far) / fade, 0.0, 1.0)
    b = amount * rise * (1.0 - t * t * (3.0 - 2.0 * t))
    b[hole] = 0.0
    for j in range(1, len(z)):                               # printable: it grows upward no faster than slope
        np.minimum(b[j], b[j - 1] + slope * (z[j] - z[j - 1]), out=b[j])
    return b


# ================================================================== the pot
def insert_rows(z, arrays, zs):
    """The rows with more rows put in at heights zs, each part of ``arrays`` (K, ...) straight between its
    neighbours. Returns (z, arrays, the index of each new row)."""
    z = np.asarray(z, dtype=float)
    arrays = [np.asarray(a) for a in arrays]
    for zq in sorted(set(float(v) for v in zs)):
        j = int(np.searchsorted(z, zq))
        if j < len(z) and abs(z[j] - zq) < 1e-9:
            continue
        if j > 0 and abs(z[j - 1] - zq) < 1e-9:
            continue
        j = min(max(j, 1), len(z) - 1)
        u = (zq - z[j - 1]) / (z[j] - z[j - 1])
        z = np.insert(z, j, zq)
        arrays = [np.insert(a, j, a[j - 1] + u * (a[j] - a[j - 1]), axis=0) for a in arrays]
    index = {float(v): int(np.argmin(np.abs(z - float(v)))) for v in zs}
    return z, arrays, index


def pot(z, O, I, f, floor_row=None, roof_row=None, swell=None):
    """The hollow pot from rows at heights z (K,): the outer face O and inner face I (K, N, 2), and the hole
    field f (K, N), below nought in the wall.

    floor_row: the row at the top of a solid floor - the outer face alone below it, over a flat bottom - or
    None for a wall open at the bottom. roof_row: the row under a closed top's solid point - the inner face
    ends there in a small ceiling, and the outer face alone goes on up - or None for an open rim.
    swell (K, N): how far the wall swells out and in at each point, mm each side (see ``swell``); the holes'
    edges stay where the faces were, so each swell curves down to meet its hole's side.
    Returns (verts (V, 3), faces (F, 3), kind of each face).
    """
    K, N = f.shape
    # a hair's breadth inside a hole counts as wall: no slivers a few thousandths of a millimetre across
    f = np.asarray(f, dtype=float)
    f = np.where(f < 0.02, np.minimum(f, -0.02), f)
    kb = 0 if floor_row is None else int(floor_row)
    kr = K - 1 if roof_row is None else int(roof_row)
    if floor_row is not None:
        f[:kb + 1] = np.minimum(f[:kb + 1], -1e-9)          # solid below the floor's top
    if roof_row is not None:
        f[kr:] = np.minimum(f[kr:], -1e-9)                  # ... and above the ceiling
    hole = f > 0
    zz = np.broadcast_to(z[:, None, None], (K, N, 1))
    Ow, Iw = O, I                                       # the faces' own points, swollen
    if swell is not None:
        Ow = O + sections.normals(O) * swell[..., None]
        Iw = I - sections.normals(I) * swell[..., None]
    pts = [np.concatenate([Ow, zz], axis=2).reshape(-1, 3),
           np.concatenate([Iw, zz], axis=2)[kb:kr + 1].reshape(-1, 3)]
    vo = np.arange(K * N).reshape(K, N)
    vi = np.full((K, N), -1, dtype=np.int64)
    vi[kb:kr + 1] = K * N + np.arange((kr + 1 - kb) * N).reshape(kr + 1 - kb, N)
    count = K * N + (kr + 1 - kb) * N
    # where the hole edges cross the grid's sides: one vertex each, outside and in
    hx = hole != np.roll(hole, -1, axis=1)
    vx = hole[:-1] != hole[1:]
    hxo, hxi = np.full((K, N), -1, dtype=np.int64), np.full((K, N), -1, dtype=np.int64)
    vxo, vxi = np.full((K - 1, N), -1, dtype=np.int64), np.full((K - 1, N), -1, dtype=np.int64)
    fn = np.roll(f, -1, axis=1)
    j, i = np.nonzero(hx)
    if len(j):
        u = (f[j, i] / (f[j, i] - fn[j, i]))[:, None]
        i1 = (i + 1) % N
        for face, out in ((O, hxo), (I, hxi)):
            p = face[j, i] + (face[j, i1] - face[j, i]) * u
            pts.append(np.concatenate([p, z[j][:, None]], axis=1))
            out[j, i] = count + np.arange(len(j))
            count += len(j)
    j, i = np.nonzero(vx)
    if len(j):
        u = f[j, i] / (f[j, i] - f[j + 1, i])
        for face, out in ((O, vxo), (I, vxi)):
            p = face[j, i] + (face[j + 1, i] - face[j, i]) * u[:, None]
            pts.append(np.concatenate([p, (z[j] + (z[j + 1] - z[j]) * u)[:, None]], axis=1))
            out[j, i] = count + np.arange(len(j))
            count += len(j)
    verts = np.concatenate(pts)
    faces, kinds = [], []

    # whole cells of wall: two triangles each, split along the shorter diagonal
    full = ~(hole[:-1] | hole[1:] | np.roll(hole, -1, axis=1)[:-1] | np.roll(hole, -1, axis=1)[1:])
    for face_v, kind, lo, hi in ((vo, OUTER, 0, K), (vi, INNER, kb, kr)):
        cells = full.copy()
        cells[:lo] = False
        cells[hi:] = False
        cj, ci = np.nonzero(cells)
        ci1 = (ci + 1) % N
        a, b, c, d = face_v[cj, ci], face_v[cj, ci1], face_v[cj + 1, ci1], face_v[cj + 1, ci]
        along = (np.linalg.norm(verts[a] - verts[c], axis=1) <= np.linalg.norm(verts[b] - verts[d], axis=1))[:, None]
        t1 = np.where(along, np.stack([a, b, c], 1), np.stack([a, b, d], 1))
        t2 = np.where(along, np.stack([a, c, d], 1), np.stack([b, c, d], 1))
        tris = np.concatenate([t1, t2])
        if kind == INNER:
            tris = tris[:, ::-1]
        faces.append(tris)
        kinds.append(np.full(len(tris), kind))

    # cells a hole's edge crosses: the wall's part of each, and the hole's side
    extra, extra_kind = [], []
    mixed_j, mixed_i = np.nonzero(~full & ~(hole[:-1] & hole[1:] & np.roll(hole, -1, axis=1)[:-1]
                                            & np.roll(hole, -1, axis=1)[1:]))
    for j, i in zip(mixed_j.tolist(), mixed_i.tolist()):
        i1 = (i + 1) % N
        corners = ((j, i), (j, i1), (j + 1, i1), (j + 1, i))
        sides = (("h", j, i), ("v", j, i1), ("h", j + 1, i), ("v", j, i))
        ring = []                        # (outer vertex, inner vertex, on a hole's edge)
        for (cj, ck), (kind_s, sj, si) in zip(corners, sides):
            if not hole[cj, ck]:
                ring.append((vo[cj, ck], vi[cj, ck], False))
            xo = (hxo if kind_s == "h" else vxo)[sj, si]
            if xo >= 0:
                xi = (hxi if kind_s == "h" else vxi)[sj, si]
                ring.append((xo, xi, True))
        if len(ring) < 3:
            continue
        for k in range(1, len(ring) - 1):
            extra.append((ring[0][0], ring[k][0], ring[k + 1][0]))
            extra_kind.append(OUTER)
            if j >= kb:
                extra.append((ring[k + 1][1], ring[k][1], ring[0][1]))
                extra_kind.append(INNER)
        if j < kb:
            continue
        for k in range(len(ring)):
            a, b = ring[k], ring[(k + 1) % len(ring)]
            if a[2] and b[2]:            # along a hole's edge: the hole's side, outside face to inside
                extra.append((b[0], a[0], a[1]))
                extra.append((b[0], a[1], b[1]))
                extra_kind += [SIDE, SIDE]
    if extra:
        faces.append(np.array(extra, dtype=np.int64))
        kinds.append(np.array(extra_kind))

    # the ends: the rim at the top; a flat bottom and the floor, or the wall's open bottom end
    def ends(j, up):
        tris = []
        for i in range(N):
            i1 = (i + 1) % N
            a_in, b_in = not hole[j, i], not hole[j, i1]
            if a_in and b_in:
                q = (vo[j, i], vo[j, i1], vi[j, i1], vi[j, i])
            elif a_in:
                q = (vo[j, i], hxo[j, i], hxi[j, i], vi[j, i])
            elif b_in:
                q = (hxo[j, i], vo[j, i1], vi[j, i1], hxi[j, i])
            else:
                continue
            tris += [(q[0], q[1], q[2]), (q[0], q[2], q[3])]
        tris = np.array(tris, dtype=np.int64).reshape(-1, 3)
        return tris if up else tris[:, ::-1]

    if roof_row is None:
        caps = [ends(K - 1, True)]
    else:                                                   # the closed top's point, and the ceiling under it
        caps = [vo[K - 1][sections.triangulate(Ow[K - 1])], vi[kr][sections.triangulate(Iw[kr])][:, ::-1]]
    if floor_row is None:
        caps.append(ends(0, False))
    else:
        caps.append(vo[0][sections.triangulate(Ow[0])][:, ::-1])
        caps.append(vi[kb][sections.triangulate(Iw[kb])])
    caps = np.concatenate(caps)
    faces.append(caps)
    kinds.append(np.full(len(caps), CAP))
    faces = np.concatenate(faces)
    kinds = np.concatenate(kinds)
    # keep only the vertices used
    used = np.zeros(len(verts), dtype=bool)
    used[faces.ravel()] = True
    remap = np.cumsum(used) - 1
    return verts[used], remap[faces], kinds


def bridge_span(ring, samples: int = 48) -> float:
    """How far a flat ceiling over a loop (n, 2) has to bridge: across the widest circle that fits inside it."""
    P = np.asarray(ring, dtype=float)
    lo, hi = P.min(axis=0), P.max(axis=0)
    gx, gy = np.meshgrid(np.linspace(lo[0], hi[0], samples), np.linspace(lo[1], hi[1], samples))
    g = np.stack([gx.ravel(), gy.ravel()], 1)
    A, B = P, np.roll(P, -1, axis=0)
    # inside: an odd number of sides crossed on the way out to the right
    ya, yb = A[None, :, 1], B[None, :, 1]
    up = (ya <= g[:, None, 1]) != (yb <= g[:, None, 1])
    with np.errstate(divide="ignore", invalid="ignore"):
        x = A[None, :, 0] + (g[:, None, 1] - ya) * (B[None, :, 0] - A[None, :, 0]) / (yb - ya)
    inside = (up & (x > g[:, None, 0])).sum(axis=1) % 2 == 1
    if not inside.any():
        return 0.0
    g = g[inside]
    ab = B - A
    t = np.clip(np.einsum("gnk,nk->gn", g[:, None, :] - A[None], ab) / np.maximum((ab * ab).sum(1), 1e-12), 0, 1)
    d = np.linalg.norm(g[:, None, :] - (A[None] + t[..., None] * ab[None]), axis=2).min(axis=1)
    return 2.0 * float(d.max())


def bridges(verts, faces, kinds, limit: float, longest: float = 8.0):
    """The short bridges at the very tops of holes, marked TIP: where a hole's point closes between two grid
    points, its last bit of roof is flat for a few millimetres - a gap any printer bridges.

    Steep downward faces of the holes' sides that touch are taken together; a group that spans less than
    ``longest`` mm along the wall is such a bridge. Returns (kinds, the widest bridge in mm, and the steepest
    lean of any hole's side apart from them).
    """
    kinds = kinds.copy()
    side = np.nonzero(kinds == SIDE)[0]
    if not len(side):
        return kinds, 0.0, 0.0
    tri = verts[faces[side]]
    n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
    over = np.degrees(np.arcsin(np.clip(-n[:, 2], 0.0, 1.0)))       # leaning out over the hole below
    steep = np.nonzero(over > limit + 0.25)[0]
    widest = 0.0
    if len(steep):
        # group the steep faces that share a corner
        parent = list(range(len(steep)))

        def find(a):
            while parent[a] != a:
                parent[a] = parent[parent[a]]
                a = parent[a]
            return a

        seen = {}
        for k, face in enumerate(faces[side[steep]].tolist()):
            for v in face:
                if v in seen:
                    ra, rb = find(k), find(seen[v])
                    if ra != rb:
                        parent[ra] = rb
                else:
                    seen[v] = k
        groups = {}
        for k in range(len(steep)):
            groups.setdefault(find(k), []).append(k)
        for members in groups.values():
            pts = tri[steep[members]].reshape(-1, 3)
            out = pts[:, :2].mean(axis=0)
            along = np.array([-out[1], out[0]]) / max(float(np.hypot(*out)), 1e-9)   # round the wall, here
            span = float(np.ptp(pts[:, :2] @ along))
            if span < longest:
                kinds[side[steep[members]]] = TIP
                widest = max(widest, span)
        over[np.isin(np.arange(len(side)), steep[[kinds[side[s]] == TIP for s in steep]])] = 0.0
    return kinds, widest, float(over.max())
