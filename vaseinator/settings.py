"""Every setting the Advanced panel shows, the rules for which are shown, and what a change brings with it.

Shared by the desktop app and the web version, so both behave alike. Nothing here needs Qt.
"""

from __future__ import annotations

from . import sections
from .params import (ALMOND_EYES, BANDS, CHIN_MOUTH, CIRCLE, DIAMOND, DRAWN, EASE, ELLIPSE, EVENLY, FAKE_VASE, GLOSSY,
                     GRADIENT, GRILLE_MOUTH, MATTE, NO_EYES, NO_HOLES, NO_MOUTH, NO_NOSE, ONE_COLOUR, OPEN_MOUTH, OWN,
                     OWN_PROFILE, PEBBLE, RAISED_NOSE, REAL_VASE, ROUND, ROUND_EYES, SAME, SHAPES, SILK, SLOTS,
                     SLOW_DOWN, SPEED_UP, STRIPES, SWING, TRANSLUCENT, VORONOI, VaseParams, colour_style_of,
                     needs_normal)
from .presets import outline
from .shapes import (PROFILES, SHAPE_LABELS, SHAPE_NAMES, change as change_of, progress, sample_points, shape_table,
                     strength, strength_names, style_names)

PROFILE_CHOICES = [(i, name) for i, (name, _) in enumerate(PROFILES)] + [(OWN_PROFILE, "Your own (drawn below)")]
SHAPE_CHOICES = [(k, SHAPE_NAMES[k]) for k in SHAPES]
TWIST_STYLES = list(style_names().items())
MORPH_STYLES = [(EVENLY, "Evenly"), (EASE, "Eases in and out"), (SLOW_DOWN, "Mostly near the bottom"),
                (SPEED_UP, "Mostly near the top"), (SWING, "Back and forth"), (OWN, "Your own curve")]
STRENGTHS = list(strength_names().items())
COLOUR_STYLES = [(ONE_COLOUR, "One colour"), (BANDS, "Bands up the vase"), (STRIPES, "Stripes"),
                 (GRADIENT, "Gradient spool")]
LOOKS = [(MATTE, "Matte"), (SILK, "Silk"), (GLOSSY, "Glossy"), (TRANSLUCENT, "Translucent")]
VASE_MODES = [(FAKE_VASE, "Normal print - walls, any colours"),
              (REAL_VASE, "Seamless - spiral vase mode, one colour")]
REAL_COLOUR_STYLES = [(ONE_COLOUR, "One colour"), (GRADIENT, "Gradient spool")]
USED = [(2, "Two"), (3, "Three"), (4, "Four")]
HOLE_CHOICES = [(NO_HOLES, "None"), (VORONOI, "Voronoi"), (ROUND, "Round holes"), (DIAMOND, "Diamonds"),
                (SLOTS, "Slots")]
EYE_CHOICES = [(NO_EYES, "None"), (ALMOND_EYES, "Almond"), (ROUND_EYES, "Round")]
NOSE_CHOICES = [(NO_NOSE, "None"), (RAISED_NOSE, "Raised")]
MOUTH_CHOICES = [(NO_MOUTH, "None"), (OPEN_MOUTH, "Open"), (GRILLE_MOUTH, "A grille of slots"),
                 (CHIN_MOUTH, "Open down to the chin")]


def _shape(k: int) -> tuple:
    """The settings of the bottom (1) or top (2) cross-section."""
    first = k == 1
    return [
        (f"shape{k}", "Cross-section" if first else "Turns into", "choice",
         SHAPE_CHOICES if first else [(SAME, "Stays the same")] + SHAPE_CHOICES, None, None, "",
         "The shape of the vase seen from above, at the bottom." if first else
         "A second shape that the first one turns into on the way up - or the same shape all the way.\n"
         "Drawn: any outline you like, drawn with smooth points and sharp corners - lobes that bulge\n"
         "out past their necks, lopsided shapes, shapes off the middle."),
        (f"drawn{k}", "", "outline", None, None, None, "",
         "The outline, seen from above. The middle is the vase's axis; the dashed circle is its widest\n"
         "(the outline is scaled so its furthest point touches it). Drag the points; double-click the\n"
         "line to add one, double-click a point to make it a sharp corner or smooth again, right-click\n"
         "a point to take it away. A red outline crosses itself and can't be built."),
        (f"repeat{k}", "Repeat around", "int", 1, 100, 1, "",
         "Draw one piece - one lobe, one petal - and repeat it this many times round the axis.\n"
         "1: the whole outline is drawn, and can be lopsided."),
        (f"count{k}", "Sides", "int", 1, 99, 1, "", "How many sides, points, petals or teeth."),
        (f"depth{k}", "Depth", "pct", 0.0, 90.0, 1.0, " %",
         "How far in the shape cuts between its points or petals, as a share of the radius."),
        (f"sharp{k}", "Sharpness", "pct", 0.0, 100.0, 5.0, " %",
         "Polygon: how round the corners are. Star: from soft waves to sharp points.\n"
         "Flower: from fat round petals to narrow ones. Gear: how wide the teeth are."),
        (f"turn{k}", "Turned", "float", -180.0, 180.0, 5.0, "°", "Turn the shape round the axis."),
    ]


