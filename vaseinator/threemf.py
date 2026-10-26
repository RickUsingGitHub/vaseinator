"""3MF export: the vase as one object, placed in the middle of the bed.

A 3MF file is a zip archive holding an XML model.  Two kinds are written:

* **The vase in colour** (:func:`write_3mf`): one object with a part per
  colour band, each set to its filament in ``Metadata/model_settings.config``
  - as Lenticular Sign Maker and Maze Tube Designer write them.  It holds no
  printer or print settings, so nothing in the slicer is changed by it.  The
  slicers will not print an object of several filaments in spiral vase mode,
  so a vase in bands prints as an ordinary hollow vase this way.
* **A slicer project** (:func:`write_project_3mf`) for the Bambu Studio /
  OrcaSlicer family (Flash Studio is one).  Its printer and filament settings
  come from a project the user saved in their slicer, with spiral vase mode
  switched on and the colour bands as filament changes at their layers
  (``Metadata/custom_gcode_per_layer.xml``).  These slicers only read
  settings and layer changes from a file that is one of their own projects,
  so the project's application stamp is kept too.  Open it as a project,
  not with Import, which reads the shapes only.
"""

from __future__ import annotations

import json
import re
import zipfile

import numpy as np

from .geometry import layer_top

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


def _object_xml(obj_id: int, name: str, verts: np.ndarray, faces: np.ndarray, material: str = "") -> str:
    v = np.asarray(verts, dtype=np.float64)
    f = np.asarray(faces)
    # numpy string formatting is much faster than a Python loop for big meshes
    vs = np.char.add(np.char.add('<vertex x="', np.char.mod("%.5f", v[:, 0])), '" y="')
    vs = np.char.add(np.char.add(vs, np.char.mod("%.5f", v[:, 1])), '" z="')
    vs = np.char.add(np.char.add(vs, np.char.mod("%.5f", v[:, 2])), '"/>')
    ts = np.char.add(np.char.add('<triangle v1="', np.char.mod("%d", f[:, 0])), '" v2="')
    ts = np.char.add(np.char.add(ts, np.char.mod("%d", f[:, 1])), '" v3="')
    ts = np.char.add(np.char.add(ts, np.char.mod("%d", f[:, 2])), '"/>')
    return (f' <object id="{obj_id}" type="model" name="{_xml_escape(name)}"{material}>\n'
            '  <mesh>\n   <vertices>\n' + "\n".join(vs.tolist()) + '\n   </vertices>\n'
            '   <triangles>\n' + "\n".join(ts.tolist()) + '\n   </triangles>\n  </mesh>\n'
            ' </object>\n')


def write_3mf(path: str, name: str, parts, position=(0.0, 0.0, 0.0)):
    """Write the vase as one object made of single-filament parts - one per colour band.

    parts: list of (part name, verts (V,3), faces (F,3), filament number from 1,
    display colour (r, g, b) in 0..1).  The same layout as Lenticular Sign Maker
    and Maze Tube Designer: Flash Studio / OrcaSlicer read each part's filament
    number from ``Metadata/model_settings.config`` on File ▸ Import, and the
    colours can be reassigned there.  The position goes into the build
    transform, so the vase sits at its place on the plate.
    """
    resources = [' <basematerials id="1">\n'
                 + "".join(f'  <base name="{_xml_escape(nm)}" displaycolor="{_hex(rgb)}"/>\n'
                           for nm, _, _, _, rgb in parts)
                 + ' </basematerials>\n']
    ids = []
    for k, (nm, verts, faces, _, _) in enumerate(parts):
        ids.append(k + 2)
        resources.append(_object_xml(k + 2, nm, verts, faces, f' pid="1" pindex="{k}"'))
    item = len(parts) + 2
    comps = "".join(f'   <component objectid="{i}"/>\n' for i in ids)
    resources.append(f' <object id="{item}" type="model" name="{_xml_escape(name)}">\n'
                     f'  <components>\n{comps}  </components>\n </object>\n')
    x, y, z = (float(c) for c in position)
    model = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<model unit="millimeter" xml:lang="en-US" '
        'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">\n'
        f' <metadata name="Title">{_xml_escape(name)}</metadata>\n'
        ' <metadata name="Application">Vaseinator</metadata>\n'
        ' <resources>\n' + "".join(resources) + ' </resources>\n'
        ' <build>\n'
        f'  <item objectid="{item}" transform="1 0 0 0 1 0 0 0 1 {x:.4f} {y:.4f} {z:.4f}"/>\n'
        ' </build>\n'
        '</model>\n')
    # the part list Orca-family slicers read names and filament numbers from
    settings = (
        '<?xml version="1.0" encoding="UTF-8"?>\n<config>\n'
        f' <object id="{item}">\n'
        f'  <metadata key="name" value="{_xml_escape(name)}"/>\n'
        f'  <metadata key="extruder" value="{int(parts[0][3])}"/>\n'
        + "".join(f'  <part id="{i}" subtype="normal_part">\n'
                  f'   <metadata key="name" value="{_xml_escape(nm)}"/>\n'
                  f'   <metadata key="extruder" value="{int(fil)}"/>\n'
                  f'  </part>\n'
                  for i, (nm, _, _, fil, _) in zip(ids, parts))
        + ' </object>\n</config>\n')
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        zf.writestr("[Content_Types].xml", _CONTENT_TYPES)
        zf.writestr("_rels/.rels", _RELS)
        zf.writestr("3D/3dmodel.model", model)
        zf.writestr("Metadata/model_settings.config", settings)


