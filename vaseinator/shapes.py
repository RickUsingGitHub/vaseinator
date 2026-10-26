"""The building blocks of a vase: outlines, cross-sections, curves up the height, textures.

Every vase is a radial height map r(theta, z): one radius for each direction
round the axis at each height.  Everything here returns numpy arrays.
"""

from __future__ import annotations

import math

import numpy as np

from .params import (CIRCLE, EASE, ELLIPSE, EVENLY, EVERYWHERE, FADES, FLOWER, GEAR, GROWS, MIDDLE,
                     OWN, PEBBLE, POLYGON, SLOW_DOWN, SPEED_UP, STAR, SWING)

TAU = 2.0 * math.pi
TABLE = 4096                    # samples round one turn of a cross-section

# Outline presets: (name, [(height 0..1, diameter as a share of the widest)]).
PROFILES = [
    ("Classic", [(0.0, 0.64), (0.36, 1.0), (0.8, 0.6), (1.0, 0.71)]),
    ("Cylinder", [(0.0, 1.0), (1.0, 1.0)]),
    ("Bucket (wider at the top)", [(0.0, 0.66), (1.0, 1.0)]),
    ("Cone (narrower at the top)", [(0.0, 1.0), (1.0, 0.62)]),
    ("Barrel", [(0.0, 0.8), (0.5, 1.0), (1.0, 0.8)]),
    ("Bulb", [(0.0, 0.56), (0.32, 1.0), (0.76, 0.46), (1.0, 0.44)]),
    ("Tulip", [(0.0, 0.46), (0.55, 1.0), (0.86, 0.9), (1.0, 0.96)]),
    ("Hourglass", [(0.0, 1.0), (0.5, 0.62), (1.0, 1.0)]),
    ("Amphora", [(0.0, 0.42), (0.16, 0.74), (0.45, 1.0), (0.8, 0.5), (0.92, 0.44), (1.0, 0.56)]),
    ("Bottle", [(0.0, 0.92), (0.55, 1.0), (0.76, 0.5), (1.0, 0.4)]),
    ("Gourd", [(0.0, 0.72), (0.26, 1.0), (0.52, 0.62), (0.73, 0.76), (1.0, 0.46)]),
    ("Trumpet", [(0.0, 0.5), (0.4, 0.42), (0.75, 0.55), (1.0, 1.0)]),
]

SHAPE_NAMES = {CIRCLE: "Circle", POLYGON: "Polygon", STAR: "Star", FLOWER: "Flower", GEAR: "Gear",
               ELLIPSE: "Ellipse", PEBBLE: "Pebble"}
# what each shape's count, depth and sharpness are called (None: the shape has no such setting)
SHAPE_LABELS = {
    CIRCLE: (None, None, None),
    POLYGON: ("Sides", None, "Corner rounding"),
    STAR: ("Points", "Depth", "Sharpness"),
    FLOWER: ("Petals", "Depth", "Petal shape"),
    GEAR: ("Teeth", "Depth", "Tooth width"),
    ELLIPSE: (None, "Squash", None),
    PEBBLE: ("Pebble no.", "Lumpiness", None),
}


