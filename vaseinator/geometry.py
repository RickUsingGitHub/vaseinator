"""The vase itself: its surface, made printable, as closed watertight meshes.

The surface is a radial height map r(theta, z) on a grid of heights and
angles.  Because every height has exactly one radius in each direction,
each layer is one simple closed loop round the axis - just what a spiral
vase slicer needs - and the mesh can never cross itself: every triangle
lies in its own wedge of angle between two heights.

Overhangs are measured on the real surface normal.  A wall leaning out *or
in* overhangs the single printed line beneath it, so both count.  Where the
wall leans too far, the radius is limited column by column (a Lipschitz
envelope from above and below, averaged), with the allowed change per layer
worked out from how the wall faces there - a flank that faces sideways may
move a long way sideways.  The finished triangles are then checked, and the
limit tightened until every one of them is within it.
"""

from __future__ import annotations

import math

import numpy as np

from .expr import ExprError, compile_expression
from . import sections
from .params import (BANDS, DRAWN, FAKE_VASE, GRADIENT, MAX_BANDS, ONE_COLOUR, OWN, SAME, STRIPES, VaseParams,
                     colour_style_of)
from .shapes import (TABLE, TAU, blur, change, lobes_needed, organic, pchip, progress, sample, shape_table,
                     smooth_max, smoothstep, strength)

TOLERANCE = 0.3          # degrees over the overhang limit still counted as within it


# ===================================================================== meshes
def grid_side(z, theta, R):
    """The wall from a grid: rows of radii at shared angles.

    Returns (verts, faces, band of each face, first ring, last ring).  Each
    cell is split along the diagonal whose ends are closer in radius, so
    ridges that spiral up the vase stay smooth.
    """
    K, N = R.shape
    c, s = np.cos(theta)[None, :], np.sin(theta)[None, :]
    verts = np.stack([R * c, R * s, np.broadcast_to(z[:, None], R.shape)], -1).reshape(-1, 3)
    idx = np.arange(K * N).reshape(K, N)
    nxt = np.roll(idx, -1, axis=1)
    v00, v01, v10, v11 = idx[:-1], nxt[:-1], idx[1:], nxt[1:]
    Rn = np.roll(R, -1, axis=1)
    along = (np.abs(R[:-1] - Rn[1:]) <= np.abs(Rn[:-1] - R[1:]))[..., None]
    t1 = np.where(along, np.stack([v00, v01, v11], -1), np.stack([v00, v01, v10], -1))
    t2 = np.where(along, np.stack([v00, v11, v10], -1), np.stack([v01, v11, v10], -1))
    faces = np.concatenate([t1.reshape(-1, 3), t2.reshape(-1, 3)])
    band = np.tile(np.repeat(np.arange(K - 1), N), 2)
    return verts, faces, band, idx[0].copy(), idx[-1].copy()


def loft_side(rows):
    """The wall from rings with angles of their own: (z, angles ascending, radii) each.

    Neighbouring rings are joined by walking round both at once, always
    stepping on along the one whose next point comes first.
    """
    verts, starts, o = [], [], 0
    for z, a, r in rows:
        verts.append(np.stack([r * np.cos(a), r * np.sin(a), np.full(len(a), z)], 1))
        starts.append(o)
        o += len(a)
    faces, band = [], []
    for k in range(len(rows) - 1):
        A, B = rows[k][1], rows[k + 1][1]
        na, nb, sa, sb = len(A), len(B), starts[k], starts[k + 1]
        d = np.mod(B - A[0] + math.pi, TAU) - math.pi
        j0 = int(np.argmin(np.abs(d)))
        b0 = A[0] + d[j0]
        au = A[0] + np.append(np.mod(A - A[0], TAU), TAU)
        bu = b0 + np.append(np.mod(np.roll(B, -j0) - B[j0], TAU), TAU)
        i = j = 0
        while i < na or j < nb:
            if j >= nb or (i < na and au[i + 1] <= bu[j + 1]):
                faces.append((sa + i % na, sa + (i + 1) % na, sb + (j0 + j) % nb))
                i += 1
            else:
                faces.append((sa + i % na, sb + (j0 + j + 1) % nb, sb + (j0 + j) % nb))
                j += 1
            band.append(k)
    verts = np.concatenate(verts)
    first = np.arange(starts[0], starts[0] + len(rows[0][1]))
    last = np.arange(starts[-1], starts[-1] + len(rows[-1][1]))
    return verts, np.array(faces, dtype=np.int64), np.array(band), first, last


def grid_side_xy(z, P):
    """The wall from rows of outline points (K, N, 2), point i of each row joined to point i of the next.

    Returns (verts, faces, band of each face, first ring, last ring).  Each cell
    is split along its shorter diagonal.
    """
    K, N = P.shape[:2]
    verts = np.concatenate([P, np.broadcast_to(z[:, None, None], (K, N, 1))], axis=2).reshape(-1, 3)
    idx = np.arange(K * N).reshape(K, N)
    nxt = np.roll(idx, -1, axis=1)
    v00, v01, v10, v11 = idx[:-1], nxt[:-1], idx[1:], nxt[1:]
    d1 = np.linalg.norm(verts[v00] - verts[v11], axis=-1)
    d2 = np.linalg.norm(verts[v01] - verts[v10], axis=-1)
    along = (d1 <= d2)[..., None]
    t1 = np.where(along, np.stack([v00, v01, v11], -1), np.stack([v00, v01, v10], -1))
    t2 = np.where(along, np.stack([v00, v11, v10], -1), np.stack([v01, v11, v10], -1))
    faces = np.concatenate([t1.reshape(-1, 3), t2.reshape(-1, 3)])
    band = np.tile(np.repeat(np.arange(K - 1), N), 2)
    return verts, faces, band, idx[0].copy(), idx[-1].copy()


def limit_slope(v, step):
    """A 1D curve kept within a most change per step (step[i] between v[i] and v[i+1]).

    The largest curve under it and the smallest over it that keep within the
    limit, averaged - as the columns of a radial vase are softened.
    """
    lo, hi = v.copy(), v.copy()
    for i in range(1, len(v)):
        lo[i] = min(lo[i], lo[i - 1] + step[i - 1])
        hi[i] = max(hi[i], hi[i - 1] - step[i - 1])
    for i in range(len(v) - 2, -1, -1):
        lo[i] = min(lo[i], lo[i + 1] + step[i])
        hi[i] = max(hi[i], hi[i + 1] - step[i])
    return 0.5 * (lo + hi)


def fall_gently(v, step: float):
    """The largest curve under v that changes by at most step from one value to the next."""
    lo = v.copy()
    for i in range(1, len(v)):
        lo[i] = min(lo[i], lo[i - 1] + step)
    for i in range(len(v) - 2, -1, -1):
        lo[i] = min(lo[i], lo[i + 1] + step)
    return lo


def fan(center: int, ring, up: bool):
    """A flat cap: triangles from the centre to each side of a ring."""
    ring = np.asarray(ring)
    nxt = np.roll(ring, -1)
    c = np.full(len(ring), center)
    return np.stack([c, ring, nxt] if up else [c, nxt, ring], 1)


