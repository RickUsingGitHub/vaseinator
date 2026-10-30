"""Drawn cross-sections: any closed outline, not only one radius in each direction.

A drawn outline is a loop of control points, each smooth (the curve runs
through it in a spline) or a cusp (a sharp corner).  It can be repeated round
the axis - draw one lobe, get five.  The vase is then built from the outline
itself, point by point, so lobes may bulge out past their own necks and a
shape need not surround the axis at all.

Everything here works on plain numpy arrays of (x, y) points in the drawing's
own units: the axis of the vase is the origin, and the widest point is scaled
to radius 1 before use.
"""

from __future__ import annotations

import math

import numpy as np

TAU = 2.0 * math.pi


# ===================================================================== curves
def chain(points, repeat: int = 1):
    """The full loop of control points: the drawn chain, repeated round the axis.

    points: [[x, y, cusp], ...].  Returns (xy (n, 2), cusp flags (n,)).
    """
    pts = np.asarray([p[:2] for p in points], dtype=float)
    cusp = np.asarray([bool(p[2]) if len(p) > 2 else False for p in points])
    n = max(int(repeat), 1)
    if n == 1:
        return pts, cusp
    loops = []
    for k in range(n):
        a = TAU * k / n
        c, s = math.cos(a), math.sin(a)
        loops.append(pts @ np.array([[c, s], [-s, c]]))
    return np.concatenate(loops), np.tile(cusp, n)


def spline(points, repeat: int = 1, per: int = 48) -> np.ndarray:
    """The outline through the control points, as a dense closed polyline (k, 2).

    Smooth points get a tangent along the line from the point before to the
    point after, as long as each neighbouring side (so uneven spacing never
    loops); at a cusp each side leaves straight towards its neighbour.
    """
    P, cusp = chain(points, repeat)
    n = len(P)
    if n < 3:
        raise ValueError("an outline needs at least three points")
    prev, nxt = np.roll(P, 1, axis=0), np.roll(P, -1, axis=0)
    back = np.linalg.norm(P - prev, axis=1)               # length of the side coming in
    ahead = np.linalg.norm(nxt - P, axis=1)               # ... and going out
    d = nxt - prev
    d /= np.maximum(np.linalg.norm(d, axis=1, keepdims=True), 1e-12)
    t_out = d * ahead[:, None]
    t_in = d * back[:, None]
    unit_ahead = (nxt - P) / np.maximum(ahead[:, None], 1e-12)
    unit_back = (P - prev) / np.maximum(back[:, None], 1e-12)
    t_out[cusp] = unit_ahead[cusp] * ahead[cusp, None] * 0.35
    t_in[cusp] = unit_back[cusp] * back[cusp, None] * 0.35
    t = np.linspace(0.0, 1.0, per, endpoint=False)[:, None]
    h00, h10 = 2 * t ** 3 - 3 * t ** 2 + 1, t ** 3 - 2 * t ** 2 + t
    h01, h11 = -2 * t ** 3 + 3 * t ** 2, t ** 3 - t ** 2
    out = []
    for i in range(n):
        j = (i + 1) % n
        out.append(h00 * P[i] + h10 * t_out[i] + h01 * P[j] + h11 * t_in[j])
    return np.concatenate(out)


def area(poly) -> float:
    """Signed area: positive when the loop runs anticlockwise."""
    x, y = poly[:, 0], poly[:, 1]
    return 0.5 * float(np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y))


def normalised(poly) -> np.ndarray:
    """The loop anticlockwise, its widest point at radius 1 from the axis."""
    poly = np.asarray(poly, dtype=float)
    if area(poly) < 0:
        poly = poly[::-1]
    r = np.hypot(poly[:, 0], poly[:, 1]).max()
    return poly / max(r, 1e-9)


