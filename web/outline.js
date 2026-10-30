// The cross-section editor - the desktop app's outline_editor.py, in a canvas.
//
// The middle is the vase's axis and the dashed circle its widest (the outline is scaled so its furthest point
// touches it). With Repeat around above 1 the points drawn are one piece - one lobe - and the rest are copies
// turned round the axis, shown fainter; with many repeats it shows one close up, turned to point upwards. In a
// big window the wheel zooms and a right or middle drag moves the view.

import { themeColour } from "./curves.js";

const HIT = 11;
const REACH = 1.35;            // how far from the axis a point may go, in widest radii
export const CLOSE_UP_FROM = 8;
const PER = 24;                // points along each side of the spline

// ------------------------------------------------------------------ the spline, as sections.py makes it
function chain(points, repeat) {
  const n = Math.max(Math.round(repeat), 1);
  const P = [];
  const cusp = [];
  for (let k = 0; k < n; k++) {
    const a = (2 * Math.PI * k) / n;
    const c = Math.cos(a);
    const s = Math.sin(a);
    for (const [x, y, sharp] of points) {
      P.push([x * c - y * s, x * s + y * c]);
      cusp.push(Boolean(sharp));
    }
  }
  return [P, cusp];
}

export function spline(points, repeat = 1, per = PER) {
  const [P, cusp] = chain(points, repeat);
  const n = P.length;
  const out = [];
  const tOut = [];
  const tIn = [];
  for (let i = 0; i < n; i++) {
    const prev = P[(i - 1 + n) % n];
    const nxt = P[(i + 1) % n];
    const p = P[i];
    const back = Math.hypot(p[0] - prev[0], p[1] - prev[1]);
    const ahead = Math.hypot(nxt[0] - p[0], nxt[1] - p[1]);
    if (cusp[i]) {
      tOut.push([(nxt[0] - p[0]) * 0.35, (nxt[1] - p[1]) * 0.35]);
      tIn.push([(p[0] - prev[0]) * 0.35, (p[1] - prev[1]) * 0.35]);
    } else {
      let dx = nxt[0] - prev[0];
      let dy = nxt[1] - prev[1];
      const l = Math.max(Math.hypot(dx, dy), 1e-12);
      dx /= l;
      dy /= l;
      tOut.push([dx * ahead, dy * ahead]);
      tIn.push([dx * back, dy * back]);
    }
  }
  for (let i = 0; i < n; i++) {
    const j = (i + 1) % n;
    for (let s = 0; s < per; s++) {
      const t = s / per;
      const h00 = 2 * t ** 3 - 3 * t ** 2 + 1;
      const h10 = t ** 3 - 2 * t ** 2 + t;
      const h01 = -2 * t ** 3 + 3 * t ** 2;
      const h11 = t ** 3 - t ** 2;
      out.push([h00 * P[i][0] + h10 * tOut[i][0] + h01 * P[j][0] + h11 * tIn[j][0],
        h00 * P[i][1] + h10 * tOut[i][1] + h01 * P[j][1] + h11 * tIn[j][1]]);
    }
  }
  return out;
}

export function crosses(loop, piece) {
  // whether a repeated outline crosses itself, looking only at the drawn piece's sides (every copy is the same)
  const n = loop.length;
  const m = Math.min(Math.max(piece, 1), n);
  let bx0 = Infinity; let by0 = Infinity; let bx1 = -Infinity; let by1 = -Infinity;
  for (let i = 0; i <= m; i++) {
    const [x, y] = loop[i % n];
    bx0 = Math.min(bx0, x); by0 = Math.min(by0, y); bx1 = Math.max(bx1, x); by1 = Math.max(by1, y);
  }
  const near = [];
  for (let j = 0; j < n; j++) {
    const a = loop[j];
    const b = loop[(j + 1) % n];
    if (Math.max(a[0], b[0]) >= bx0 && Math.min(a[0], b[0]) <= bx1 && Math.max(a[1], b[1]) >= by0
        && Math.min(a[1], b[1]) <= by1) near.push(j);
  }
  for (let i = 0; i < m; i++) {
    const p = loop[i];
    const q = loop[(i + 1) % n];
    const rx = q[0] - p[0];
    const ry = q[1] - p[1];
    for (const j of near) {
      if (j === i || j === (i + 1) % n || j === (i - 1 + n) % n || (j < m && j <= i)) continue;
      const a = loop[j];
      const b = loop[(j + 1) % n];
      const sx = b[0] - a[0];
      const sy = b[1] - a[1];
      const den = rx * sy - ry * sx;
      if (Math.abs(den) < 1e-12) continue;
      const qx = a[0] - p[0];
      const qy = a[1] - p[1];
      const t = (qx * sy - qy * sx) / den;
      const u = (qx * ry - qy * rx) / den;
      if (t >= 0 && t < 1 && u >= 0 && u < 1) return true;
    }
  }
  return false;
}