# (key, label, kind, min, max, step, suffix/special, tooltip)
SPEC = [
    ("Size", [
        ("height", "Height", "float", 5.0, 1000.0, 5.0, " mm", "Height of the vase, from the bed to the rim."),
        ("widest", "Widest", "widest", 4.0, 1000.0, 5.0, " mm",
         "Diameter at the widest point of the outline. Changing it scales the whole outline;\n"
         "shapes and patterns add to it."),
        ("profile", "Outline", "choice", PROFILE_CHOICES, None, None, "",
         "The shape of the vase from the side. Pick one to start from, then drag its points\n"
         "in the curve below (Detailed) to make it your own."),
        ("silhouette", "", "curve", dict(lo=0.0, hi=140.0, unit=" mm", mirror=True, height=170, floor=4.0,
                                          grow=True, decimals=0), None, None, "",
         "The outline: diameter at each height. Drag the points; double-click to add one,\n"
         "right-click to take one away. The curve through them never overshoots."),
    ]),
    ("Shape", _shape(1) + _shape(2) + [
        ("morph", "Change happens", "choice", MORPH_STYLES, None, None, "",
         "How the first shape turns into the second on the way up. Back and forth changes\n"
         "smoothly to the second shape and back again, as many times as you like."),
        ("morph_swings", "Changes", "int", 1, 40, 1, "",
         "How many times the shape changes on the way up, back and forth.\n"
         "3: bottom shape → top shape → bottom shape → top shape."),
        ("morph_curve", "", "curve", dict(lo=0.0, hi=1.0, unit="", height=110, decimals=2), None, None, "",
         "How far the shape has changed at each height, from the bottom of the vase on the left to the\n"
         "top on the right: 0 (down) is the bottom shape, 1 (up) the top one. Drag a point down to\n"
         "go back towards the bottom shape; double-click to add points for a wave."),
    ]),
    ("Spin", [
        ("twist", "Twist", "float", -3600.0, 3600.0, 15.0, "°",
         "How far the shape turns round from the bottom to the top. A back-and-forth twist\n"
         "swings this far each way."),
        ("twist_style", "Twist goes", "choice", TWIST_STYLES, None, None, "",
         "How the turning is spread up the vase: evenly, easing in and out, speeding up,\n"
         "slowing down, swinging back and forth, or along your own curve."),
        ("swings", "Swings", "int", 1, 40, 1, "", "How many times a back-and-forth twist changes direction."),
        ("twist_curve", "", "curve", dict(lo=-180.0, hi=180.0, unit="°", height=110, grow=True, decimals=0),
         None, None, "", "How far the shape has turned at each height, in degrees."),
        ("lattice", "Both ways", "bool", None, None, None, "",
         "Twist the shape both ways at once and keep whichever sticks out further: the\n"
         "ridges cross, making a lattice. Try a polygon or a star."),
    ]),
    ("Surface", [
        ("rib_count", "Ribs", "int", 0, 400, 1, "|None", "Ribs running up the vase."),
        ("rib_depth", "Rib depth", "float", -10.0, 10.0, 0.1, " mm",
         "How far the ribs stand out (+), or how deep they cut in as grooves (-)."),
        ("rib_sharp", "Rib shape", "pct", 0.0, 100.0, 5.0, " %", "0 %: smooth flutes. 100 %: narrow ridges."),
        ("rib_lean", "Ribs spiral", "float", -7200.0, 7200.0, 15.0, "°",
         "The ribs wind this far round the vase on the way up, on top of any twist."),
        ("rib_cross", "Ribs cross", "bool", None, None, None, "",
         "A second set of ribs winds the other way: diamond knurling."),
        ("ring_count", "Rings", "int", 0, 400, 1, "|None", "Rings round the vase, evenly up it."),
        ("ring_depth", "Ring depth", "float", -10.0, 10.0, 0.1, " mm", "How far the rings stand out (+) or cut in (-)."),
        ("ring_sharp", "Ring shape", "pct", 0.0, 100.0, 5.0, " %", "0 %: gentle waves. 100 %: narrow beads."),
        ("bump_around", "Bumps around", "int", 0, 200, 1, "|None", "Bumps in staggered rows: how many round the vase."),
        ("bump_up", "Bumps up", "int", 1, 200, 1, "", "... and how many rows up it."),
        ("bump_depth", "Bump depth", "float", -10.0, 10.0, 0.1, " mm", "How far the bumps stand out (+) or dimple in (-)."),
        ("organic_depth", "Organic", "float", 0.0, 20.0, 0.1, " mm|None",
         "Smooth random lumps all over: how far they go in and out."),
        ("organic_scale", "Lump size", "float", 3.0, 300.0, 1.0, " mm", "The size of one lump."),
        ("organic_seed", "Lump pattern", "seed", 0, 99999, 1, "", "Another number, another pattern of lumps."),
        ("texture_twist", "Turn with the twist", "bool", None, None, None, "",
         "The patterns turn with the shape's twist. Off: they stay square to the bed."),
        ("strength", "Strength", "choice", STRENGTHS, None, None, "", "How strong the patterns are on the way up."),
        ("strength_curve", "", "curve", dict(lo=0.0, hi=1.5, unit="×", height=100, decimals=2), None, None, "",
         "How strong the patterns are at each height (1 = as set)."),
        ("fade_foot", "Plain foot", "float", 0.0, 200.0, 0.5, " mm|None",
         "The patterns fade out over this much at the bottom, for a clean foot."),
        ("fade_rim", "Plain rim", "float", 0.0, 200.0, 0.5, " mm|None",
         "The patterns fade out over this much at the top, for a clean rim."),
    ]),
    ("Low-poly", [
        ("facets", "Flat facets", "bool", None, None, None, "",
         "Make the whole vase from flat triangles, like a cut gem. The shape and patterns\n"
         "are sampled at the corners of the facets."),
        ("facets_around", "Facets around", "int", 3, 400, 1, "", "How many facets round the vase."),
        ("facets_up", "Facets up", "int", 1, 400, 1, "", "How many rows of facets up the vase."),
        ("facet_rough", "Rough cut", "pct", 0.0, 100.0, 5.0, " %", "Move the corners about for a rougher, hand-cut look."),
        ("facet_seed", "Cut pattern", "seed", 0, 99999, 1, "", "Another number, another rough cut."),
    ]),
    ("Holes and openings", [
        ("holes", "Holes", "choice", HOLE_CHOICES, None, None, "",
         "Holes right through the wall: a Voronoi pattern (a honeycomb when regular), round holes, diamonds\n"
         "or slots. Every hole's top comes to a point, so it prints without support. A vase with holes is\n"
         "printed normally, with walls - spiral vase mode prints one closed line a layer."),
        ("hole_size", "Hole size", "float", 4.0, 120.0, 1.0, " mm", "From one hole to the next."),
        ("hole_strut", "Wall between", "float", 0.8, 30.0, 0.2, " mm",
         "The wall left between the holes. Two lines wide or more prints well."),
        ("hole_jitter", "Irregular", "pct", 0.0, 100.0, 5.0, " %",
         "Voronoi: 0 % is a regular honeycomb; more makes the cells more varied."),
        ("hole_seed", "Hole pattern", "seed", 0, 99999, 1, "", "Another number, another pattern of cells."),
        ("hole_foot", "Plain foot", "float", 0.0, 1000.0, 1.0, " mm", "Solid wall kept at the foot, above the floor."),
        ("hole_rim", "Plain rim", "float", 0.0, 1000.0, 1.0, " mm", "Solid wall kept at the rim."),
        ("open_bottom", "Open at the bottom", "bool", None, None, None, "",
         "No floor: open at both ends - a lampshade, a sleeve, a holder. Printed normally."),
        ("closed_top", "Closed at the top", "bool", None, None, None, "",
         "The top closes over in a point, leaning in no more than the overhang limit, so it prints without\n"
         "support: a helmet, a dome, a bell. The outline is rounded in to meet the point."),
        ("around", "Goes round", "float", 30.0, 360.0, 10.0, "°",
         "How far round the wall goes: 360° is all the way round; about 200° makes a mask. The gap\n"
         "is at the back. Printed normally."),
    ]),
    ("Masks and helmets", [
        ("worn", "For a head", "bool", None, None, None, "",
         "Made to wear: the panel gives the head it fits, and Head size makes it fit another.\n"
         "The face is at the front, the side facing you in the 3D view as it starts."),
        ("head", "Head size", "head", 30.0, 90.0, 0.5, " cm",
         "Round the head, above the eyebrows and ears, as a hat is measured (an adult: about 54 to 60 cm).\n"
         "Changing it scales the whole design - its height, outline and face - so the inside fits a head\n"
         "this size, with a centimetre to spare."),
        ("eyes", "Eyes", "choice", EYE_CHOICES, None, None, "",
         "Eye holes at the front. Their tops come to a point, so they print without support."),
        ("eye_width", "Eye width", "float", 2.0, 200.0, 1.0, " mm", "How wide each eye is."),
        ("eye_height", "Eye height", "float", 2.0, 200.0, 1.0, " mm",
         "How tall each eye is, before its top comes to a point."),
        ("eye_apart", "Eyes apart", "float", 0.0, 400.0, 1.0, " mm",
         "From the middle of one eye to the middle of the other, along the face (an adult: about 64 mm)."),
        ("eye_up", "Eyes at", "float", 0.0, 1000.0, 1.0, " mm", "How high the eyes' middles are, from the bottom."),
        ("eye_tilt", "Eye tilt", "float", -60.0, 60.0, 1.0, "°", "The outer corners raised (+) or lowered (-)."),
        ("nose", "Nose", "choice", NOSE_CHOICES, None, None, "",
         "A raised nose: a ridge from between the eyes down to its tip, sloping back to the face\n"
         "underneath no steeper than the overhang limit. Hollow inside, with room for a real nose."),
        ("nose_width", "Nose width", "float", 2.0, 200.0, 1.0, " mm", "How wide the nose is at its tip."),
        ("nose_length", "Nose length", "float", 2.0, 400.0, 1.0, " mm", "From its tip up to between the eyes."),
        ("nose_depth", "Nose sticks out", "float", 0.0, 80.0, 0.5, " mm", "How far the tip stands out from the face."),
        ("nose_up", "Nose tip at", "float", -400.0, 1000.0, 1.0, " mm",
         "How high the tip of the nose is, from the bottom (below nought: only the top of the nose)."),
        ("mouth", "Mouth", "choice", MOUTH_CHOICES, None, None, "",
         "A mouth: an open one (its top comes to a point), a grille of upright slots - which can smile -\n"
         "or an opening down to the chin, like an old Greek helmet's."),
        ("mouth_width", "Mouth width", "float", 2.0, 400.0, 1.0, " mm", "How wide the mouth is."),
        ("mouth_height", "Mouth height", "float", 2.0, 200.0, 1.0, " mm", "How tall the mouth, or each slot, is."),
        ("mouth_up", "Mouth at", "float", 0.0, 1000.0, 1.0, " mm",
         "How high the mouth's middle is, from the bottom - or, open down to the chin, how high it reaches."),
        ("mouth_slots", "Slots", "int", 1, 40, 1, "", "How many slots the grille has."),
        ("mouth_smile", "Smile", "float", -100.0, 100.0, 0.5, " mm",
         "The slots at the corners of the mouth this much higher than the middle: a smile (or, below\n"
         "nought, a frown)."),
        ("straps", "Strap slots", "bool", None, None, None, "",
         "A slot each side for an elastic strap: near the edges of a mask, or at the sides of a helmet."),
        ("strap_up", "Strap slots at", "float", 0.0, 1000.0, 1.0, " mm", "How high the strap slots are."),
    ]),
    ("Your own function", [
        ("expression", "", "expr", None, None, None, "",
         "A formula added to the radius, in mm. Variables: theta (angle round, radians),\n"
         "phi (the angle turning with the twist), z (height, mm), h (0 at the bottom, 1 at\n"
         "the top), r (the radius so far) and H (the height). Help lists the functions.\n"
         "Several lines are read as one formula: start each new line with + - * or /.\n"
         "Anything after a # is a note."),
    ]),
    ("Colours", [
        ("palette", "Palette", "palette", None, None, None, "", "Set all four filament colours from a palette."),
        ("color1", "Filament 1", "color", None, None, None, "",
         "Colour of filament 1. Load the same colour in slot 1 of the slicer."),
        ("color2", "Filament 2", "color", None, None, None, "", "Colour of filament 2."),
        ("color3", "Filament 3", "color", None, None, None, "", "Colour of filament 3."),
        ("color4", "Filament 4", "color", None, None, None, "", "Colour of filament 4."),
        ("colour_style", "Colours", "choice", COLOUR_STYLES, None, None, "",
         "One colour; bands of colour up the vase; thin stripes; or a gradient spool (one\n"
         "filament that changes colour along its length - shown as it will come out, by\n"
         "how much filament each height uses).\n"
         "Bands and stripes need a normal print: each band is its own part in the 3MF."),
        ("colours_used", "Filaments", "choice", USED, None, None, "", "How many filaments the colours go through, from 1."),
        ("band_count", "Bands", "int", 2, 64, 1, "", "How many bands of colour, bottom to top."),
        ("band_spacing", "Band sizes", "slider", -1.0, 1.0, 0.01, "",
         "Even bands in the middle; slide left for thicker bands at the bottom, right for\n"
         "thicker bands at the top."),
        ("stripe_height", "Stripe height", "float", 0.2, 500.0, 1.0, " mm", "Height of each stripe."),
        ("gradient_length", "Colour cycle", "float", 0.1, 1000.0, 0.5, " m",
         "Metres of filament for one full cycle of the gradient spool's colours\n"
         "(see the spool's label; often 5 to 20 m)."),
        ("look", "Looks like", "choice", LOOKS, None, None, "", "How the filament looks in the 3D view."),
    ]),
    ("Printing", [
        ("vase_mode", "Print as", "choice", VASE_MODES, None, None, "",
         "Normal print: printed with walls, like any other print - sturdy, watertight, and in any\n"
         "colours (each band of colour is its own part in the 3MF).\n"
         "Seamless: the slicer's spiral vase mode - one line climbing round and round, so there is\n"
         "no seam, and a single wall that glows when lit. Hardly quicker, and one filament only:\n"
         "Flash Studio won't change filament in it (a gradient spool still works)."),
        ("walls", "Walls", "int", 1, 10, 1, "",
         "Normal print: how many walls round the vase (the slicer's wall loops). Two make a\n"
         "sturdy, watertight vase."),
        ("max_overhang", "Steepest overhang", "float", 10.0, 70.0, 1.0, "°",
         "How far the wall may lean from upright, out or in. A spiral wall is one line wide,\n"
         "so it leans on the line beneath it either way. 45° prints on almost any printer."),
        ("soften", "Soften to fit", "bool", None, None, None, "",
         "Soften any part that leans more than that until it prints without supports. The\n"
         "panel says how far the surface was moved. Off: the Overhangs view shows the\n"
         "faces that would need support in red."),
        ("line_width", "Line width", "float", 0.2, 2.5, 0.02, " mm",
         "The slicer's spiral (outer wall) line width: the wall's thickness. 0.6 to 0.8 mm on\n"
         "a 0.4 mm nozzle makes a stronger wall that holds water better."),
        ("layer_height", "Layer height", "float", 0.04, 1.0, 0.02, " mm", "The layer height you will slice with."),
        ("bottom", "Solid bottom", "float", 0.2, 20.0, 0.2, " mm",
         "The solid floor the slicer prints first. Set the slicer's bottom layers to match:\n"
         "the panel gives the number."),
        ("printer_height", "Printer height", "float", 20.0, 2000.0, 5.0, " mm", "The tallest part the printer can make."),
        ("bed_x", "Bed width", "float", 30.0, 2000.0, 5.0, " mm", "Width of the printer bed."),
        ("bed_y", "Bed depth", "float", 30.0, 2000.0, 5.0, " mm", "Depth of the printer bed."),
        ("speed", "Print speed", "float", 5.0, 1000.0, 5.0, " mm/s", "The spiral wall's speed, for the print time."),
        ("max_flow", "Max flow", "float", 1.0, 200.0, 1.0, " mm³/s",
         "The most plastic the hot end can melt: it caps the speed of a wide line."),
        ("filament_d", "Filament", "float", 1.0, 3.5, 0.05, " mm", "Filament diameter."),
        ("density", "Density", "float", 0.5, 3.0, 0.01, " g/cm³", "PLA 1.24, PETG 1.27, ABS 1.04, TPU 1.21."),
        ("facet_size", "Mesh detail", "float", 0.15, 5.0, 0.05, " mm",
         "Spacing of the points on the surface: smaller is smoother but slower, and a bigger\n"
         "file. Shapes and patterns get enough points of their own."),
    ]),
]

