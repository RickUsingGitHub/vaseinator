# Vaseinator

A Windows desktop app that designs **vases that print without supports** – as an ordinary print with a
few walls, in any colours, or **seamless** in the slicer's spiral vase mode. Every vase it makes is a
closed, watertight model, every layer is one single loop, and no part of the wall leans further than you
allow.

**Simple** mode is a handful of choices made from pictures – easy enough for anyone – and one big
**Save for printing** button; **Advanced** has every setting.

Shape the outline, pick a cross-section and what it turns into on the way up, **spin** it, cover it in
ribs, rings, bumps, organic lumps or **your own formula**, and colour it in bands, stripes or a
gradient spool. Cut **holes** through it, open it at the bottom, close it over at the top – or give it a
**face** and make a **mask or a helmet**, sized for the head it fits. The app shows the vase in 3D as it will print, cuts it in half to show the wall, colours
every face by how far it leans, plays the print back in real print time, and exports an STL or 3MF
ready to slice.

![Vaseinator main window](docs/images/main_window.png)

![The ready-made vases](docs/images/gallery.png)

| Advanced: draw how things change up the vase | Section: the printed wall |
|---|---|
| ![Advanced mode with curves](docs/images/detailed.png) | ![Section view](docs/images/section.png) |
| **Overhangs: green is easy, red needs support** | **Watch it print, in real print time** |
| ![Overhang check](docs/images/overhangs.png) | ![Print layout and animation](docs/images/print_layout.png) |
| **Draw any cross-section, sharp corners and all** | **Draw one lobe, repeat it: three bulbs become six** |
| ![The cross-section editor](docs/images/drawn_claw_shell.png) | ![Repeat around](docs/images/drawn_bulb_swirl.png) |

## Features

* **Outline** from twelve presets (classic, bulb, tulip, amphora, bottle, gourd, trumpet, …) or drawn
  by hand: drag points on the outline curve; the curve through them never overshoots.
* **Cross-section**: circle, polygon (with rounded corners), star, flower, gear, ellipse or pebble – and
  a second shape it **turns into** on the way up – evenly, early, late, **back and forth** as many times
  as you like (circle → pentagon → circle → pentagon), or along your own curve.
* **Draw any cross-section**: a spline editor with smooth points and sharp **cusps**, for shapes no
  formula makes – lobes that swell past their necks, a crescent, a claw, a heart, nothing symmetrical at
  all. Draw one lobe and **repeat it around** – up to 100 times – start from a built-in shape, or
  **trace a picture**. Draw close up on one repeat, or in a **full window** with zoom.
* **Spin**: twist the shape round as it rises – evenly, easing in and out, speeding up, slowing down,
  **back and forth**, or along your own curve – or **both ways at once** for a lattice of crossing ridges.
* **Surface patterns**: ribs (that can spiral, or cross for diamond knurling), rings, staggered bumps
  and smooth organic lumps, each with its own depth and shape, a strength that can change up the vase,
  and a plain foot and rim.
* **Low-poly facets**: the whole vase from flat triangles, like a cut gem, with an optional rough cut.
* **Your own function**: type a formula in millimetres – `1.5 * sin(6*theta + 4*pi*h)` – added to the
  radius everywhere. Variables for the angle, the angle turning with the twist, height, share of the
  height and the radius so far; trig, waves, steps and smooth noise. A long formula can go over several
  lines – they are read as one, so start each new line with + - * or / – with notes after a `#`. It is
  checked and run safely: numbers, the listed variables and functions only; a mistake is pointed out by
  line and character.
* **A normal print, or seamless**: a vase prints like any other print, and is exported as the **hollow pot**
  it is – the wall as thick as it prints, the floor and the rim – so the slicer needs **no special
  settings**: sturdy, watertight and in colour. Or, in one colour (or a gradient spool), **seamless** in the
  slicer's spiral vase mode: one line climbing round and round, with no seam and a single wall that glows
  when lit. Spiral vase mode is hardly any quicker, so a normal print is the usual.
