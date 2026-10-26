"""Slice a project 3MF with Flash Studio's own engine, headless, and report what it would print.

    .venv\\Scripts\\python tools\\check_with_slicer.py vase.3mf [--slicer "C:\\...\\flash studio.exe"]

It runs the slicer's command line (OrcaSlicer's --slice), which never opens a
window, then reads the G-code: is spiral vase on, does the wall climb all the
way round, and where does it change toolhead or filament.
"""

import os
import re
import subprocess
import sys
import tempfile

SLICERS = [r"C:\Program Files\Flashforge\Flash Studio Desktop\flash studio.exe",
           r"C:\Program Files\OrcaSlicer\orca-slicer.exe"]


def slice_3mf(project: str, slicer: str, out_dir: str) -> str:
    """Slice every plate; returns the first plate's G-code path."""
    subprocess.run([slicer, "--slice", "0", "--outputdir", out_dir, os.path.abspath(project)], check=True,
                   timeout=900, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    gcode = os.path.join(out_dir, "plate_1.gcode")
    if not os.path.exists(gcode):
        raise RuntimeError(f"the slicer wrote no G-code (see {out_dir})")
    return gcode


def read_gcode(path: str) -> dict:
    """What a sliced spiral vase does: its settings, how much climbs, and each tool change."""
    settings, tools, layer_z, climbing, layers = {}, [], None, 0, 0
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if line.startswith(";Z:"):
                layer_z = float(line[3:])
                layers += 1
            elif line.startswith("G1 Z") and " E" in line and " X" in line:
                climbing += 1                    # a spiral move: up a little while it prints
            elif re.match(r"T\d+\s*$", line) or re.match(r"M600\b", line):
                tools.append((layer_z, line.strip()))
            elif line.startswith("; ") and " = " in line:
                key, _, value = line[2:].partition(" = ")
                settings[key.strip()] = value.strip()
    return dict(settings=settings, tools=tools, climbing=climbing, layers=layers)


def main(argv):
    files = [a for a in argv if a.lower().endswith(".3mf")]
    slicer = argv[argv.index("--slicer") + 1] if "--slicer" in argv else next((s for s in SLICERS if os.path.exists(s)), None)
    if not slicer or not files:
        print(__doc__)
        return 2
    ok = True
    for f in files:
        with tempfile.TemporaryDirectory() as out:
            g = read_gcode(slice_3mf(f, slicer, out))
        s = g["settings"]
        changes = [t for t in g["tools"] if t[0] is not None]
        spiral = s.get("spiral_mode") == "1" and g["climbing"] > 0
        print(f"{os.path.basename(f)}: {s.get('printer_model', '?')}")
        print(f"  {'✓' if spiral else '✗'} spiral vase: spiral_mode = {s.get('spiral_mode')}, "
              f"{g['climbing']:,} moves climb as they print, {g['layers']} layers")
        print(f"  wall loops {s.get('wall_loops')}, top layers {s.get('top_shell_layers')}, bottom layers "
              f"{s.get('bottom_shell_layers')}, infill {s.get('sparse_infill_density')}, supports {s.get('enable_support')}, "
              f"line {s.get('outer_wall_line_width')} mm, layers {s.get('layer_height')} mm")
        print(f"  filaments: {s.get('filament_colour')}")
        print("  colour changes: " + (", ".join(f"{cmd} at {z:g} mm" for z, cmd in changes) or "none"))
        ok &= spiral
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
