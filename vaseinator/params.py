"""Design parameters for a spiral vase, with JSON persistence."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields

FILE_FORMAT = "vaseinator"
FILE_VERSION = 1
FILAMENTS = (1, 2, 3, 4)

# cross-section shapes; SAME (for the top shape) keeps the bottom one all the way up
SAME, CIRCLE, POLYGON, STAR, FLOWER, GEAR, ELLIPSE, PEBBLE, DRAWN = -1, 0, 1, 2, 3, 4, 5, 6, 7
SHAPES = (CIRCLE, POLYGON, STAR, FLOWER, GEAR, ELLIPSE, PEBBLE, DRAWN)   # DRAWN: any outline, from points

# how something changes on the way up (the twist, the change of shape, the texture strength)
EVENLY, EASE, SPEED_UP, SLOW_DOWN, SWING, OWN = 0, 1, 2, 3, 4, 5
EVERYWHERE, GROWS, FADES, MIDDLE = 0, 1, 2, 3            # texture strength (OWN = own curve)
OWN_PROFILE = -1                                          # the outline has been drawn by hand

ONE_COLOUR, BANDS, STRIPES, GRADIENT = 0, 1, 2, 3         # how the colours go up the vase
REAL_VASE, FAKE_VASE = 0, 1                               # spiral vase mode, or an ordinary print with walls
NO_HOLES, VORONOI, ROUND, DIAMOND, SLOTS = 0, 1, 2, 3, 4  # holes right through the wall
NO_EYES, ALMOND_EYES, ROUND_EYES = 0, 1, 2                # a face: its eyes ...
NO_NOSE, RAISED_NOSE = 0, 1                               # ... its nose ...
NO_MOUTH, OPEN_MOUTH, GRILLE_MOUTH, CHIN_MOUTH = 0, 1, 2, 3   # ... and its mouth (CHIN: open down to the chin)
MATTE, SILK, GLOSSY, TRANSLUCENT = 0, 1, 2, 3             # how the filament looks in the 3D view

MAX_REPEAT = 100                                          # most copies of a drawn piece round the axis
MAX_BANDS = 64                                            # colour bands the 3D view can show


def _pts(*pairs):
    return field(default_factory=lambda: [list(p) for p in pairs])


# one lobe, from neck to neck: repeated five times round the axis it makes a five-lobed flower
FIVE_LOBES = ((0.42, -0.12, True), (0.62, -0.38, False), (0.95, -0.22, False), (0.95, 0.22, False),
              (0.62, 0.38, False), (0.42, 0.12, True))


@dataclass
class VaseParams:
    name: str = "lagoon_twist"

    # --- size ---------------------------------------------------------------
    height: float = 180.0
    profile: int = 0              # outline preset (shapes.PROFILES), or OWN_PROFILE once drawn by hand
    silhouette: list = _pts((0.0, 66.0), (0.36, 104.0), (0.8, 62.0), (1.0, 74.0))   # (height 0..1,
    #                               diameter mm) points, joined by a smooth curve that never overshoots

    # --- cross-section ------------------------------------------------------
    shape1: int = FLOWER          # the shape at the bottom
    count1: int = 7               # sides, points, petals, teeth (or the pebble's number)
    depth1: float = 0.16          # how far in the shape cuts, as a share of the radius
    sharp1: float = 0.45          # sharpness / corner rounding / petal shape / tooth width (0..1)
    turn1: float = 0.0            # turned round the axis (degrees)
    drawn1: list = field(default_factory=lambda: [list(p) for p in FIVE_LOBES])   # a drawn outline's
    #                               control points [x, y, cusp]; the axis is the origin
    repeat1: int = 5              # ... repeated this many times round the axis
    shape2: int = SAME            # the shape it turns into at the top
    count2: int = 5
    depth2: float = 0.0
    sharp2: float = 0.5
    turn2: float = 0.0
    drawn2: list = field(default_factory=lambda: [list(p) for p in FIVE_LOBES])
    repeat2: int = 5
    morph: int = EVENLY           # how the change of shape happens on the way up
    morph_swings: int = 3         # back and forth: how many changes (3: bottom, top, bottom, top shape)
    morph_curve: list = _pts((0.0, 0.0), (1.0, 1.0))

    # --- spin ---------------------------------------------------------------
    twist: float = 150.0          # degrees the shape turns from bottom to top
    twist_style: int = EASE
    swings: int = 3               # half-waves of a back-and-forth twist
    twist_curve: list = _pts((0.0, 0.0), (1.0, 150.0))    # (height, degrees) for an own twist
    lattice: bool = False         # twist both ways at once: a lattice of crossing ridges

    # --- surface ------------------------------------------------------------
    rib_count: int = 0            # ribs running up the vase (0 = none)
    rib_depth: float = 1.2        # mm out (+) or grooves in (-)
    rib_sharp: float = 0.3        # 0 smooth flutes ... 1 narrow ridges
    rib_lean: float = 0.0         # the ribs spiral this far round on top of the twist (degrees)
    rib_cross: bool = False       # a second set spirals the other way: diamond knurling
    ring_count: int = 0           # rings round the vase (0 = none)
    ring_depth: float = 1.0
    ring_sharp: float = 0.3
    bump_around: int = 0          # bumps round the vase (0 = none)
    bump_up: int = 8              # ... and up it
    bump_depth: float = 1.5
    organic_depth: float = 0.0    # smooth random lumps, in and out (mm, 0 = none)
    organic_scale: float = 22.0   # size of one lump (mm)
    organic_seed: int = 7
    texture_twist: bool = True    # the surface patterns turn with the twist
    strength: int = EVERYWHERE    # how strong the patterns are on the way up
    strength_curve: list = _pts((0.0, 1.0), (1.0, 1.0))
    fade_foot: float = 3.0        # patterns fade out over this much of the bottom (mm)
    fade_rim: float = 4.0         # ... and of the top

    # --- low-poly -----------------------------------------------------------
    facets: bool = False          # flat facets, like a cut gem
    facets_around: int = 14
    facets_up: int = 10
    facet_rough: float = 0.0      # 0 regular ... 1 rough cut
    facet_seed: int = 1

    # --- your own function --------------------------------------------------
    expression: str = ""          # mm added to the radius: f(theta, phi, z, h, r, H)

    # --- colours ------------------------------------------------------------
    color1: str = "#0E7C86"
    color2: str = "#3FC1C9"
    color3: str = "#F5F5F5"
    color4: str = "#FC5185"
    colour_style: int = BANDS
    colours_used: int = 3         # filaments the bands, stripes or gradient go through
    band_count: int = 3
    band_spacing: float = 0.0     # -1 bands thicker at the bottom ... 0 even ... 1 thicker at the top
    stripe_height: float = 12.0   # mm
    gradient_length: float = 8.0  # metres of filament for one colour cycle of a gradient spool
    look: int = SILK

    # --- holes and an open bottom (a normal print) ---------------------------
    holes: int = NO_HOLES         # holes right through the wall: Voronoi, round, diamonds, slots
    hole_size: float = 14.0       # from one hole to the next (mm)
    hole_strut: float = 3.0       # the wall left between holes (mm)
    hole_jitter: float = 0.7      # Voronoi: 0 a regular honeycomb ... 1 quite irregular
    hole_seed: int = 5
    hole_foot: float = 18.0       # solid wall kept at the foot, above the floor (mm)
    hole_rim: float = 12.0        # ... and at the rim
    open_bottom: bool = False     # no floor: open at both ends (a lampshade, a sleeve)
    closed_top: bool = False      # the top closes over in a point no steeper than the overhang limit
    around: float = 360.0         # how far round the wall goes (degrees): less for a mask

    # --- masks and helmets: a face at the front (-y), sizes and heights in mm --------------------
    worn: bool = False            # made for a head: sized by the head it fits
    eyes: int = NO_EYES
    eye_width: float = 34.0
    eye_height: float = 18.0
    eye_apart: float = 64.0       # between the eyes' middles, along the surface
    eye_up: float = 112.0         # the eyes' middles, from the bottom
    eye_tilt: float = 10.0        # the outer corners raised (degrees)
    nose: int = NO_NOSE
    nose_width: float = 30.0
    nose_length: float = 46.0     # from its tip up to between the eyes
    nose_depth: float = 14.0      # how far its tip stands out
    nose_up: float = 70.0         # its tip, from the bottom
    mouth: int = NO_MOUTH
    mouth_width: float = 44.0
    mouth_height: float = 14.0
    mouth_up: float = 40.0        # its middle (the top of an opening down to the chin), from the bottom
    mouth_slots: int = 5          # a grille's slots
    mouth_smile: float = 0.0      # ... its outer slots this much higher (mm): a smile
    straps: bool = False          # a slot each side for an elastic strap
    strap_up: float = 112.0

    # --- printing -----------------------------------------------------------
    vase_mode: int = FAKE_VASE    # real: spiral vase mode, one solid, one colour (slicers won't change
    #                               filament in it); fake: an ordinary print with walls, the colour
    #                               bands as parts of their own filaments
    walls: int = 2                # fake vase: walls round the vase
    max_overhang: float = 45.0    # steepest lean of the wall from upright, either way (degrees)
    soften: bool = True           # soften anything steeper until it prints without supports
    line_width: float = 0.6       # the slicer's spiral wall line width: the printed wall
    layer_height: float = 0.2
    bottom: float = 1.2           # solid bottom the slicer prints first (mm)
    printer_height: float = 250.0
    bed_x: float = 256.0
    bed_y: float = 256.0
    speed: float = 40.0           # spiral wall speed (mm/s)
    max_flow: float = 12.0        # the hot end's flow limit (mm³/s)
    filament_d: float = 1.75
    density: float = 1.24         # g/cm³ (PLA 1.24, PETG 1.27)
    facet_size: float = 0.7       # mesh detail: spacing of the points on the surface (mm)

    # ---------------------------------------------------------------- utils
    def copy(self) -> "VaseParams":
        return VaseParams.from_dict(self.to_dict())

    def to_dict(self) -> dict:
        return asdict(self)

    def colors(self) -> dict:
        """Filament number -> (r, g, b) in 0..1."""
        return {k: hex_to_rgb(getattr(self, f"color{k}")) for k in FILAMENTS}

    @classmethod
    def from_dict(cls, d: dict) -> "VaseParams":
        p = cls()
        fresh = cls()
        for f in fields(cls):
            if f.name not in d:
                continue
            cur, v = getattr(p, f.name), d[f.name]
            try:
                if isinstance(cur, bool):
                    v = bool(v)
                elif isinstance(cur, int):
                    v = int(v)
                elif isinstance(cur, float):
                    v = float(v)
                elif isinstance(cur, list):
                    v = clean_outline(v) if f.name in ("drawn1", "drawn2") else clean_curve(v)
                    if v is None:
                        continue
                else:
                    v = str(v)
            except (TypeError, ValueError):
                continue
            setattr(p, f.name, v)
        allowed = {"shape1": SHAPES, "shape2": (SAME,) + SHAPES,
                   "morph": (EVENLY, EASE, SPEED_UP, SLOW_DOWN, SWING, OWN),
                   "twist_style": (EVENLY, EASE, SPEED_UP, SLOW_DOWN, SWING, OWN),
                   "strength": (EVERYWHERE, GROWS, FADES, MIDDLE, OWN),
                   "colour_style": (ONE_COLOUR, BANDS, STRIPES, GRADIENT), "colours_used": (1, 2, 3, 4),
                   "look": (MATTE, SILK, GLOSSY, TRANSLUCENT), "vase_mode": (REAL_VASE, FAKE_VASE),
                   "holes": (NO_HOLES, VORONOI, ROUND, DIAMOND, SLOTS),
                   "eyes": (NO_EYES, ALMOND_EYES, ROUND_EYES), "nose": (NO_NOSE, RAISED_NOSE),
                   "mouth": (NO_MOUTH, OPEN_MOUTH, GRILLE_MOUTH, CHIN_MOUTH)}
        for key, values in allowed.items():
            if getattr(p, key) not in values:
                setattr(p, key, getattr(fresh, key))
        if any(d <= 0 for _, d in p.silhouette):
            p.silhouette = fresh.silhouette
        p.walls = min(max(p.walls, 1), 10)
        p.repeat1, p.repeat2 = (min(max(r, 1), MAX_REPEAT) for r in (p.repeat1, p.repeat2))
        p.mouth_slots = min(max(p.mouth_slots, 1), 40)
        for key, lo, hi in (("depth1", 0.0, 0.9), ("depth2", 0.0, 0.9), ("sharp1", 0.0, 1.0),
                            ("sharp2", 0.0, 1.0), ("rib_sharp", 0.0, 1.0), ("ring_sharp", 0.0, 1.0),
                            ("facet_rough", 0.0, 1.0), ("band_spacing", -1.0, 1.0), ("hole_jitter", 0.0, 1.0),
                            ("hole_size", 3.0, 200.0), ("hole_strut", 0.8, 50.0), ("hole_foot", 0.0, 2000.0),
                            ("hole_rim", 0.0, 2000.0), ("around", 30.0, 360.0), ("eye_width", 2.0, 400.0),
                            ("eye_height", 2.0, 400.0), ("eye_apart", 0.0, 2000.0), ("eye_tilt", -80.0, 80.0),
                            ("nose_width", 2.0, 400.0), ("nose_length", 2.0, 1000.0), ("nose_depth", 0.0, 100.0),
                            ("mouth_width", 2.0, 1000.0), ("mouth_height", 2.0, 400.0),
                            ("mouth_smile", -400.0, 400.0)):
            setattr(p, key, min(max(getattr(p, key), lo), hi))
        for k in FILAMENTS:
            try:
                hex_to_rgb(getattr(p, f"color{k}"))
            except ValueError:
                setattr(p, f"color{k}", getattr(fresh, f"color{k}"))
        return p


def face_holes(p: VaseParams) -> bool:
    """Whether the face has holes of its own: eyes, a mouth or strap slots."""
    return p.eyes != NO_EYES or p.mouth != NO_MOUTH or p.straps


def needs_normal(p: VaseParams) -> bool:
    """Whether the wall is cut open - holes, an open bottom, part way round - so it must be printed normally:
    spiral vase mode prints one closed line a layer."""
    return p.holes != NO_HOLES or p.open_bottom or p.around < 360.0 or face_holes(p)


def colour_style_of(p: VaseParams) -> int:
    """The colour style that really prints: a real spiral vase is one filament, so no bands or stripes."""
    if p.vase_mode == REAL_VASE and p.colour_style in (BANDS, STRIPES):
        return ONE_COLOUR
    return p.colour_style


def clean_outline(points):
    """A drawn outline's control points made safe: [[x, y, cusp], ...], at least three; None if unusable."""
    try:
        out = [[float(p[0]), float(p[1]), bool(p[2]) if len(p) > 2 else False] for p in points]
    except (TypeError, ValueError, IndexError):
        return None
    out = [p for p in out if all(map(lambda c: abs(c) < 1e6, p[:2]))]
    return out if len(out) >= 3 else None