REMEMBERED = ("line_width", "layer_height", "bottom", "printer_height", "bed_x", "bed_y", "speed", "max_flow",
              "filament_d", "density", "max_overhang")
LIVE_KEYS = {"band_spacing"}            # sliders: follow the hand with quick draft builds
TEXT_KEYS = {"expression"}


def widest(p: VaseParams) -> float:
    """The outline's widest diameter."""
    return max(d for _, d in p.silhouette)


def wanted(p, key) -> bool:
    """Whether a setting's row is shown: only what the current choices use."""
    twisting = p.twist_style == OWN or abs(p.twist) > 1e-9
    patterns = p.rib_count > 0 or p.ring_count > 0 or p.bump_around > 0 or p.organic_depth > 0
    show = True
    if key[:-1] in ("count", "depth", "sharp") and key[-1] in "12":
        k = int(key[-1])
        kind = getattr(p, f"shape{k}")
        idx = ("count", "depth", "sharp").index(key[:-1])
        show = kind != SAME and SHAPE_LABELS.get(kind, (None,) * 3)[idx] is not None
    elif key in ("turn1", "turn2"):
        show = getattr(p, f"shape{key[-1]}") not in (CIRCLE, SAME)
    elif key == "morph":
        show = p.shape2 != SAME
    elif key == "morph_swings":
        show = p.shape2 != SAME and p.morph == SWING
    elif key == "morph_curve":
        show = p.shape2 != SAME and p.morph == OWN
    elif key == "twist":
        show = p.twist_style != OWN
    elif key == "swings":
        show = p.twist_style == SWING
    elif key == "twist_curve":
        show = p.twist_style == OWN
    elif key in ("drawn1", "repeat1", "drawn2", "repeat2"):
        show = getattr(p, f"shape{key[-1]}") == DRAWN
    elif key == "lattice":
        show = twisting and DRAWN not in (p.shape1, p.shape2)      # a radius-only idea
    elif key.startswith("rib_") and key != "rib_count":
        show = p.rib_count > 0 and (key != "rib_cross" or p.rib_lean != 0)
    elif key.startswith("ring_") and key != "ring_count":
        show = p.ring_count > 0
    elif key in ("bump_up", "bump_depth"):
        show = p.bump_around > 0
    elif key in ("organic_scale", "organic_seed"):
        show = p.organic_depth > 0
    elif key == "texture_twist":
        show = patterns and twisting
    elif key in ("strength", "fade_foot", "fade_rim"):
        show = patterns
    elif key == "strength_curve":
        show = patterns and p.strength == OWN
    elif key == "facets":
        show = DRAWN not in (p.shape1, p.shape2)                   # a radius-only idea
    elif key.startswith("facet") and key != "facet_size":
        show = p.facets and DRAWN not in (p.shape1, p.shape2)
    elif key in ("colours_used", "palette"):
        show = colour_style_of(p) != ONE_COLOUR
    elif key in ("band_count", "band_spacing"):
        show = colour_style_of(p) == BANDS
    elif key == "stripe_height":
        show = colour_style_of(p) == STRIPES
    elif key == "gradient_length":
        show = colour_style_of(p) == GRADIENT
    elif key.startswith("color") and key[-1] in "1234":
        show = int(key[-1]) <= (1 if colour_style_of(p) == ONE_COLOUR else p.colours_used)
    elif key == "walls":
        show = p.vase_mode == FAKE_VASE
    elif key in ("hole_size", "hole_strut", "hole_seed", "hole_foot", "hole_rim"):
        show = p.holes != NO_HOLES
    elif key == "hole_jitter":
        show = p.holes == VORONOI
    elif key == "head":
        show = p.worn
    elif key.startswith("eye_"):
        show = p.eyes != NO_EYES
    elif key.startswith("nose_"):
        show = p.nose != NO_NOSE
    elif key in ("mouth_width", "mouth_up"):
        show = p.mouth != NO_MOUTH
    elif key == "mouth_height":
        show = p.mouth in (OPEN_MOUTH, GRILLE_MOUTH)
    elif key in ("mouth_slots", "mouth_smile"):
        show = p.mouth == GRILLE_MOUTH
    elif key == "strap_up":
        show = p.straps
    return show