# ===================================================================== curves
def pchip(xk, yk, x):
    """Monotone cubic (Fritsch-Carlson) through the points: smooth, and it never overshoots."""
    xk = np.asarray(xk, dtype=float)
    yk = np.asarray(yk, dtype=float)
    x = np.asarray(x, dtype=float)
    n = len(xk)
    if n == 1:
        return np.full_like(x, yk[0])
    hk = np.diff(xk)
    delta = np.diff(yk) / hk
    d = np.zeros(n)
    if n == 2:
        d[:] = delta[0]
    else:
        for k in range(1, n - 1):
            if delta[k - 1] * delta[k] > 0:
                w1, w2 = 2 * hk[k] + hk[k - 1], hk[k] + 2 * hk[k - 1]
                d[k] = (w1 + w2) / (w1 / delta[k - 1] + w2 / delta[k])
        for end, (h0, h1, d0, d1) in ((0, (hk[0], hk[1], delta[0], delta[1])),
                                      (n - 1, (hk[-1], hk[-2], delta[-1], delta[-2]))):
            v = ((2 * h0 + h1) * d0 - h0 * d1) / (h0 + h1)
            if np.sign(v) != np.sign(d0):
                v = 0.0
            elif np.sign(d0) != np.sign(d1) and abs(v) > abs(3 * d0):
                v = 3 * d0
            d[end] = v
    i = np.clip(np.searchsorted(xk, x, side="right") - 1, 0, n - 2)
    t = np.clip((x - xk[i]) / hk[i], 0.0, 1.0)
    t2, t3 = t * t, t * t * t
    return ((2 * t3 - 3 * t2 + 1) * yk[i] + (t3 - 2 * t2 + t) * hk[i] * d[i]
            + (-2 * t3 + 3 * t2) * yk[i + 1] + (t3 - t2) * hk[i] * d[i + 1])