def resample(poly, n: int) -> np.ndarray:
    """n points evenly spaced along the loop, starting where it crosses the +x axis furthest out.

    Starting every outline at the same place lets two of them be blended point
    for point when one turns into the other.
    """
    poly = np.asarray(poly, dtype=float)
    nxt = np.roll(poly, -1, axis=0)
    seg = np.linalg.norm(nxt - poly, axis=1)
    cum = np.concatenate([[0.0], np.cumsum(seg)])
    total = cum[-1]
    # where the loop crosses the +x axis: the crossing furthest out is the start
    y0, y1 = poly[:, 1], nxt[:, 1]
    cross = (y0 <= 0) & (y1 > 0) | (y0 >= 0) & (y1 < 0)
    t = np.where(cross, -y0 / np.where(y1 == y0, 1.0, y1 - y0), 0.0)
    x = poly[:, 0] + (nxt[:, 0] - poly[:, 0]) * t
    ok = cross & (x > 0)
    if ok.any():
        i = int(np.argmax(np.where(ok, x, -np.inf)))
        start = cum[i] + seg[i] * t[i]
    else:
        start = cum[int(np.argmax(poly[:, 0]))]
    s = np.mod(start + np.arange(n) * (total / n), total)
    k = np.clip(np.searchsorted(cum, s, side="right") - 1, 0, len(poly) - 1)
    f = (s - cum[k]) / np.maximum(seg[k], 1e-12)
    return poly[k] + (nxt[k] - poly[k]) * f[:, None]


def from_table(table, samples: int = 2048) -> np.ndarray:
    """A built-in cross-section (radius at even angles) as a loop of points."""
    a = np.arange(len(table)) * (TAU / len(table))
    idx = np.linspace(0, len(table), samples, endpoint=False).astype(int)
    return np.stack([table[idx] * np.cos(a[idx]), table[idx] * np.sin(a[idx])], 1)


def control_points_from_table(table, count: int = 16):
    """A built-in cross-section as editable control points: [[x, y, cusp], ...]."""
    poly = resample(from_table(table), max(count * 8, 64))
    keep = simplify(poly, 0.012, closed=True)
    pts = poly[keep]
    return [[round(float(x), 4), round(float(y), 4), bool(c)] for (x, y), c in zip(pts, sharp_corners(pts))]


def motif_from_table(table, repeat: int):
    """One period of a built-in cross-section as a chain of control points, for Repeat around ``repeat``.

    A five-petalled flower becomes one petal to edit, repeated five times.
    """
    n = max(int(repeat), 1)
    if n == 1:
        return control_points_from_table(table)
    K = 480
    ang = np.linspace(-math.pi / n, math.pi / n, K, endpoint=False)
    r = table[(np.mod(ang, TAU) * len(table) / TAU).astype(int) % len(table)]
    P = np.stack([r * np.cos(ang), r * np.sin(ang)], 1)
    keep = simplify(P, 0.01, closed=False)
    pts = P[keep]
    a = TAU / n                                           # the next copy's first point: don't double it
    first_next = pts[0] @ np.array([[math.cos(a), math.sin(a)], [-math.sin(a), math.cos(a)]])
    if len(pts) > 3 and np.linalg.norm(pts[-1] - first_next) < 0.03:
        pts = pts[:-1]
    sharp = sharp_corners(pts)
    sharp[0] = sharp[-1] = False
    return [[round(float(x), 4), round(float(y), 4), bool(c)] for (x, y), c in zip(pts, sharp)]


def respace(points, old: int, new: int):
    """A chain drawn to repeat ``old`` times round the axis, narrowed or widened to repeat ``new`` times.

    Each point keeps its distance from the axis and its angle is scaled about
    the middle of the chain's share of the circle, so one lobe stays one lobe:
    five wide lobes become a hundred thin ones, as deep as before.
    """
    old, new = max(int(old), 1), max(int(new), 1)
    if old == new or len(points) < 2:
        return [list(q) for q in points]
    P = np.asarray([q[:2] for q in points], dtype=float)
    r = np.hypot(P[:, 0], P[:, 1])
    a = np.unwrap(np.arctan2(P[:, 1], P[:, 0]))
    mid = a[0] + math.pi / old                           # the middle of its share, first point to next copy's
    b = mid + (a - mid) * old / new
    return [[round(float(rr * math.cos(t)), 6), round(float(rr * math.sin(t)), 6), bool(q[2])]
            for rr, t, q in zip(r, b, points)]


