"""Write the ready-made vases to examples/ as .vase design files, and five of them to examples/stl/.

    .venv\\Scripts\\python tools\\make_examples.py
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from vaseinator.geometry import VaseDesign  # noqa: E402
from vaseinator.params import save_design  # noqa: E402
from vaseinator.presets import GALLERY, gallery_design  # noqa: E402
from vaseinator.stl import write_stl  # noqa: E402

STLS = ("Lagoon Twist", "Star to Moon", "Lattice Lantern", "Gem Facets", "Coral Reef")


def main():
    out = os.path.join(ROOT, "examples")
    os.makedirs(os.path.join(out, "stl"), exist_ok=True)
    for title, _, _ in GALLERY:
        p = gallery_design(title)
        save_design(os.path.join(out, p.name + ".vase"), p)
        print("wrote", p.name + ".vase")
        if title in STLS:
            d = VaseDesign(p)
            assert d.closed and not d.errors, title
            write_stl(os.path.join(out, "stl", p.name + "_vase.stl"), d.verts, d.faces, p.name + "_vase")
            print("wrote", f"stl\\{p.name}_vase.stl")


if __name__ == "__main__":
    main()