def annulus(outer, inner):
    """A flat, upward-facing ring between two rings of the same angles."""
    o, i = np.asarray(outer), np.asarray(inner)
    o1, i1 = np.roll(o, -1), np.roll(i, -1)
    return np.concatenate([np.stack([o, o1, i1], 1), np.stack([o, i1, i], 1)])


def face_normals(verts, faces):
    tri = verts[faces]
    n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    ln = np.linalg.norm(n, axis=1, keepdims=True)
    ln[ln == 0] = 1.0
    return n / ln


def lean_angles(verts, faces):
    """How far each face leans from upright (degrees), out or in alike."""
    n = face_normals(verts, faces)
    return np.degrees(np.arcsin(np.clip(np.abs(n[:, 2]), 0.0, 1.0)))


def mesh_volume(verts, faces) -> float:
    tri = verts[faces]
    return float(np.einsum("ij,ij->i", tri[:, 0], np.cross(tri[:, 1], tri[:, 2])).sum() / 6.0)


def edge_check(faces):
    """Whether a mesh is closed: every edge used once each way, by exactly two faces.

    Returns (closed, number of bad edges).
    """
    f = np.asarray(faces, dtype=np.int64)
    a = f.ravel()
    b = np.roll(f, -1, axis=1).ravel()
    n = int(f.max()) + 1
    fwd = np.sort(a * n + b)
    rev = np.sort(b * n + a)
    twice = int((np.diff(fwd) == 0).sum())          # an edge used twice the same way
    unmatched = int((fwd != rev).sum())             # an edge with no face the other way
    return twice == 0 and unmatched == 0, twice + unmatched


def inset(angles, radii, width):
    """Radii of a ring moved in by ``width`` square to the wall (as a radial map)."""
    a = np.asarray(angles)
    r = np.asarray(radii)
    da = np.mod(np.roll(a, -1, axis=-1) - np.roll(a, 1, axis=-1), TAU)
    da[da == 0] = 1e-9
    rth = (np.roll(r, -1, axis=-1) - np.roll(r, 1, axis=-1)) / da
    out = r - width * np.sqrt(r * r + rth * rth) / np.maximum(r, 1e-6)
    return np.maximum(out, np.maximum(0.15 * r, 0.2))


def soften(R, dth, dz, angle_deg, scale=None, rounds=4):
    """Limit the radius so that no part of the wall leans more than angle_deg from upright.

    Column by column, the largest surface under R and the smallest one over
    it that keep within the lean are found and averaged: peaks are cut back
    and hollows filled in by the same amount.  ``scale`` tightens the limit
    point by point where the finished triangles showed it was needed.
    """
    t = math.tan(math.radians(max(angle_deg, 1.0)))
    R = R.copy()
    for _ in range(rounds):
        # how far the wall faces sideways there - smoothed round the vase, so that neighbouring
        # columns are allowed much the same and a sharp tip passing across them doesn't streak
        rth = (np.roll(R, -1, axis=1) - np.roll(R, 1, axis=1)) / (2.0 * dth)
        k = np.sqrt(R * R + rth * rth) / np.maximum(R, 1e-6)
        k = t * np.exp(blur_around(np.log(k), 1.5))
        if scale is not None:
            k = k * scale
        step = np.minimum(k[:-1], k[1:]) * dz              # most each row may differ from the next
        lo, hi = R.copy(), R.copy()
        for j in range(1, len(R)):
            np.minimum(lo[j], lo[j - 1] + step[j - 1], out=lo[j])
            np.maximum(hi[j], hi[j - 1] - step[j - 1], out=hi[j])
        for j in range(len(R) - 2, -1, -1):
            np.minimum(lo[j], lo[j + 1] + step[j], out=lo[j])
            np.maximum(hi[j], hi[j + 1] - step[j], out=hi[j])
        new = 0.5 * (lo + hi)
        moved = float(np.abs(new - R).max())
        R = new
        if moved < 1e-4:
            break
    return R


def ease_twist(R, dth, omega, angle_deg, rounds=3):
    """Soften the flanks of a fast-twisting shape round the vase, layer by layer.

    A flank that faces sideways and is carried sideways by the twist leans by
    tan(lean) = r·ω·|r_θ| / sqrt(r² + r_θ²).  Where r·ω is more than the limit
    allows, only a gentler flank can keep within it, so |r_θ| is limited round
    each layer (envelopes from above and below, averaged, as for the columns).
    Every layer of a twisted shape is softened alike, so it stays one clean
    twisted shape.  A little is left in hand for the outline's own slope.
    """
    t = math.tan(math.radians(max(angle_deg, 1.0))) * 0.9
    N = R.shape[1]
    for _ in range(rounds):
        rw = R * omega[:, None]
        if not (rw > t).any():
            break
        bound = np.where(rw > t, R * t / np.sqrt(np.maximum(rw * rw - t * t, 1e-12)), np.inf)
        step = np.minimum(bound, np.roll(bound, -1, axis=1)) * dth      # between column i and i + 1
        lo, hi = R.copy(), R.copy()
        for _ in range(2):                                              # twice round, for the wrap
            for i in range(N):
                np.minimum(lo[:, i], lo[:, i - 1] + step[:, i - 1], out=lo[:, i])
                np.maximum(hi[:, i], hi[:, i - 1] - step[:, i - 1], out=hi[:, i])
            for i in range(N - 1, -1, -1):
                np.minimum(lo[:, i], lo[:, (i + 1) % N] + step[:, i], out=lo[:, i])
                np.maximum(hi[:, i], hi[:, (i + 1) % N] - step[:, i], out=hi[:, i])
        R = 0.5 * (lo + hi)
    return R


def blur_around(a, sigma_cols):
    """Smooth a grid round the vase (each row on its own), sigma in columns."""
    N = a.shape[1]
    k = np.fft.rfftfreq(N, d=1.0 / N)
    gain = np.exp(-0.5 * (k * sigma_cols * TAU / N) ** 2)
    return np.fft.irfft(np.fft.rfft(a, axis=1) * gain[None, :], n=N, axis=1)


def layer_top(z: float, layer: float, first: float | None = None) -> tuple[int, float]:
    """The first layer that starts at height z or above: (its number from 1, the height of its top).

    The first layer may be thicker than the rest, as slicers often make it.
    """
    first = layer if first is None else first
    if z <= first * 0.5:
        return 1, first
    k = max(math.ceil((z - first) / layer - 0.5), 0)         # whole layers above the first one, below z
    return k + 2, round(first + (k + 1) * layer, 4)


def duration(seconds: float) -> str:
    m = int(round(seconds / 60.0))
    return f"{m // 60} h {m % 60:02d} min" if m >= 60 else f"{max(m, 1)} min"


