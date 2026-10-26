"""Ready-made vases, and Surprise me: a new random vase that still prints."""

from __future__ import annotations

import random

from .expr import EXAMPLES
from .params import (BANDS, CIRCLE, EASE, ELLIPSE, EVENLY, EVERYWHERE, FADES, FLOWER, GEAR, GLOSSY,
                     GRADIENT, GROWS, MATTE, MIDDLE, ONE_COLOUR, PEBBLE, POLYGON, SAME, SILK,
                     SLOW_DOWN, SPEED_UP, STAR, STRIPES, SWING, TRANSLUCENT, VaseParams)
from .shapes import PALETTES, PROFILES

# the settings that belong to the printer, not the design: kept when a design is swapped
PRINTER_KEYS = ("line_width", "layer_height", "bottom", "printer_height", "bed_x", "bed_y", "speed",
                "max_flow", "filament_d", "density", "facet_size", "max_overhang")


def outline(profile: int, widest: float):
    """The points of an outline preset, for a vase this wide."""
    return [[h, round(f * widest, 2)] for h, f in PROFILES[profile][1]]


def palette(name: str) -> dict:
    cols = dict(PALETTES)[name]
    return {f"color{k + 1}": c for k, c in enumerate(cols)}


def slug(text: str) -> str:
    keep = "".join(ch.lower() if ch.isalnum() else "_" for ch in text)
    while "__" in keep:
        keep = keep.replace("__", "_")
    return keep.strip("_")[:40] or "vase"


def _profile(i, widest):
    return dict(profile=i, silhouette=outline(i, widest))


GALLERY = [
    ("Lagoon Twist", "Seven petals turning as they rise, in three bands of colour.", {}),
    ("Twisted Hexagon", "A softened hexagon that turns a third of the way round. Gold silk.",
     dict(shape1=POLYGON, count1=6, sharp1=0.25, twist=120, twist_style=EVENLY, colour_style=ONE_COLOUR,
          color1="#C9A227", look=SILK)),
    ("Lattice Lantern", "An octagon twisted both ways at once: a lattice of crossing ridges.",
     dict(**_profile(4, 100), height=170, shape1=POLYGON, count1=8, sharp1=0.05, lattice=True, twist=100,
          twist_style=EVENLY, colour_style=BANDS, band_count=3, colours_used=3, look=GLOSSY, **palette("Ember"))),
    ("Ocean Ripple", "Rings like ripples over a gently lumpy wall, on a gradient spool.",
     dict(**_profile(2, 104), shape1=CIRCLE, ring_count=14, ring_depth=1.3, ring_sharp=0.2, organic_depth=0.8,
          organic_scale=30, twist=0, colour_style=GRADIENT, colours_used=4, gradient_length=4.0, look=SILK,
          **palette("Glacier"))),
    ("Tulip Bloom", "Six petals at the foot opening out into a round rim.",
     dict(**_profile(6, 104), shape1=FLOWER, count1=6, depth1=0.28, sharp1=0.25, shape2=CIRCLE, morph=SLOW_DOWN,
          twist=60, twist_style=EASE, colour_style=BANDS, band_count=2, colours_used=2, band_spacing=0.6,
          color1="#FF70A6", color2="#FFFFFF", look=SILK)),
    ("Gem Facets", "Low-poly facets with a slightly rough cut, like a cut stone.",
     dict(shape1=CIRCLE, facets=True, facets_around=12, facets_up=9, facet_rough=0.25, twist=60,
          twist_style=EVENLY, colour_style=ONE_COLOUR, color1="#7B2CBF", look=GLOSSY)),
    ("Coral Reef", "A lumpy pebble shape covered in organic bumps.",
     dict(**_profile(10, 104), shape1=PEBBLE, count1=12, depth1=0.3, organic_depth=3.0, organic_scale=16,
          twist=0, colour_style=GRADIENT, colours_used=3, gradient_length=6.0, look=MATTE, **palette("Sunset"))),
    ("Spiral Ribs", "Thirty ribs winding three quarters of the way round a bottle.",
     dict(**_profile(9, 96), height=200, shape1=CIRCLE, rib_count=30, rib_depth=1.6, rib_sharp=0.4,
          rib_lean=270, twist=0, colour_style=ONE_COLOUR, color1="#E9C46A", look=SILK)),
    ("Knurled Tumbler", "Diamond knurling from two sets of ribs spiralling opposite ways.",
     dict(profile=-1, silhouette=[[0.0, 84.0], [1.0, 92.0]], height=120, shape1=CIRCLE, rib_count=28,
          rib_depth=1.1, rib_sharp=0.15, rib_lean=140, rib_cross=True, twist=0, fade_rim=6.0,
          colour_style=ONE_COLOUR, color1="#2B2D42", look=MATTE)),
    ("Gear Tower", "Gear teeth swinging back and forth, in stripes of gold and black.",
     dict(profile=-1, silhouette=[[0.0, 90.0], [1.0, 74.0]], height=200, shape1=GEAR, count1=14, depth1=0.08,
          sharp1=0.5, twist=24, twist_style=SWING, swings=2, colour_style=STRIPES, stripe_height=20.0,
          colours_used=2, look=GLOSSY, **palette("Gold and black"))),
    ("Star to Moon", "A five-pointed star that turns and melts into a circle.",
     dict(**_profile(5, 104), shape1=STAR, count1=5, depth1=0.35, sharp1=0.7, shape2=CIRCLE, morph=EASE,
          twist=144, twist_style=SLOW_DOWN, colour_style=BANDS, band_count=4, colours_used=4,
          band_spacing=-0.3, look=SILK, **palette("Neon"))),
    ("Pentagon Pulse", "Circle, pentagon, circle, pentagon: the shape changes back and forth up the vase.",
     dict(profile=-1, silhouette=[[0.0, 82.0], [0.5, 96.0], [1.0, 84.0]], shape1=CIRCLE, shape2=POLYGON, count2=5,
          sharp2=0.08, morph=SWING, morph_swings=3, twist=36, twist_style=EVENLY, colour_style=ONE_COLOUR,
          color1="#457B9D", look=SILK)),
    ("Bubble Wrap", "Rows of soft bumps, in a translucent filament.",
     dict(**_profile(4, 100), shape1=CIRCLE, bump_around=14, bump_up=12, bump_depth=1.8, twist=0,
          colour_style=ONE_COLOUR, color1="#90E0EF", look=TRANSLUCENT)),
    ("Pagoda Rings", "A rounded square with deep rings, turning more slowly as it rises.",
     dict(**_profile(3, 104), shape1=POLYGON, count1=4, sharp1=0.45, ring_count=7, ring_depth=2.5,
          ring_sharp=0.55, twist=90, twist_style=SLOW_DOWN, colour_style=BANDS, band_count=7, colours_used=2,
          look=GLOSSY, color1="#9D0208", color2="#1A1A1A")),
    ("Hourglass Weave", "Ten petals twisted both ways round an hourglass.",
     dict(**_profile(7, 100), shape1=FLOWER, count1=10, depth1=0.12, sharp1=0.5, lattice=True, twist=120,
          twist_style=EVENLY, colour_style=BANDS, band_count=2, colours_used=2, look=SILK, **palette("Forest"))),
    ("Math Waves", "Your own function: waves winding round the vase.",
     dict(profile=-1, silhouette=[[0.0, 80.0], [0.5, 92.0], [1.0, 80.0]], shape1=CIRCLE, twist=0,
          expression="1.5 * sin(6*theta + 4*pi*h)", colour_style=GRADIENT, colours_used=4, gradient_length=5.0,
          look=SILK, **palette("Rainbow"))),
    ("Organic Bark", "Your own function: rough bark from layered noise.",
     dict(shape1=PEBBLE, count1=3, depth1=0.2, twist=0, expression=dict(EXAMPLES)["Bark"],
          colour_style=ONE_COLOUR, color1="#6B4F3A", look=MATTE)),
]


