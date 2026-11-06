"""Portable design tools shared by desktop and web; storage belongs to each UI."""

from __future__ import annotations

import copy
import json
import math
import uuid
from datetime import datetime, timezone
from html import escape

import numpy as np

from .params import VaseParams
from .presets import PRINTER_KEYS, surprise
from .shapes import pchip

LOCKS = {
    "Dimensions": ("height",),
    "Silhouette": ("profile", "silhouette"),
    "Cross-section": tuple(
        f"{key}{n}"
        for n in (1, 2)
        for key in ("shape", "count", "depth", "sharp", "turn", "drawn", "repeat")
    )
    + ("morph", "morph_swings", "morph_curve"),
    "Twist": ("twist", "twist_style", "swings", "twist_curve", "lattice"),
    "Colours": (
        "color1",
        "color2",
        "color3",
        "color4",
        "colour_style",
        "colours_used",
        "band_count",
        "band_spacing",
        "stripe_height",
        "gradient_length",
        "look",
    ),
}
MATERIAL_KEYS = ("max_flow", "density", "filament_d", "speed")
PROFILE_KEYS = {
    "printer": tuple(k for k in PRINTER_KEYS if k not in MATERIAL_KEYS),
    "material": MATERIAL_KEYS,
}


def locked_surprise(p, seed, locks):
    q = surprise(p, seed)
    width = max(v for _, v in p.silhouette)
    for group in locks:
        for key in LOCKS.get(group, ()):
            setattr(q, key, copy.deepcopy(getattr(p, key)))
    if "Dimensions" in locks:
        factor = width / max(v for _, v in q.silhouette)
        q.silhouette = [[h, v * factor] for h, v in q.silhouette]
    elif "Silhouette" in locks:
        # A locked silhouette includes its width, rather than distorting it.
        q.silhouette = copy.deepcopy(p.silhouette)
    return q


def thumbnail(p):
    """A portable silhouette thumbnail, explicitly a sketch rather than a render."""
    raw = np.asarray(p.silhouette, dtype=float)
    heights = np.linspace(0, 1, 50)
    points = list(zip(heights, pchip(raw[:, 0], raw[:, 1], heights)))
    width = max(v for _, v in points)
    right = [(60 + 42 * v / width, 112 - 104 * h) for h, v in points]
    left = [(120 - x, y) for x, y in reversed(right)]
    coords = " ".join(f"{x:.2f},{y:.2f}" for x, y in right + left)
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 120"><title>Silhouette sketch</title><polygon points="{coords}" fill="{escape(p.color1, quote=True)}" stroke="#888"/></svg>'


class Workspace:
    def __init__(self, data=None):
        self.data = {
            "format": "vaseinator-library",
            "version": 1,
            "designs": [],
            "profiles": [],
            "recovery": [],
            "locks": [],
        }
        if data is not None:
            if (
                not isinstance(data, dict)
                or data.get("format") != self.data["format"]
                or data.get("version") != 1
            ):
                raise ValueError("Not a supported Vaseinator library file.")
            for kind in ("designs", "profiles", "recovery"):
                entries = data.get(kind, [])
                if not isinstance(entries, list) or len(entries) > 500:
                    raise ValueError(
                        "A library may hold at most 500 entries per category."
                    )
                for entry in entries:
                    if not isinstance(entry, dict) or not isinstance(
                        entry.get("params"), dict
                    ):
                        raise ValueError("Invalid library entry.")
                    p = VaseParams.from_dict(entry["params"])
                    self.data[kind].append(
                        {
                            "id": str(entry.get("id") or uuid.uuid4()),
                            "name": str(entry.get("name", p.name))[:120],
                            "created": str(entry.get("created", "")),
                            "favorite": bool(entry.get("favorite", False)),
                            "kind": entry.get("kind", "printer")
                            if entry.get("kind") in PROFILE_KEYS
                            else "printer",
                            "params": p.to_dict(),
                        }
                    )
            self.data["locks"] = [k for k in data.get("locks", []) if k in LOCKS]
            self.data["recovery"] = self.data["recovery"][-30:]

    def entry(self, category, ident):
        return next(e for e in self.data[category] if e["id"] == ident)

    def add(self, category, p, name=None, kind="printer"):
        if category not in ("designs", "profiles", "recovery"):
            raise ValueError("Unknown library category.")
        if category != "recovery" and len(self.data[category]) >= 500:
            raise ValueError(
                "This category is full. Export a backup and remove an entry first."
            )
        if (
            category == "recovery"
            and self.data[category]
            and self.data[category][-1]["params"] == p.to_dict()
        ):
            return
        entry = dict(
            id=str(uuid.uuid4()),
            name=(name or p.name).strip()[:120] or "Untitled",
            created=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            favorite=False,
            kind=kind,
            params=p.to_dict(),
        )
        self.data[category].append(entry)
        if category == "recovery":
            self.data[category] = self.data[category][-30:]
        return entry

    def apply_profile(self, p, ident):
        entry = self.entry("profiles", ident)
        q = p.to_dict()
        q.update({k: entry["params"][k] for k in PROFILE_KEYS[entry["kind"]]})
        return VaseParams.from_dict(q)

    def merge(self, other):
        incoming = Workspace(other)
        for category in ("designs", "profiles", "recovery"):
            ids = {e["id"] for e in self.data[category]}
            additions = [e for e in incoming.data[category] if e["id"] not in ids]
            if (
                category != "recovery"
                and len(self.data[category]) + len(additions) > 500
            ):
                raise ValueError("The imported library would exceed 500 entries.")
        for category in ("designs", "profiles", "recovery"):
            ids = {e["id"] for e in self.data[category]}
            self.data[category].extend(
                e for e in incoming.data[category] if e["id"] not in ids
            )
        self.data["recovery"] = sorted(
            self.data["recovery"], key=lambda e: e["created"]
        )[-30:]
        self.data["locks"] = [
            k for k in LOCKS if k in self.data["locks"] or k in incoming.data["locks"]
        ]

    def dumps(self):
        return json.dumps(self.data, allow_nan=False)

    def command(self, op, p, payload=None):
        payload = payload or {}
        result = None
        if op == "locks":
            self.data["locks"] = [k for k in payload["locks"] if k in LOCKS]
        elif op == "save":
            self.add(
                payload["category"],
                p,
                payload.get("name"),
                payload.get("kind", "printer"),
            )
        elif op == "favorite":
            e = self.entry("designs", payload["id"])
            e["favorite"] = not e["favorite"]
        elif op == "delete":
            category = payload["category"]
            self.data[category] = [
                e for e in self.data[category] if e["id"] != payload["id"]
            ]
        elif op == "restore":
            category = payload["category"]
            result = (
                self.apply_profile(p, payload["id"])
                if category == "profiles"
                else VaseParams.from_dict(self.entry(category, payload["id"])["params"])
            )
        elif op == "import":
            self.merge(payload)
        elif op == "recover":
            self.add("recovery", p)
        elif op != "read":
            raise ValueError("Unknown library action.")
        return dict(
            workspace=self.data,
            params=result.to_dict() if result else None,
            locks=list(LOCKS),
            thumbnails={
                e["id"]: thumbnail(VaseParams.from_dict(e["params"]))
                for e in self.data["designs"]
            },
        )


