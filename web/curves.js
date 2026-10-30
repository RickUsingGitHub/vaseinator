// A small editor for a curve up the height of the vase - the desktop app's curves.py, in a canvas.
//
// Most curves are drawn as an ordinary graph: the vase from bottom to top runs left to right, and the value
// runs up. The outline's editor is drawn mirrored and upright instead, like the vase from the side.

const POINT_R = 5;
const HIT = 10;
const GAP = 0.02;               // the closest two points may come in height

export function pchip(xk, yk, xs) {
  // monotone cubic (Fritsch-Carlson) through the points: smooth, and it never overshoots
  const n = xk.length;
  if (n === 1) return xs.map(() => yk[0]);
  const hk = [];
  const delta = [];
  for (let k = 0; k < n - 1; k++) {
    hk.push(xk[k + 1] - xk[k]);
    delta.push((yk[k + 1] - yk[k]) / hk[k]);
  }
  const d = new Array(n).fill(0);
  if (n === 2) {
    d[0] = d[1] = delta[0];
  } else {
    for (let k = 1; k < n - 1; k++) {
      if (delta[k - 1] * delta[k] > 0) {
        const w1 = 2 * hk[k] + hk[k - 1];
        const w2 = hk[k] + 2 * hk[k - 1];
        d[k] = (w1 + w2) / (w1 / delta[k - 1] + w2 / delta[k]);
      }
    }
    const end = (h0, h1, d0, d1) => {
      let v = ((2 * h0 + h1) * d0 - h0 * d1) / (h0 + h1);
      if (Math.sign(v) !== Math.sign(d0)) v = 0;
      else if (Math.sign(d0) !== Math.sign(d1) && Math.abs(v) > Math.abs(3 * d0)) v = 3 * d0;
      return v;
    };
    d[0] = end(hk[0], hk[1], delta[0], delta[1]);
    d[n - 1] = end(hk[n - 2], hk[n - 3], delta[n - 2], delta[n - 3]);
  }
  return xs.map((x) => {
    let i = 0;
    while (i < n - 2 && x >= xk[i + 1]) i++;
    const t = Math.min(Math.max((x - xk[i]) / hk[i], 0), 1);
    const t2 = t * t;
    const t3 = t2 * t;
    return (2 * t3 - 3 * t2 + 1) * yk[i] + (t3 - 2 * t2 + t) * hk[i] * d[i]
      + (-2 * t3 + 3 * t2) * yk[i + 1] + (t3 - t2) * hk[i] * d[i + 1];
  });
}

