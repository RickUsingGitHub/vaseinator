"""Put the web version together in site/: the page, the Python it runs, and the gallery pictures.

    .venv\\Scripts\\python tools\\build_web.py            then, to try it:
    .venv\\Scripts\\python -m http.server 8000 -d site    and open http://localhost:8000

The page runs the same vaseinator package as the desktop app - the parts of it that need no Qt - in the
browser with Pyodide. GitHub Pages publishes site/ (see .github/workflows/pages.yml).
"""

import json
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# the package's modules that need no Qt: the geometry, the designs and the exports
MODULES = ("__init__", "choices", "expr", "geometry", "hollow", "params", "presets", "sections", "shapes", "stl",
           "threemf")
PAGE = ("index.html", "style.css", "app.js", "worker.js")


def main(out=None):
    out = out or os.path.join(ROOT, "site")
    if os.path.isdir(out):
        shutil.rmtree(out)
    os.makedirs(os.path.join(out, "py", "vaseinator"))
    os.makedirs(os.path.join(out, "gallery"))
    for name in PAGE:
        shutil.copy2(os.path.join(ROOT, "web", name), os.path.join(out, name))
    shutil.copy2(os.path.join(ROOT, "assets", "icon.png"), os.path.join(out, "icon.png"))
    files = ["bridge.py"]
    shutil.copy2(os.path.join(ROOT, "web", "bridge.py"), os.path.join(out, "py", "bridge.py"))
    for m in MODULES:
        src = os.path.join(ROOT, "vaseinator", m + ".py")
        with open(src, encoding="utf-8") as fh:
            text = fh.read()
        if "PySide6" in text.split("def ", 1)[0]:             # imported at the top: it would not load
            sys.exit(f"vaseinator/{m}.py needs Qt, so it can't run in the browser")
        shutil.copy2(src, os.path.join(out, "py", "vaseinator", m + ".py"))
        files.append(f"vaseinator/{m}.py")
    with open(os.path.join(out, "py", "files.json"), "w", encoding="utf-8") as fh:
        json.dump(files, fh)
    pictures = os.path.join(ROOT, "assets", "gallery")
    for name in sorted(os.listdir(pictures)):
        if name.endswith(".png"):
            shutil.copy2(os.path.join(pictures, name), os.path.join(out, "gallery", name))
    open(os.path.join(out, ".nojekyll"), "w").close()      # serve every file as it is
    print("built", out)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