def bulbs(n: int, neck: float = 0.42, bulb: float = 0.3):
    """One petal of a flower whose round petals bulge out past their necks - no radius map can make it."""
    a = math.pi / n
    cx = 1.0 - bulb
    chain = [[neck * math.cos(-0.72 * a), neck * math.sin(-0.72 * a), True]]
    for t in (-115, -65, 0, 65, 115):
        chain.append([cx + bulb * math.cos(math.radians(t)), bulb * math.sin(math.radians(t)), False])
    chain.append([neck * math.cos(0.72 * a), neck * math.sin(0.72 * a), True])
    return [[round(x, 4), round(y, 4), c] for x, y, c in chain]


# a claw, traced from a sketch
CLAW = [
    [-0.424, 0.594, 1], [-0.437, 0.500, 0], [-0.428, 0.258, 0], [-0.351, 0.017, 0], [-0.239, -0.175, 0],
    [-0.152, -0.296, 0], [0.041, -0.496, 0], [0.227, -0.631, 0], [0.414, -0.738, 0], [0.488, -0.757, 1],
    [0.348, -0.626, 0], [0.257, -0.499, 0], [0.233, -0.417, 0], [0.237, -0.280, 0], [0.288, -0.148, 0],
    [0.387, -0.034, 0], [0.608, 0.032, 1], [0.074, 0.331, 0], [-0.344, 0.536, 0]]

# starting outlines for the cross-section editor: (name, control points, repeat around)
OUTLINES = [
    ("Circle", [[round(math.cos(a), 4), round(math.sin(a), 4), False]
                for a in np.linspace(0, TAU, 8, endpoint=False)], 1),
    ("Five lobes", [[0.42, -0.12, True], [0.62, -0.38, False], [0.95, -0.22, False], [0.95, 0.22, False],
                    [0.62, 0.38, False], [0.42, 0.12, True]], 5),
    ("Three bulbs", bulbs(3), 3),
    ("Six bulbs", bulbs(6, 0.5, 0.24), 6),
    ("Claw", [[x, y, bool(c)] for x, y, c in CLAW], 1),
    ("Teardrop", [[1.0, 0.0, True], [0.2, 0.55, False], [-0.6, 0.45, False], [-0.85, 0.0, False],
                  [-0.6, -0.45, False], [0.2, -0.55, False]], 1),
    ("Heart", [[0.0, -0.9, True], [0.75, 0.0, False], [0.7, 0.6, False], [0.35, 0.75, False], [0.0, 0.45, True],
               [-0.35, 0.75, False], [-0.7, 0.6, False], [-0.75, 0.0, False]], 1),
]


# ================================================================== checking
def crossings(poly, limit: int = 4000) -> list:
    """Where a loop crosses itself: a list of (x, y), empty for a simple loop."""
    poly = np.asarray(poly, dtype=float)
    if len(poly) > limit:                                   # a coarser look is enough to find a crossing
        poly = poly[np.linspace(0, len(poly), limit, endpoint=False).astype(int)]
    a, b = poly, np.roll(poly, -1, axis=0)
    n = len(a)
    found = []
    lo, hi = np.minimum(a, b), np.maximum(a, b)
    for i in range(n - 2):
        j = np.arange(i + 2, n if i > 0 else n - 1)
        if not len(j):
            continue
        near = ((lo[j, 0] <= hi[i, 0]) & (hi[j, 0] >= lo[i, 0]) & (lo[j, 1] <= hi[i, 1]) & (hi[j, 1] >= lo[i, 1]))
        j = j[near]
        if not len(j):
            continue
        p, r = a[i], b[i] - a[i]
        q, s = a[j], b[j] - a[j]
        den = r[0] * s[:, 1] - r[1] * s[:, 0]
        qp = q - p
        with np.errstate(divide="ignore", invalid="ignore"):
            t = (qp[:, 0] * s[:, 1] - qp[:, 1] * s[:, 0]) / den
            u = (qp[:, 0] * r[1] - qp[:, 1] * r[0]) / den
        # a crossing exactly at a point counts once: at the start of the sides that leave it
        hit = (np.abs(den) > 1e-12) & (t >= 0) & (t < 1) & (u >= 0) & (u < 1)
        for k in np.nonzero(hit)[0]:
            found.append(tuple(p + r * t[k]))
        if len(found) > 20:
            break
    return found