# ===================================================================== design
class VaseDesign:
    """A vase built from its parameters: the solid to export, the shell to show, and its sums."""

    def __init__(self, p: VaseParams, draft: bool = False):
        self.p = p
        self.draft = draft
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.notes: list[str] = []
        self.fn = None
        self.closed = None
        self.free = DRAWN in (self.p.shape1, self.p.shape2)    # a drawn outline: built point by point
        self.outer_rows = None
        try:
            if self._check():
                if self.free:
                    self._free_surface()
                    if self.errors:
                        return
                    self._free_printable()
                    self._free_shell()
                else:
                    self._grid_size()
                    self._surface()
                    self._printable()
                    self._shell()
                self._measure()
                self._colours()
                self._advice()
        except ExprError as exc:
            self.errors.append(f"Your own function: {exc}")

    # ------------------------------------------------------------ checks
    def _check(self) -> bool:
        p = self.p
        if p.height < 5.0:
            self.errors.append("The vase must be at least 5 mm tall.")
        if len(p.silhouette) < 2 or min(d for _, d in p.silhouette) <= 0:
            self.errors.append("The outline needs at least two points, every one wider than nothing.")
        for key, label in (("line_width", "Line width"), ("layer_height", "Layer height"),
                           ("filament_d", "Filament diameter"), ("speed", "Print speed"),
                           ("max_flow", "Max flow"), ("density", "Filament density")):
            if getattr(p, key) <= 0:
                self.errors.append(f"{label} must be more than zero.")
        if p.facet_size <= 0:
            self.errors.append("Mesh detail must be more than zero.")
        try:
            self.fn = compile_expression(p.expression)
        except ExprError as exc:
            self.errors.append(f"Your own function: {exc}")
        return not self.errors

    def _grid_size(self):
        p = self.p
        self.H = H = float(p.height)
        sil = np.asarray(p.silhouette, dtype=float)
        tex = ((abs(p.rib_depth) if p.rib_count > 0 else 0.0) + (abs(p.ring_depth) if p.ring_count > 0 else 0.0)
               + (abs(p.bump_depth) if p.bump_around > 0 else 0.0) + 1.2 * max(p.organic_depth, 0.0))
        r_est = 0.5 * sil[:, 1].max() + tex
        step = max(p.facet_size, 0.15) * (2.6 if self.draft else 1.0)
        per = 10 if self.draft else 22                       # points round each lobe or rib
        lobes = [lobes_needed(p.shape1, p.count1)]
        if p.shape2 != SAME:
            lobes.append(lobes_needed(p.shape2, p.count2))
        if p.rib_count > 0:
            lobes.append(p.rib_count * (2 if p.rib_cross else 1))
        if p.bump_around > 0:
            lobes.append(p.bump_around)
        N = max(math.ceil(TAU * r_est / step), per * max(lobes), 96)
        M = max(math.ceil(H / step), (8 if self.draft else 16) * max(p.ring_count, 1), 24)
        if p.bump_around > 0:
            M = max(M, (8 if self.draft else 16) * p.bump_up)
        if p.organic_depth > 0:                             # a few points across every lump
            fine = max(p.organic_scale, 2.0) / (5 if self.draft else 10)
            N = max(N, math.ceil(TAU * r_est / fine))
            M = max(M, math.ceil(H / fine))
        if self.fn is not None:
            N = max(N, 180 if self.draft else 480)
        limit = 140_000 if self.draft else 1_200_000
        if N * M > limit:
            f = math.sqrt(limit / (N * M))
            N, M = max(int(N * f), 64), max(int(M * f), 16)
            if not self.draft:
                self.notes.append("The surface detail was capped to keep the mesh a manageable size.")
        self.N = (N + 3) // 4 * 4
        self.M = M

    # ----------------------------------------------------------- surface
    def twist_at(self, h):
        """How far the shape has turned at height h (radians)."""
        p = self.p
        if p.twist_style == OWN:
            deg = progress(OWN, h, p.twist_curve)
        else:
            deg = p.twist * progress(p.twist_style, h, swings=p.swings)
        return np.radians(deg)

    def _texture(self, frame, z, mean_r: float):
        """The surface patterns in mm, out (+) or in, at angles ``frame`` (rows, columns) and heights z."""
        p = self.p
        h = z / self.H
        tex = np.zeros(np.broadcast(frame, z[:, None]).shape)
        if p.rib_count > 0 and p.rib_depth != 0:
            k = 1.0 + 7.0 * p.rib_sharp ** 2
            lean = math.radians(p.rib_lean) * h[:, None]
            rib = (0.5 * (1.0 + np.cos(p.rib_count * (frame - lean)))) ** k
            if p.rib_cross:
                rib = np.maximum(rib, (0.5 * (1.0 + np.cos(p.rib_count * (frame + lean)))) ** k)
            tex += p.rib_depth * rib
        if p.ring_count > 0 and p.ring_depth != 0:
            k = 1.0 + 7.0 * p.ring_sharp ** 2
            tex += p.ring_depth * ((0.5 * (1.0 - np.cos(TAU * p.ring_count * h))) ** k)[:, None]
        if p.bump_around > 0 and p.bump_depth != 0:
            tex += p.bump_depth * (0.5 * (1.0 + np.cos(p.bump_around * frame)
                                          * np.cos(TAU * max(p.bump_up, 1) * h)[:, None])) ** 1.5
        if p.organic_depth > 0:
            tex += p.organic_depth * organic(frame, z[:, None], p.organic_scale, mean_r, p.organic_seed)
        return tex

    def _envelope(self, z):
        """How strong the surface patterns are at each height: the strength curve, faded at foot and rim."""
        p = self.p
        env = strength(p.strength, z / self.H, p.strength_curve)
        if p.fade_foot > 0:
            env = env * smoothstep(z / p.fade_foot)
        if p.fade_rim > 0:
            env = env * smoothstep((self.H - z) / p.fade_rim)
        return env

    def _surface(self):
        p, H, N, M = self.p, self.H, self.N, self.M
        self.z = z = np.linspace(0.0, H, M + 1)
        self.theta = theta = np.arange(N) * (TAU / N)
        self.dz, self.dth = H / M, TAU / N
        h = z / H
        sil = np.asarray(p.silhouette, dtype=float)
        R0 = 0.5 * pchip(sil[:, 0], sil[:, 1], h)
        self.tau = tau = self.twist_at(h)
        TH, TA = theta[None, :], tau[:, None]

        tab1 = blur(shape_table(p.shape1, p.count1, p.depth1, p.sharp1), self.dth)
        if p.shape2 != SAME:
            tab2 = blur(shape_table(p.shape2, p.count2, p.depth2, p.sharp2), self.dth)
            mix = change(p.morph, h, p.morph_curve, p.morph_swings)[:, None]
            mix = np.clip(mix, 0.0, 1.0)
        a1, a2 = math.radians(p.turn1), math.radians(p.turn2)

        def section(angle):
            s = sample(tab1, angle - a1)
            if p.shape2 != SAME:
                s = (1.0 - mix) * s + mix * sample(tab2, angle - a2)
            return s

        s = section(TH - TA)
        if p.lattice:
            # round the crossing ridges over a couple of mesh columns, so they don't alias
            steep = float(np.abs(np.diff(tab1)).max()) * TABLE / TAU
            s = smooth_max(s, section(TH + TA), 3.0 * self.dth * steep)
        r = R0[:, None] * s

        frame = TH - TA if p.texture_twist else np.broadcast_to(TH, r.shape)
        r = r + self._envelope(z)[:, None] * self._texture(frame, z, float(R0.mean()))

        if self.fn is not None:
            env_vars = dict(theta=np.broadcast_to(TH, r.shape), phi=frame, z=z[:, None], h=h[:, None], r=r,
                            H=np.float64(H))
            add = self.fn(**env_vars)
            # does the function meet itself round the back?  Try it a whole turn on.
            wrap = self.fn(theta=np.full((M + 1, 1), TAU), phi=frame[:, :1] + TAU, z=z[:, None],
                           h=h[:, None], r=r[:, :1], H=np.float64(H))
            if float(np.abs(wrap[:, 0] - add[:, 0]).max()) > 0.05:
                self.warnings.append(
                    "Your own function doesn't meet itself round the vase, so there is a step "
                    "up the back. Use whole numbers with the angle, e.g. sin(5*theta), not sin(2.5*theta).")
            r = r + add

        floor_r = max(1.5, 2.0 * self.wall)
        if (r < floor_r).any():
            self.notes.append(f"Where the shape came near the middle it is kept {floor_r:.1f} mm out from it.")
        self.R_design = np.maximum(r, floor_r)

    # ----------------------------------------------------- printable solid
    def _rows(self, R):
        """The low-poly rings: (z, angles, radii) for each row of facets."""
        p, H = self.p, self.H
        rng = np.random.default_rng(int(p.facet_seed))
        Nf, Mf = max(int(p.facets_around), 3), max(int(p.facets_up), 1)
        rows = []
        for j in range(Mf + 1):
            zj = H * j / Mf
            a = TAU * np.arange(Nf) / Nf + (j % 2) * math.pi / Nf + float(self.twist_at(np.array([zj / H]))[0])
            if p.facet_rough > 0:
                a = a + rng.uniform(-0.35, 0.35, Nf) * p.facet_rough * TAU / Nf
            r = self._sample(R, zj, a)
            if p.facet_rough > 0:
                r = r * (1.0 + rng.uniform(-0.05, 0.05, Nf) * p.facet_rough)
            rows.append((zj, a, r))
        return rows

    def _sample(self, R, zq, aq):
        """The radius between the grid points (bilinear, round the back too)."""
        fj = min(max(zq / self.dz, 0.0), self.M)
        j0 = min(int(fj), self.M - 1)
        tj = fj - j0
        fi = np.mod(aq, TAU) / self.dth
        i0 = np.floor(fi).astype(np.int64)
        ti = fi - i0
        i0 %= self.N
        i1 = (i0 + 1) % self.N
        lo = R[j0, i0] * (1 - ti) + R[j0, i1] * ti
        hi = R[j0 + 1, i0] * (1 - ti) + R[j0 + 1, i1] * ti
        return lo * (1 - tj) + hi * tj

    def _solid(self, R):
        """The solid to export from a surface: (verts, faces, band of each wall face, wall face count, rows)."""
        rows = self._rows(R) if self.p.facets else None
        if rows is None:
            verts, faces, band, first, last = grid_side(self.z, self.theta, R)
        else:
            verts, faces, band, first, last = loft_side(rows)
        nv = len(verts)
        verts = np.concatenate([verts, [[0.0, 0.0, 0.0], [0.0, 0.0, self.H]]])
        side = len(faces)
        faces = np.concatenate([faces, fan(nv, first, up=False), fan(nv + 1, last, up=True)])
        return verts, faces, band, side, rows

    def _soften(self, target, scale):
        """The design softened, with the correction smoothed round the vase and softened again.

        Each column is softened on its own, so on its own the correction can
        differ a little from column to column and leave fine streaks; smoothing
        it sideways and softening once more keeps the surface clean.
        """
        base = self.R_base
        R = soften(base, self.dth, self.dz, target, scale)
        for _ in range(2):
            fix = blur_around(R - base, 2.0)
            R = soften(base + fix, self.dth, self.dz, target, scale)
        return R

    def _printable(self):
        p = self.p
        target = p.max_overhang
        scale = np.ones_like(self.R_design)       # where the limit has to be tighter than it looks
        R = self.R_design
        self.R_base = self.R_design
        if p.soften:                              # a fast twist first: gentler flanks, layer by layer
            omega = np.abs(np.gradient(self.tau, self.dz))
            self.R_base = ease_twist(self.R_design, self.dth, omega, p.max_overhang)
        for attempt in range(14 if p.soften else 1):
            R = self._soften(target, scale) if p.soften else self.R_design
            verts, faces, band, side, rows = self._solid(R)
            lean = lean_angles(verts, faces[:side])
            worst = float(lean.max())
            if worst <= p.max_overhang + TOLERANCE or not p.soften:
                break
            if rows is None:
                # tighten only round the faces that still lean too far
                # by as much as each face is over, spread a little and feathered over a few columns
                # and rows, so the tightening itself leaves no crease
                over = lean > p.max_overhang + 0.5 * TOLERANCE
                cut = 1.0 - math.tan(math.radians(p.max_overhang - 0.25)) / np.tan(np.radians(lean[over]))
                cut = np.clip(cut + 0.03, 0.03, 0.6)
                corner = faces[:side][over].ravel()
                keep = corner < (self.M + 1) * self.N
                j, i = np.divmod(corner[keep], self.N)
                tight = np.zeros_like(scale)
                np.maximum.at(tight, (j, i), np.repeat(cut, 3)[keep])
                for axis in (0, 1):
                    tight = np.maximum(tight, np.maximum(np.roll(tight, 1, axis), np.roll(tight, -1, axis)))
                tight = blur_around(tight, 1.5)
                scale *= 1.0 - np.clip(tight, 0.0, 0.6)
                if attempt >= 6:                  # still not there: ask a little less everywhere too
                    target -= max(1.0, worst - p.max_overhang)
            else:
                # low-poly: the facets cut across the softened surface, so ask for less everywhere
                target -= max(0.75, worst - p.max_overhang)
                if target < 2.0:
                    break
        self.R, self.rows = R, rows
        self.verts, self.faces, self.side = verts, faces, side
        self.band, self.lean = band, lean
        self.worst = worst
        self.softened = float(np.abs(R - self.R_design).max()) if p.soften else 0.0
        self.row_moved = np.abs(R - self.R_design).max(axis=1) if rows is None else None
        if not self.draft:
            self.closed = edge_check(faces)[0]
        nb = int(band.max()) + 1
        self.band_lean = np.zeros(nb)
        np.maximum.at(self.band_lean, band, lean)
        self.triangles = len(faces)
        lo, hi = verts.min(0), verts.max(0)
        self.size = hi - lo
        self.top = self.H

    # --------------------------------------------------------- shown shell
    @property
    def wall(self) -> float:
        """How thick the printed wall is: one spiral line, or a fake vase's walls side by side."""
        p = self.p
        return p.line_width * (max(int(p.walls), 1) if p.vase_mode == FAKE_VASE else 1)

    def _shell(self):
        """What the printer really makes: the wall over a solid bottom, for the 3D view."""
        p = self.p
        w = self.wall
        zb = min(max(p.bottom, p.layer_height), 0.5 * self.H)
        self.zb = zb
        if self.rows is None:
            z, R = self.z, self.R
            keep = z > zb + 0.3 * self.dz
            fj = zb / self.dz
            j0 = min(int(fj), self.M - 1)
            first = R[j0] + (R[j0 + 1] - R[j0]) * (fj - j0)
            zi = np.concatenate([[zb], z[keep]])
            Ri = inset(self.theta, np.vstack([first, R[keep]]), w)
            o_verts, o_faces, _, o_first, o_last = grid_side(z, self.theta, R)
            i_verts, i_faces, _, i_first, i_last = grid_side(zi, self.theta, Ri)
            self.inner_rows = [(zz, self.theta, rr) for zz, rr in zip(zi, Ri)]
        else:
            rows = self.rows
            inner = [(zb, rows[0][1], inset(rows[0][1], rows[0][2], w))]
            inner += [(zz, a, inset(a, r, w)) for zz, a, r in rows[1:] if zz > zb + 0.3]
            o_verts, o_faces, _, o_first, o_last = loft_side(rows)
            i_verts, i_faces, _, i_first, i_last = loft_side(inner)
            self.inner_rows = inner
        no, ni = len(o_verts), len(i_verts)
        verts = np.concatenate([o_verts, i_verts, [[0.0, 0.0, 0.0], [0.0, 0.0, zb]]])
        cb, cf = no + ni, no + ni + 1
        walls = np.concatenate([o_faces, i_faces[:, ::-1] + no])
        caps = np.concatenate([fan(cb, o_first, up=False), fan(cf, i_first + no, up=True),
                               annulus(o_last, i_last + no)])
        self.shell_verts = verts
        self.shell_faces = np.concatenate([walls, caps])
        self.shell_lean = np.concatenate([lean_angles(verts, walls), np.full(len(caps), -1.0)])

    # ======================================================= drawn outlines
    def _outline(self, k: int):
        """Cross-section k (1 at the bottom, 2 at the top) as a loop of points, widest at radius 1."""
        p = self.p
        kind = getattr(p, f"shape{k}")
        if kind == DRAWN:
            pts = getattr(p, f"drawn{k}")
            loop = sections.spline(pts, getattr(p, f"repeat{k}"))
            hits = sections.piece_crossings(loop, 48 * len(pts))
            if hits:
                x, y = hits[0]
                where = "bottom" if k == 1 else "top"
                self.errors.append(f"The drawn {where} outline crosses itself (near {x:.2f}, {y:.2f} in the "
                                   "drawing): move its points apart so it makes one simple loop.")
        else:
            loop = sections.from_table(shape_table(kind, getattr(p, f"count{k}"), getattr(p, f"depth{k}"),
                                                   getattr(p, f"sharp{k}")))
        loop = sections.normalised(loop)
        a = math.radians(getattr(p, f"turn{k}"))
        c, s = math.cos(a), math.sin(a)
        return loop @ np.array([[c, s], [-s, c]])

    def _free_surface(self):
        """The designed surface of a vase with a drawn outline: rows of points (M + 1, N, 2)."""
        p = self.p
        self.H = H = float(p.height)
        loops = [self._outline(1)] + ([self._outline(2)] if p.shape2 != SAME else [])
        if self.errors:
            return
        sil = np.asarray(p.silhouette, dtype=float)
        tex = ((abs(p.rib_depth) if p.rib_count > 0 else 0.0) + (abs(p.ring_depth) if p.ring_count > 0 else 0.0)
               + (abs(p.bump_depth) if p.bump_around > 0 else 0.0) + 1.2 * max(p.organic_depth, 0.0))
        self.tex_depth = tex
        perimeter = max(float(np.linalg.norm(np.roll(L, -1, axis=0) - L, axis=1).sum()) for L in loops)
        step = max(p.facet_size, 0.15) * (2.6 if self.draft else 1.0)
        per = 10 if self.draft else 22
        reps = max([getattr(p, f"repeat{k}") for k in (1, 2) if getattr(p, f"shape{k}") == DRAWN] + [1])
        N = max(math.ceil(perimeter * (0.5 * sil[:, 1].max() + tex) / step),
                per * max(p.rib_count * (2 if p.rib_cross else 1), p.bump_around, reps), 160)
        M = max(math.ceil(H / step), (8 if self.draft else 16) * max(p.ring_count, 1), 24)
        if p.bump_around > 0:
            M = max(M, (8 if self.draft else 16) * p.bump_up)
        if p.organic_depth > 0:
            fine = max(p.organic_scale, 2.0) / (5 if self.draft else 10)
            N = max(N, math.ceil(perimeter * 0.5 * sil[:, 1].max() / fine))
            M = max(M, math.ceil(H / fine))
        if self.fn is not None:
            N = max(N, 180 if self.draft else 480)
        limit = 140_000 if self.draft else 1_200_000
        if N * M > limit:
            f = math.sqrt(limit / (N * M))
            N, M = max(int(N * f), 64, 8 * reps), max(int(M * f), 16)      # each repeat keeps a few points
        self.N, self.M = (N + 3) // 4 * 4, M
        self.z = z = np.linspace(0.0, H, M + 1)
        self.dz = H / M
        h = z / H
        self.C1 = sections.resample(loops[0], self.N)
        self.C2 = sections.resample(loops[1], self.N) if len(loops) > 1 else None
        self.R0_d = 0.5 * pchip(sil[:, 0], sil[:, 1], h)
        self.tau = self.tau_d = self.twist_at(h)
        self.mix_d = (np.clip(change(p.morph, h, p.morph_curve, p.morph_swings), 0.0, 1.0) if self.C2 is not None
                      else np.zeros_like(h))
        self.env_d = self._envelope(z)
        if p.lattice and (p.twist_style == OWN or abs(p.twist) > 1e-9):
            self.notes.append("Both ways (lattice) works on the built-in shapes only: a drawn outline twists one way.")
        if p.facets:
            self.notes.append("Low-poly facets work on the built-in shapes only: a drawn outline stays smooth.")
        self.P_design = self._free_points(self.R0_d, self.tau_d, self.mix_d, self.env_d)
        # a blend of two outlines, or deep patterns in a tight corner, can make a layer cross itself
        for j in np.linspace(0, M, 7).astype(int):
            if sections.crossings(self.P_design[j], limit=max(700, 12 * reps)):
                self.warnings.append(f"The outline crosses itself at about {z[j]:.0f} mm up (where the shapes "
                                     "blend, or patterns meet in a tight corner): the slicer may fill it wrongly "
                                     "there. Ease the change of shape or the patterns.")
                break

    def _free_points(self, R0, tau, mix, env):
        """The surface's points: the outline blended, sized, turned, then patterned square to the wall."""
        p = self.p
        base = (self.C1[None] if self.C2 is None
                else (1.0 - mix)[:, None, None] * self.C1 + mix[:, None, None] * self.C2)
        P = base * R0[:, None, None]
        c, s = np.cos(tau)[:, None], np.sin(tau)[:, None]
        x, y = P[..., 0], P[..., 1]
        P = np.stack([x * c - y * s, x * s + y * c], -1)
        # patterns run round the outline (turning with it), or round the axis if they shouldn't turn
        along = np.arange(self.N) * (TAU / self.N)
        frame = (np.broadcast_to(along, P.shape[:2]) if p.texture_twist
                 else np.mod(np.arctan2(P[..., 1], P[..., 0]), TAU))
        out = sections.normals(P)
        tex = env[:, None] * self._texture(frame, self.z, float(R0.mean()))
        if self.fn is not None:
            tex = tex + self.fn(theta=np.mod(np.arctan2(P[..., 1], P[..., 0]), TAU), phi=frame,
                                z=self.z[:, None], h=(self.z / self.H)[:, None], r=np.hypot(P[..., 0], P[..., 1]),
                                H=np.float64(self.H))
        return P + tex[..., None] * out

    def _free_solid(self, P):
        """The closed solid from rows of outline points: (verts, faces, band of each wall face, wall face count)."""
        verts, faces, band, first, last = grid_side_xy(self.z, P)
        side = len(faces)
        bottom = first[sections.triangulate(P[0])][:, ::-1]           # facing down, onto the bed
        top = last[sections.triangulate(P[-1])]
        return verts, np.concatenate([faces, bottom, top]), band, side

    def _free_printable(self):
        """Soften a drawn vase until no face leans past the limit.

        A drawn outline itself stands upright; only the changes up the vase
        lean it - the outline widening or narrowing, the twist, the change of
        shape and the patterns.  Where faces lean too far, those changes are
        slowed at that height (the same envelopes as for the columns of a
        radial vase) and the patterns eased, until every face is within it.
        """
        p = self.p
        R0, tau, mix, env = self.R0_d.copy(), self.tau_d.copy(), self.mix_d.copy(), self.env_d.copy()
        aim = math.tan(math.radians(max(p.max_overhang - 0.4, 1.0)))
        # patterns fade in and out over a few layers: a sudden change of depth would lean the wall itself
        fade = 0.1 * aim * self.dz / max(self.tex_depth, 1e-6)
        P = self.P_design
        for attempt in range(12 if p.soften else 1):
            if attempt:
                P = self._free_points(R0, tau, mix, env)
            verts, faces, band, side = self._free_solid(P)
            lean = lean_angles(verts, faces[:side])
            worst = float(lean.max())
            if worst <= p.max_overhang + TOLERANCE or not p.soften:
                break
            over = np.zeros(self.M)
            np.maximum.at(over, band, lean)
            f = np.where(over > p.max_overhang, aim / np.tan(np.radians(np.minimum(over, 89.0))), 1.0)
            f = np.clip(f, 0.1, 1.0)
            pad = np.concatenate([[f[0]] * 2, f, [f[-1]] * 2])
            f = np.minimum.reduce([pad[k:k + self.M] for k in range(5)])       # a little room each side
            R0 = limit_slope(R0, np.abs(np.diff(R0)) * f)
            tau = limit_slope(tau, np.abs(np.diff(tau)) * f)
            mix = limit_slope(mix, np.abs(np.diff(mix)) * f)
            env = fall_gently(env * np.minimum(np.concatenate([[f[0]], f]), np.concatenate([f, [f[-1]]])), fade)
        self.P, self.tau, self.rows = P, tau, None
        # what softening changed, in the design's own terms
        with np.errstate(divide="ignore", invalid="ignore"):
            kept = np.where(self.env_d > 1e-6, env / self.env_d, 1.0)
        self.eased = dict(twist=float(np.degrees(np.abs(tau - self.tau_d)).max()),
                          width=float(2.0 * np.abs(R0 - self.R0_d).max()),
                          change=float(np.abs(mix - self.mix_d).max()), patterns=float(np.min(kept)))
        self.verts, self.faces, self.side = verts, faces, side
        self.band, self.lean, self.worst = band, lean, worst
        moved = np.linalg.norm(P - self.P_design, axis=-1)
        self.row_moved = moved.max(axis=1)
        self.softened = float(moved.max()) if p.soften else 0.0
        if not self.draft:
            self.closed = edge_check(faces)[0]
        self.band_lean = np.zeros(self.M)
        np.maximum.at(self.band_lean, band, lean)
        self.triangles = len(faces)
        self.size = verts.max(0) - verts.min(0)
        self.top = self.H

    def _P_at(self, zq):
        """The outline's points at height zq, between the rows."""
        fj = min(max(zq / self.dz, 0.0), self.M)
        j = min(int(fj), self.M - 1)
        return self.P[j] + (fj - j) * (self.P[j + 1] - self.P[j])

    def _free_shell(self):
        """What the printer makes of a drawn vase: the wall moved in square to itself, over a solid bottom."""
        p = self.p
        w = self.wall
        zb = min(max(p.bottom, p.layer_height), 0.5 * self.H)
        self.zb = zb
        P, z = self.P, self.z
        keep = z > zb + 0.3 * self.dz
        zi = np.concatenate([[zb], z[keep]])
        Pi = np.stack([sections.inset(row, w) for row in np.concatenate([self._P_at(zb)[None], P[keep]])])
        o_verts, o_faces, _, o_first, o_last = grid_side_xy(z, P)
        i_verts, i_faces, _, i_first, i_last = grid_side_xy(zi, Pi)
        no = len(o_verts)
        verts = np.concatenate([o_verts, i_verts])
        walls = np.concatenate([o_faces, i_faces[:, ::-1] + no])
        caps = np.concatenate([o_first[sections.triangulate(P[0])][:, ::-1],
                               (i_first + no)[sections.triangulate(Pi[0])], annulus(o_last, i_last + no)])
        self.shell_verts = verts
        self.shell_faces = np.concatenate([walls, caps])
        self.shell_lean = np.concatenate([lean_angles(verts, walls), np.full(len(caps), -1.0)])

        def polar(zs, rows):
            return [(zz, np.arctan2(r[:, 1], r[:, 0]), np.hypot(r[:, 0], r[:, 1])) for zz, r in zip(zs, rows)]
        self.outer_rows = polar(z, P)
        self.inner_rows = polar(zi, Pi)

    # ---------------------------------------------------------- the sums
    def _ring_stats(self, rows):
        """Perimeter and enclosed area of each ring."""
        per, area = [], []
        for _, a, r in rows:
            x, y = r * np.cos(a), r * np.sin(a)
            x1, y1 = np.roll(x, -1), np.roll(y, -1)
            per.append(float(np.hypot(x1 - x, y1 - y).sum()))
            area.append(float(0.5 * (x * y1 - x1 * y).sum()))
        return np.array(per), np.array(area)

    def _measure(self):
        p = self.p
        w, lh = self.wall, p.layer_height
        loops = max(int(p.walls), 1) if p.vase_mode == FAKE_VASE else 1      # lines round each layer
        if self.outer_rows is not None:
            outer = self.outer_rows
        elif self.rows is not None:
            outer = self.rows
        else:
            outer = [(zz, self.theta, rr) for zz, rr in zip(self.z, self.R)]
        oz = np.array([o[0] for o in outer])
        o_per, o_area = self._ring_stats(outer)
        iz = np.array([i[0] for i in self.inner_rows])
        _, i_area = self._ring_stats(self.inner_rows)
        zb = self.zb
        above = oz >= zb
        zs = np.concatenate([[zb], oz[above]])
        ps = np.concatenate([[np.interp(zb, oz, o_per)], o_per[above]])
        wall_area = float(np.sum(0.5 * (ps[1:] + ps[:-1]) * np.diff(zs)))     # mm² of wall, unrolled
        bottom_vol = float(np.interp(0.0, oz, o_area)) * zb
        self.capacity = float(np.sum(0.5 * (i_area[1:] + i_area[:-1]) * np.diff(iz))) / 1000.0  # ml
        fil_area = math.pi * (p.filament_d / 2.0) ** 2
        vol = wall_area * w + bottom_vol
        self.grams = vol / 1000.0 * p.density
        self.metres = vol / fil_area / 1000.0
        v = min(p.speed, p.max_flow / max(p.line_width * lh, 1e-6))
        layers_bottom = max(1, math.ceil(zb / lh - 1e-6))
        path = wall_area * loops / lh + layers_bottom * float(np.interp(0.0, oz, o_area)) / p.line_width
        self.seconds = path / max(v, 0.1) + 120.0
        self.layers = int(round(self.H / lh))
        self.bottom_layers = layers_bottom
        # filament used up to each height, for a gradient spool's colours
        cum = np.concatenate([[0.0], np.cumsum(0.5 * (o_per[1:] + o_per[:-1]) * np.diff(oz))]) * w
        cum += np.minimum(oz, zb) * float(np.interp(0.0, oz, o_area))
        self.filament_z, self.filament_at = oz, cum / fil_area                # mm of filament
        self.solid_volume = mesh_volume(self.verts, self.faces) / 1000.0     # cm³
        r0, rt = outer[0][2], self.inner_rows[-1][2]
        self.base_d = (2 * float(r0.min()), 2 * float(r0.max()))
        self.top_d = (2 * float(rt.min()), 2 * float(rt.max()))
        self.widest = 2 * float(max(o[2].max() for o in outer))
        # for the profile picture: the widest and narrowest radius at each height
        self.profile_z = oz
        self.profile_max = np.array([o[2].max() for o in outer])
        self.profile_min = np.array([o[2].min() for o in outer])

    # ----------------------------------------------------------- colours
    def _colours(self):
        """The filament for each height: [(from z, filament)], snapped to layers."""
        p = self.p
        lh, H = p.layer_height, self.H
        used = max(1, min(int(p.colours_used), 4))
        bands = [(0.0, 1)]
        if colour_style_of(p) == BANDS:
            k = max(int(p.band_count), 1)
            gamma = 2.0 ** (1.3 * p.band_spacing)
            bands = [(H * (i / k) ** gamma, 1 + i % used) for i in range(k)]
        elif colour_style_of(p) == STRIPES:
            stripe = max(p.stripe_height, lh)
            n = math.ceil(H / stripe - 1e-9)
            if n > MAX_BANDS:
                stripe = H / MAX_BANDS
                n = MAX_BANDS
                self.warnings.append(f"Stripes that thin would be more than {MAX_BANDS} colour changes: "
                                     f"they are made {stripe:.1f} mm tall.")
            bands = [(i * stripe, 1 + i % used) for i in range(n)]
        snapped = []
        for i, (zs, fil) in enumerate(bands):
            zs = 0.0 if i == 0 else round(zs / lh) * lh
            if zs >= H - 0.5 * lh:                      # starts at the very top: never printed
                continue
            if snapped and zs <= snapped[-1][0] + 0.5 * lh:
                snapped[-1] = (snapped[-1][0], fil)       # the band before has no layers: this one takes over
            else:
                snapped.append((zs, fil))
        merged = []
        for zs, fil in snapped:
            if not merged or merged[-1][1] != fil:
                merged.append((zs, fil))
        self.bands = merged or [(0.0, 1)]
        self.gradient = colour_style_of(p) == GRADIENT
        self.gradient_fils = list(range(1, used + 1))

    def filament_of(self, k: int) -> str:
        return getattr(self.p, f"color{k}").upper()

    def band_parts(self):
        """The vase as one closed solid per colour band: [(filament, verts, faces)], bottom to top.

        Neighbouring bands meet on a shared flat face at the height where the
        colour changes, so together they fill the vase exactly once - the way
        a slicer wants the parts of a multi-colour object.
        """
        tops = [zs for zs, _ in self.bands[1:]] + [self.H]
        parts = []
        for (lo, fil), hi in zip(self.bands, tops):
            if self.free:
                inside = (self.z > lo + 1e-6) & (self.z < hi - 1e-6)
                zs = np.concatenate([[lo], self.z[inside], [hi]])
                Ps = np.concatenate([self._P_at(lo)[None], self.P[inside], self._P_at(hi)[None]])
                verts, faces, _, first, last = grid_side_xy(zs, Ps)
                faces = np.concatenate([faces, first[sections.triangulate(Ps[0])][:, ::-1],
                                        last[sections.triangulate(Ps[-1])]])
                parts.append((fil, verts, faces))
                continue
            if self.rows is None:
                inside = (self.z > lo + 1e-6) & (self.z < hi - 1e-6)
                zs = np.concatenate([[lo], self.z[inside], [hi]])
                Rs = np.vstack([self._row_at(lo), self.R[inside], self._row_at(hi)])
                verts, faces, _, first, last = grid_side(zs, self.theta, Rs)
            else:
                rings = [self._ring_at(lo)] + [r for r in self.rows if lo + 1e-6 < r[0] < hi - 1e-6] + [self._ring_at(hi)]
                verts, faces, _, first, last = loft_side(rings)
            n = len(verts)
            verts = np.concatenate([verts, [[0.0, 0.0, lo], [0.0, 0.0, hi]]])
            faces = np.concatenate([faces, fan(n, first, up=False), fan(n + 1, last, up=True)])
            parts.append((fil, verts, faces))
        return parts

    def _row_at(self, zq):
        """The surface's radii at height zq, between the grid's rows (straight up each column)."""
        fj = min(max(zq / self.dz, 0.0), self.M)
        j = min(int(fj), self.M - 1)
        return self.R[j] + (fj - j) * (self.R[j + 1] - self.R[j])

    def _ring_at(self, zq):
        """The low-poly wall's cross-section at height zq, as a ring (z, angles, radii)."""
        for row in self.rows:
            if abs(row[0] - zq) < 1e-6:
                return row
        j = max(k for k, row in enumerate(self.rows) if row[0] < zq)
        verts, faces, *_ = loft_side(self.rows[j:j + 2])
        tri = verts[faces]
        d = tri[:, :, 2] - zq
        pts = []
        for a, b in ((0, 1), (1, 2), (2, 0)):
            hit = d[:, a] * d[:, b] < 0
            t = d[hit, a] / (d[hit, a] - d[hit, b])
            pts.append(tri[hit, a] + (tri[hit, b] - tri[hit, a]) * t[:, None])
        pts = np.unique(np.round(np.concatenate(pts)[:, :2], 6), axis=0)
        ang = np.mod(np.arctan2(pts[:, 1], pts[:, 0]), TAU)
        order = np.argsort(ang)
        ang, rad = ang[order], np.hypot(pts[order, 0], pts[order, 1])
        keep = np.concatenate([[True], np.diff(ang) > 1e-7])
        return (zq, ang[keep], rad[keep])

    def colour_changes(self, first_layer: float | None = None):
        """[(layer number, height of that layer's top, filament)] for each change after the first.

        first_layer: the slicer's first layer height, if it differs from the rest.
        """
        lh = self.p.layer_height
        return [(*layer_top(zs, lh, first_layer), fil) for zs, fil in self.bands[1:]]

    def colour_phase(self, z):
        """Colour cycles of a gradient spool used by each height."""
        length = max(self.p.gradient_length, 0.05) * 1000.0
        return np.interp(z, self.filament_z, self.filament_at) / length

    def colour_plan(self, first_layer: float | None = None) -> str:
        p = self.p
        lines = [f"Vaseinator: {p.name} - spiral vase, {p.layer_height:g} mm layers"]
        if self.gradient:
            lines.append(f"Print with one gradient spool (one colour cycle every {p.gradient_length:g} m).")
            return "\n".join(lines)
        lines.append(f"Start with filament {self.bands[0][1]} ({self.filament_of(self.bands[0][1])})")
        for layer, ztop, fil in self.colour_changes(first_layer):
            lines.append(f"Layer {layer} ({ztop:.2f} mm): change to filament {fil} ({self.filament_of(fil)})")
        return "\n".join(lines)

    # ------------------------------------------------------------ advice
    def _advice(self):
        p = self.p
        if self.worst > p.max_overhang + TOLERANCE:
            if p.soften:
                self.warnings.append(
                    f"Some of the wall still leans {self.worst:.0f}° (the limit is {p.max_overhang:g}°). "
                    "With low-poly facets, more facets round the vase or fewer up it lean less.")
            else:
                self.warnings.append(
                    f"The wall leans up to {self.worst:.0f}°, over the {p.max_overhang:g}° limit: it would "
                    "sag or fail there (red in the Overhangs view). Turn on Soften to fit, or make the "
                    "shape gentler.")
        elif self.softened > 0.05 and self.free:
            e = self.eased
            what = [f"the twist by up to {e['twist']:.0f}°" if e["twist"] > 0.5 else "",
                    f"the outline's width by up to {e['width']:.1f} mm" if e["width"] > 0.05 else "",
                    f"the change of shape by up to {100 * e['change']:.0f}%" if e["change"] > 0.005 else "",
                    f"the patterns to {100 * e['patterns']:.0f}% at the steepest place" if e["patterns"] < 0.995 else ""]
            what = [w for w in what if w]
            self.notes.append("Overhangs softened, so no part of the wall leans more than "
                              f"{p.max_overhang:g}°: " + (", ".join(what) if what else "slightly") + ".")
        elif self.softened > 0.05:
            self.notes.append(f"Overhangs softened: the surface was moved by up to {self.softened:.1f} mm so "
                              f"no part of the wall leans more than {p.max_overhang:g}°.")
        if self.H > p.printer_height:
            self.warnings.append(f"The vase is {self.H:.0f} mm tall: taller than the printer ({p.printer_height:.0f} mm).")
        sx, sy = self.size[0], self.size[1]
        if sx > p.bed_x or sy > p.bed_y:
            self.warnings.append(f"The vase is {sx:.0f} × {sy:.0f} mm across: bigger than the bed "
                                 f"({p.bed_x:.0f} × {p.bed_y:.0f} mm).")
        if self.H > 3.2 * self.base_d[1] and self.H > 60:
            self.warnings.append(f"The base is narrow for the height (Ø {self.base_d[1]:.0f} mm under a "
                                 f"{self.H:.0f} mm vase): it may topple, on the bed or with flowers in. "
                                 "A brim helps it print.")
        if self.top_d[0] < 8.0:
            self.notes.append(f"The opening at the top is only {self.top_d[0]:.0f} mm across: a bud vase.")
        changes = len(self.bands) - 1
        if changes > 20:
            self.warnings.append(f"{changes} colour changes: each one takes time and leaves a small seam. "
                                 "Fewer, taller bands print cleaner.")
        if p.line_width < 0.45:
            self.notes.append("A wider line (0.6 to 0.8 mm on a 0.4 mm nozzle) makes a stronger, more surely "
                              "watertight wall.")
        if self.closed is False:          # pragma: no cover - the construction should never allow it
            self.warnings.append("The mesh is not closed: please report this design.")

    # -------------------------------------------------------------- view
    def info(self) -> dict:
        p = self.p
        lean = f"{self.worst:.1f}° from upright (limit {p.max_overhang:g}°)"
        lean += " ✓" if self.worst <= p.max_overhang + TOLERANCE else " ✗"
        mesh = f"{self.triangles:,} triangles"
        if self.closed:
            mesh += ", closed and watertight ✓"
        d = {
            "Height": f"{self.H:.1f} mm, {self.layers} layers of {p.layer_height:g} mm",
            "Widest": f"Ø {self.widest:.1f} mm",
            "Footprint": f"{self.size[0]:.1f} × {self.size[1]:.1f} mm",
            "Base": f"Ø {self.base_d[0]:.0f}–{self.base_d[1]:.0f} mm",
            "Opening at the top": f"Ø {self.top_d[0]:.0f}–{self.top_d[1]:.0f} mm",
            "Holds": f"about {self.capacity:.0f} ml of water",
            "Wall": (f"one {p.line_width:g} mm spiral line" if p.vase_mode != FAKE_VASE else
                     f"{max(int(p.walls), 1)} walls of {p.line_width:g} mm (about {self.wall:.1f} mm)")
                    + f", on a {self.zb:g} mm solid bottom ({self.bottom_layers} layers)",
            "Steepest overhang": lean,
            "Filament": f"{self.grams:.0f} g, {self.metres:.1f} m",
            "Print time": f"about {duration(self.seconds)}",
            "Mesh": mesh,
        }
        return d

    def contour(self, zc: float):
        """Where the wall crosses height zc: line segments (K, 2, 3), for the print animation."""
        if not hasattr(self, "_tri"):
            tri = self.verts[self.faces[:self.side]]
            self._tri = tri
            self._tz = (tri[:, :, 2].min(1), tri[:, :, 2].max(1))
        zc = float(zc) + 1e-7
        sel = self._tri[(self._tz[0] < zc) & (self._tz[1] > zc)]
        if not len(sel):
            return np.zeros((0, 2, 3))
        pts, crosses = [], []
        for a, b in ((0, 1), (1, 2), (2, 0)):
            za, zb = sel[:, a, 2], sel[:, b, 2]
            cross = (za - zc) * (zb - zc) < 0
            t = np.where(cross, (zc - za) / np.where(zb == za, 1.0, zb - za), 0.0)
            pts.append(sel[:, a] + (sel[:, b] - sel[:, a]) * t[:, None])
            crosses.append(cross)
        P, C = np.stack(pts, 1), np.stack(crosses, 1)
        first_two = np.argsort(~C, axis=1, kind="stable")[:, :2]     # the two edges each face crosses
        seg = np.take_along_axis(P, first_two[:, :, None], axis=1)
        return seg[C.sum(1) >= 2]
