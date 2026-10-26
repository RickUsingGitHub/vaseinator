# Vaseinator

A Windows desktop app that designs **vases for a 3D printer's spiral vase mode**: one continuous wall
climbing round and round on a solid bottom. Every vase it makes is a closed, watertight model, every
layer is one single loop, and no part of the wall leans further than you allow – so it **prints
without supports**.

Shape the outline, pick a cross-section and what it turns into on the way up, **spin** it, cover it in
ribs, rings, bumps, organic lumps or **your own formula**, and colour it in bands, stripes or a
gradient spool. The app shows the vase in 3D as it will print, cuts it in half to show the wall, colours
every face by how far it leans, plays the print back in real print time, and exports an STL or 3MF
ready to slice.

![Vaseinator main window](docs/images/main_window.png)

![The ready-made vases](docs/images/gallery.png)

| Draw how things change up the vase | Section: the single printed wall |
|---|---|
| ![Detailed mode with curves](docs/images/detailed.png) | ![Section view](docs/images/section.png) |
| **Overhangs: green is easy, red needs support** | **Watch it print, in real print time** |
| ![Overhang check](docs/images/overhangs.png) | ![Print layout and animation](docs/images/print_layout.png) |

## Features

* **Outline** from twelve presets (classic, bulb, tulip, amphora, bottle, gourd, trumpet, …) or drawn
  by hand: drag points on the outline curve; the curve through them never overshoots.
* **Cross-section**: circle, polygon (with rounded corners), star, flower, gear, ellipse or pebble – and
  a second shape it **turns into** on the way up – evenly, early, late, **back and forth** as many times
  as you like (circle → pentagon → circle → pentagon), or along your own curve.
* **Spin**: twist the shape round as it rises – evenly, easing in and out, speeding up, slowing down,
  **back and forth**, or along your own curve – or **both ways at once** for a lattice of crossing ridges.
* **Surface patterns**: ribs (that can spiral, or cross for diamond knurling), rings, staggered bumps
  and smooth organic lumps, each with its own depth and shape, a strength that can change up the vase,
  and a plain foot and rim.
* **Low-poly facets**: the whole vase from flat triangles, like a cut gem, with an optional rough cut.
* **Your own function**: type a formula in millimetres – `1.5 * sin(6*theta + 4*pi*h)` – added to the
  radius everywhere. Variables for the angle, the angle turning with the twist, height, share of the
  height and the radius so far; trig, waves, steps and smooth noise. It is checked and run safely:
  numbers, the listed variables and functions only.
* **Colours**: up to four filaments with palettes, in one colour, **bands** (even, or thicker at the
  top or the bottom), **stripes**, or a **gradient spool** – shown where its colours will really land,
  worked out from the filament each height uses. The panel lists the layer of every filament change.
* **Looks**: matte, silk, glossy or translucent in the 3D view.
* **Printable, always**: a spiral wall rests on the single line below it, so it may lean neither out nor
  in further than the limit (45° by default). **Soften to fit** reshapes only what leans too far – and
  tells you by how much – and every triangle is checked afterwards.
* **Views**: the vase, a **section** through the printed wall, an **overhang check**, and the print
  layout on your bed inside the printer's build volume. **Spin** turns it on a turntable; **Watch it
  print** builds it up in real print time (wide layers take longer).
* **The sums**: size, base and opening, how much water it holds, filament in grams and metres, print
  time, steepest overhang, and the mesh – closed and watertight.
* **Slicer projects**: on a project saved in Flash Studio (or OrcaSlicer or Bambu Studio), Export 3MF
  writes a ready-to-slice project with spiral vase on and the colour bands as tool or filament changes.
* **Gallery** of seventeen ready-made vases, **Surprise me** (a new random vase that still prints), and
  **undo / redo** of everything.
* Exports a solid **STL** for spiral vase mode, or a **3MF** placed in the middle of the bed and set to
  the vase's first filament. Designs save as `.vase` files (JSON).
* **Simple** shows the essentials; **Detailed** shows every setting and the curves.

## Download and run

* **Windows app (no Python needed):** run `dist\Vaseinator.exe` (or build it, below). It is a single
  file: nothing to unzip or install. It isn't code-signed, so Windows SmartScreen may say "Windows
  protected your PC": click **More info → Run anyway**.
