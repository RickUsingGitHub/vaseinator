"""What the app says about a vase, and its help: the panel beside the 3D view, the steps to print it, and the
help texts. Plain HTML, shared by the desktop app and the web version. Nothing here needs Qt."""

from __future__ import annotations

import os
from html import escape

from . import __version__
from .expr import FUNCTION_HELP, VARIABLES
from .geometry import duration
from .params import REAL_VASE

APP_NAME = "Vaseinator"


def _chip(d, fil):
    c = d.filament_of(fil)
    return f"<span style='background:{c}; color:{c};'>&nbsp;■■&nbsp;</span>"


def info_html(d, errors, warnings) -> str:
    """What the panel beside the 3D view says about a vase: its sums, notes, warnings, colours and how to slice it."""
    css = ("<style>td{padding:2px 6px;} .k{color:#9aa3ad;} .e{color:#ff6b6b;} "
           ".w{color:#f2c14e;} .ok{color:#6fdc8c;} h3{margin:4px 0 6px 0;}</style>")
    html = [css]
    if errors:
        html.append("<h3 class='e'>Cannot build this vase</h3><ul>")
        html += [f"<li class='e'>{escape(e)}</li>" for e in errors]
        html.append("</ul>")
    if d is not None:
        html.append("<h3>The vase</h3><table>")
        for k, v in d.info().items():
            cls = " class='ok'" if v.endswith("✓") else (" class='e'" if v.endswith("✗") else "")
            html.append(f"<tr><td class='k'>{k}</td><td{cls}>{v}</td></tr>")
        html.append("</table>")
        for note in d.notes:
            html.append(f"<p class='k'>ℹ {escape(note)}</p>")
    if warnings:
        html.append("<h3 class='w'>Warnings</h3><ul>")
        html += [f"<li class='w'>{escape(w)}</li>" for w in warnings]
        html.append("</ul>")
    if d is not None:
        p = d.p
        real = p.vase_mode == REAL_VASE
        html.append("<h3>Colours</h3>")
        if d.gradient:
            cycles = d.metres / max(p.gradient_length, 0.05)
            html.append(f"<p class='k'>One gradient spool: about {cycles:.1f} colour cycles over the "
                        f"{d.metres:.1f} m this vase uses. The view shows where each colour lands.</p>")
        elif len(d.bands) == 1:
            f0 = d.bands[0][1]
            html.append(f"<p>{_chip(d, f0)} filament {f0}</p>")
            if real:
                html.append("<p class='k'>A seamless (spiral vase mode) print is one filament: Flash Studio "
                            "won't change filament in spiral vase mode. For bands or stripes of colour, "
                            "print it normally (Advanced ▸ Printing ▸ Print as).</p>")
        else:
            html.append("<table>")
            tops = [z for z, _ in d.bands[1:]] + [d.H]
            for (z, fil), top in zip(d.bands, tops):
                html.append(f"<tr><td class='k'>{z:.1f} – {top:.1f} mm</td>"
                            f"<td>{_chip(d, fil)} filament {fil}</td></tr>")
            html.append("</table><p class='k'><b>Export 3MF</b> makes each band its own part, set to its "
                        "filament: load it with File ▸ Import, and change the colours there as you like. "
                        "The slicer prints each band with its own filament.</p>")
        if real:
            html.append(
                "<h3>Slicing it: seamless, in spiral vase mode</h3>"
                "<p class='k'>Turn on <b>spiral vase</b> (Spiralize). "
                f"<b>{d.bottom_layers} bottom layers</b> at <b>{p.layer_height:g} mm</b>, 0 top layers, "
                f"0% infill, 1 wall, outer wall line width <b>{p.line_width:g} mm</b>. Supports off - "
                f"none are needed: nothing leans more than {d.worst:.0f}°. "
                "For a watertight vase: a little extra flow (103–105%), 5–10 °C hotter than usual for "
                "strong layer bonds, and a wide line. A brim helps a narrow foot stay put.</p>")
        else:
            html.append(
                "<h3>Slicing it: a normal print</h3>"
                "<p class='k'>Leave spiral vase <b>off</b> and slice with your <b>usual settings</b>: the "
                f"vase is exported as the hollow pot it is - a wall {d.wall:.1f} mm thick"
                + ("" if p.open_bottom else f" on a {d.zb:g} mm floor") + ", the holes cut through - so the "
                f"slicer just fills it in. Supports off - none are needed: nothing leans more than "
                f"{d.worst:.0f}°" + (f", and the points of the holes bridge at most {d.bridge:.1f} mm"
                                     if d.bridge > 0 else "") + ". A brim helps a narrow foot, or a "
                "mask's thin edge, stay put.</p>")
    return "".join(html)