def piece_crossings(loop, piece: int) -> list:
    """Where a repeated outline crosses itself, looking only at the drawn piece: its first ``piece`` sides.

    Every copy is the same piece turned, so any crossing has a twin on the
    drawn one - and only sides near it can cross it. Quick even for a hundred
    copies, and exact: nothing is thinned out.
    """
    loop = np.asarray(loop, dtype=float)
    n = len(loop)
    m = min(max(int(piece), 1), n)
    a, b = loop, np.roll(loop, -1, axis=0)
    lo, hi = np.minimum(a, b), np.maximum(a, b)
    box_lo, box_hi = lo[:m].min(0), hi[:m].max(0)
    near = np.nonzero((lo[:, 0] <= box_hi[0]) & (hi[:, 0] >= box_lo[0])
                      & (lo[:, 1] <= box_hi[1]) & (hi[:, 1] >= box_lo[1]))[0]
    found = []
    for i in range(m):
        # not the side itself or its neighbours, and each pair of the piece's own sides once
        j = near[(near != i) & (near != (i + 1) % n) & (near != (i - 1) % n) & ((near >= m) | (near > i))]
        j = j[(lo[j, 0] <= hi[i, 0]) & (hi[j, 0] >= lo[i, 0]) & (lo[j, 1] <= hi[i, 1]) & (hi[j, 1] >= lo[i, 1])]
        if not len(j):
            continue
        p, r = a[i], b[i] - a[i]
        q, s = a[j], b[j] - a[j]
        den = r[0] * s[:, 1] - r[1] * s[:, 0]
        qp = q - p
        with np.errstate(divide="ignore", invalid="ignore"):
            t = (qp[:, 0] * s[:, 1] - qp[:, 1] * s[:, 0]) / den
            u = (qp[:, 0] * r[1] - qp[:, 1] * r[0]) / den
        hit = (np.abs(den) > 1e-12) & (t >= 0) & (t < 1) & (u >= 0) & (u < 1)
        for k in np.nonzero(hit)[0]:
            found.append(tuple(p + r * t[k]))
        if len(found) > 20:
            break
    return found


