"""Check STL files for spiral vase printing, straight from the file.

    .venv\\Scripts\\python tools\\verify_stl.py vase.stl [more.stl ...] [--limit 45] [--layer 0.2]

For each file: is it closed and watertight (every edge shared by exactly two
faces, once each way), do its faces point outwards, is it one piece with no
holes through it, does it stand flat on the bed, does any of the wall lean more
than the limit, and is every layer one single closed loop?
"""

import math
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from vaseinator.geometry import edge_check, lean_angles, mesh_volume  # noqa: E402
from vaseinator.stl import read_stl  # noqa: E402
from vaseinator.viewer import plane_cut  # noqa: E402


def loops(segments) -> int:
    """Separate closed loops among line segments; -1 if they don't close up."""
    if not len(segments):
        return 0
    pts = np.round(segments.reshape(-1, 3)[:, :2], 4)
    _, inv = np.unique(pts, axis=0, return_inverse=True)
    edges = inv.reshape(-1, 2)
    edges = edges[edges[:, 0] != edges[:, 1]]
    inv = np.unique(edges, return_inverse=True)[1]
    edges = inv.reshape(-1, 2)
    n = int(inv.max()) + 1
    if not (np.bincount(edges.ravel(), minlength=n) == 2).all():
        return -1
    parent = list(range(n))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for a, b in edges:
        parent[find(a)] = find(b)
    return len({find(a) for a in range(n)})


def verify(path, limit=45.0, layer=0.2):
    verts, faces = read_stl(path)
    results = []

    def check(what, ok, detail=""):
        results.append(ok)
        print(f"  {'✓' if ok else '✗'} {what}" + (f": {detail}" if detail else ""))

    print(f"{os.path.basename(path)}: {len(faces):,} triangles, {len(verts):,} points")
    closed, bad = edge_check(faces)
    check("closed and watertight", closed, "every edge shared by two faces" if closed else f"{bad} bad edges")
    vol = mesh_volume(verts, faces)
    check("faces point outwards", vol > 0, f"{vol / 1000:.1f} cm³ solid")
    edges = {tuple(sorted(e)) for e in np.concatenate([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]]).tolist()}
    euler = len(verts) - len(edges) + len(faces)
    check("one piece, no holes through it", euler == 2, f"Euler characteristic {euler}")
    lo, hi = verts.min(0), verts.max(0)
    tri = verts[faces]
    n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    flat_down = (np.abs(tri[:, :, 2] - lo[2]).max(1) < 1e-6) & (n[:, 2] < 0)
    check("stands flat on the bed", flat_down.any() and abs(lo[2]) < 1e-6,
          f"base at z = {lo[2]:.3f}, {flat_down.sum()} faces on the bed")
    wall = np.abs(n[:, 2]) / np.maximum(np.linalg.norm(n, axis=1), 1e-12) < 0.999   # not a floor or the top
    lean = lean_angles(verts, faces[wall])
    check(f"no support needed (wall leans ≤ {limit:g}°)", lean.max() <= limit + 0.3,
          f"steepest {lean.max():.2f}° from upright, {np.mean(lean > limit - 5):.1%} of the wall within 5° of it")
    zs = np.arange(lo[2] + 0.5 * layer, hi[2] - 0.25 * layer, layer)
    counts = [loops(plane_cut(tri, tri[:, :, 2] - z)) for z in zs]
    wrong = [round(float(z), 2) for z, c in zip(zs, counts) if c != 1]
    check("every layer is one closed loop (spiral vase)", not wrong,
          f"{len(zs)} layers of {layer:g} mm" + (f"; not at {wrong[:5]}" if wrong else ""))
    print(f"  size {hi[0] - lo[0]:.1f} × {hi[1] - lo[1]:.1f} × {hi[2] - lo[2]:.1f} mm")
    return all(results)


def main(argv):
    limit = float(argv[argv.index("--limit") + 1]) if "--limit" in argv else 45.0
    layer = float(argv[argv.index("--layer") + 1]) if "--layer" in argv else 0.2
    files = [a for i, a in enumerate(argv) if a.lower().endswith(".stl") and argv[i - 1] not in ("--limit", "--layer")]
    good = [verify(f, limit, layer) for f in files]
    print(f"\n{sum(good)} of {len(good)} files ready for spiral vase printing")
    return 0 if all(good) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