def print_steps(d, path: str, parts: int, where: str = "your slicer") -> str:
    """After Save for printing: where the file is, and plain steps to print it (HTML)."""
    p = d.p
    if p.vase_mode == REAL_VASE:
        settings = (f"turn on <b>Spiral vase</b> (Spiralize), with <b>{d.bottom_layers} bottom layers</b> "
                    f"and the outer wall <b>{p.line_width:g} mm</b> wide")
    else:
        settings = ("leave <b>Spiral vase off</b> and use your <b>usual settings</b>: the wall is in the model, "
                    f"{d.wall:.1f} mm thick, so there is nothing to change")
    colours = ("Load the filament you want and print." if parts == 1 else
               f"It comes as <b>{parts} parts</b>, one for each band of colour, already set to filaments "
               f"{', '.join(str(k) for k in sorted({f for _, f in d.bands}))}: load those colours in those "
               "slots, or change them in the slicer.")
    edge = ""
    if p.worn or p.around < 360.0 or p.open_bottom:
        edge = ("<li>Add a <b>brim</b>: it stands on a thin edge" + (", a mask on its chin" if p.around < 360.0
                                                                   else "") + ".</li>")
    if p.straps:
        edge += "<li>When it is done, thread an <b>elastic strap</b> through the slots at the sides.</li>"
    return (f"<p>Saved <b>{os.path.basename(path)}</b><br>in {os.path.dirname(path)}</p>"
            f"<ol><li>Open it in {where} (the button below, or File ▸ Import).</li>"
            f"<li>In the print settings: {settings}.</li>"
            f"<li><b>No supports</b> - none are needed: nothing leans more than {d.worst:.0f}°.</li>{edge}"
            f"<li>{colours}</li>"
            f"<li>Slice it and print. It takes about <b>{duration(d.seconds)}</b> and "
            f"<b>{d.grams:.0f} g</b> of filament.</li></ol>")


PRINTING_HELP = ("<p><b>Save for printing</b> saves the vase as a 3MF and says how to print it. Advanced ▸ "
                 "Printing ▸ <b>Print as</b> chooses how:</p>"
                 "<ul><li><b>Normal print</b> (the usual): printed like any other print, the wall in the model. "
                 "Sturdy, watertight, in <b>colour</b> - each band is its own part in the 3MF, set to its filament "
                 "(load it with File ▸ Import and change the colours there as you like) - and it can have "
                 "<b>holes</b> or an <b>open bottom</b>.</li>"
                 "<li><b>Seamless</b>: the slicer's spiral vase mode - one continuous line, with no seam and a single "
                 "wall that glows when lit, in <b>one filament</b> (Flash Studio won't change filament in spiral "
                 "vase mode; a gradient spool still works). Hardly quicker than a normal print.</li></ul>"
                 "<h3>Seamless (spiral vase mode)</h3>"
                 "<p>The exported model is <b>solid</b>: spiral vase mode (Spiralize) prints only its outside, as one "
                 "continuous line climbing round and round, on a solid bottom. Don't slice it normally with infill - "
                 "it would print as a solid block.</p>"
                 "<ul><li><b>Spiral vase / Spiralize</b> on; 1 wall; 0 top layers; 0% infill.</li>"
                 "<li><b>Bottom layers</b>: the number in the panel, so the floor is as thick as set.</li>"
                 "<li><b>Outer wall line width</b>: the app's line width. 0.6–0.8 mm on a 0.4 mm nozzle is much "
                 "stronger and more watertight than 0.4 mm.</li>"
                 "<li><b>No supports</b>: every part of the wall leans no more than the limit you set, either way, "
                 "and the panel shows the steepest.</li></ul>"
                 "<h3>To make sure it holds water</h3>"
                 "<ul><li>A little extra flow (103–105%) and 5–10 °C hotter than usual bond the layers well.</li>"
                 "<li>Slow down: 30–50 mm/s for the wall.</li>"
                 "<li>PETG is more watertight than PLA. Silk PLA looks great but bonds a little less well.</li>"
                 "<li>Test it in a sink first. A coat of clear epoxy or varnish inside seals any weep.</li>"
                 "</ul>"
                 "<h3>Normal print</h3>"
                 "<ul><li><b>Spiral vase off</b>; otherwise your <b>usual settings</b>. The vase comes as the hollow "
                 "pot it is - the wall as thick as Walls × Line width, the floor, the rim, any holes cut through - so "
                 "there is nothing to set.</li>"
                 "<li>No supports, just as for a seamless one: every hole's top comes to a point, with at most a short "
                 "bridge at its very tip.</li></ul>"
                 "<h3>Masks and helmets</h3>"
                 "<ul><li>Gallery ▸ Choose a design has masks and a helmet, sized for a head 57 cm round. "
                 "<b>Head size</b> (Simple, or Advanced ▸ Masks and helmets) fits one to another head: measure round "
                 "the head above the eyebrows and ears, as for a hat.</li>"
                 "<li>A mask prints standing on its chin, a helmet on its rim: add a <b>brim</b>. No supports - the "
                 "eyes, mouth and strap slots come to points at the top, and a closed top comes in to a point no "
                 "steeper than the overhang limit, over a small ceiling the printer bridges.</li>"
                 "<li>Thread an elastic strap through the slots, and pad a helmet with a strip of foam inside.</li>"
                 "</ul>")