# =============================================================== making solid
def triangulate(poly) -> np.ndarray:
    """Triangles filling a simple anticlockwise loop, as indices into it (ear clipping).

    The loop is a linked list and its inward (reflex) corners sit in a grid, so
    each ear is checked only against the corners near it: thousands of points
    take a moment. A loop that is not quite simple (a wall moved in past a sharp
    tip folds over a little) still gets one triangle per point but two, every
    side used once: where no ear is clear, the one with the fewest corners
    inside it is cut.
    """
    P = np.asarray(poly, dtype=float)
    n = len(P)
    if n < 3:
        return np.zeros((0, 3), dtype=np.int64)
    xs, ys = P[:, 0].tolist(), P[:, 1].tolist()
    prv = [n - 1] + list(range(n - 1))
    nxt = list(range(1, n)) + [0]

    def turn(i):
        a, c = prv[i], nxt[i]
        return (xs[i] - xs[a]) * (ys[c] - ys[i]) - (ys[i] - ys[a]) * (xs[c] - xs[i])

    x0, y0 = min(xs), min(ys)
    size = max(max(xs) - x0, max(ys) - y0, 1e-12)
    h = size / max(math.sqrt(n), 1.0)                    # about one corner per cell
    grid = {}

    def cell(i):
        return int((xs[i] - x0) / h), int((ys[i] - y0) / h)

    reflex = set()
    for i in range(n):
        if turn(i) <= 1e-14:
            reflex.add(i)
            grid.setdefault(cell(i), set()).add(i)

    def inside_count(i, stop_at_one):
        """Reflex corners in the triangle cut off at corner i (on its sides counts as in)."""
        a, c = prv[i], nxt[i]
        ax, ay, bx, by, cx, cy = xs[a], ys[a], xs[i], ys[i], xs[c], ys[c]
        lo_x, hi_x = min(ax, bx, cx), max(ax, bx, cx)
        lo_y, hi_y = min(ay, by, cy), max(ay, by, cy)
        i0, i1 = int((lo_x - x0) / h), int((hi_x - x0) / h)
        j0, j1 = int((lo_y - y0) / h), int((hi_y - y0) / h)
        if (i1 - i0 + 1) * (j1 - j0 + 1) > len(reflex):
            near = reflex
        else:
            near = [q for gi in range(i0, i1 + 1) for gj in range(j0, j1 + 1) for q in grid.get((gi, gj), ())]
        count = 0
        for q in near:
            if q == a or q == c or q == i:
                continue
            qx, qy = xs[q], ys[q]
            if qx < lo_x or qx > hi_x or qy < lo_y or qy > hi_y:
                continue
            if ((bx - ax) * (qy - ay) - (by - ay) * (qx - ax) >= 0 and (cx - bx) * (qy - by) - (cy - by) * (qx - bx) >= 0
                    and (ax - cx) * (qy - cy) - (ay - cy) * (qx - cx) >= 0):
                count += 1
                if stop_at_one:
                    break
        return count

    tris = []
    left = n
    i, tried = 0, 0
    while left > 3:
        if i not in reflex and inside_count(i, True) == 0:
            cut = i
        elif tried < left:
            i, tried = nxt[i], tried + 1
            continue
        else:                                              # no ear is clear: the one hiding fewest corners
            cut, fewest, j = None, None, i
            for _ in range(left):
                if turn(j) > 1e-14:
                    k = inside_count(j, False)
                    if fewest is None or k < fewest:
                        cut, fewest = j, k
                j = nxt[j]
            if cut is None:                                # no corner turns the right way: fan the rest
                j = nxt[i]
                while nxt[j] != i:
                    tris.append((i, j, nxt[j]))
                    j = nxt[j]
                left = 0
                break
        a, c = prv[cut], nxt[cut]
        tris.append((a, cut, c))
        nxt[a], prv[c] = c, a
        left -= 1
        for v in (a, c):                                   # a neighbour may have turned convex
            if v in reflex and turn(v) > 1e-14:
                reflex.discard(v)
                grid[cell(v)].discard(v)
        i, tried = a, 0
    if left == 3:
        tris.append((prv[i], i, nxt[i]))
    return np.array(tris, dtype=np.int64)


def inset(poly, d: float) -> np.ndarray:
    """A loop moved in by d square to its sides (mitred, with a limit at sharp inner corners)."""
    P = np.asarray(poly, dtype=float)
    e = np.roll(P, -1, axis=0) - P
    en = np.stack([e[:, 1], -e[:, 0]], 1)                  # outward normal of each side (anticlockwise loop)
    en /= np.maximum(np.linalg.norm(en, axis=1, keepdims=True), 1e-12)
    prev = np.roll(en, 1, axis=0)
    vn = en + prev
    vn /= np.maximum(np.linalg.norm(vn, axis=1, keepdims=True), 1e-12)
    stretch = 1.0 / np.maximum(np.einsum("ij,ij->i", vn, en), 0.4)
    return P - vn * (d * stretch)[:, None]


