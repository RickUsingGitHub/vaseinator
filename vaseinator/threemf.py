"""3MF export: the vase as one object, placed in the middle of the bed.

A 3MF file is a zip archive holding an XML model.  For the Bambu Studio /
OrcaSlicer family (Flash Studio, Orca-Flashforge, ...) the file also carries
``Metadata/model_settings.config``, which sets the object's filament, so it
arrives in the slot of the vase's first colour.  It holds no printer or print
settings, so nothing in the slicer is changed by opening the file.
"""

from __future__ import annotations

import zipfile

import numpy as np

_CONTENT_TYPES = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">\n'
    ' <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>\n'
    ' <Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>\n'
    ' <Default Extension="config" ContentType="text/xml"/>\n'
    '</Types>\n')

_RELS = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
    ' <Relationship Target="/3D/3dmodel.model" Id="rel0" '
    'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>\n'
    '</Relationships>\n')

_NS = {"m": "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"}


def _xml_escape(text: str) -> str:
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def _hex(rgb) -> str:
    return "#" + "".join(f"{int(round(max(0.0, min(1.0, c)) * 255)):02X}" for c in rgb)


def write_3mf(path: str, name: str, verts: np.ndarray, faces: np.ndarray, filament: int = 1,
              color=(0.8, 0.8, 0.8), position=(0.0, 0.0, 0.0)):
    """Write the vase as one object; the position goes into the build transform."""
    v = np.asarray(verts, dtype=np.float64)
    f = np.asarray(faces)
    # numpy string formatting is much faster than a Python loop for big meshes
    vs = np.char.add(np.char.add('<vertex x="', np.char.mod("%.5f", v[:, 0])), '" y="')
    vs = np.char.add(np.char.add(vs, np.char.mod("%.5f", v[:, 1])), '" z="')
    vs = np.char.add(np.char.add(vs, np.char.mod("%.5f", v[:, 2])), '"/>')
    ts = np.char.add(np.char.add('<triangle v1="', np.char.mod("%d", f[:, 0])), '" v2="')
    ts = np.char.add(np.char.add(ts, np.char.mod("%d", f[:, 1])), '" v3="')
    ts = np.char.add(np.char.add(ts, np.char.mod("%d", f[:, 2])), '"/>')
    x, y, z = (float(c) for c in position)
    nm = _xml_escape(name)
    model = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<model unit="millimeter" xml:lang="en-US" '
        'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">\n'
        f' <metadata name="Title">{nm}</metadata>\n'
        ' <metadata name="Application">Vaseinator</metadata>\n'
        ' <resources>\n'
        f'  <basematerials id="1">\n   <base name="{nm}" displaycolor="{_hex(color)}"/>\n  </basematerials>\n'
        f'  <object id="2" type="model" name="{nm}" pid="1" pindex="0">\n'
        '   <mesh>\n    <vertices>\n' + "\n".join(vs.tolist()) + '\n    </vertices>\n'
        '    <triangles>\n' + "\n".join(ts.tolist()) + '\n    </triangles>\n   </mesh>\n'
        '  </object>\n'
        ' </resources>\n'
        ' <build>\n'
        f'  <item objectid="2" transform="1 0 0 0 1 0 0 0 1 {x:.4f} {y:.4f} {z:.4f}"/>\n'
        ' </build>\n'
        '</model>\n')
    settings = (
        '<?xml version="1.0" encoding="UTF-8"?>\n<config>\n'
        ' <object id="2">\n'
        f'  <metadata key="name" value="{nm}"/>\n'
        f'  <metadata key="extruder" value="{int(filament)}"/>\n'
        '  <part id="2" subtype="normal_part">\n'
        f'   <metadata key="name" value="{nm}"/>\n'
        f'   <metadata key="extruder" value="{int(filament)}"/>\n'
        '  </part>\n'
        ' </object>\n</config>\n')
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        zf.writestr("[Content_Types].xml", _CONTENT_TYPES)
        zf.writestr("_rels/.rels", _RELS)
        zf.writestr("3D/3dmodel.model", model)
        zf.writestr("Metadata/model_settings.config", settings)


def read_3mf(path: str):
    """Read back a 3MF written by :func:`write_3mf` (used by the tests).

    Returns (name, verts, faces, filament, (x, y, z)).
    """
    import xml.etree.ElementTree as ET

    with zipfile.ZipFile(path) as zf:
        root = ET.fromstring(zf.read("3D/3dmodel.model"))
        config = ET.fromstring(zf.read("Metadata/model_settings.config"))
    assert root.get("unit") == "millimeter"
    fil = int(config.find("object/metadata[@key='extruder']").get("value"))
    obj = root.find("m:resources", _NS).find("m:object", _NS)
    mesh = obj.find("m:mesh", _NS)
    v = np.array([[float(e.get(a)) for a in "xyz"]
                  for e in mesh.find("m:vertices", _NS).findall("m:vertex", _NS)])
    f = np.array([[int(e.get(a)) for a in ("v1", "v2", "v3")]
                  for e in mesh.find("m:triangles", _NS).findall("m:triangle", _NS)])
    item = root.find("m:build", _NS).find("m:item", _NS)
    t = [float(x) for x in item.get("transform").split()]
    return obj.get("name"), v, f, fil, tuple(t[9:12])