def read_3mf(path: str):
    """Read back a 3MF written by :func:`write_3mf` (used by the tests).

    Returns a list of (part name, verts, faces, filament number, (x, y, z)).
    """
    import xml.etree.ElementTree as ET

    with zipfile.ZipFile(path) as zf:
        root = ET.fromstring(zf.read("3D/3dmodel.model"))
        config = ET.fromstring(zf.read("Metadata/model_settings.config"))
    assert root.get("unit") == "millimeter"
    fils = {part.get("id"): int(part.find("metadata[@key='extruder']").get("value"))
            for part in config.iter("part")}
    meshes, groups = {}, {}
    for obj in root.find("m:resources", _NS).findall("m:object", _NS):
        mesh = obj.find("m:mesh", _NS)
        if mesh is None:
            groups[obj.get("id")] = [c.get("objectid") for c in
                                     obj.find("m:components", _NS).findall("m:component", _NS)]
            continue
        v = np.array([[float(e.get(a)) for a in "xyz"]
                      for e in mesh.find("m:vertices", _NS).findall("m:vertex", _NS)])
        f = np.array([[int(e.get(a)) for a in ("v1", "v2", "v3")]
                      for e in mesh.find("m:triangles", _NS).findall("m:triangle", _NS)])
        meshes[obj.get("id")] = (obj.get("name"), v, f)
    out = []
    for item in root.find("m:build", _NS).findall("m:item", _NS):
        t = [float(x) for x in item.get("transform").split()]
        for oid in groups[item.get("objectid")]:
            name, v, f = meshes[oid]
            out.append((name, v, f, fils[oid], tuple(t[9:12])))
    return out


# ============================================================ slicer projects
class TemplateError(ValueError):
    """The chosen file can't give slicer settings; the message says why, in plain words."""


_STAMP = re.compile(r'<metadata name="(Application|OrcaSlicer|BambuStudio:3mfVersion)">([^<]*)</metadata>')


def read_template(path: str) -> dict:
    """The slicer settings in a project 3MF saved by Flash Studio, OrcaSlicer or Bambu Studio.

    Returns dict(config, stamp, content_types, slice_info, printer, filaments).
    """
    try:
        with zipfile.ZipFile(path) as z:
            names = set(z.namelist())
            if "Metadata/project_settings.config" not in names:
                raise TemplateError("it holds no slicer settings. Open a print in Flash Studio, set it up for "
                                    "your printer and filaments, and save it with File ▸ Save Project.")
            head = z.read("3D/3dmodel.model")[:6000].decode("utf-8", "replace")
            stamp = _STAMP.findall(head)
            if not any(k == "Application" and v.startswith("BambuStudio") for k, v in stamp):
                raise TemplateError("it wasn't saved by Flash Studio, OrcaSlicer or Bambu Studio.")
            config = json.loads(z.read("Metadata/project_settings.config"))
            content_types = z.read("[Content_Types].xml")
            slice_info = z.read("Metadata/slice_info.config") if "Metadata/slice_info.config" in names else None
    except TemplateError:
        raise
    except (OSError, zipfile.BadZipFile, KeyError, ValueError) as exc:
        raise TemplateError(f"it can't be read as a 3MF project ({exc}).") from None
    return dict(config=config, stamp=stamp, content_types=content_types, slice_info=slice_info,
                printer=str(config.get("printer_model") or config.get("printer_settings_id") or "your printer"),
                filaments=max(len(config.get("filament_colour", [])), 1))