def smoothstep(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def progress(style: int, h, curve=None, swings: int = 1):
    """How far something has got at height h (0..1): 0 at the bottom, 1 at the top.

    A back-and-forth swing goes out and back ``swings`` times, between -1 and 1.
    OWN follows the curve's points as they are.
    """
    h = np.asarray(h, dtype=float)
    if style == EASE:
        return smoothstep(h)
    if style == SPEED_UP:
        return h * h
    if style == SLOW_DOWN:
        return 1.0 - (1.0 - h) ** 2
    if style == SWING:
        return np.sin(math.pi * max(int(swings), 1) * h)
    if style == OWN and curve:
        pts = np.asarray(curve, dtype=float)
        return pchip(pts[:, 0], pts[:, 1], h)
    return h.copy()


def change(style: int, h, curve=None, changes: int = 3):
    """How far the bottom shape has turned into the top one at height h: 0 the bottom shape, 1 the top.

    Back and forth goes smoothly to the top shape and back, ``changes`` times
    in all: 3 is bottom shape, top, bottom, top.
    """
    if style == SWING:
        return 0.5 * (1.0 - np.cos(math.pi * max(int(changes), 1) * np.asarray(h, dtype=float)))
    return progress(style, h, curve)


def sample_points(fn, style: int, swings: int):
    """Points for an own curve that follows ``fn`` - at each peak and trough of a back-and-forth."""
    n = 2 * max(int(swings), 1) + 1 if style == SWING else 5
    hs = np.linspace(0.0, 1.0, n)
    return [[round(float(h), 4), float(v)] for h, v in zip(hs, fn(hs))]


def strength(style: int, h, curve=None):
    """How strong the surface patterns are at height h."""
    h = np.asarray(h, dtype=float)
    if style == GROWS:
        return smoothstep(h)
    if style == FADES:
        return smoothstep(1.0 - h)
    if style == MIDDLE:
        return np.sin(math.pi * h) ** 2
    if style == OWN and curve:
        pts = np.asarray(curve, dtype=float)
        return np.clip(pchip(pts[:, 0], pts[:, 1], h), -2.0, 2.0)
    return np.ones_like(h)


# ============================================================= cross-sections
def _polar(xs, ys):
    """A closed outline, star-shaped about the middle, as radius at TABLE even angles."""
    ang = np.mod(np.arctan2(ys, xs), TAU)
    rad = np.hypot(xs, ys)
    order = np.argsort(ang, kind="stable")
    ang, rad = ang[order], rad[order]
    a = np.concatenate([ang - TAU, ang, ang + TAU])
    r = np.concatenate([rad, rad, rad])
    return np.interp(np.arange(TABLE) * (TAU / TABLE), a, r)


def _segments(points, per=256):
    """Dense points along the straight sides of a closed polygon."""
    pts = np.asarray(points, dtype=float)
    nxt = np.roll(pts, -1, axis=0)
    t = (np.arange(per) / per)[None, :, None]
    dense = pts[:, None, :] + (nxt - pts)[:, None, :] * t
    dense = dense.reshape(-1, 2)
    return dense[:, 0], dense[:, 1]


def shape_table(kind: int, count: int, depth: float, sharp: float) -> np.ndarray:
    """One cross-section as radius at TABLE even angles, its widest point at 1."""
    u = np.arange(TABLE) * (TAU / TABLE)
    n = max(int(count), 1)
    d = min(max(float(depth), 0.0), 0.9)
    s = min(max(float(sharp), 0.0), 1.0)
    if kind == POLYGON:
        n = max(n, 3)
        inr = math.cos(math.pi / n)                      # inradius of the sharp polygon
        q = s * inr * 0.98                               # radius of the rounded corners
        c = 1.0 - q                                      # where the corner circles sit
        xs, ys = [], []
        for k in range(n):
            a = TAU * k / n
            # the corner arc, between the normals of the two sides it joins
            arc = np.linspace(a - math.pi / n, a + math.pi / n, 96)
            cx, cy = c * math.cos(a), c * math.sin(a)
            xs.append(cx + q * np.cos(arc))
            ys.append(cy + q * np.sin(arc))
        if q < 1e-6:                                     # sharp corners: straight sides
            xs, ys = _segments([(math.cos(TAU * k / n), math.sin(TAU * k / n)) for k in range(n)])
        else:
            arcs = np.stack([np.concatenate(xs), np.concatenate(ys)], 1).reshape(n, 96, 2)
            # the straight sides, from the end of each corner arc to the start of the next
            t = np.linspace(0.0, 1.0, 256)[None, :, None]
            a, b = arcs[:, -1, :], np.roll(arcs[:, 0, :], -1, axis=0)
            sides = (a[:, None, :] + (b - a)[:, None, :] * t).reshape(-1, 2)
            pts = np.concatenate([arcs.reshape(-1, 2), sides])
            xs, ys = pts[:, 0], pts[:, 1]
        r = _polar(xs, ys)
    elif kind == STAR:
        n = max(n, 2)
        pts = []
        for k in range(n):
            a = TAU * k / n
            pts += [(math.cos(a), math.sin(a)),
                    ((1 - d) * math.cos(a + math.pi / n), (1 - d) * math.sin(a + math.pi / n))]
        sharp_star = _polar(*_segments(pts))
        soft = (1 - d) + d * 0.5 * (1 + np.cos(n * u))
        r = s * sharp_star + (1 - s) * soft
    elif kind == FLOWER:
        p = 0.4 + 3.6 * s * s                           # fat round petals ... narrow petals
        r = (1 - d) + d * np.abs(np.cos(0.5 * n * u)) ** p
    elif kind == GEAR:
        duty = 0.2 + 0.6 * s                             # share of each pitch that is tooth
        x = np.cos(n * u)
        raw = np.tanh(7.0 * (x - math.cos(math.pi * duty)))
        lo, hi = raw.min(), raw.max()
        r = (1 - d) + d * (raw - lo) / max(hi - lo, 1e-9)
    elif kind == ELLIPSE:
        a = 1.0 - min(d, 0.85)
        r = 1.0 / np.sqrt(np.cos(u) ** 2 + (np.sin(u) / a) ** 2)
    elif kind == PEBBLE:
        rng = np.random.default_rng(1000 + n)
        wave = np.zeros_like(u)
        for k in range(2, 7):
            wave += rng.normal() / k * np.cos(k * u + rng.uniform(0, TAU))
        wave /= max(np.abs(wave).max(), 1e-9)
        r = 1.0 + 0.6 * max(d, 0.02) * wave
    else:
        r = np.ones_like(u)
    r = np.maximum(r, 0.05)
    return r / r.max()


def blur(table: np.ndarray, sigma: float) -> np.ndarray:
    """A cross-section smoothed round the turn (Gaussian, sigma in radians), its widest point at 1 again.

    Sharp points and valleys are rounded to about the mesh's own spacing, so a
    point that twists across the mesh doesn't alias into a row of little teeth.
    """
    if sigma <= 0:
        return table
    k = np.fft.rfftfreq(TABLE, d=1.0 / TABLE)                  # whole waves round the turn
    out = np.fft.irfft(np.fft.rfft(table) * np.exp(-0.5 * (k * sigma) ** 2), n=TABLE)
    out = np.maximum(out, 0.05)
    return out / out.max()


def smooth_max(a, b, eps: float):
    """The larger of a and b, with the crease where they meet rounded over a width of about eps."""
    if eps <= 0:
        return np.maximum(a, b)
    return 0.5 * (a + b + np.sqrt((a - b) ** 2 + eps * eps)) - 0.5 * eps


def sample(table: np.ndarray, angle) -> np.ndarray:
    """A cross-section's radius in the given directions (radians, any range)."""
    f = np.mod(angle, TAU) * (TABLE / TAU)
    i0 = np.floor(f).astype(np.int64)
    t = f - i0
    i0 %= TABLE
    return table[i0] * (1.0 - t) + table[(i0 + 1) % TABLE] * t


# ================================================================== textures
def organic(angle, z, scale: float, mean_r: float, seed: int, waves: int = 48):
    """Smooth random lumps: about -1..1, seamless round the vase.

    A sum of plane waves on the unrolled wall, each a whole number of times
    round, so the pattern always meets itself.
    """
    rng = np.random.default_rng(int(seed))
    k0 = TAU / max(scale, 1.0)
    out = np.zeros(np.broadcast(angle, z).shape)
    for _ in range(waves):
        k = k0 * math.exp(rng.normal(0.0, 0.3))
        phi = rng.uniform(0, TAU)
        n = round(k * math.cos(phi) * mean_r)            # whole waves round the vase
        m = k * math.sin(phi)
        out += np.cos(n * angle + m * z + rng.uniform(0, TAU))
    return out / (math.sqrt(waves / 2.0) * 2.2)


def lobes_needed(kind: int, count: int) -> int:
    """Rough number of features a cross-section has round one turn, for the mesh detail."""
    if kind in (CIRCLE,):
        return 1
    if kind == ELLIPSE:
        return 2
    if kind == PEBBLE:
        return 6
    return max(int(count), 1)


# ============================================================ colour palettes
PALETTES = [
    ("Lagoon", ["#0E7C86", "#3FC1C9", "#F5F5F5", "#FC5185"]),
    ("Sunset", ["#FF6B35", "#F7C59F", "#EFEFD0", "#004E89"]),
    ("Forest", ["#2D6A4F", "#95D5B2", "#D8F3DC", "#1B4332"]),
    ("Candy", ["#FF70A6", "#FF9770", "#FFD670", "#70D6FF"]),
    ("Midnight", ["#22223B", "#4A4E69", "#9A8C98", "#F2E9E4"]),
    ("Ember", ["#370617", "#9D0208", "#E85D04", "#FAA307"]),
    ("Glacier", ["#CAF0F8", "#90E0EF", "#0096C7", "#023E8A"]),
    ("Desert", ["#CB997E", "#DDBEA9", "#FFE8D6", "#6B705C"]),
    ("Neon", ["#F72585", "#7209B7", "#3A0CA3", "#4CC9F0"]),
    ("Gold and black", ["#D4AF37", "#1A1A1A", "#F4E9C1", "#8C6D1F"]),
    ("Rainbow", ["#E63946", "#F4A261", "#2A9D8F", "#457B9D"]),
    ("Porcelain", ["#F8F9FA", "#1D3557", "#A8DADC", "#E9C46A"]),
]


def style_names():
    """Names for the ways something can change on the way up."""
    return {EVENLY: "Evenly", EASE: "Eases in and out", SPEED_UP: "Speeds up", SLOW_DOWN: "Slows down",
            SWING: "Back and forth", OWN: "Your own curve"}


def strength_names():
    return {EVERYWHERE: "The same all the way", GROWS: "Grows towards the top", FADES: "Fades towards the top",
            MIDDLE: "Strongest in the middle", OWN: "Your own curve"}