// ------------------------------------------------------------------ the editor
export class OutlineEditor {
  // onChange(points, live): live while a point is dragged; onView(): close up switched
  constructor(canvas, { big = false } = {}, onChange, onView = () => {}) {
    this.canvas = canvas;
    this.big = big;
    this.onChange = onChange;
    this.onView = onView;
    this.points = [[1, 0, false], [-0.5, 0.87, false], [-0.5, -0.87, false]];
    this.repeat = 1;
    this.choice = null;           // one repeat close up: null follows Repeat around
    this.view = null;             // [cx, cy, pixels per unit, turn] - fitted again when null
    this.byHand = false;
    this.drag = null;
    this.hover = null;
    this.inside = false;
    this.pan = null;
    this.cache = null;
    canvas.tabIndex = 0;
    canvas.title = "Drag the points. Double-click the line to add a point; double-click a point to make it sharp "
      + "(a cusp) or smooth again; right-click a point to take it away. The middle is the vase's axis; the dashed "
      + "circle is its widest." + (big ? " The wheel zooms; drag with the right or middle button to move; F fits it again." : "");
    canvas.addEventListener("pointerdown", (e) => this.down(e));
    canvas.addEventListener("pointermove", (e) => this.move(e));
    canvas.addEventListener("pointerup", (e) => this.up(e));
    canvas.addEventListener("pointercancel", (e) => this.up(e));
    canvas.addEventListener("dblclick", (e) => this.double(e));
    canvas.addEventListener("contextmenu", (e) => e.preventDefault());
    canvas.addEventListener("wheel", (e) => this.wheel(e), { passive: false });
    canvas.addEventListener("keydown", (e) => this.key(e));
    canvas.addEventListener("pointerenter", () => { this.inside = true; this.draw(); });
    canvas.addEventListener("pointerleave", () => { this.inside = false; this.hover = null; this.draw(); });
    new ResizeObserver(() => {
      if (!this.byHand) this.view = null;
      this.draw();
    }).observe(canvas);
  }

  setOutline(points, repeat) {
    if (this.drag !== null) return;
    repeat = Math.max(Math.round(repeat), 1);
    if (repeat !== this.repeat) {
      this.choice = null;
      this.view = null;
      this.byHand = false;
    }
    this.points = points.map(([x, y, c]) => [Number(x), Number(y), Boolean(c)]);
    this.repeat = repeat;
    if (this.view && !this.byHand && this.closeUp() && !this.allSeen()) this.view = null;
    this.draw();
    this.onView();
  }

  copy() {
    return this.points.map(([x, y, c]) => [Math.round(x * 1e4) / 1e4, Math.round(y * 1e4) / 1e4, Boolean(c)]);
  }

  closeUp() {
    if (this.repeat < 2) return false;
    return this.choice !== null ? this.choice : this.repeat > CLOSE_UP_FROM;
  }

  setCloseUp(on) {
    if (Boolean(on) !== this.closeUp()) {
      this.choice = Boolean(on);
      this.fit();
    }
  }

  fit() {
    this.view = null;
    this.byHand = false;
    this.draw();
    this.onView();
  }

  piece() {
    // the drawn piece's angles (unwound along it) and distances from the axis
    const a = [];
    const r = [];
    let last = null;
    for (const [x, y] of this.points) {
      let t = Math.atan2(y, x);
      if (last !== null) {
        while (t - last > Math.PI) t -= 2 * Math.PI;
        while (t - last < -Math.PI) t += 2 * Math.PI;
      }
      a.push(t);
      r.push(Math.hypot(x, y));
      last = t;
    }
    return [a, r];
  }