DRAWING_HELP = ("<p>Choose <b>Drawn - any outline</b> as the cross-section (or what it turns into) and draw the "
                "shape the vase has seen from above: lobes that swell past their necks, a crescent, a heart - "
                "anything that doesn't cross itself.</p>"
                "<ul><li>The middle of the editor is the vase's axis; the dashed circle is its widest. The outline "
                "is scaled so its furthest point touches it, and sized up the vase by the outline curve.</li>"
                "<li><b>Drag</b> a point. <b>Double-click</b> the line to add one; double-click a point to make it "
                "a <b>sharp corner</b> (a diamond) or smooth again (a circle). Right-click a point, or hover and "
                "press Delete, to take it away.</li>"
                "<li><b>Repeat around</b>, up to 100: draw one lobe and have it copied round the axis - the faint "
                "copies. Change the number and the lobe narrows or widens to fit, just as deep. Double-clicking a "
                "copy adds the point to the lobe you draw.</li>"
                "<li><b>Close up</b> shows one repeat big, turned to point upwards, with a little of its "
                "neighbours; above 8 repeats the editor starts that way.</li>"
                "<li><b>Full window…</b> opens the editor as big as the screen, with Repeat around and Start from. "
                "The wheel zooms, a right or middle drag moves it, F or Fit shows it all again. The vase follows as "
                "you draw; un-maximise it to watch.</li>"
                "<li><b>Start from</b>: ready-made outlines - a claw, bulbs, a heart - or "
                "<b>Trace a picture…</b> - a dark closed line, or a dark filled shape, on a light or see-through "
                "ground.</li>"
                "<li>For a blank start, <b>Gallery ▸ Plain cylinder</b> (or File ▸ New plain cylinder, "
                "Ctrl+Shift+N) gives a cylinder 200 mm across and 200 mm tall with everything else off; choose "
                "Drawn there and it starts as a circle.</li>"
                "<li>Switching a built-in shape to Drawn starts from that shape - a five-petalled flower becomes one "
                "petal, repeated five times - so you can pull it about.</li>"
                "<li>Twist, the change into a second shape, the patterns and the colours all work as before. The "
                "outline turns red if it crosses itself: such a layer can't print as one loop. With many thin "
                "lobes, deep patterns can close the gaps between them: the panel warns if a layer crosses "
                "itself.</li></ul>")

ABOUT = (f"<h3>{APP_NAME} {__version__}</h3>"
        "<p>Designs vases that print without supports - normally with walls, or seamless in spiral vase "
        "mode. Shape the outline, the cross-section and how it changes on the way up, spin it, cover it in "
        "patterns or your own formula, and colour it in bands, stripes or a gradient. Cut holes through it, "
        "open it at the bottom, close it over at the top - or give it a face, and make a mask or a "
        "helmet.</p>"
        "<p><b>3D view:</b> left-drag turn · right-drag / shift-drag pan · wheel zoom · double-click or F to "
        "go back to the chosen view · S spin · F5 watch it print.</p>"
        "<p>Exports are in millimetres, standing on the bed, ready to slice.</p>"
        "<p>Vaseinator is free. If it has made you something you like, you can "
        "<a href='https://ko-fi.com/rickapps'>buy me a coffee</a>.</p>")


def function_help() -> str:
    """What a formula can use, with tips."""
    rows = "".join(f"<tr><td><code>{k}</code></td><td>{v}</td></tr>" for k, v in VARIABLES.items())
    funcs = "".join(f"<tr><td><code>{k}</code></td><td>{v}</td></tr>" for k, v in FUNCTION_HELP)
    return ("<style>td{padding:2px 8px;vertical-align:top;} code{color:#f0a356;}</style>"
            "<p>Type a formula in millimetres; it is <b>added to the radius</b> everywhere on the vase. "
            "The vase is still softened afterwards, so even a wild formula prints without supports.</p>"
            f"<h4>Variables</h4><table>{rows}<tr><td><code>pi tau e</code></td><td>the constants</td></tr></table>"
            f"<h4>Functions</h4><table>{funcs}</table>"
            "<h4>Tips</h4><ul>"
            "<li>Spread a long formula over several lines if you like: the lines are read as <b>one formula</b>, "
            "so start each new line with + - * or / (a line starting with + adds another part). Anything after "
            "a # is a note:<br><code>1.5 * sin(6*theta + 4*pi*h)&nbsp;&nbsp;# waves<br>"
            "+ 0.8 * noise(4*cos(theta), 4*sin(theta), z/15)&nbsp;&nbsp;# and lumps</code></li>"
            "<li>Use whole numbers with the angle - <code>sin(5*theta)</code> - so the pattern meets itself "
            "round the back.</li>"
            "<li><code>phi</code> turns with the twist, so <code>sin(8*phi)</code> makes ribs that twist "
            "with the shape.</li>"
            "<li>For seamless noise, feed it the angle as a circle: "
            "<code>noise(4*cos(theta), 4*sin(theta), z/15)</code>.</li>"
            "<li><code>h</code> runs 0 to 1 up the vase, so <code>sin(pi*h)</code> is 0 at the ends and 1 in "
            "the middle - good for fading things in and out.</li></ul>")
