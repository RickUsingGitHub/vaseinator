"""Binary STL export, and a reader for the tests."""

from __future__ import annotations

import numpy as np

_RECORD = np.dtype([("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")])


def face_normals(verts: np.ndarray, faces: np.ndarray) -> np.ndarray:
    v0, v1, v2 = verts[faces[:, 0]], verts[faces[:, 1]], verts[faces[:, 2]]
    n = np.cross(v1 - v0, v2 - v0)
    ln = np.linalg.norm(n, axis=1, keepdims=True)
    ln[ln == 0] = 1.0
    return n / ln


def write_stl(path: str, verts: np.ndarray, faces: np.ndarray, name: str = "vase"):
    """Write a binary STL file (units: millimetres)."""
    rec = np.zeros(len(faces), dtype=_RECORD)
    rec["n"] = face_normals(verts, faces).astype(np.float32)
    rec["v"] = verts[faces].astype(np.float32)
    header = f"{name} - Vaseinator spiral vase (mm)".encode("ascii", "replace")[:80]
    with open(path, "wb") as fh:
        fh.write(header.ljust(80, b" "))
        fh.write(np.uint32(len(faces)).tobytes())
        fh.write(rec.tobytes())


def read_stl(path: str):
    """Read a binary STL back as (verts, faces), with coincident corners merged into one vertex."""
    with open(path, "rb") as fh:
        fh.read(80)
        count = int(np.frombuffer(fh.read(4), dtype="<u4")[0])
        rec = np.frombuffer(fh.read(count * _RECORD.itemsize), dtype=_RECORD)
    corners = rec["v"].reshape(-1, 3).astype(np.float64)
    verts, inverse = np.unique(corners, axis=0, return_inverse=True)
    return verts, inverse.reshape(-1, 3)