  fitView() {
    const w = Math.max(this.canvas.clientWidth, 1);
    const h = Math.max(this.canvas.clientHeight, 1);
    if (!this.closeUp()) return [0, 0, 0.42 * Math.min(w, h), 0];
    const n = this.repeat;
    const [a, r] = this.piece();
    const lo = Math.min(...a);
    const hi = Math.max(...a);
    const mid = 0.5 * (lo + hi);
    const half = Math.min(Math.max(0.5 * (hi - lo), Math.PI / n) + (0.6 * Math.PI) / n, Math.PI);
    const rIn = Math.max(Math.min(Math.min(...r), 0.97) - 0.05, 0);
    const rOut = Math.max(Math.max(...r), 1) + 0.05;
    let x0 = Infinity; let y0 = Infinity; let x1 = -Infinity; let y1 = -Infinity;
    for (let k = 0; k <= 60; k++) {
      const t = 0.5 * Math.PI - half + (2 * half * k) / 60;           // turned to point straight up
      for (const rr of [rIn, rOut]) {
        const x = rr * Math.cos(t);
        const y = rr * Math.sin(t);
        x0 = Math.min(x0, x); y0 = Math.min(y0, y); x1 = Math.max(x1, x); y1 = Math.max(y1, y);
      }
    }
    const s = 0.92 * Math.min(w / Math.max(x1 - x0, 1e-9), h / Math.max(y1 - y0, 1e-9));
    return [0.5 * (x0 + x1), 0.5 * (y0 + y1), s, 0.5 * Math.PI - mid];
  }

  xf() {
    if (!this.view) this.view = this.fitView();
    const [cx, cy, s, turn] = this.view;
    return [cx, cy, s, Math.cos(turn), Math.sin(turn)];
  }

  to(x, y) {
    const [cx, cy, s, c, sn] = this.xf();
    return [this.canvas.clientWidth / 2 + (x * c - y * sn - cx) * s, this.canvas.clientHeight / 2 - (x * sn + y * c - cy) * s];
  }

  from(px, py) {
    const [cx, cy, s, c, sn] = this.xf();
    const xr = cx + (px - this.canvas.clientWidth / 2) / s;
    const yr = cy + (this.canvas.clientHeight / 2 - py) / s;
    let x = xr * c + yr * sn;
    let y = -xr * sn + yr * c;
    const r = Math.hypot(x, y);
    if (r > REACH) {
      x *= REACH / r;
      y *= REACH / r;
    }
    return [x, y];
  }

  allSeen() {
    const w = this.canvas.clientWidth;
    const h = this.canvas.clientHeight;
    return this.points.every(([x, y]) => {
      const [sx, sy] = this.to(x, y);
      return sx >= 0 && sx <= w && sy >= 0 && sy <= h;
    });
  }

  pos(e) {
    const r = this.canvas.getBoundingClientRect();
    return [e.clientX - r.left, e.clientY - r.top];
  }

  hit(px, py) {
    let best = null;
    let bestD = HIT;
    this.points.forEach(([x, y], i) => {
      const [sx, sy] = this.to(x, y);
      const d = Math.abs(sx - px) + Math.abs(sy - py);
      if (d < bestD) {
        best = i;
        bestD = d;
      }
    });
    return best;
  }

  loop() {
    const key = JSON.stringify([this.points, this.repeat]);
    if (!this.cache || this.cache.key !== key) {
      let loop = null;
      let crossed = false;
      if (this.points.length >= 3) {
        loop = spline(this.points, this.repeat);
        crossed = crosses(loop, PER * this.points.length);
      }
      this.cache = { key, loop, crossed };
    }
    return this.cache;
  }

  // ---------------------------------------------------------------- the mouse
  down(e) {
    const [px, py] = this.pos(e);
    const i = this.hit(px, py);
    if (e.button === 2 && i !== null) {
      if (this.points.length > 3) {                                  // right-click a point: take it away
        this.points.splice(i, 1);
        this.hover = null;
        this.draw();
        this.onChange(this.copy(), false);
      }
      return;
    }
    if (this.big && (e.button === 1 || e.button === 2)) {
      this.pan = { x: px, y: py, view: this.xf() && [...this.view] };
      this.canvas.setPointerCapture(e.pointerId);
      e.preventDefault();
      return;
    }
    if (e.button === 0 && i !== null) {
      this.drag = i;
      this.canvas.setPointerCapture(e.pointerId);
      e.preventDefault();
      this.draw();
    }
  }

  move(e) {
    const [px, py] = this.pos(e);
    if (this.pan) {
      const [cx, cy, s, turn] = this.pan.view;
      this.view = [cx - (px - this.pan.x) / s, cy + (py - this.pan.y) / s, s, turn];
      this.byHand = true;
      this.draw();
      return;
    }
    if (this.drag === null) {
      const i = this.hit(px, py);
      if (i !== this.hover) {
        this.hover = i;
        this.draw();
      }
      return;
    }
    const [x, y] = this.from(px, py);
    this.points[this.drag][0] = x;
    this.points[this.drag][1] = y;
    this.draw();
    this.onChange(this.copy(), true);
  }

