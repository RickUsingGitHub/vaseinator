// The pictures under the 3D view - the desktop app's plots.py: the vase from the side, in the colour of each
// height, and fifteen layers seen from above.

import { themeColour } from "./curves.js";

const rgb = (c, a = 1) => `rgba(${Math.round(c[0] * 255)}, ${Math.round(c[1] * 255)}, ${Math.round(c[2] * 255)}, ${a})`;

function prepare(canvas) {
  const w = canvas.clientWidth;
  const h = canvas.clientHeight;
  if (!w || !h) return null;
  const dpr = window.devicePixelRatio || 1;
  if (canvas.width !== Math.round(w * dpr) || canvas.height !== Math.round(h * dpr)) {
    canvas.width = Math.round(w * dpr);
    canvas.height = Math.round(h * dpr);
  }
  const g = canvas.getContext("2d");
  g.setTransform(dpr, 0, 0, dpr, 0, 0);
  g.fillStyle = themeColour("--well");
  g.fillRect(0, 0, w, h);
  return [g, w, h];
}

export function drawSide(canvas, d, limitTicks = true) {
  // the filled outline in the colour of each height; the narrowest radius dashed inside; the solid bottom;
  // orange ticks on the left where it was softened, red on the right anything still leaning too far
  const ready = prepare(canvas);
  if (!ready || !d) return;
  const [g, w, h] = ready;
  const a = { left: 8, top: 6, width: w - 16, height: h - 26 };
  const rmax = Math.max(...d.rmax, 1);
  const s = Math.min(a.width / (2 * rmax), a.height / Math.max(d.height, 1)) * 0.96;
  const cx = a.left + a.width / 2;
  const base = a.top + a.height;
  const X = (x) => cx + x * s;
  const Y = (z) => base - z * s;
  const n = d.z.length;
  for (let k = 0; k < n - 1; k++) {                               // a strip for each step up, in its colour
    g.fillStyle = rgb(d.colours[k]);
    g.beginPath();
    g.moveTo(X(d.rmax[k]), Y(d.z[k]));
    g.lineTo(X(d.rmax[k + 1]), Y(d.z[k + 1]) - 0.5);
    g.lineTo(X(-d.rmax[k + 1]), Y(d.z[k + 1]) - 0.5);
    g.lineTo(X(-d.rmax[k]), Y(d.z[k]));
    g.fill();
  }
  g.strokeStyle = "rgba(20, 22, 26, 0.35)";                     // an edge, so a white vase shows on a light page
  g.beginPath();
  d.z.forEach((z, k) => (k ? g.lineTo(X(d.rmax[k]), Y(z)) : g.moveTo(X(d.rmax[k]), Y(z))));
  for (let k = n - 1; k >= 0; k--) g.lineTo(X(-d.rmax[k]), Y(d.z[k]));
  g.closePath();
  g.stroke();
  g.strokeStyle = "rgba(20, 22, 26, 0.6)";
  g.setLineDash([4, 3]);
  for (const sign of [-1, 1]) {
    g.beginPath();
    d.z.forEach((z, k) => (k ? g.lineTo(X(sign * d.rmin[k]), Y(z)) : g.moveTo(X(sign * d.rmin[k]), Y(z))));
    g.stroke();
  }
  g.setLineDash([]);
  g.strokeStyle = "rgba(255, 255, 255, 0.3)";
  g.beginPath();
  g.moveTo(X(-d.rmax[0]), Y(d.zb));
  g.lineTo(X(d.rmax[0]), Y(d.zb));
  g.stroke();
  if (limitTicks) {
    g.lineWidth = 2;
    g.strokeStyle = "#eb3c32";
    g.beginPath();
    for (const z of d.bad) {
      g.moveTo(a.left + a.width - 9, Y(z));
      g.lineTo(a.left + a.width - 3, Y(z));
    }
    g.stroke();
    g.strokeStyle = "rgba(240, 163, 86, 0.8)";
    g.beginPath();
    for (const z of d.moved) {
      g.moveTo(a.left + 3, Y(z));
      g.lineTo(a.left + 9, Y(z));
    }
    g.stroke();
    g.lineWidth = 1;
  }
  g.fillStyle = themeColour("--muted");
  g.font = "11px system-ui, sans-serif";
  g.textAlign = "center";
  g.textBaseline = "bottom";
  g.fillText(`${Math.round(d.height)} mm tall, Ø ${Math.round(d.widest)} mm`, w / 2, h - 3);
}

export function drawTop(canvas, d) {
  // the layers seen from above, lower ones fainter, the top one bold
  const ready = prepare(canvas);
  if (!ready || !d) return;
  const [g, w, h] = ready;
  const s = (Math.min(w, h - 6) / (2 * d.half)) * 0.95;
  const cx = w / 2;
  const cy = (h - 6) / 2 + 3;
  const n = d.slices.length;
  const path = (segs) => {
    g.beginPath();
    for (let i = 0; i + 3 < segs.length; i += 4) {
      g.moveTo(cx + segs[i] * s, cy - segs[i + 1] * s);
      g.lineTo(cx + segs[i + 2] * s, cy - segs[i + 3] * s);
    }
  };
  d.slices.forEach((segs, k) => {
    const width = k === n - 1 ? 2.2 : 1.2;
    path(segs);
    g.strokeStyle = "rgba(20, 22, 26, 0.18)";                    // an edge, so a white vase shows on a light page
    g.lineWidth = width + 1.2;
    g.stroke();
    g.strokeStyle = rgb(d.slice_colours[k], (120 + (135 * k) / Math.max(n - 1, 1)) / 255);
    g.lineWidth = width;
    g.stroke();
  });
  g.strokeStyle = themeColour("--muted");
  g.lineWidth = 1;
  g.beginPath();
  g.moveTo(cx - 4, cy); g.lineTo(cx + 4, cy);
  g.moveTo(cx, cy - 4); g.lineTo(cx, cy + 4);
  g.stroke();
}