def clean_curve(points):
    """A curve's points made safe: [[h, v], ...] sorted, from h = 0 to h = 1, at least two.

    Returns None if there is nothing usable.
    """
    try:
        pts = sorted((min(max(float(h), 0.0), 1.0), float(v)) for h, v in points)
    except (TypeError, ValueError):
        return None
    out = []
    for h, v in pts:
        if out and h - out[-1][0] < 0.005:     # two points at one height: keep the later one
            out[-1] = [out[-1][0], v]
        else:
            out.append([h, v])
    if len(out) < 2:
        return None
    out[0][0], out[-1][0] = 0.0, 1.0
    if out[-1][0] - out[-2][0] < 0.005 and len(out) > 2:
        del out[-2]
    return out


def hex_to_rgb(text: str):
    """'#RRGGBB' -> (r, g, b) in 0..1."""
    t = text.strip().lstrip("#")
    if len(t) != 6:
        raise ValueError(f"not a colour: {text!r}")
    return tuple(int(t[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def save_design(path: str, params: VaseParams):
    data = {"format": FILE_FORMAT, "version": FILE_VERSION, "params": params.to_dict()}
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)


def load_design(path: str) -> VaseParams:
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if data.get("format") != FILE_FORMAT:
        raise ValueError("Not a Vaseinator design file")
    return VaseParams.from_dict(data.get("params", {}))