export function themeColour(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

export class CurveEditor {
  // onChange(points, live): live while a point is dragged, then once more when it is let go
  constructor(canvas, { lo, hi, unit = "", mirror = false, height = 110, floor = null, grow = false, decimals = 0 },
              onChange) {
    this.canvas = canvas;
    this.lo = lo;
    this.hi = hi;
    this.base = [lo, hi];
    this.unit = unit;
    this.mirror = mirror;
    this.floor = floor;
    this.grow = grow;
    this.decimals = decimals;
    this.onChange = onChange;
    this.points = [[0, 0], [1, 0]];
    this.drag = null;
    this.hover = null;
    this.inside = false;
    canvas.style.height = `${height}px`;
    canvas.title = mirror
      ? "Drag the points out and in. Double-click to add one; right-click a point to take it away. Up the editor is up the vase."
      : "Drag a point up for more, down for less. Double-click to add a point; right-click a point to take it away. Left to right is the bottom of the vase to the top.";
    canvas.addEventListener("pointerdown", (e) => this.down(e));
    canvas.addEventListener("pointermove", (e) => this.move(e));
    canvas.addEventListener("pointerup", (e) => this.up(e));
    canvas.addEventListener("pointercancel", (e) => this.up(e));
    canvas.addEventListener("dblclick", (e) => this.double(e));
    canvas.addEventListener("contextmenu", (e) => this.remove(e));
    canvas.addEventListener("pointerenter", () => { this.inside = true; this.draw(); });
    canvas.addEventListener("pointerleave", () => { this.inside = false; this.hover = null; this.draw(); });
    new ResizeObserver(() => this.draw()).observe(canvas);
  }

  setPoints(points) {
    if (this.drag !== null) return;               // the hand is on it: don't move it from under the hand
    this.points = points.map((p) => [Number(p[0]), Number(p[1])]);
    this.fitRange();
    this.draw();
  }

  fitRange() {
    if (!this.grow) return;
    const vals = this.points.map((p) => p[1]);
    let [lo, hi] = this.base;
    if (this.mirror) {
      hi = Math.max(hi, Math.max(...vals) * 1.15);
    } else {
      const span = Math.max(Math.abs(Math.min(...vals)), Math.abs(Math.max(...vals)),
        Math.max(Math.abs(lo), Math.abs(hi)) * 0.25) * 1.2;
      [lo, hi] = Math.min(lo, Math.min(...vals)) < 0 ? [-span, span] : [Math.min(lo, 0), Math.max(hi, span)];
    }
    this.lo = lo;
    this.hi = hi;
  }

  copy() {
    return this.points.map(([h, v]) => [Math.round(h * 1e4) / 1e4, Math.round(v * 1e3) / 1e3]);
  }

  area() {
    const w = this.canvas.clientWidth;
    const h = this.canvas.clientHeight;
    return { left: 8, top: 8, width: Math.max(w - 16, 10), height: Math.max(h - 32, 10) };
  }

  xy(h, v) {
    const a = this.area();
    if (this.mirror) {
      return [a.left + a.width / 2 + (0.5 * v / Math.max(this.hi, 1e-9)) * a.width, a.top + a.height - h * a.height];
    }
    const frac = (v - this.lo) / Math.max(this.hi - this.lo, 1e-9);
    return [a.left + h * a.width, a.top + a.height - frac * a.height];
  }

  value(x, y) {
    const a = this.area();
    let h;
    let v;
    if (this.mirror) {
      h = (a.top + a.height - y) / a.height;
      v = (Math.abs(x - (a.left + a.width / 2)) / (0.5 * a.width)) * this.hi;
    } else {
      h = (x - a.left) / a.width;
      v = this.lo + ((a.top + a.height - y) / a.height) * (this.hi - this.lo);
      v = Math.min(Math.max(v, this.lo), this.hi);
    }
    if (this.floor !== null && this.floor !== undefined) v = Math.max(v, this.floor);
    return [Math.min(Math.max(h, 0), 1), v];
  }

  pos(e) {
    const r = this.canvas.getBoundingClientRect();
    return [e.clientX - r.left, e.clientY - r.top];
  }

  hit(x, y) {
    let best = null;
    let bestD = HIT;
    const a = this.area();
    this.points.forEach(([h, v], i) => {
      const [px, py] = this.xy(h, v);
      const spots = this.mirror ? [[px, py], [2 * (a.left + a.width / 2) - px, py]] : [[px, py]];
      for (const [qx, qy] of spots) {
        const d = Math.abs(qx - x) + Math.abs(qy - y);
        if (d < bestD) {
          best = i;
          bestD = d;
        }
      }
    });
    return best;
  }

  down(e) {
    if (e.button !== 0) return;
    const i = this.hit(...this.pos(e));
    if (i === null) return;
    this.drag = i;
    this.canvas.setPointerCapture(e.pointerId);
    e.preventDefault();
    this.draw();
  }

  move(e) {
    const [x, y] = this.pos(e);
    if (this.drag === null) {
      const i = this.hit(x, y);
      if (i !== this.hover) {
        this.hover = i;
        this.draw();
      }
      return;
    }
    let [h, v] = this.value(x, y);
    const i = this.drag;
    if (i === 0) h = 0;
    else if (i === this.points.length - 1) h = 1;
    else h = Math.min(Math.max(h, this.points[i - 1][0] + GAP), this.points[i + 1][0] - GAP);
    this.points[i] = [h, v];
    this.draw();
    this.onChange(this.copy(), true);
  }

  up() {
    if (this.drag === null) return;
    this.drag = null;
    this.fitRange();
    this.draw();
    this.onChange(this.copy(), false);
  }

  double(e) {
    const [x, y] = this.pos(e);
    if (this.hit(x, y) !== null) return;
    const [h, v] = this.value(x, y);
    if (this.points.some((q) => Math.abs(h - q[0]) < GAP)) return;
    this.points.push([h, v]);
    this.points.sort((p, q) => p[0] - q[0]);
    this.draw();
    this.onChange(this.copy(), false);
  }

  remove(e) {
    e.preventDefault();
    const i = this.hit(...this.pos(e));
    if (i !== null && i > 0 && i < this.points.length - 1) {
      this.points.splice(i, 1);
      this.hover = null;
      this.draw();
      this.onChange(this.copy(), false);
    }
  }

  fmt(v) {
    return v.toFixed(this.decimals);
  }

  draw() {
    const c = this.canvas;
    const w = c.clientWidth;
    const h = c.clientHeight;
    if (!w || !h) return;
    const dpr = window.devicePixelRatio || 1;
    if (c.width !== Math.round(w * dpr) || c.height !== Math.round(h * dpr)) {
      c.width = Math.round(w * dpr);
      c.height = Math.round(h * dpr);
    }
    const g = c.getContext("2d");
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    const accent = themeColour("--accent");
    const muted = themeColour("--muted");
    const line = themeColour("--line");
    g.fillStyle = themeColour("--well");
    g.fillRect(0, 0, w, h);
    const a = this.area();
    g.strokeStyle = line;
    g.lineWidth = 1;
    g.strokeRect(a.left + 0.5, a.top + 0.5, a.width, a.height);
    g.setLineDash([2, 3]);
    for (const k of [0.25, 0.5, 0.75]) {                          // quarters of the vase's height
      g.beginPath();
      if (this.mirror) {
        const y = a.top + a.height - k * a.height;
        g.moveTo(a.left, y);
        g.lineTo(a.left + a.width, y);
      } else {
        const x = a.left + k * a.width;
        g.moveTo(x, a.top);
        g.lineTo(x, a.top + a.height);
      }
      g.stroke();
    }
    g.setLineDash([]);
    if (!this.mirror && this.lo < 0 && this.hi > 0) {             // the zero line
      const y0 = this.xy(0, 0)[1];
      g.beginPath();
      g.moveTo(a.left, y0);
      g.lineTo(a.left + a.width, y0);
      g.stroke();
    }
    const hs = Array.from({ length: 160 }, (_, i) => i / 159);
    const vs = pchip(this.points.map((p) => p[0]), this.points.map((p) => p[1]), hs);
    const pts = hs.map((hh, i) => this.xy(hh, vs[i]));
    g.fillStyle = accent;
    g.globalAlpha = 0.18;
    g.beginPath();
    if (this.mirror) {
      const cx = a.left + a.width / 2;
      pts.forEach(([x, y], i) => (i ? g.lineTo(x, y) : g.moveTo(x, y)));
      for (let i = pts.length - 1; i >= 0; i--) g.lineTo(2 * cx - pts[i][0], pts[i][1]);
    } else {
      const base = this.xy(0, Math.min(Math.max(0, this.lo), this.hi))[1];
      g.moveTo(pts[0][0], base);
      pts.forEach(([x, y]) => g.lineTo(x, y));
      g.lineTo(pts[pts.length - 1][0], base);
    }
    g.fill();
    g.globalAlpha = 1;
    g.strokeStyle = accent;
    g.lineWidth = 1.6;
    const sides = this.mirror ? [pts, pts.map(([x, y]) => [2 * (a.left + a.width / 2) - x, y])] : [pts];
    for (const side of sides) {
      g.beginPath();
      side.forEach(([x, y], i) => (i ? g.lineTo(x, y) : g.moveTo(x, y)));
      g.stroke();
    }
    this.points.forEach(([hh, v], i) => {
      const [x, y] = this.xy(hh, v);
      const on = i === this.drag || i === this.hover;
      g.beginPath();
      g.arc(x, y, POINT_R + (on ? 1 : 0), 0, 2 * Math.PI);
      g.fillStyle = on ? "#ffffff" : accent;
      g.fill();
      g.strokeStyle = "#14161a";
      g.lineWidth = 1;
      g.stroke();
    });
    g.font = "11px system-ui, sans-serif";
    g.fillStyle = muted;
    g.textBaseline = "middle";
    const under = a.top + a.height + 12;
    const range = `${this.fmt(this.mirror ? 0 : this.lo)} … ${this.fmt(this.hi)}${this.unit}`;
    if (this.mirror) {
      g.textAlign = "left";
      g.fillText("↑ up the vase", a.left, under);
      g.textAlign = "right";
      g.fillText(range, a.left + a.width, under);
    } else {
      g.textAlign = "left";
      g.fillText("bottom", a.left, under);
      g.textAlign = "center";
      g.fillText(`→ up the vase →   (${range})`, a.left + a.width / 2, under);
      g.textAlign = "right";
      g.fillText("top", a.left + a.width, under);
    }
    if (this.inside && this.drag === null && this.hover === null) {
      g.textAlign = "right";
      g.fillText("double-click: add a point · right-click: remove", a.left + a.width - 4, a.top + 9);
    }
    const k = this.drag !== null ? this.drag : this.hover;
    if (k !== null) {
      const [hh, v] = this.points[k];
      const [x, y] = this.xy(hh, v);
      const text = `${this.fmt(v)}${this.unit} at ${Math.round(hh * 100)}% up`;
      g.fillStyle = themeColour("--text");
      const right = x + 10 + g.measureText(text).width < a.left + a.width;
      g.textAlign = right ? "left" : "right";
      g.fillText(text, right ? x + 10 : x - 10, y - 12 < a.top ? y + 12 : y - 12);
    }
  }
}
