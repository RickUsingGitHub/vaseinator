"""The vase as a normal print makes it: a hollow pot, with holes cut right through its wall if you like.

The pot is built from rows of points round the vase - the outer face's and the
inner face's, at the same heights - on the grid the vase's surface is made on.
A hole pattern is a number at each grid point: how far inside a hole it is, in
mm, below nought in the wall. The wall is cut where that number is nought
(marching squares), the same on both faces, and a side face joins them round
each hole. Every cut is one vertex shared by the faces on either side of it,
so the pot stays closed and watertight.

Holes print without supports: going up the wall a hole may only close in as
fast as the overhang limit allows, so each one ends in a pointed top.
"""

from __future__ import annotations

import math

import numpy as np

from . import sections
from .params import DIAMOND, NO_HOLES, ROUND, SLOTS, VORONOI

OUTER, INNER, SIDE, CAP, TIP = 0, 1, 2, 3, 4   # what each face of the pot is: TIP is the short bridge at the
                                               # very top of a hole, where it closes between two grid points


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
        pitch = size * math.sqrt(3.0) / 2.0
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


def hole_field(kind, t, z, L, size, strut, jitter, seed, z_lo, z_hi):
    """How far inside a hole each grid point is, in mm (below nought in the wall).

    t (K, N): the share of the way round of each grid point, 0..1 (turning with the shape when it twists);
    z (K,): the rows' heights; L (K,): their lengths round. Holes keep between z_lo and z_hi.
    """
    K, N = t.shape
    f = np.full((K, N), -1.0)
    if kind == NO_HOLES or z_hi - z_lo < 0.5 * size:
        return f
    band = (z >= z_lo - size) & (z <= z_hi + size)
    rows_in = np.nonzero(band)[0]
    if not len(rows_in):
        return f
    n_round = max(int(round(float(np.mean(L[band])) / size)), 3)
    pitch, zs, n_round = _lattice(kind, size, strut, z_lo, z_hi, n_round)
    if not len(zs):
        return f
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
        edge = 0.5 * (best[..., 1] - best[..., 0])          # how far in from the cell's edge
        fr = np.where(best_hole, edge - 0.5 * strut, -edge - 0.5 * strut)
    elif kind == ROUND:
        sx = LL / n_round
        near = np.minimum(sx, np.hypot(0.5 * sx, pitch))     # the nearest neighbour's distance, this row
        fr = 0.5 * (near - strut) - best[..., 0]
    else:
        fr = -best[..., 0]
    fr = np.where(np.isfinite(fr), fr, -1.0)
    # never into the foot or the rim
    fr = np.minimum(fr, np.minimum(zz - z_lo, z_hi - zz))
    f[rows_in] = fr
    return f


def pointed_tops(f, z, O, slope):
    """Every hole closes at its top no faster than ``slope`` (mm in, each side, for each mm up).

    Going up row by row, the wall over a hole may only reach in that far past the wall below it - measured
    from the point really below, so on a twisting vase, whose grid leans round with the shape, the holes'
    sides lean no further than their tops. Where a hole would close faster it is kept open, so its top comes
    to a point instead of a flat roof that would need support.
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
        elif not hole.any() and below is not None:
            row = below                           # a hole closes under this row: its top rises from its edges
        f[j] = row
        if j + 1 < K:
            step = slope * (z[j + 1] - z[j])
            if (row > -4.0 * step).any():
                # this row, read at the points under the next row's, narrowed by a step
                ext = np.concatenate([along[j] - L[j], along[j], along[j] + L[j]])
                val = np.concatenate([row, row, row])
                q = np.mod(along[j] + slide[j], L[j])
                below = np.interp(q, ext, val) - step
            else:
                below = None
    return f


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


def pot(z, O, I, f, floor_row=None):
    """The hollow pot from rows at heights z (K,): the outer face O and inner face I (K, N, 2), and the hole
    field f (K, N), below nought in the wall.

    floor_row: the row at the top of a solid floor - the outer face alone below it, over a flat bottom - or
    None for a wall open at the bottom. The top is always the wall's open rim.
    Returns (verts (V, 3), faces (F, 3), kind of each face).
    """
    K, N = f.shape
    # a hair's breadth inside a hole counts as wall: no slivers a few thousandths of a millimetre across
    f = np.asarray(f, dtype=float)
    f = np.where(f < 0.02, np.minimum(f, -0.02), f)
    kb = 0 if floor_row is None else int(floor_row)
    if floor_row is not None:
        f[:kb + 1] = np.minimum(f[:kb + 1], -1e-9)          # solid below the floor's top
    hole = f > 0
    zz = np.broadcast_to(z[:, None, None], (K, N, 1))
    pts = [np.concatenate([O, zz], axis=2).reshape(-1, 3), np.concatenate([I, zz], axis=2)[kb:].reshape(-1, 3)]
    vo = np.arange(K * N).reshape(K, N)
    vi = np.full((K, N), -1, dtype=np.int64)
    vi[kb:] = K * N + np.arange((K - kb) * N).reshape(K - kb, N)
    count = K * N + (K - kb) * N
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
    for face_v, kind, lo in ((vo, OUTER, 0), (vi, INNER, kb)):
        cells = full.copy()
        cells[:lo] = False
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

    caps = [ends(K - 1, True)]
    if floor_row is None:
        caps.append(ends(0, False))
    else:
        caps.append(vo[0][sections.triangulate(O[0])][:, ::-1])
        caps.append(vi[kb][sections.triangulate(I[kb])])
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