* **From source (any OS with Python 3.10+):**

  ```
  pip install -r requirements.txt
  python main.py
  ```

  On Windows, `run.bat` sets up a virtual environment in `.venv` the first time and starts the app.
* **Build the exe yourself:** run `build_exe.bat`. It writes `dist\Vaseinator.exe`.

`examples\` holds the gallery as `.vase` designs to open. `tools\make_examples.py` writes them again, and
five of them to `examples\stl\` as finished STLs, checked and ready to slice: Lagoon Twist, Star to Moon,
Lattice Lantern, Gem Facets and Coral Reef. (STLs are big, so they are not kept in git.)

On first run the app borrows your printer's bed size and height from Maze Tube Designer or Lenticular
Sign Maker, if you have used them. Printer settings are remembered for new designs.

## Using it

Pick a vase from the **Gallery** or press **Surprise me**, then change it. Every change rebuilds the vase
at once; while you drag a point on a curve, a quicker rough version follows your hand.

The curves for the twist, the change of shape and the pattern strength are ordinary graphs: the vase
from bottom to top runs left to right, and the value runs up – drag a point up for more, down for
less. Double-click to add a point (a few make a wave), right-click to take one away. The outline's
curve is drawn upright and mirrored instead, like the vase from the side.

| Group | What it does |
| --- | --- |
| **Size** | Height, the widest diameter (scales the whole outline), and the outline: a preset, or your own curve – diameter at each height, drawn as the vase seen from the side. |
| **Shape** | The cross-section at the bottom, and what it turns into at the top. Each shape has its own settings: sides, points, petals or teeth; how deep it cuts in; how sharp it is; how far it is turned. **Change happens** says how the first shape becomes the second on the way up – including back and forth, as many **Changes** as you like, and your own curve. |
| **Spin** | How far the shape turns from bottom to top, and how the turning is spread up the vase – including back and forth, and your own curve. **Both ways** twists it both ways at once. |
| **Surface** | Ribs, rings, bumps and organic lumps; whether they turn with the twist; how strong they are up the vase; and a plain foot and rim. |
| **Low-poly** | Flat facets: how many round and up, and how rough the cut. |
| **Your own function** | A formula added to the radius. **Examples** has eight to try; **Help…** lists the variables and functions. |
| **Colours** | A palette or four filament colours, and how they go up the vase: one colour, bands, stripes or a gradient spool. How it looks: matte, silk, glossy, translucent. |
| **Printing** | The steepest overhang allowed and **Soften to fit**; the line width (the wall's thickness) and layer height; the solid bottom; the printer's height and bed; speed and flow (for the print time); filament diameter and density (for the weight); and the mesh detail. |

**3D view:** left-drag turns it, right-drag or shift-drag moves it, the wheel zooms, double-click or F goes
back to the chosen view. **S** spins it, **F5** watches it print, **Ctrl+1–4** switch views, **Ctrl+R**
is Surprise me, **Ctrl+Z / Ctrl+Y** undo and redo.

Under the 3D view, **From the side** shows the outline in the colour of each height (the dashed line is
the narrowest radius, so you can see how deep the shape goes; an orange tick on the left marks heights
that were softened, a red tick on the right anything still leaning too far), and **Layers from above**
shows fifteen layers stacked, so the twist and the change of shape are easy to see.

## Printing

* **Slice with spiral vase mode on** (Spiralize). The exported STL is **solid**: the slicer prints only its
  outside, as one continuous line. Don't slice it normally with infill – it would print as a solid block.
* Set **bottom layers** to the number the panel gives (6 for a 1.2 mm bottom at 0.2 mm layers), **0 top
  layers**, 0% infill, 1 wall.
* Set the **outer wall line width** to the app's line width. 0.6–0.8 mm on a 0.4 mm nozzle is much
  stronger and more watertight than 0.4 mm.
* **No supports.** The panel shows the steepest lean of the wall; the Overhangs view shows where it is.
* **To make sure it holds water:** a little extra flow (103–105%), 5–10 °C hotter than usual for strong
  layer bonds, and a moderate speed (30–50 mm/s for the wall). PETG is more watertight than PLA; silk PLA
  looks lovely but bonds a little less well. Test it in a sink. A coat of clear epoxy or varnish inside
  seals any weep.
* **Sturdier still:** slice the same STL normally with 2–3 walls, 0% infill and 0 top layers – the wall is
  then several lines thick.
* A **brim** helps a vase with a narrow foot stay put.
* **Colour bands and stripes:** with **Slicer settings** chosen, Export 3MF puts the filament changes in for
  you (see below). Without, add a filament change at each layer the panel lists on the slicer's layer
  slider (**Edit ▸ Copy colour changes** puts the list on the clipboard). Each change pauses the spiral and
  leaves a small seam, so a few tall bands print cleaner than many thin ones. A gradient spool needs
  nothing.

`tools\verify_stl.py` checks any STL for spiral vase printing, straight from the file: closed and
watertight, faces outwards, one piece, flat on the bed, no wall leaning past the limit, and every layer
one closed loop.

```
.venv\Scripts\python tools\verify_stl.py examples\stl\lagoon_twist_vase.stl
```

## Opening the 3MF in your slicer

**With slicer settings (recommended).** Under *Printing*, choose **Slicer settings**: a project you have
saved in Flash Studio (or OrcaSlicer or Bambu Studio) for your printer and filaments – set up any print and
use **File ▸ Save Project** there. It is remembered. **Export 3MF** then writes a project on exactly those
printer and filament settings, with:

* spiral vase mode on: one wall of the app's line width, the right number of bottom layers, no top
  layers, no infill and no supports, at the app's layer height;
* the filament colours of the vase;
* the colour bands and stripes as **filament changes at their layers**, at the first layer of each band
  (allowing for a thicker first layer).

Open it in Flash Studio with **File ▸ Open** (Ctrl+O) – *not* Import, which takes the shape only – check
the preview and print. On a printer with several toolheads, such as the **Flashforge Creator 5 Pro**, each
change parks one toolhead and picks up the next, which heats up before the spiral carries on: a short pause
and a small seam, and no purge tower is needed. On a printer with one filament, each change is a pause for
you to swap it by hand.

`tools\check_with_slicer.py` slices an exported project with Flash Studio's own engine, without opening
a window, and reports whether it spirals and where it changes colour:

```
.venv\Scripts\python tools\check_with_slicer.py lagoon_twist.3mf
```

**Without slicer settings,** Export 3MF writes the vase alone, in the middle of the bed and set to its
first filament. In Flash Studio or OrcaSlicer, use **File ▸ Import** (Ctrl+I) and turn on spiral vase
mode yourself.

## Project layout

| File | What it holds |
| --- | --- |
| `main.py` | Starts the app. |
| `vaseinator/app.py` | The main window: settings panel, views, animations, gallery, undo, exports. |
| `vaseinator/geometry.py` | The vase itself: the surface, softening, the solid and the shown shell, and the sums. |
| `vaseinator/shapes.py` | Outlines, cross-sections, curves up the height, textures, palettes. |
| `vaseinator/expr.py` | Your own function: checked, then evaluated with numpy. |
| `vaseinator/curves.py` | The curve editor. |
| `vaseinator/plots.py` | The side and from-above pictures. |
| `vaseinator/viewer.py` | The OpenGL 3D view. |
| `vaseinator/presets.py` | The gallery and Surprise me. |
| `vaseinator/params.py` | Settings, and saving and opening designs. |
| `vaseinator/stl.py`, `threemf.py` | The exports. |
| `tests/test_vase.py`, `tests/test_app.py` | Self-tests of the geometry and the window. |
| `tools/` | The icon, the example files, the STL checker, and the slicer check. |

### How the geometry works

The vase is a radial height map r(θ, z): one radius in each direction round the axis at each height,
built on a grid of heights and angles. Because each height has exactly one radius in each direction,
every layer is one simple closed loop – what spiral vase mode needs – and the mesh can't cross itself:
each triangle lies in its own wedge of angle between two heights. The wall is joined to a flat bottom
and a flat top, so the solid is closed, watertight and one piece, with no boolean operations.

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
cases, and checks that each is closed and watertight with outward faces, flat on the bed, within the
overhang limit, and one closed loop at every height tested; that leans are measured right; that a
cylinder has the right volume and capacity; that STL and 3MF files read back the same; that designs save
and open; that your own function can reach nothing it shouldn't; and that colour changes land on layers.
`.venv\Scripts\python -m tests.test_app` drives the window itself: edits, curves, undo, the gallery,
Surprise me, every view, the print animation, saving and exporting. Test windows open on the second
screen, if there is one.

## License

MIT – see [LICENSE](LICENSE).