def outline_from_shape(p: VaseParams, k: int):
    """Set drawn outline k from the cross-section it is replacing (the bottom one, for a top shape that was the
    same all the way): one petal of it, repeated, to edit."""
    kind = getattr(p, f"shape{k}")
    src = 1 if kind == SAME else k
    kind = getattr(p, f"shape{src}")
    if kind == DRAWN:                                    # the top copies the drawn bottom
        pts, repeat = [list(q) for q in p.drawn1], p.repeat1
    elif kind == CIRCLE:
        name, pts, repeat = sections.OUTLINES[0]
    else:
        count = getattr(p, f"count{src}")
        repeat = 1 if kind in (ELLIPSE, PEBBLE) else max(int(count), 1)
        table = shape_table(kind, count, getattr(p, f"depth{src}"), getattr(p, f"sharp{src}"))
        pts = sections.motif_from_table(table, repeat)
    setattr(p, f"drawn{k}", [list(q) for q in pts])
    setattr(p, f"repeat{k}", int(repeat))


def change(p: VaseParams, key: str, value) -> tuple[list, str]:
    """Make one change to the settings as the panel makes it, with what follows from it: Widest scales the
    outline, an outline preset draws it, an own curve starts from the curve as it was, a drawn outline from the
    shape it replaces, and so on. Returns (the other settings it changed, a message to show, or "")."""
    touched, message = [], ""
    if key == "widest":
        old = widest(p)
        if old > 0 and value > 0:
            p.silhouette = [[h, round(d * value / old, 3)] for h, d in p.silhouette]
            touched.append("silhouette")
        return touched, message
    if key == "profile":
        p.profile = value
        if value != OWN_PROFILE:
            p.silhouette = outline(value, widest(p))
            touched.append("silhouette")
        return touched, message
    if key == "silhouette":
        p.silhouette = value
        if p.profile != OWN_PROFILE:
            p.profile = OWN_PROFILE
            touched.append("profile")
        touched.append("widest")
        return touched, message
    # an own curve starts from the curve as it was, a point at each peak of a back-and-forth
    if key == "twist_style" and value == OWN and p.twist_style != OWN:
        p.twist_curve = [[h, round(d, 1)] for h, d in sample_points(
            lambda hs: p.twist * progress(p.twist_style, hs, swings=p.swings), p.twist_style, p.swings)]
        touched.append("twist_curve")
    elif key == "morph" and value == OWN and p.morph != OWN:
        p.morph_curve = [[h, round(m, 3)] for h, m in sample_points(
            lambda hs: change_of(p.morph, hs, changes=p.morph_swings), p.morph, p.morph_swings)]
        touched.append("morph_curve")
    elif key == "strength" and value == OWN and p.strength != OWN:
        p.strength_curve = [[h, round(s, 3)] for h, s in sample_points(
            lambda hs: strength(p.strength, hs), p.strength, 1)]
        touched.append("strength_curve")
    elif key == "colour_style" and value != ONE_COLOUR and p.colours_used < 2:
        p.colours_used = 3
        touched.append("colours_used")
    elif key in ("repeat1", "repeat2"):
        # the drawn piece narrows or widens to fit: one lobe stays one lobe, as deep as before
        k = key[-1]
        setattr(p, f"drawn{k}", sections.respace(getattr(p, f"drawn{k}"), getattr(p, key), value))
        touched += [key, f"drawn{k}"]
    elif key in ("shape1", "shape2") and value == DRAWN and getattr(p, key) != DRAWN:
        # a drawn outline starts as the shape it was: one petal of it, repeated, to edit
        outline_from_shape(p, int(key[-1]))
        touched += [f"repeat{key[-1]}", f"drawn{key[-1]}"]
    setattr(p, key, value)
    if key != "vase_mode" and p.vase_mode == REAL_VASE and needs_normal(p):
        p.vase_mode = FAKE_VASE                       # spiral vase mode prints one closed line a layer
        touched.append("vase_mode")
        message = ("Holes, a face, an open bottom and a wall part way round need a normal print: Print as is now "
                   "Normal print")
    return touched, message