def spiral_settings(bottom_layers: int, layer_height: float, line_width: float) -> dict:
    """The print settings spiral vase mode needs, as Orca-family slicers name them."""
    return {"spiral_mode": "1", "wall_loops": "1", "top_shell_layers": "0", "top_shell_thickness": "0",
            "bottom_shell_layers": str(int(bottom_layers)), "bottom_shell_thickness": "0",
            "sparse_infill_density": "0%", "enable_support": "0", "timelapse_type": "0",
            "enable_wrapping_detection": "0", "layer_height": f"{layer_height:g}",
            "outer_wall_line_width": f"{line_width:g}", "inner_wall_line_width": f"{line_width:g}"}


def write_project_3mf(path: str, name: str, verts: np.ndarray, faces: np.ndarray, template: dict,
                      settings: dict, bands, colours: dict, position=(0.0, 0.0, 0.0)) -> list:
    """Write the vase as a slicer project, on the template's printer and filament settings.

    settings: print settings to change (spiral_settings()).  bands: [(from z,
    filament)], the first from 0.  colours: filament number -> '#RRGGBB'.
    Returns the colour changes written: [(layer, top of that layer, filament)].
    A printer with several filaments changes tool (or filament) at a layer; one
    with a single filament pauses there for a colour change by hand.
    """
    config = dict(template["config"])
    essential = {"spiral_mode", "wall_loops", "top_shell_layers", "bottom_shell_layers", "sparse_infill_density",
                 "enable_support", "layer_height"}
    config.update({k: v for k, v in settings.items() if k in config or k in essential})
    if isinstance(config.get("filament_colour"), list):
        config["filament_colour"] = [colours.get(k + 1, c) for k, c in enumerate(config["filament_colour"])]
    lh = float(config.get("layer_height", 0.2))
    try:
        first = float(config.get("initial_layer_print_height", lh))
    except (TypeError, ValueError):
        first = lh
    several = template["filaments"] > 1
    changes, items = [], []
    for z, fil in bands[1:]:
        layer, top = layer_top(z, lh, first)
        changes.append((layer, top, fil))
        if several:      # a tool change, or a filament change on a printer that switches filament itself
            items.append(f'<layer top_z="{top:g}" type="2" extruder="{int(fil)}" color="{colours[fil]}" extra="" '
                         'gcode="tool_change"/>')
        else:            # one filament: a pause to change colour by hand
            items.append(f'<layer top_z="{top:g}" type="0" extruder="1" color="{colours[fil]}" extra="" '
                         'gcode="M600"/>')
    # one object on one filament: these slicers keep its layer changes as "multi as single"
    mode = "MultiAsSingle" if several else "SingleExtruder"
    custom = ('<?xml version="1.0" encoding="utf-8"?>\n<custom_gcodes_per_layer>\n<plate>\n<plate_info id="1"/>\n'
              + "".join(i + "\n" for i in items) + f'<mode value="{mode}"/>\n</plate>\n</custom_gcodes_per_layer>\n')

    v = np.asarray(verts, dtype=np.float64)
    f = np.asarray(faces)
    vs = np.char.add(np.char.add('<vertex x="', np.char.mod("%.5f", v[:, 0])), '" y="')
    vs = np.char.add(np.char.add(vs, np.char.mod("%.5f", v[:, 1])), '" z="')
    vs = np.char.add(np.char.add(vs, np.char.mod("%.5f", v[:, 2])), '"/>')
    ts = np.char.add(np.char.add('<triangle v1="', np.char.mod("%d", f[:, 0])), '" v2="')
    ts = np.char.add(np.char.add(ts, np.char.mod("%d", f[:, 1])), '" v3="')
    ts = np.char.add(np.char.add(ts, np.char.mod("%d", f[:, 2])), '"/>')
    ns = ('xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02" '
          'xmlns:BambuStudio="http://schemas.bambulab.com/package/2021" '
          'xmlns:p="http://schemas.microsoft.com/3dmanufacturing/production/2015/06" requiredextensions="p"')
    mesh = ('<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<model unit="millimeter" xml:lang="en-US" {ns}>\n'
            ' <metadata name="BambuStudio:3mfVersion">1</metadata>\n <resources>\n'
            '  <object id="1" p:UUID="00010000-81cb-4c03-9d28-80fed5dfa1dc" type="model">\n   <mesh>\n    <vertices>\n'
            + "\n".join(vs.tolist()) + '\n    </vertices>\n    <triangles>\n' + "\n".join(ts.tolist())
            + '\n    </triangles>\n   </mesh>\n  </object>\n </resources>\n <build/>\n</model>\n')
    x, y, z0 = (float(c) for c in position)
    place = f"1 0 0 0 1 0 0 0 1 {x:.4f} {y:.4f} {z0:.4f}"
    nm = _xml_escape(name)
    stamp = "".join(f' <metadata name="{k}">{_xml_escape(val)}</metadata>\n' for k, val in template["stamp"])
    model = ('<?xml version="1.0" encoding="UTF-8"?>\n'
             f'<model unit="millimeter" xml:lang="en-US" {ns}>\n' + stamp
             + f' <metadata name="Title">{nm}</metadata>\n <resources>\n'
             '  <object id="2" p:UUID="00000001-61cb-4c03-9d28-80fed5dfa1dc" type="model">\n   <components>\n'
             '    <component p:path="/3D/Objects/vase_1.model" objectid="1" '
             'p:UUID="00010000-b206-40ff-9872-83e8017abed1" transform="1 0 0 0 1 0 0 0 1 0 0 0"/>\n'
             '   </components>\n  </object>\n </resources>\n'
             ' <build p:UUID="2c7c17d8-22b5-4d84-8835-1976022ea369">\n'
             f'  <item objectid="2" p:UUID="00000002-b1ec-4553-aec9-835e5b724bb4" transform="{place}" printable="1"/>\n'
             ' </build>\n</model>\n')
    model_settings = (
        '<?xml version="1.0" encoding="UTF-8"?>\n<config>\n  <object id="2">\n'
        f'    <metadata key="name" value="{nm}"/>\n    <metadata key="extruder" value="{int(bands[0][1])}"/>\n'
        '    <part id="1" subtype="normal_part">\n'
        f'      <metadata key="name" value="{nm}"/>\n'
        '      <metadata key="matrix" value="1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1"/>\n'
        '    </part>\n  </object>\n  <plate>\n    <metadata key="plater_id" value="1"/>\n'
        '    <metadata key="plater_name" value=""/>\n    <metadata key="locked" value="false"/>\n'
        '    <model_instance>\n      <metadata key="object_id" value="2"/>\n'
        '      <metadata key="instance_id" value="0"/>\n    </model_instance>\n  </plate>\n'
        f'  <assemble>\n   <assemble_item object_id="2" instance_id="0" transform="{place}" offset="0 0 0" />\n'
        '  </assemble>\n</config>\n')
    rels = ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
            ' <Relationship Target="{}" Id="rel-1" '
            'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>\n</Relationships>\n')
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        zf.writestr("[Content_Types].xml", template["content_types"])
        zf.writestr("_rels/.rels", rels.format("/3D/3dmodel.model"))
        zf.writestr("3D/3dmodel.model", model)
        zf.writestr("3D/_rels/3dmodel.model.rels", rels.format("/3D/Objects/vase_1.model"))
        zf.writestr("3D/Objects/vase_1.model", mesh)
        zf.writestr("Metadata/project_settings.config", json.dumps(config, indent=4))
        zf.writestr("Metadata/model_settings.config", model_settings)
        zf.writestr("Metadata/custom_gcode_per_layer.xml", custom)
        if template["slice_info"] is not None:
            zf.writestr("Metadata/slice_info.config", template["slice_info"])
    return changes