def comparison(d):
    """Same original/final side envelope and movement values in both interfaces."""
    if d.errors:
        raise ValueError("; ".join(d.errors))
    if d.free:
        before = np.linalg.norm(d.P_design, axis=2)
        after = np.linalg.norm(d.P, axis=2)
        z = d.z
    else:
        before, after, z = d.R_design, d.R, d.z
    old, new = before.max(axis=1), after.max(axis=1)
    pick = np.unique(np.linspace(0, len(z) - 1, min(160, len(z))).astype(int))
    scale = 240 / max(float(old.max()), float(new.max()), 1)

    def line(values, side):
        return " ".join(
            f"{300 + side * float(values[i]) * scale:.2f},{330 - 300 * float(z[i]) / d.H:.2f}"
            for i in pick
        )

    paths = []
    for side in (-1, 1):
        for values, colour in ((old, "#008fa8"), (new, "#e88224")):
            paths.append(
                f'<polyline points="{line(values, side)}" fill="none" stroke="{colour}" stroke-width="2"/>'
            )
    for i in pick:
        if abs(old[i] - new[i]) > 0.05:
            y = 330 - 300 * float(z[i]) / d.H
            for side in (-1, 1):
                paths.append(
                    f'<path d="M{300 + side * old[i] * scale:.2f},{y:.2f} H{300 + side * new[i] * scale:.2f}" stroke="#e88224" opacity=".5"/>'
                )
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 360">'
        + "".join(paths)
        + "</svg>"
    )
    return dict(
        svg=svg,
        moved=float(d.softened),
        text="Blue: requested surface. Orange: softened surface. Side envelopes are shown; angular changes may overlap. Maximum surface movement: "
        + f"{d.softened:.2f} mm.",
    )


def calibration_parts():
    """Five closed sockets and matching pins; gaps are radial, in millimetres."""
    from .geometry import grid_side, fan, annulus, edge_check

    angles = np.arange(96) * 2 * math.pi / 96
    parts = []
    for k, gap in enumerate((0.1, 0.2, 0.3, 0.4, 0.5)):
        z = np.array([0.0, 3.0])
        v, f, _, first, last = grid_side(z, angles, np.full((2, 96), 8.0))
        vi, fi, _, a, b = grid_side(z, angles, np.full((2, 96), 5 + gap))
        n = len(v)
        faces = np.concatenate(
            [f, fi[:, ::-1] + n, annulus(last, b + n), annulus(first, a + n)[:, ::-1]]
        )
        verts = np.concatenate([v, vi])
        verts[:, 0] += (k - 2) * 19
        assert edge_check(faces)[0]
        parts.append(
            (
                f"Socket {k + 1}: radial gap {gap:.1f} mm",
                verts,
                faces,
                1,
                (0.1, 0.5, 0.6),
            )
        )
        v, f, _, a, b = grid_side(z, angles, np.full((2, 96), 5.0))
        n = len(v)
        v = np.concatenate([v, [[0, 0, 0], [0, 0, 3]]])
        f = np.concatenate([f, fan(n, a, False), fan(n + 1, b, True)])
        v[:, 0] += (k - 2) * 19
        v[:, 1] -= 20
        assert edge_check(f)[0]
        parts.append((f"Pin {k + 1}: 10 mm diameter", v, f, 1, (0.1, 0.5, 0.6)))
    return parts


CALIBRATION_HELP = (
    "Print all five socket-and-pin pairs with the material and settings intended for your design. "
    "Left to right: 0.1, 0.2, 0.3, 0.4 and 0.5 mm radial clearance (diametral gaps are twice these). "
    "Pins are 10 mm across; every piece is 3 mm tall. Try each pin in its socket. "
    "Choose the clearance that slides or grips as you need. This is a general fit test, not a lid-latch test; "
    "it does not automatically change the design. Keep the pairs in order when arranging them in the slicer."
)