def normals(P) -> np.ndarray:
    """Outward unit normals at each point of anticlockwise loops (..., n, 2)."""
    t = np.roll(P, -1, axis=-2) - np.roll(P, 1, axis=-2)
    n = np.stack([t[..., 1], -t[..., 0]], -1)
    return n / np.maximum(np.linalg.norm(n, axis=-1, keepdims=True), 1e-12)


# ================================================================ simplifying
def simplify(poly, tol: float, closed: bool = True) -> np.ndarray:
    """Indices of the points Douglas-Peucker keeps, for a tolerance in the loop's units."""
    P = np.asarray(poly, dtype=float)
    n = len(P)
    if closed:                                             # split the loop at its two furthest points
        far = int(np.argmax(np.linalg.norm(P - P[0], axis=1)))
        first = _dp(P, 0, far, tol)
        second = _dp(np.concatenate([P, P[:1]]), far, n, tol)
        keep = sorted(set(first) | {k % n for k in second})
        return np.array(keep)
    return np.array(sorted(_dp(P, 0, n - 1, tol)))


def _dp(P, i, j, tol):
    keep = {i, j}
    stack = [(i, j)]
    while stack:
        a, b = stack.pop()
        if b - a < 2:
            continue
        seg = P[b] - P[a]
        L = np.linalg.norm(seg)
        mid = P[a + 1:b]
        if L < 1e-12:
            dist = np.linalg.norm(mid - P[a], axis=1)
        else:
            dist = np.abs(seg[0] * (mid[:, 1] - P[a][1]) - seg[1] * (mid[:, 0] - P[a][0])) / L
        k = int(np.argmax(dist))
        if dist[k] > tol:
            m = a + 1 + k
            keep.add(m)
            stack += [(a, m), (m, b)]
    return keep


def sharp_corners(pts, degrees: float = 50.0) -> np.ndarray:
    """Which points of a loop turn sharply enough to be cusps."""
    P = np.asarray(pts, dtype=float)
    a = P - np.roll(P, 1, axis=0)
    b = np.roll(P, -1, axis=0) - P
    cosang = np.einsum("ij,ij->i", a, b) / np.maximum(np.linalg.norm(a, axis=1) * np.linalg.norm(b, axis=1), 1e-12)
    return cosang < math.cos(math.radians(degrees))


# ===================================================================== tracing
def trace_mask(inside: np.ndarray, detail: float = 0.012):
    """Control points tracing the biggest filled region of a mask (rows down the picture).

    Returns [[x, y, cusp], ...] centred on the region's middle, widest point at
    radius 0.9, y up.
    """
    mask = _largest(inside)
    if mask.sum() < 20:
        raise ValueError("there is no closed shape in the picture")
    edge = _boundary(mask)
    P = edge.astype(float)
    P[:, 1] = -P[:, 1]                                     # rows run down; y runs up
    # smooth the pixel steps away, then keep the points that matter
    k = 3
    P = np.stack([np.convolve(np.concatenate([P[-k:, c], P[:, c], P[:k, c]]), np.ones(2 * k + 1) / (2 * k + 1),
                              mode="valid") for c in (0, 1)], 1)
    if area(P) < 0:
        P = P[::-1]
    cx, cy = _centroid(P)
    P -= (cx, cy)
    P /= np.hypot(P[:, 0], P[:, 1]).max() / 0.9
    keep = simplify(P, detail, closed=True)
    pts = P[keep]
    return [[round(float(x), 4), round(float(y), 4), bool(c)] for (x, y), c in zip(pts, sharp_corners(pts))]


def trace_picture(path: str, size: int = 360):
    """Control points tracing the outline drawn in a picture: dark lines on a light or clear ground."""
    from PySide6.QtGui import QImage

    img = QImage(path)
    if img.isNull():
        raise ValueError("the picture can't be read")
    img = img.convertToFormat(QImage.Format_RGBA8888)
    w, h = img.width(), img.height()
    arr = np.frombuffer(img.constBits(), dtype=np.uint8, count=img.sizeInBytes())
    return trace_rgba(arr.reshape(h, img.bytesPerLine())[:, :w * 4].reshape(h, w, 4), size)