def gallery_design(name: str, keep: VaseParams | None = None) -> VaseParams:
    """A ready-made vase, with the printer settings of ``keep``."""
    for title, _, changes in GALLERY:
        if title == name:
            p = VaseParams(**{"name": slug(title), **changes})
            if keep is not None:
                for k in PRINTER_KEYS:
                    setattr(p, k, getattr(keep, k))
            return p.copy()
    raise KeyError(name)


ADJECTIVES = ["Twisted", "Velvet", "Molten", "Crystal", "Whispering", "Electric", "Hollow", "Lunar", "Coral",
              "Spiral", "Rippled", "Frozen", "Golden", "Wild", "Dancing", "Secret", "Sleepy", "Cosmic",
              "Tidal", "Ancient"]
NOUNS = ["Lagoon", "Spire", "Bloom", "Lantern", "Tide", "Ember", "Orchid", "Comet", "Totem", "Nebula",
         "Chalice", "Reef", "Cascade", "Vortex", "Fern", "Prism", "Urn", "Geode", "Siren", "Thistle"]


def surprise(keep: VaseParams, seed: int) -> VaseParams:
    """A new random vase, made to fit the printer of ``keep``; softening stays on, so it always prints."""
    rng = random.Random(seed)
    p = VaseParams()
    for k in PRINTER_KEYS:
        setattr(p, k, getattr(keep, k))
    p.soften = True
    p.name = slug(f"{rng.choice(ADJECTIVES)} {rng.choice(NOUNS)}")
    tallest = max(60.0, min(240.0, p.printer_height - 5.0))
    p.height = float(rng.randrange(int(min(110, tallest)), int(tallest) + 1, 5))
    widest = rng.uniform(70.0, max(72.0, min(135.0, min(p.bed_x, p.bed_y) - 12.0)))
    prof = rng.randrange(len(PROFILES))
    p.profile = prof
    pts = outline(prof, widest)
    for q in pts[1:-1]:
        q[1] = round(q[1] * rng.uniform(0.93, 1.06), 2)
    p.silhouette = pts

    def shape(k):
        kind = rng.choices([CIRCLE, POLYGON, STAR, FLOWER, GEAR, ELLIPSE, PEBBLE], [2, 3, 2, 3, 1, 1, 1])[0]
        count = {POLYGON: rng.randint(3, 9), STAR: rng.randint(4, 10), FLOWER: rng.randint(3, 12),
                 GEAR: rng.randint(8, 24), PEBBLE: rng.randint(1, 99)}.get(kind, 5)
        depth = {STAR: rng.uniform(0.12, 0.35), FLOWER: rng.uniform(0.08, 0.3), GEAR: rng.uniform(0.04, 0.12),
                 ELLIPSE: rng.uniform(0.15, 0.4), PEBBLE: rng.uniform(0.1, 0.3)}.get(kind, 0.0)
        setattr(p, f"shape{k}", kind)
        setattr(p, f"count{k}", count)
        setattr(p, f"depth{k}", round(depth, 3))
        setattr(p, f"sharp{k}", round(rng.uniform(0.05, 0.8), 2))
        setattr(p, f"turn{k}", float(rng.choice([0, 0, 15, 30, 45])))

    shape(1)
    if rng.random() < 0.45:
        shape(2)
        p.morph = rng.choice([EVENLY, EASE, SPEED_UP, SLOW_DOWN])
    else:
        p.shape2 = SAME
    if rng.random() < 0.3:
        p.twist = 0.0
    else:
        p.twist = float(rng.choice([45, 60, 90, 120, 150, 180, 240, 360])) * rng.choice([-1, 1])
        p.twist_style = rng.choices([EVENLY, EASE, SPEED_UP, SLOW_DOWN, SWING], [3, 3, 1, 1, 1])[0]
        if p.twist_style == SWING:
            p.swings = rng.randint(1, 4)
            p.twist = abs(p.twist) * 0.4
        p.lattice = rng.random() < 0.18
    p.rib_count = p.ring_count = p.bump_around = 0
    p.organic_depth = 0.0
    for kind in rng.sample(["ribs", "rings", "bumps", "organic"], rng.choices([0, 1, 2], [3, 4, 2])[0]):
        if kind == "ribs":
            p.rib_count = rng.randint(8, 48)
            p.rib_depth = round(rng.uniform(0.6, 2.0) * rng.choice([1, 1, -1]), 2)
            p.rib_sharp = round(rng.uniform(0.0, 0.7), 2)
            p.rib_lean = float(rng.choice([0, 0, 60, 120, 180, 270, 360]) * rng.choice([-1, 1]))
            p.rib_cross = rng.random() < 0.25 and p.rib_lean != 0
        elif kind == "rings":
            p.ring_count = rng.randint(3, 16)
            p.ring_depth = round(rng.uniform(0.5, 1.6), 2)
            p.ring_sharp = round(rng.uniform(0.0, 0.6), 2)
        elif kind == "bumps":
            p.bump_around = rng.randint(6, 20)
            p.bump_up = rng.randint(4, 14)
            p.bump_depth = round(rng.uniform(0.8, 2.0), 2)
        else:
            p.organic_depth = round(rng.uniform(1.0, 3.5), 2)
            p.organic_scale = round(rng.uniform(10.0, 35.0), 1)
            p.organic_seed = rng.randint(1, 999)
    p.strength = rng.choices([EVERYWHERE, GROWS, FADES, MIDDLE], [5, 1, 1, 1])[0]
    p.facets = rng.random() < 0.12
    if p.facets:
        p.facets_around = rng.randint(8, 24)
        p.facets_up = rng.randint(5, 16)
        p.facet_rough = round(rng.uniform(0.0, 0.5), 2)
        p.facet_seed = rng.randint(1, 999)
    p.expression = rng.choice(EXAMPLES)[1] if rng.random() < 0.08 else ""
    for k, v in palette(rng.choice(PALETTES)[0]).items():
        setattr(p, k, v)
    p.colour_style = rng.choices([ONE_COLOUR, BANDS, STRIPES, GRADIENT], [3, 3, 1, 2])[0]
    p.colours_used = rng.randint(2, 4)
    p.band_count = rng.randint(2, 6)
    p.band_spacing = round(rng.uniform(-0.6, 0.6), 2)
    p.stripe_height = float(rng.randrange(6, 22, 2))
    p.gradient_length = float(rng.randrange(3, 13))
    p.look = rng.choices([SILK, MATTE, GLOSSY, TRANSLUCENT], [3, 2, 1, 1])[0]
    return p.copy()
