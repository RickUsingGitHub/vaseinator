"""The choices Simple mode offers as pictures - shared by the desktop app and the web page.

Each picture sets a few settings at once; ``pattern_of`` says which pattern
picture a vase is, so that one can be lit.
"""

from __future__ import annotations

from .params import (BANDS, CIRCLE, DRAWN, ELLIPSE, FAKE_VASE, FLOWER, GEAR, NO_HOLES, PEBBLE, POLYGON, ROUND, STAR,
                     STRIPES, VORONOI)

# the shape from above: (name, the settings it sets)
SHAPES_FROM_ABOVE = [
    ("Round", dict(shape1=CIRCLE)),
    ("Square", dict(shape1=POLYGON, count1=4, sharp1=0.35, turn1=45.0)),
    ("Hexagon", dict(shape1=POLYGON, count1=6, sharp1=0.3)),
    ("Star", dict(shape1=STAR, count1=5, depth1=0.35, sharp1=0.6)),
    ("Flower", dict(shape1=FLOWER, count1=6, depth1=0.18, sharp1=0.45)),
    ("Cog", dict(shape1=GEAR, count1=14, depth1=0.12, sharp1=0.5)),
    ("Oval", dict(shape1=ELLIPSE, depth1=0.3)),
    ("Pebble", dict(shape1=PEBBLE, count1=3, depth1=0.2)),
]

# the patterns: (name, the settings it sets); each starts from no pattern at all
NO_PATTERN = dict(rib_count=0, rib_lean=0.0, rib_cross=False, ring_count=0, bump_around=0, organic_depth=0.0,
                  facets=False, holes=NO_HOLES)
PATTERNS = [
    ("Smooth", {}),
    ("Ribs", dict(rib_count=24, rib_depth=1.2, rib_sharp=0.3)),
    ("Spiral ribs", dict(rib_count=24, rib_depth=1.2, rib_sharp=0.4, rib_lean=180.0)),
    ("Rings", dict(ring_count=10, ring_depth=1.2, ring_sharp=0.3)),
    ("Bumps", dict(bump_around=14, bump_up=12, bump_depth=1.6)),
    ("Diamonds", dict(rib_count=36, rib_depth=0.9, rib_sharp=0.6, rib_lean=360.0, rib_cross=True)),
    ("Lumpy", dict(organic_depth=2.0, organic_scale=22.0)),
    ("Gem", dict(facets=True, facets_around=14, facets_up=10, facet_rough=0.2)),
    ("Voronoi holes", dict(holes=VORONOI, hole_size=14.0, hole_strut=3.0, hole_jitter=0.7, vase_mode=FAKE_VASE)),
    ("Round holes", dict(holes=ROUND, hole_size=12.0, hole_strut=3.0, vase_mode=FAKE_VASE)),
]

COLOURS = [("White", "#F5F5F5"), ("Black", "#1A1A1A"), ("Grey", "#8D99AE"), ("Red", "#D62828"),
           ("Orange", "#F77F00"), ("Yellow", "#FCBF49"), ("Green", "#2A9D8F"), ("Lime", "#80B918"),
           ("Blue", "#457B9D"), ("Navy", "#1D3557"), ("Purple", "#7B2CBF"), ("Pink", "#FC5185")]
MANY_COLOURS = [("Bands", "Sunset", dict(colour_style=BANDS, band_count=3, colours_used=3, vase_mode=FAKE_VASE)),
                ("Stripes", "Candy", dict(colour_style=STRIPES, stripe_height=12.0, colours_used=3,
                                          vase_mode=FAKE_VASE))]


def twist_words(deg: float) -> str:
    d = abs(deg)
    words = {0: "No twist", 90: "A quarter turn", 180: "Half a turn", 270: "Three quarters of a turn",
             360: "A whole turn", 720: "Two whole turns"}
    for k, w in words.items():
        if abs(d - k) < 0.5:
            return w
    return f"{deg:.0f}°"


def pattern_of(p) -> int | None:
    """Which pattern picture a vase's surface is, if any."""
    if p.expression.strip():
        return None
    names = [n for n, _ in PATTERNS]
    if p.holes == VORONOI:
        return names.index("Voronoi holes")
    if p.holes == ROUND:
        return names.index("Round holes")
    if p.holes != NO_HOLES:
        return None
    if p.facets and DRAWN not in (p.shape1, p.shape2):
        return names.index("Gem")
    if p.organic_depth > 0:
        return names.index("Lumpy")
    if p.bump_around > 0:
        return names.index("Bumps")
    if p.rib_count > 0:
        if p.rib_cross and p.rib_lean != 0:
            return names.index("Diamonds")
        return names.index("Spiral ribs" if p.rib_lean != 0 else "Ribs")
    if p.ring_count > 0:
        return names.index("Rings")
    return names.index("Smooth")