def trace_rgba(pixels, size: int = 360):
    """Control points tracing the outline drawn in a picture's pixels (rows, columns, RGBA 0..255)."""
    arr = np.asarray(pixels).astype(float)
    h, w = arr.shape[:2]
    lum = 0.299 * arr[..., 0] + 0.587 * arr[..., 1] + 0.114 * arr[..., 2]
    ink = (arr[..., 3] > 100) & (lum < 120)
    block = max(1, math.ceil(max(w, h) / size))            # shrink, keeping any ink in a block
    H, W = math.ceil(h / block), math.ceil(w / block)
    pad = np.zeros((H * block, W * block), dtype=bool)
    pad[:h, :w] = ink
    ink = pad.reshape(H, block, W, block).any(axis=(1, 3))
    ink = _dilate(ink)                                      # close small gaps in the line
    outside = _flood(~ink)
    return trace_mask(~outside)


def _dilate(m):
    out = m.copy()
    out[1:] |= m[:-1]
    out[:-1] |= m[1:]
    out[:, 1:] |= m[:, :-1]
    out[:, :-1] |= m[:, 1:]
    return out


def _flood(free):
    """Free cells reachable from the edge of the picture."""
    reach = np.zeros_like(free)
    reach[0, :], reach[-1, :], reach[:, 0], reach[:, -1] = free[0, :], free[-1, :], free[:, 0], free[:, -1]
    while True:
        grown = _dilate(reach) & free
        if (grown == reach).all():
            return reach
        reach = grown


def _largest(mask):
    """The biggest 4-connected region of a mask."""
    seen = np.zeros_like(mask)
    best, best_n = None, 0
    H, W = mask.shape
    for start in zip(*np.nonzero(mask)):
        if seen[start]:
            continue
        region = [start]
        seen[start] = True
        k = 0
        while k < len(region):
            r, c = region[k]
            k += 1
            for rr, cc in ((r + 1, c), (r - 1, c), (r, c + 1), (r, c - 1)):
                if 0 <= rr < H and 0 <= cc < W and mask[rr, cc] and not seen[rr, cc]:
                    seen[rr, cc] = True
                    region.append((rr, cc))
        if len(region) > best_n:
            best, best_n = region, len(region)
    out = np.zeros_like(mask)
    if best:
        rr, cc = zip(*best)
        out[list(rr), list(cc)] = True
    return out


def _boundary(mask):
    """The outer edge of a filled region, in order (Moore neighbour tracing): (n, 2) as (x, y)."""
    m = np.pad(mask, 1)
    rows, cols = np.nonzero(m)
    start = (rows[0], cols[0])                              # top-most, then left-most cell
    dirs = [(-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1)]
    path = [start]
    cur, back = start, 6                                    # we came from the left
    for _ in range(4 * m.size):
        for k in range(8):
            d = (back + 1 + k) % 8
            nr, nc = cur[0] + dirs[d][0], cur[1] + dirs[d][1]
            if m[nr, nc]:
                cur = (nr, nc)
                back = (d + 4) % 8
                break
        else:
            break
        if cur == start:
            break
        path.append(cur)
    p = np.array(path)
    return np.stack([p[:, 1] - 1, p[:, 0] - 1], 1)


def _centroid(P):
    x, y = P[:, 0], P[:, 1]
    x1, y1 = np.roll(x, -1), np.roll(y, -1)
    cr = x * y1 - x1 * y
    a = cr.sum() / 2.0
    if abs(a) < 1e-12:
        return float(x.mean()), float(y.mean())
    return float(((x + x1) * cr).sum() / (6 * a)), float(((y + y1) * cr).sum() / (6 * a))