  up() {
    if (this.pan) {
      this.pan = null;
      return;
    }
    if (this.drag === null) return;
    this.drag = null;
    this.draw();
    this.onChange(this.copy(), false);
  }

  double(e) {
    const [px, py] = this.pos(e);
    const i = this.hit(px, py);
    if (i !== null) {                                                // a point: sharp or smooth
      this.points[i][2] = !this.points[i][2];
      this.draw();
      this.onChange(this.copy(), false);
      return;
    }
    const [x, y] = this.from(px, py);
    // on whichever copy is nearest: the point goes into the drawn piece, turned back to it
    let best = null;
    for (let k = 0; k < this.repeat; k++) {
      const a = (-2 * Math.PI * k) / this.repeat;
      const xk = x * Math.cos(a) - y * Math.sin(a);
      const yk = x * Math.sin(a) + y * Math.cos(a);
      const [side, dist] = this.nearestSide(xk, yk);
      if (!best || dist < best[0]) best = [dist, side, xk, yk];
    }
    this.points.splice(best[1] + 1, 0, [best[2], best[3], false]);
    this.draw();
    this.onChange(this.copy(), false);
  }

  nearestSide(x, y) {
    const n = this.points.length;
    let best = [0, Infinity];
    for (let i = 0; i < n; i++) {
      const p = this.points[i];
      let q = this.points[(i + 1) % n];
      if (i === n - 1 && this.repeat > 1) {                          // the last point joins the next copy's first
        const a = (2 * Math.PI) / this.repeat;
        q = [q[0] * Math.cos(a) - q[1] * Math.sin(a), q[0] * Math.sin(a) + q[1] * Math.cos(a)];
      }
      const dx = q[0] - p[0];
      const dy = q[1] - p[1];
      const t = Math.min(Math.max(((x - p[0]) * dx + (y - p[1]) * dy) / Math.max(dx * dx + dy * dy, 1e-12), 0), 1);
      const d = Math.hypot(p[0] + dx * t - x, p[1] + dy * t - y);
      if (d < best[1]) best = [i, d];
    }
    return best;
  }

  wheel(e) {
    if (!this.big) return;                                           // in the panel the wheel scrolls the panel
    e.preventDefault();
    const [cx, cy, s, turn] = this.view || this.fitView();
    const s2 = Math.min(Math.max(s * 1.0015 ** -e.deltaY, 20), 2e6);
    const [px, py] = this.pos(e);
    const w = this.canvas.clientWidth;
    const h = this.canvas.clientHeight;
    const xr = cx + (px - w / 2) / s;
    const yr = cy + (h / 2 - py) / s;
    this.view = [xr - (px - w / 2) / s2, yr - (h / 2 - py) / s2, s2, turn];
    this.byHand = true;
    this.draw();
  }

  key(e) {
    if ((e.key === "Delete" || e.key === "Backspace") && this.hover !== null && this.points.length > 3) {
      this.points.splice(this.hover, 1);
      this.hover = null;
      this.draw();
      this.onChange(this.copy(), false);
      e.preventDefault();
    } else if (e.key === "f" || e.key === "F" || e.key === "Home") {
      this.fit();
      e.preventDefault();
    }
  }