* **Holes** right through the wall: **Voronoi** cells (a honeycomb when regular), **round holes**,
  **diamonds** or **slots**, as big and as far apart as you like, kept clear of a plain foot and rim, and
  turning with the twist. Every hole's top comes to a **point** that closes no faster than the overhang
  limit, so it prints **without support** – with at most a short bridge, a few millimetres, at its very tip.
  And **open at the bottom** too, for lampshades, sleeves and holders.
* **Closed at the top**: the top comes in to a point, leaning no more than the overhang limit, over a
  ceiling a few millimetres across that the printer bridges – a helmet, a dome, a bell, a sealed egg. The
  outline is rounded in to meet the point.
* **Part way round**: the wall goes only so far round – about 200° makes a mask – with the gap at the back.
* **Masks and helmets**: a **face** at the front – **eyes** (almond or round, apart, tilted), a raised
  **nose**, a **mouth** (open, a grille of slots that can smile, or open down to the chin like an old
  Greek helmet's) and **slots for an elastic strap** – every hole with a pointed top, so it prints without
  support. **Head size** fits one to a head: measure round it above the eyebrows and ears, as for a hat,
  and the whole design – height, outline and face – is scaled so the inside fits with a centimetre to
  spare. Stylised, not anatomical.
* **Colours**: one colour or a **gradient spool** – shown where its colours will really land, worked out
  from the filament each height uses – and, printed normally, up to four filaments in **bands**
  (even, or thicker at the top or the bottom) or **stripes**, with palettes.
* **Looks**: matte, silk, glossy or translucent in the 3D view.
* **Printable, always**: each layer of the wall rests on the one below it, so it may lean neither out nor
  in further than the limit (45° by default). **Soften to fit** reshapes only what leans too far – and
  tells you by how much – and every triangle is checked afterwards.
* **Views**: the vase, a **section** through the printed wall, an **overhang check**, and the print
  layout on your bed inside the printer's build volume. **Spin** turns it on a turntable; **Watch it
  print** builds it up in real print time (wide layers take longer).
* **The sums**: size, base and opening, how much water it holds, filament in grams and metres, print
  time, steepest overhang, and the mesh – closed and watertight.
* **Gallery** of twenty-seven ready-made designs – lampshades and baskets with holes among them, three masks
  and a helmet – a **plain cylinder** to start from blank, **Surprise me** (a new random vase that still
  prints), and **undo / redo** of everything.
* **Save for printing**: a **3MF** in the middle of the bed – each colour band its own part, set to its
  filament (one solid for a seamless vase) – as Lenticular Sign Maker and Maze Tube Designer do, with plain
  steps to print it and **Open in slicer** (Flash Studio, OrcaSlicer, Bambu Studio, PrusaSlicer, Cura… –
  whichever is installed). Also a solid **STL**. Designs save as `.vase` files (JSON).
* **Simple**: a design chosen from pictures, how big (in centimetres – or, for a mask or helmet, the head
  size), the shape from above and from the side, the twist, a pattern and a colour – each a picture to
  click. **Advanced** has every setting and
  the curves, your own function among them. **Bigger text** and a **light theme** are in the View menu.

## Download and run

* **Windows app (no Python needed):** download `Vaseinator.exe` from the
  [Releases](../../releases) page and run it. It is a single file: nothing to unzip or install.
  It isn't code-signed, so Windows SmartScreen may ask once; choose **More info → Run anyway**.
* **From source** (Python 3.10+, any OS with OpenGL):
  ```
  git clone https://github.com/RickUsingGitHub/vaseinator.git
  cd vaseinator
  python -m venv .venv
  .venv\Scripts\pip install -r requirements.txt      # macOS/Linux: .venv/bin/pip
  .venv\Scripts\python main.py
  ```
  On Windows you can also just double-click `run.bat`, which sets everything up on first run.
* **Build the Windows app yourself:** `build_exe.bat` (uses PyInstaller; the result is
  `dist\Vaseinator.exe`).

Vaseinator is free. If it has made you something you like, you can [buy me a coffee](https://ko-fi.com/rickapps).

`examples\` holds the gallery as `.vase` designs to open. `tools\make_examples.py` writes them again, and
six of them to `examples\stl\` as finished STLs, checked and ready to slice: Lagoon Twist, Star to Moon,
Lattice Lantern, Gem Facets, Coral Reef and Claw Shell. (STLs are big, so they are not kept in git.)

On first run the app borrows your printer's bed size and height from Maze Tube Designer or Lenticular
Sign Maker, if you have used them. Printer settings are remembered for new designs.

## Using it

In **Simple** mode, click **Choose a design…** (every ready-made vase as a picture) or **Surprise me**,
then click the pictures to change it: the shape from above, the shape from the side, a pattern, a colour;
**Tall** and **Wide** size it – for a mask or helmet, **Head size** – and the slider twists it. **Draw my own shape…** opens a big window to draw
the shape from above yourself. When it looks right, **Save for printing…** saves it for the slicer and
says, in plain steps, how to print it – with a button to open it in your slicer (File ▸ Choose slicer
program picks a different one).

Or start blank: **Plain cylinder**, first in the gallery (or **File ▸ New plain cylinder**, Ctrl+Shift+N),
is a cylinder 200 mm across and 200 mm tall with everything else off, ready for your own function or a
drawn cross-section; your printer settings are kept. Every change rebuilds the vase at once; while you
drag a point on a curve, a quicker rough version follows your hand.

The curves for the twist, the change of shape and the pattern strength are ordinary graphs: the vase
from bottom to top runs left to right, and the value runs up – drag a point up for more, down for
less. Double-click to add a point (a few make a wave), right-click to take one away. The outline's
curve is drawn upright and mirrored instead, like the vase from the side.

| Group | What it does |
| --- | --- |
| **Size** | Height, the widest diameter (scales the whole outline), and the outline: a preset, or your own curve – diameter at each height, drawn as the vase seen from the side. |
| **Shape** | The cross-section at the bottom, and what it turns into at the top. Each shape has its own settings: sides, points, petals or teeth; how deep it cuts in; how sharp it is; how far it is turned. **Drawn – any outline** gives you the cross-section editor instead (below). **Change happens** says how the first shape becomes the second on the way up – including back and forth, as many **Changes** as you like, and your own curve. |
| **Spin** | How far the shape turns from bottom to top, and how the turning is spread up the vase – including back and forth, and your own curve. **Both ways** twists it both ways at once. |
| **Surface** | Ribs, rings, bumps and organic lumps; whether they turn with the twist; how strong they are up the vase; and a plain foot and rim. |
| **Low-poly** | Flat facets: how many round and up, and how rough the cut. |
| **Holes and openings** | The **holes** – none, Voronoi, round, diamonds or slots – their size, the wall between them, how irregular the Voronoi cells are and their pattern, and how much plain wall to keep at the foot and the rim; **open at the bottom**; **closed at the top**; and how far the wall **goes round**. Holes, an open bottom and a wall part way round are printed normally. |
| **Masks and helmets** | **For a head** and its **head size**; the **eyes** – almond or round, their size, how far apart, how high and tilted; a raised **nose** – its width, length, how far it sticks out and how high its tip is; the **mouth** – open, a grille of slots (how many, and how much they smile) or open down to the chin; and **strap slots**. Sizes and heights are in millimetres along the face, from the bottom. |
| **Your own function** | A formula added to the radius. **Examples** has eight to try; **Help…** lists the variables and functions. |
| **Colours** | The colour, or – printed normally – a palette or four filament colours, and how they go up the vase: one colour, bands, stripes or a gradient spool. How it looks: matte, silk, glossy, translucent. |
| **Printing** | **Print as**: a normal print (walls, any colours – the usual) or seamless (spiral vase mode, one colour). For a normal print, how many **walls**. The steepest overhang allowed and **Soften to fit**; the line width and layer height; the solid bottom; the printer's height and bed; speed and flow (for the print time); filament diameter and density (for the weight); and the mesh detail. |

**3D view:** left-drag turns it, right-drag or shift-drag moves it, the wheel zooms, double-click or F goes
back to the chosen view. **S** spins it, **F5** watches it print, **Ctrl+1–4** switch views, **Ctrl+R**
is Surprise me, **Ctrl+Z / Ctrl+Y** undo and redo.

**Drawing a cross-section:** the middle of the editor is the vase's axis and the dashed circle its widest
(the outline is scaled so its furthest point touches it). Drag a point; double-click the line to add one,
and double-click a point to switch it between smooth (a circle) and a sharp corner (a diamond);
right-click a point to take it away. **Repeat around** copies what you draw round the axis – draw one lobe,
get five, or up to a hundred; change the number and the lobe narrows or widens to fit, just as deep.
**Close up** shows one repeat big, turned to point upwards (above 8 repeats the editor starts that way),
and double-clicking any copy adds the point to the lobe you draw. **Full window…** opens the editor as big
as the screen: the wheel zooms, a right or middle drag moves it, **F** fits it again, and the vase follows
as you draw. **Start from** has ready-made outlines – a claw, bulbs, a heart – and **Trace a
picture…** (a dark closed line or filled shape on a light ground). Switching a built-in shape to Drawn
starts from it: a five-petalled flower becomes one petal, repeated five times. Twist, the change into a
second shape, the patterns and colour bands all work on a drawn outline; it turns red if it crosses itself.

Under the 3D view, **From the side** shows the outline in the colour of each height (the dashed line is
the narrowest radius, so you can see how deep the shape goes; an orange tick on the left marks heights
that were softened, a red tick on the right anything still leaning too far), and **Layers from above**
shows fifteen layers stacked, so the twist and the change of shape are easy to see.

## Printing

**Save for printing** gives the steps for your vase. *Advanced ▸ Printing ▸ Print as* chooses a normal
print (the usual) or seamless.

**A normal print**

* Leave spiral vase mode **off**, and otherwise print with your **usual settings**. The vase comes as the
  hollow pot it is – a wall as thick as *Walls* × *Line width* (1.2 mm as it comes), the floor, the rim and
  any holes – so the slicer simply fills it in: there is nothing to set.
* The colour bands and stripes are parts of their own filaments in the 3MF, so the slicer prints them in
  colour by itself; on a printer with several toolheads, like the Creator 5 Pro, each band uses its own
  head. It prints a layer at a time, with a seam.

**Seamless (spiral vase mode)**

* **Slice with spiral vase mode on** (Spiralize). The exported model is **solid**: the slicer prints only
  its outside, as one continuous line. Don't slice it normally with infill – it would print as a solid
  block.
* Set **bottom layers** to the number the panel gives (6 for a 1.2 mm bottom at 0.2 mm layers), **0 top
  layers**, 0% infill, 1 wall.
* Set the **outer wall line width** to the app's line width. 0.6–0.8 mm on a 0.4 mm nozzle is much
  stronger and more watertight than 0.4 mm.
* It prints **one filament**. Flash Studio won't change filament in spiral vase mode (*Change Filament* is
  greyed out on the layer slider), and won't spiral an object made of parts of several filaments. A
  gradient spool is one filament, so it works.

**Either way**

* **No supports.** The panel shows the steepest lean of the wall; the Overhangs view shows where it is.
* **To make sure it holds water:** a little extra flow (103–105%), 5–10 °C hotter than usual for strong
  layer bonds, and a moderate speed (30–50 mm/s for the wall). PETG is more watertight than PLA; silk PLA
  looks lovely but bonds a little less well. Test it in a sink. A coat of clear epoxy or varnish inside
  seals any weep.
* A **brim** helps a vase with a narrow foot stay put – and a mask, which stands on the thin edge of its
  chin, or a helmet on its rim.

`tools\verify_stl.py` checks any STL for spiral vase printing, straight from the file: closed and
watertight, faces outwards, one piece, flat on the bed, no wall leaning past the limit, and every layer
one closed loop.

```
.venv\Scripts\python tools\verify_stl.py examples\stl\lagoon_twist_vase.stl
```

## Opening the 3MF in your slicer

**Save for printing** (and **Export 3MF**) writes the vase as one object in the middle of the bed – the
same kind of file as Lenticular Sign Maker and Maze Tube Designer. **Open in slicer** opens it for you; in
**Flash Studio or OrcaSlicer** you can also use **File ▸ Import** (Ctrl+I).

* **A normal print:** the hollow pot, each colour band its own part, set to filaments 1, 2, 3… in the
  vase's colours; reassign them in the slicer as you like. Leave spiral vase mode off and print with your
  usual settings.
* **Seamless:** the vase is one solid part. Turn on spiral vase mode and print.

## Project layout

| File | What it holds |
| --- | --- |
| `main.py` | Starts the app. |
| `vaseinator/app.py` | The main window: the Advanced settings, views, animations, gallery, undo, exports. |
| `vaseinator/simple_panel.py` | Simple mode: the picture choices, and the gallery of pictures. |
| `vaseinator/slicers.py` | Finding the slicers installed, to open a vase in one. |
| `vaseinator/geometry.py` | The vase itself: the surface, softening, the solid and the shown shell, and the sums. |
| `vaseinator/shapes.py` | Outlines, cross-sections, curves up the height, textures, palettes. |
| `vaseinator/expr.py` | Your own function: checked, then evaluated with numpy. |
| `vaseinator/hollow.py` | The hollow pot a normal print makes, the hole patterns, a face's eyes, nose, mouth and strap slots, and their pointed tops. |
| `vaseinator/sections.py` | Drawn cross-sections: the spline through the points, tracing a picture, filling and insetting outlines. |
| `vaseinator/curves.py` | The curve editor. |
| `vaseinator/outline_editor.py` | The cross-section editor. |
| `vaseinator/plots.py` | The side and from-above pictures. |
| `vaseinator/viewer.py` | The OpenGL 3D view. |
| `vaseinator/presets.py` | The gallery and Surprise me. |
| `vaseinator/params.py` | Settings, and saving and opening designs. |
| `vaseinator/stl.py`, `threemf.py` | The exports. |
| `tests/test_vase.py`, `tests/test_app.py` | Self-tests of the geometry and the window. |
| `assets/gallery/` | A picture of each ready-made vase, drawn by `tools/make_thumbnails.py`. |
| `tools/` | The icon, the gallery pictures, the example files, and the STL checker. |

### How the geometry works

The vase is a radial height map r(θ, z): one radius in each direction round the axis at each height,
built on a grid of heights and angles. Because each height has exactly one radius in each direction,
every layer is one simple closed loop – what spiral vase mode needs – and the mesh can't cross itself:
each triangle lies in its own wedge of angle between two heights. The wall is joined to a flat bottom
and a flat top, so the solid is closed, watertight and one piece, with no boolean operations.

A normal print is exported as the **hollow pot**: the outer face, an inner face moved in square to it by
the wall's thickness, a flat floor (or an open bottom) and the rim, built row by row on the same grid as
the surface. A **hole pattern** is a number at each grid point – how far inside a hole it is, in mm,
below nought in the wall – from the nearest hole centres (two of them, for Voronoi's cell edges). The
wall is cut where that number is nought (marching squares), the same on both faces, with a side face
joining them round each hole; each cut is one vertex shared by every face beside it, so the pot stays
closed. Going up row by row, the wall over a hole may only reach in so far past the wall below it –
measured from the point really below, so on a twisting vase the holes' sides lean no more than their
tops – so every hole's top closes to a point at no more than the overhang limit. Where it finally closes
between two grid points there is a short bridge, which the app measures and tells you about. Colour
bands of the pot are cut on rows put in at the band heights, each a closed part.

A **face** is more of the same: the eyes, mouth and strap slots are hole fields too, placed in
millimetres along the surface from the front, and the gap at the back of a wall that goes only part way
round is one more – so they all get pointed tops, and a pattern of holes keeps a strut's width of wall
round them. The nose is added to the radius, and softening keeps its underside within the limit. A
**closed top** caps the outline's radius with a cone leaning a little under the limit up to a point –
the two blended where they meet, so the outline curves in – and the pot's inner face ends a floor's
thickness under the point in a small flat ceiling (the app measures the widest circle that fits in it:
the span the printer bridges). **Head size** measures round the inner face where the head goes in – the
narrowest place below the widest, or for a mask the widest – less a centimetre to spare, and scales the
whole design until that is the head asked for.

A **drawn** cross-section needn't have one radius in each direction – a lobe can swell past its neck – so
it is built another way: as rows of points up the vase, each row the outline (blended into the second
one, sized by the outline curve and turned by the twist) cut into the same number of points at even
distances along it, the patterns pushed out square to it. Neighbouring rows join point to point, the
bottom and top are filled by ear clipping, and any outline that crosses itself is refused, so every layer
is still one simple loop. Softening limits how fast the size, the twist and the change of shape may go at
any height where a face leans too far, and fades the patterns there gently.

Shapes are smoothed to the grid's own spacing, so sharp points and valleys that twist across it don't
alias into rows of little teeth.

How far the wall leans is measured on the true surface normal: tan(lean) = r·|∂r/∂z| / √(r² + (∂r/∂θ)²),
out or in alike. **Soften to fit** works in two steps. A shape twisting faster than its flanks can follow
first has its flanks softened round each layer (a flank carried sideways at r·ω leans by
r·ω·|r_θ| / √(r² + r_θ²)), so it stays one clean twisted shape. Then each column up the vase is limited to
the slope the lean allows there – the largest surface under it and the smallest over it that keep within
the limit, averaged – with the correction smoothed round the vase so neighbouring columns agree. Every
finished triangle is then checked, and the limit tightened just round any that still lean too far.

`.venv\Scripts\python -m tests.test_vase` builds every gallery vase, a dozen surprises and some hard
cases – drawn outlines among them – and checks that each is closed and watertight with outward faces, flat on the bed, within the
overhang limit, and one closed loop at every height tested; that leans are measured right; that a
cylinder has the right volume and capacity; that STL and 3MF files read back the same; that designs save
and open; that your own function can reach nothing it shouldn't; that colour changes land on layers; and
that a drawn outline goes through its points, matches the built-in shape it came from, holds what a round
vase holds, is refused if it crosses itself, can be traced from a picture, and repeated a hundred times –
narrowed to fit, checked, filled and built closed in a few seconds; that a normal print is the hollow pot,
with the right volume, its colour bands parts that make it up exactly; and that every pattern of holes,
on round and drawn shapes, twisting or not, makes a closed pot whose holes' sides lean no more than the
limit but for short bridges at their points, that holds nothing, with an open bottom too; and that a
closed top comes to a point over a small ceiling (drawn and banded too), a wall part way round stops where
it should, a face's holes and nose are where they should be and print without support, and a design sized
for a head fits it – the masks and helmet a head 57 cm round.
`.venv\Scripts\python -m tests.test_app` drives the window itself: edits, curves, undo, the gallery,
Surprise me, every view, the print animation, saving and exporting, and drawing (with the mouse, close
up and in a full window, zoomed with the wheel), repeating up to a hundred times and tracing a
cross-section, and Simple mode: each kind of picture, the gallery of pictures, Save for printing with its
steps and Open in slicer, bigger text and the light theme, and a mask sized by the head it fits, its face's
settings and Undo. Test windows open on the second screen, if there is one.

## License

MIT – see [LICENSE](LICENSE).