  // ---------------------------------------------------------------- drawing
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
    g.fillStyle = themeColour("--well");
    g.fillRect(0, 0, w, h);
    const [cx, cy, s] = this.xf();
    const close = this.closeUp();
    // a grid square to the screen, a line every 28 pixels or more
    const step = [0.002, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5].find((q) => q * s >= 28) || 1;
    g.strokeStyle = themeColour("--grid");
    g.lineWidth = 1;
    g.beginPath();
    for (let k = Math.ceil((cx - w / 2 / s) / step); k <= Math.floor((cx + w / 2 / s) / step); k++) {
      const x = Math.round(w / 2 + (k * step - cx) * s) + 0.5;
      g.moveTo(x, 0);
      g.lineTo(x, h);
    }
    for (let k = Math.ceil((cy - h / 2 / s) / step); k <= Math.floor((cy + h / 2 / s) / step); k++) {
      const y = Math.round(h / 2 - (k * step - cy) * s) + 0.5;
      g.moveTo(0, y);
      g.lineTo(w, y);
    }
    g.stroke();
    // the widest circle, and where each repeat begins
    g.strokeStyle = muted;
    g.setLineDash([5, 4]);
    g.beginPath();
    for (let k = 0; k <= 720; k++) {
      const [x, y] = this.to(Math.cos((k / 720) * 2 * Math.PI), Math.sin((k / 720) * 2 * Math.PI));
      if (k) g.lineTo(x, y); else g.moveTo(x, y);
    }
    g.stroke();
    g.setLineDash([]);
    const n = this.repeat;
    if (n > 1 && (close || n <= 24)) {
      const [a] = this.piece();
      const mid = 0.5 * (Math.min(...a) + Math.max(...a));
      g.strokeStyle = themeColour("--grid");
      g.beginPath();
      const o = this.to(0, 0);
      for (let k = 0; k < n; k++) {
        const b = mid + (Math.PI * (2 * k + 1)) / n;
        const e = this.to(1.3 * Math.cos(b), 1.3 * Math.sin(b));
        g.moveTo(...o);
        g.lineTo(...e);
      }
      g.stroke();
    }
    const o = this.to(0, 0);
    g.strokeStyle = muted;
    g.beginPath();
    g.moveTo(o[0] - 5, o[1]); g.lineTo(o[0] + 5, o[1]);
    g.moveTo(o[0], o[1] - 5); g.lineTo(o[0], o[1] + 5);
    g.stroke();
    const { loop, crossed } = this.loop();
    if (loop) {
      const line = crossed ? "#eb3c32" : accent;
      const S = loop.map(([x, y]) => this.to(x, y));
      g.fillStyle = line;
      g.globalAlpha = 0.16;
      g.beginPath();
      S.forEach(([x, y], i) => (i ? g.lineTo(x, y) : g.moveTo(x, y)));
      g.closePath();
      g.fill();
      g.globalAlpha = 1;
      g.strokeStyle = line;
      // the drawn piece and a copy either side drawn bold; further copies thin
      const m = PER * this.points.length;
      g.lineWidth = n > 1 ? 1 : 1.8;
      g.globalAlpha = n > 1 ? 0.65 : 1;
      g.stroke();
      g.globalAlpha = 1;
      if (n > 1) {
        g.lineWidth = 1.8;
        g.beginPath();
        for (let i = -m; i <= 2 * m; i++) {
          const [x, y] = S[(i + S.length) % S.length];
          if (i === -m) g.moveTo(x, y); else g.lineTo(x, y);
        }
        g.stroke();
      }
    }
    // the copies' points, faint (the nearest few when close up), then the drawn ones to drag
    if (n > 1 && (close || n <= 24)) {
      const copies = close ? [1, 2, 3, n - 1, n - 2, n - 3] : Array.from({ length: n - 1 }, (_, i) => i + 1);
      g.fillStyle = accent;
      g.globalAlpha = 0.3;
      for (const k of new Set(copies.map((q) => ((q % n) + n) % n))) {
        if (k === 0) continue;
        const a = (2 * Math.PI * k) / n;
        for (const [x, y] of this.points) {
          const [sx, sy] = this.to(x * Math.cos(a) - y * Math.sin(a), x * Math.sin(a) + y * Math.cos(a));
          g.beginPath();
          g.arc(sx, sy, 2.5, 0, 2 * Math.PI);
          g.fill();
        }
      }
      g.globalAlpha = 1;
    }
    this.points.forEach(([x, y, cusp], i) => {
      const [sx, sy] = this.to(x, y);
      const on = i === this.drag || i === this.hover;
      const r = on ? 6 : 5;
      g.beginPath();
      if (cusp) {                                                     // a cusp is a diamond, a smooth point round
        g.moveTo(sx, sy - r - 1); g.lineTo(sx + r + 1, sy); g.lineTo(sx, sy + r + 1); g.lineTo(sx - r - 1, sy);
        g.closePath();
      } else {
        g.arc(sx, sy, r, 0, 2 * Math.PI);
      }
      g.fillStyle = on ? "#ffffff" : accent;
      g.fill();
      g.strokeStyle = "#14161a";
      g.lineWidth = 1;
      g.stroke();
    });
    g.font = "11px system-ui, sans-serif";
    g.textBaseline = "top";
    g.textAlign = "left";
    if (crossed) {
      g.fillStyle = "#ff786e";
      g.fillText("The outline crosses itself", 6, 5);
    } else if (close) {
      g.fillStyle = muted;
      g.fillText(`One of ${n} repeats, close up`, 6, 5);
    }
    g.fillStyle = muted;
    g.textAlign = "right";
    g.fillText("widest ⌒", w - 6, 5);
    if (this.inside && this.drag === null && !this.pan) {
      g.textAlign = "left";
      g.textBaseline = "bottom";
      let tip = "double-click: add a point · on a point: sharp / smooth · right-click: remove";
      if (this.big) tip += " · wheel: zoom · right-drag: move · F: fit";
      g.fillText(tip, 6, h - 4);
    }
  }
}
