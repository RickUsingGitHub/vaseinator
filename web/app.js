// Vaseinator on the web: the desktop app, Simple and Advanced. The vase is built by the app's own Python (in
// worker.js, with Pyodide) - the settings, the rules for which are shown and what each change brings with it,
// and the report beside the view are the desktop app's own - and drawn here with three.js.

import { CurveEditor } from "./curves.js";
import { OutlineEditor } from "./outline.js";
import { drawSide, drawTop } from "./plots.js";
import { View } from "./view.js";

const $ = (id) => document.getElementById(id);

// what this browser remembers: the design, the printer, the mode and the look - if it may
const store = {
  get(key) {
    try { return JSON.parse(localStorage.getItem("vaseinator." + key)); } catch { return null; }
  },
  set(key, value) {
    try { localStorage.setItem("vaseinator." + key, JSON.stringify(value)); } catch { /* private window */ }
  },
};

// ================================================================== Python, in two workers
// one builds the vase (which can take a few seconds); the other answers everything else straight away
class Python {
  constructor() {
    this.worker = new Worker("worker.js");
    this.waiting = new Map();
    this.next = 1;
    this.worker.onmessage = (event) => {
      const { id, ok, result, error } = event.data;
      const w = this.waiting.get(id);
      this.waiting.delete(id);
      if (ok) w.resolve(result);
      else w.reject(new Error(lastLine(error)));
    };
    this.worker.onerror = (event) => failed(event.message || "Python stopped");
  }

  call(name, ...args) {
    return new Promise((resolve, reject) => {
      const id = this.next++;
      this.waiting.set(id, { resolve, reject });
      this.worker.postMessage({ id, call: name, args });
    });
  }
}

function lastLine(text) {
  // a Python error comes with its whole traceback: its last line says what went wrong
  const lines = String(text).trim().split("\n");
  return lines[lines.length - 1].replace(/^\w*Error: /, "");
}

const builder = new Python();
const helper = new Python();

// ================================================================== the design
let C = null;                 // the settings, choices, constants and help, from Python
let K = null;                 // C.constants
let params = null;            // the design's settings
let meta = null;              // what the last build says about it
let shown = new Set();        // the Advanced settings shown for it
const undoStack = [];
const redoStack = [];
let liveFrom = null;          // the settings before a drag began, for Undo
let queue = Promise.resolve();

function pushUndo(snapshot) {
  undoStack.push(snapshot);
  if (undoStack.length > 100) undoStack.shift();
  redoStack.length = 0;
  undoButtons();
}

function undoButtons() {
  $("undo").disabled = !undoStack.length;
  $("redo").disabled = !redoStack.length;
}

function status(text) {
  $("status").textContent = text || "";
}

function needsNormal(p) {
  // holes, a face, an open bottom or a wall part way round: spiral vase mode prints one closed line a layer
  return p.holes !== 0 || p.open_bottom || p.around < 360 || p.eyes !== 0 || p.mouth !== 0 || p.straps;
}

function change(updates) {
  // several settings at once, as a picture in Simple mode sets them
  if (!C) return;
  pushUndo(JSON.stringify(params));
  Object.assign(params, updates);
  if (params.vase_mode === K.REAL_VASE && needsNormal(params)) params.vase_mode = K.FAKE_VASE;
  settled({});
}

function commit(key, value, live = false) {
  // one setting, as the desktop app's panel changes it: Python applies the app's own rules
  if (!C) return Promise.resolve();
  if (live) {
    if (liveFrom === null) liveFrom = JSON.stringify(params);
    params[key] = value;
    if (key === "silhouette") params.profile = K.OWN_PROFILE;
    rebuild({ live: true });
    return Promise.resolve();
  }
  queue = queue.then(async () => {
    const before = liveFrom !== null ? liveFrom : JSON.stringify(params);
    liveFrom = null;
    try {
      const r = JSON.parse(await helper.call("apply", JSON.stringify(params), key, JSON.stringify(value)));
      pushUndo(before);
      params = r.params;
      shown = new Set(r.shown);
      status(r.message);
      settled({ known: true });
    } catch (err) {
      showProblem(err.message);
    }
  });
  return queue;
}

function settled({ refit = false, known = false }) {
  store.set("design", params);
  refreshSimple();
  refreshAdvanced();
  if (!known) {
    helper.call("shown", JSON.stringify(params)).then((keys) => {
      shown = new Set(JSON.parse(keys));
      refreshAdvanced();
    }).catch(() => {});
  }
  rebuild({ refit });
}

function replace(next, refit = true) {
  pushUndo(JSON.stringify(params));
  params = next;
  settled({ refit });
}

function step(from, to) {
  if (!from.length) return;
  to.push(JSON.stringify(params));
  params = JSON.parse(from.pop());
  undoButtons();
  settled({});
}

// ================================================================== building it
let seq = 0;                  // the newest design asked for
let wanted = null;            // the next build to do
let busy = false;
let refit = true;
let refineTimer = 0;

function rebuild({ refit: fit = false, live = false } = {}) {
  seq += 1;
  refit = refit || fit;
  clearTimeout(refineTimer);
  wanted = { seq, draft: true, live, text: JSON.stringify(params) };
  pump();
}

async function pump() {
  if (busy || !wanted) return;
  const job = wanted;
  wanted = null;
  busy = true;
  showBusy(job.draft ? "Building…" : "Adding the fine detail…");
  let result = null;
  try {
    result = await builder.call("build", job.text, job.draft);
  } catch (err) {
    showProblem(err.message);
  }
  busy = false;
  if (result && job.seq === seq) {
    show(result);
    if (job.draft && !job.live) {
      // a quick draft first; then, if nothing changes for a moment, the vase in full detail
      refineTimer = setTimeout(() => {
        if (job.seq === seq) {
          wanted = { seq: job.seq, draft: false, text: job.text };
          pump();
        }
      }, 600);
    }
  }
  if (wanted) pump();
  else showBusy(null);
}

function showBusy(text) {
  $("busy").hidden = !text;
  if (text) $("busytext").textContent = text;
}

// ================================================================== the view, the pictures, the report
const view = new View($("canvas"), $("viewer"), (text) => { $("hint").textContent = text; });
window.vaseinator = { view, get params() { return params; }, get meta() { return meta; } };   // for checking it

function show(result) {
  const m = JSON.parse(result.meta);
  if (m.errors && m.errors.length) {
    $("report").innerHTML = m.report;
    flagCrossing(m.errors);
    return;
  }
  flagCrossing([]);
  meta = m;
  view.show(result, m, refit);
  refit = false;
  setNumber($("head"), m.head);
  setNumber(widgetInput("head"), m.head);
  lightTile($("pattern"), m.pattern);
  $("report").innerHTML = m.report;
  drawPlots();
}

function drawPlots() {
  if (!meta) return;
  drawSide($("sideplot"), meta.plots);
  drawTop($("topplot"), meta.plots);
}
new ResizeObserver(drawPlots).observe($("plots"));

function showProblem(text) {
  const p = document.createElement("p");
  p.className = "e";
  p.textContent = `✗ ${text}`;
  $("report").prepend(p);
}

function flagCrossing(errors) {
  // a drawn outline that crosses itself: the build says so; the editors show it red themselves
  const crossing = errors.some((e) => e.includes("crosses itself"));
  document.body.classList.toggle("crossing", crossing);
}

// ================================================================== Simple: the pictures
const ACCENT = "#F0A356";
const EDGE = "#966636";
const DEEP = "#82582E";
const svg = (body, size = 52) => `<svg viewBox="0 0 ${size} ${size}" aria-hidden="true">${body}</svg>`;

function aboveIcon(outline) {
  const pts = outline.map(([x, y]) => `${(26 + 22.9 * x).toFixed(1)},${(26 - 22.9 * y).toFixed(1)}`).join(" ");
  return svg(`<polygon points="${pts}" fill="${ACCENT}" stroke="${EDGE}" stroke-width="1.5"/>`);
}

function sideIcon(widths) {
  const n = widths.length;
  const left = [];
  const right = [];
  widths.forEach((w, i) => {
    const y = 48 - (44 * i) / (n - 1);
    left.push(`${(26 - 18.7 * w).toFixed(1)},${y.toFixed(1)}`);
    right.unshift(`${(26 + 18.7 * w).toFixed(1)},${y.toFixed(1)}`);
  });
  return svg(`<polygon points="${left.concat(right).join(" ")}" fill="${ACCENT}" stroke="${EDGE}" stroke-width="1.5"/>`);
}

function patternIcon(name) {
  // a little vase body with the pattern drawn on it, as the desktop app draws them
  const [l, t, r, b] = [10, 4, 42, 48];
  const lines = [];
  const line = (x1, y1, x2, y2) => lines.push(`<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}"/>`);
  const dots = [];
  const holes = [];
  const range = (a, z, n) => Array.from({ length: n }, (_, i) => a + ((z - a) * i) / (n - 1));
  if (name === "Ribs") range(l + 4, r - 4, 6).forEach((x) => line(x, t, x, b));
  if (name === "Spiral ribs" || name === "Diamonds") {
    range(l - 30, r + 4, 9).forEach((x) => {
      line(x, b, x + 26, t);
      if (name === "Diamonds") line(x, t, x + 26, b);
    });
  }
  if (name === "Rings") range(t + 5, b - 5, 6).forEach((y) => line(l, y, r, y));
  if (name === "Bumps") {
    range(t + 6, b - 6, 6).forEach((y, row) =>
      range(l + 5 + (row % 2) * 3, r - 5, 4).forEach((x) => dots.push(`<circle cx="${x}" cy="${y}" r="2.2"/>`)));
  }
  if (name === "Lumpy") {
    [[18, 12, 5], [31, 18, 6], [21, 30, 7], [34, 37, 5], [17, 44, 4]].forEach(([x, y, rr]) =>
      dots.push(`<circle cx="${x}" cy="${y}" r="${rr}" fill="#B27940"/>`));
  }
  if (name === "Gem") {
    range(t, b, 5).forEach((y) => line(l, y, r, y));
    range(t, b, 5).slice(0, -1).forEach((y, k) =>
      range(l - 8 + 4 * (k % 2), r, 4).forEach((x) => line(x, y, x + 8, y + (b - t) / 4)));
  }
  if (name === "Round holes") {
    range(t + 7, b - 7, 4).forEach((y, row) =>
      range(l + 6 + (row % 2) * 4, r - 6, 3).forEach((x) => holes.push(`<circle cx="${x}" cy="${y}" r="3"/>`)));
  }
  if (name === "Voronoi holes") {
    [[[14, 8], [22, 6], [25, 13], [19, 18], [13, 15]], [[28, 9], [35, 7], [38, 15], [31, 19]],
     [[13, 22], [21, 22], [23, 30], [15, 33]], [[27, 24], [36, 22], [38, 31], [29, 33]],
     [[15, 38], [24, 37], [25, 45], [14, 46]], [[29, 38], [37, 37], [36, 46], [28, 45]]].forEach((cell) =>
      holes.push(`<polygon points="${cell.map((p) => p.join(",")).join(" ")}"/>`));
  }
  const id = "p" + name.replace(/\W/g, "");
  return svg(
    `<defs><clipPath id="c${id}"><rect x="${l}" y="${t}" width="${r - l}" height="${b - t}" rx="6"/></clipPath>` +
    `<mask id="m${id}"><rect width="52" height="52" fill="white"/><g fill="black">${holes.join("")}</g></mask></defs>` +
    `<rect x="${l}" y="${t}" width="${r - l}" height="${b - t}" rx="6" fill="${ACCENT}" stroke="${EDGE}" ` +
    `stroke-width="1.5" mask="url(#m${id})"/>` +
    `<g clip-path="url(#c${id})" stroke="${DEEP}" stroke-width="${name === "Gem" ? 1.3 : 2.2}" ` +
    `stroke-linecap="round" fill="#A06D39">${lines.join("")}${dots.join("")}</g>`);
}

function swatch(colours) {
  const n = colours.length;
  const id = "s" + colours.join("").replace(/#/g, "");
  const bands = colours.map((c, k) =>
    `<rect x="0" y="${40 - (40 * (k + 1)) / n}" width="40" height="${40 / n + 0.5}" fill="${c}"/>`).join("");
  return `<svg viewBox="0 0 40 40" aria-hidden="true"><defs><clipPath id="${id}"><circle cx="20" cy="20" r="19"/>` +
    `</clipPath></defs><g clip-path="url(#${id})">${bands}</g></svg>`;
}

function tiles(box, items, onPick, cls = "tile") {
  box.replaceChildren();
  items.forEach(({ label, icon, tip }, k) => {
    const b = document.createElement("button");
    b.className = cls;
    b.title = tip || label;
    b.setAttribute("aria-pressed", "false");
    b.innerHTML = cls === "tile" ? `${icon}<span></span>` : `<span>${icon}</span>`;
    if (cls === "tile") b.querySelector("span").textContent = label;
    else b.setAttribute("aria-label", label);
    b.addEventListener("click", () => {
      lightTile(box, k);
      onPick(k);
    });
    box.append(b);
  });
}

function lightTile(box, k) {
  [...box.children].forEach((b, i) => b.setAttribute("aria-pressed", String(i === k)));
}

function widest() {
  return Math.max(...params.silhouette.map(([, d]) => d));
}

function setNumber(input, value) {
  if (input && document.activeElement !== input && value !== undefined && value !== null) input.value = value;
}

function twistWords(deg) {
  const words = { 0: "No twist", 90: "A quarter turn", 180: "Half a turn", 270: "Three quarters of a turn",
    360: "A whole turn", 720: "Two whole turns" };
  for (const [k, w] of Object.entries(words)) if (Math.abs(Math.abs(deg) - Number(k)) < 0.5) return w;
  return `${Math.round(deg)}°`;
}

function titleOf(p) {
  const match = C.gallery.find((g) => g.slug === p.name);
  if (match) return match.title;
  if (p.name === "plain_cylinder") return "Plain cylinder";
  const name = p.name.replace(/_/g, " ").trim();
  return name ? name[0].toUpperCase() + name.slice(1) : "Your vase";
}

function refreshSimple() {
  const p = params;
  $("name").textContent = titleOf(p);
  document.title = `${titleOf(p)} – Vaseinator`;
  setNumber($("tall"), Math.round(p.height) / 10);
  setNumber($("wide"), Math.round(widest()) / 10);
  $("size").hidden = p.worn;
  $("headrow").hidden = !p.worn;
  $("sidetitle").hidden = p.worn;
  $("side").hidden = p.worn;
  lightTile($("above"), C.shapes.findIndex(({ settings: s }) =>
    p.shape2 === K.SAME && p.shape1 === s.shape1 && (p.shape1 !== K.POLYGON || p.count1 === s.count1)));
  lightTile($("side"), p.profile >= 0 && p.profile < C.profiles.length ? p.profile : -1);
  const twist = $("twist");
  if (document.activeElement !== twist) twist.value = Math.round(Math.min(Math.max(p.twist, 0), 360) / 15);
  $("twistwords").textContent = p.twist_style === K.OWN ? "Your own curve" : twistWords(p.twist);
  if (p.colour_style === K.ONE_COLOUR) {
    lightTile($("colour"), C.colours.findIndex((c) => c.colour.toLowerCase() === p.color1.toLowerCase()));
  } else {
    const k = C.many_colours.findIndex((m) => m.settings.colour_style === p.colour_style);
    lightTile($("colour"), k < 0 ? -1 : C.colours.length + k);
  }
  for (const input of document.querySelectorAll("#printer input")) setNumber(input, p[input.dataset.key]);
}

function buildSimple() {
  tiles($("above"), C.shapes.map((s) => ({ label: s.name, icon: aboveIcon(s.outline) })),
    (k) => change({ shape2: K.SAME, turn1: 0, ...C.shapes[k].settings }));
  tiles($("side"), C.profiles.map((s) => ({ label: s.name, icon: sideIcon(s.widths), tip: s.full })),
    (k) => {
      const w = widest();
      change({ profile: k, silhouette: C.profiles[k].points.map(([h, f]) => [h, Math.round(f * w * 100) / 100]) });
    });
  tiles($("pattern"), C.patterns.map((s) => ({ label: s.name, icon: patternIcon(s.name) })),
    (k) => change({ ...C.no_pattern, ...C.patterns[k].settings }));
  const colourItems = C.colours.map((c) => ({ label: c.name, icon: swatch([c.colour]) }))
    .concat(C.many_colours.map((m) => ({ label: `${m.name} of colour (${m.palette})`, icon: swatch(m.colours.slice(0, 3)) })));
  tiles($("colour"), colourItems, (k) => {
    if (k < C.colours.length) {
      change({ colour_style: K.ONE_COLOUR, color1: C.colours[k].colour });
    } else {
      const m = C.many_colours[k - C.colours.length];
      change({ ...m.settings, ...Object.fromEntries(m.colours.map((c, i) => [`color${i + 1}`, c])) });
    }
  }, "swatch");
  $("tall").addEventListener("change", (e) => {
    const cm = parseFloat(e.target.value);
    if (cm > 0) change({ height: Math.round(cm * 100) / 10 });
  });
  $("wide").addEventListener("change", (e) => {
    const cm = parseFloat(e.target.value);
    if (cm > 0) commit("widest", cm * 10);
  });
  $("head").addEventListener("change", (e) => {
    const cm = parseFloat(e.target.value);
    if (cm > 0) fitHead(cm);
  });
  $("twist").addEventListener("input", (e) => {
    $("twistwords").textContent = twistWords(15 * e.target.value);
  });
  $("twist").addEventListener("change", (e) => {
    const updates = { twist: 15 * Number(e.target.value) };
    if (params.twist_style === K.OWN) updates.twist_style = K.EVENLY;
    change(updates);
  });
  for (const input of document.querySelectorAll("#printer input")) {
    input.addEventListener("change", () => {
      const v = parseFloat(input.value);
      if (!(v > 0)) return;
      change({ [input.dataset.key]: input.dataset.key === "walls" ? Math.round(v) : v });
      rememberPrinter();
    });
  }
  $("drawown").addEventListener("click", async () => {
    if (params.shape1 !== K.DRAWN) await commit("shape1", K.DRAWN);
    openOutline(1);
  });
}

function rememberPrinter() {
  store.set("printer", Object.fromEntries(C.printer_keys.map((k) => [k, params[k]])));
}

async function fitHead(cm) {
  await withBusy("Fitting it to the head…", async () =>
    replace(JSON.parse(await helper.call("fit", JSON.stringify(params), cm * 10)), false));
  status(`Sized for a head ${cm} cm round — Undo to go back`);
}

// ================================================================== Advanced: every setting
const widgets = new Map();    // key -> {rows: [elements], set(p), input}
const editors = {};           // the outline editors in the panel, by k

function widgetInput(key) {
  const w = widgets.get(key);
  return w ? w.input : null;
}

function colourStyleOf(p) {
  // a seamless vase prints one filament: no bands or stripes
  return p.vase_mode === K.REAL_VASE && (p.colour_style === 1 || p.colour_style === 2) ? K.ONE_COLOUR : p.colour_style;
}

function numberBox(row, { scale = 1, decimals = 2 } = {}) {
  const input = document.createElement("input");
  input.type = "number";
  input.min = row.lo * scale;
  input.max = row.hi * scale;
  input.step = row.step * scale;
  input.dataset.decimals = decimals;
  return input;
}

function makeRow(row, rowsBox) {
  const { key, label, kind } = row;
  const [unit, none] = String(row.extra || "").split("|");
  const lab = document.createElement("label");
  lab.className = "label";
  lab.textContent = label;
  lab.title = row.tip || "";
  const control = document.createElement("div");
  control.className = "control";
  control.title = row.tip || "";
  let set = () => {};
  let input = null;
  const whole = ["curve", "expr", "outline"].includes(kind);
  if (kind === "float" || kind === "int" || kind === "seed" || kind === "pct" || kind === "widest" || kind === "head") {
    const scale = kind === "pct" ? 100 : 1;
    input = numberBox(row, { scale });
    lab.htmlFor = input.id = `set-${key}`;
    control.append(input);
    if (unit) {
      const u = document.createElement("span");
      u.className = "unit";
      u.textContent = unit.trim();
      control.append(u);
    }
    let noneLabel = null;
    if (none) {
      noneLabel = document.createElement("span");
      noneLabel.className = "none";
      noneLabel.textContent = `(${none.toLowerCase()})`;
      control.append(noneLabel);
    }
    if (kind === "seed") {
      const dice = document.createElement("button");
      dice.className = "dice";
      dice.textContent = "🎲";
      dice.title = "Another pattern";
      dice.addEventListener("click", () => commit(key, Math.floor(Math.random() * 99999)));
      control.append(dice);
    }
    input.addEventListener("change", () => {
      let v = parseFloat(input.value);
      if (Number.isNaN(v)) return;
      v = Math.min(Math.max(v, row.lo * scale), row.hi * scale) / scale;
      if (kind === "int" || kind === "seed") v = Math.round(v);
      if (kind === "head") return fitHead(v);
      commit(key, v);
    });
    set = (p) => {
      let v;
      if (kind === "widest") v = Math.round(widest() * 10) / 10;
      else if (kind === "head") v = meta ? meta.head : 57;
      else v = p[key] * scale;
      setNumber(input, kind === "pct" ? Math.round(v * 10) / 10 : Math.round(v * 1000) / 1000);
      if (noneLabel) noneLabel.hidden = !(p[key] === row.lo);
      if (/^count[12]$/.test(key)) input.min = p[`shape${key.slice(-1)}`] === K.POLYGON ? 3 : 1;
    };
  } else if (kind === "bool") {
    input = document.createElement("input");
    input.type = "checkbox";
    lab.htmlFor = input.id = `set-${key}`;
    control.append(input);
    input.addEventListener("change", () => commit(key, input.checked));
    set = (p) => { input.checked = Boolean(p[key]); };
  } else if (kind === "choice") {
    input = document.createElement("select");
    lab.htmlFor = input.id = `set-${key}`;
    const fill = (choices) => {
      const now = JSON.stringify(choices);
      if (input.dataset.choices === now) return;
      input.dataset.choices = now;
      input.replaceChildren(...choices.map(([v, t]) => new Option(t, v)));
    };
    fill(row.choices);
    control.append(input);
    input.addEventListener("change", () => commit(key, Number(input.value)));
    set = (p) => {
      if (key === "colour_style") {
        fill(p.vase_mode === K.REAL_VASE ? C.real_colour_styles : C.colour_styles);
        input.value = colourStyleOf(p);
      } else {
        input.value = p[key];
      }
    };
  } else if (kind === "color") {
    input = document.createElement("input");
    input.type = "color";
    lab.htmlFor = input.id = `set-${key}`;
    const hex = document.createElement("span");
    hex.className = "unit";
    control.append(input, hex);
    input.addEventListener("change", () => commit(key, input.value.toUpperCase()));
    set = (p) => {
      input.value = p[key].toLowerCase();
      hex.textContent = p[key].toUpperCase();
    };
  } else if (kind === "slider") {
    input = document.createElement("input");
    input.type = "range";
    input.min = row.lo;
    input.max = row.hi;
    input.step = row.step;
    lab.htmlFor = input.id = `set-${key}`;
    const note = document.createElement("span");
    note.className = "unit";
    control.append(input, note);
    const words = (v) => (Math.abs(v) < 0.05 ? "Even" : v > 0 ? "Thicker towards the top" : "Thicker towards the bottom");
    input.addEventListener("input", () => {
      note.textContent = words(Number(input.value));
      commit(key, Number(input.value), true);
    });
    input.addEventListener("change", () => commit(key, Number(input.value)));
    set = (p) => {
      if (document.activeElement !== input) input.value = p[key];
      note.textContent = words(p[key]);
    };
  } else if (kind === "palette") {
    input = document.createElement("select");
    lab.htmlFor = input.id = `set-${key}`;
    input.append(new Option("Choose a palette…", ""), ...C.palettes.map((pal) => new Option(pal.name, pal.name)));
    control.append(input);
    input.addEventListener("change", () => {
      const pal = C.palettes.find((x) => x.name === input.value);
      input.value = "";
      if (pal) change(Object.fromEntries(pal.colours.map((c, i) => [`color${i + 1}`, c])));
    });
  } else if (kind === "curve") {
    control.className = "whole";
    const canvas = document.createElement("canvas");
    control.append(canvas);
    const o = row.curve;
    const editor = new CurveEditor(canvas, { lo: o.lo, hi: o.hi, unit: o.unit || "", mirror: Boolean(o.mirror),
      height: o.height || 110, floor: o.floor ?? null, grow: Boolean(o.grow), decimals: o.decimals || 0 },
    (pts, live) => commit(key, pts, live));
    set = (p) => editor.setPoints(p[key]);
  } else if (kind === "expr") {
    control.className = "whole";
    const text = document.createElement("textarea");
    text.spellcheck = false;
    text.placeholder = "1.5 * sin(6*theta + 4*pi*h)";
    text.setAttribute("aria-label", "Your own function");
    input = text;
    const tools = document.createElement("div");
    tools.className = "row";
    const examples = document.createElement("select");
    examples.append(new Option("Examples…", ""), ...C.examples.map(([n, f]) => new Option(`${n}:  ${f}`, f)));
    const help = document.createElement("button");
    help.textContent = "Help…";
    const clear = document.createElement("button");
    clear.textContent = "Clear";
    tools.append(examples, help, clear);
    control.append(text, tools);
    let timer = 0;
    text.addEventListener("input", () => {
      clearTimeout(timer);
      timer = setTimeout(() => commit(key, text.value), 600);
    });
    examples.addEventListener("change", () => {
      if (examples.value) setFormula(examples.value);
      examples.value = "";
    });
    help.addEventListener("click", () => openHelp("function"));
    clear.addEventListener("click", () => setFormula(""));
    set = (p) => { if (document.activeElement !== text && text.value !== p[key]) text.value = p[key]; };
  } else if (kind === "outline") {
    control.className = "whole outlinebox";
    const k = Number(key.slice(-1));
    const canvas = document.createElement("canvas");
    const tools = document.createElement("div");
    tools.className = "row";
    const start = startFromMenu(k);
    const close = document.createElement("button");
    close.textContent = "Close up";
    close.title = "Show one repeat close up, turned to point upwards - or the whole outline. Above 8 repeats it starts close up.";
    const big = document.createElement("button");
    big.textContent = "Full window…";
    big.title = "Draw it in a window as big as the screen: the wheel zooms, a right-drag moves it.";
    tools.append(start, close, big);
    control.append(canvas, tools);
    const editor = new OutlineEditor(canvas, {}, (pts, live) => commit(key, pts, live),
      () => close.setAttribute("aria-pressed", String(editor.closeUp())));
    editors[k] = editor;
    close.addEventListener("click", () => editor.setCloseUp(!editor.closeUp()));
    big.addEventListener("click", () => openOutline(k));
    set = (p) => editor.setOutline(p[key], p[`repeat${k}`]);
  }
  if (whole) {
    if (label) {
      lab.className = "label wholelabel";
      rowsBox.append(lab);
    }
    rowsBox.append(control);
    widgets.set(key, { rows: label ? [lab, control] : [control], set, input, lab });
  } else {
    rowsBox.append(lab, control);
    widgets.set(key, { rows: [lab, control], set, input, lab });
  }
}

function startFromMenu(k) {
  const start = document.createElement("select");
  start.setAttribute("aria-label", "Start from");
  start.title = "Start again from a ready-made outline, or trace one from a picture: dark lines drawn round a shape on a light or see-through ground.";
  start.append(new Option("Start from…", ""), ...C.outlines.map((o, i) => new Option(o.name, String(i))),
    new Option("Trace a picture…", "trace"));
  start.addEventListener("change", () => {
    const v = start.value;
    start.value = "";
    if (v === "trace") tracePicture(k);
    else if (v !== "") useOutline(k, C.outlines[Number(v)].points, C.outlines[Number(v)].repeat);
  });
  return start;
}

function useOutline(k, points, repeat) {
  // start drawn outline k again from given control points
  liveFrom = JSON.stringify(params);
  params[`repeat${k}`] = repeat;
  return commit(`drawn${k}`, points);
}

let traceFor = 1;
function tracePicture(k) {
  traceFor = k;
  $("picturefile").click();
}

async function traceFile(file) {
  await withBusy("Tracing the picture…", async () => {
    const bitmap = await createImageBitmap(file);
    const scale = Math.min(1, 1080 / Math.max(bitmap.width, bitmap.height));
    const w = Math.max(Math.round(bitmap.width * scale), 1);
    const h = Math.max(Math.round(bitmap.height * scale), 1);
    const canvas = new OffscreenCanvas(w, h);
    const g = canvas.getContext("2d");
    g.drawImage(bitmap, 0, 0, w, h);
    const pixels = g.getImageData(0, 0, w, h).data;
    let text = "";
    for (let i = 0; i < pixels.length; i += 0x8000) text += String.fromCharCode(...pixels.subarray(i, i + 0x8000));
    const pts = JSON.parse(await helper.call("trace", btoa(text), w, h));
    await useOutline(traceFor, pts, 1);
    status(`Traced ${file.name}: ${pts.length} points, ${pts.filter((q) => q[2]).length} sharp corners.`);
  }).catch(() => {});
}

function setFormula(text) {
  const w = widgets.get("expression");
  if (w && w.input) w.input.value = text;
  commit("expression", text);
}

function buildAdvanced() {
  const box = $("groups");
  box.replaceChildren();
  for (const group of C.spec) {
    const section = document.createElement("details");
    section.className = "group";
    section.open = !store.get(`closed.${group.title}`);
    section.addEventListener("toggle", () => store.set(`closed.${group.title}`, !section.open));
    const summary = document.createElement("summary");
    summary.textContent = group.title;
    const rows = document.createElement("div");
    rows.className = "rows";
    section.append(summary, rows);
    box.append(section);
    group.rows.forEach((row) => makeRow(row, rows));
    group.element = section;
  }
  $("designname").addEventListener("change", (e) => commit("name", e.target.value.trim() || "vase"));
}

function refreshAdvanced() {
  if (!C || !params) return;
  const p = params;
  setNumber($("designname"), p.name);
  for (const [key, w] of widgets) {
    const show = shown.size === 0 || shown.has(key);
    w.rows.forEach((el) => { el.hidden = !show; });
    if (show) w.set(p);
  }
  for (const group of C.spec) group.element.hidden = !group.rows.some((r) => shown.size === 0 || shown.has(r.key));
  // the settings named for the shape: sides, points, petals, teeth
  for (const k of [1, 2]) {
    const names = C.shape_labels[String(p[`shape${k}`])] || [null, null, null];
    ["count", "depth", "sharp"].forEach((what, i) => {
      const w = widgets.get(`${what}${k}`);
      if (w && names[i]) w.lab.textContent = names[i];
    });
  }
  const c1 = widgets.get("color1");
  if (c1) c1.lab.textContent = colourStyleOf(p) === K.ONE_COLOUR ? "Colour" : "Filament 1";
  if (outlineWindow.k) {
    const k = outlineWindow.k;
    outlineWindow.editor.setOutline(p[`drawn${k}`], p[`repeat${k}`]);
    setNumber($("winrepeat"), p[`repeat${k}`]);
  }
}

function setMode(advanced) {
  $("simple").hidden = advanced;
  $("advanced").hidden = !advanced;
  $("simplebtn").setAttribute("aria-selected", String(!advanced));
  $("advancedbtn").setAttribute("aria-selected", String(advanced));
  store.set("advanced", advanced);
  if (advanced) refreshAdvanced();
}

// ================================================================== drawing in a window of its own
const outlineWindow = { k: 0, editor: null };

function openOutline(k) {
  const win = $("outlinewin");
  outlineWindow.k = k;
  $("outlinetitle").textContent = k === 1 ? "Drawing the cross-section" : "Drawing what it turns into";
  $("winrepeat").value = params[`repeat${k}`];
  win.showModal();
  outlineWindow.editor.view = null;
  outlineWindow.editor.setOutline(params[`drawn${k}`], params[`repeat${k}`]);
  $("bigoutline").focus();
}

function buildOutlineWindow() {
  const close = $("winclose");
  outlineWindow.editor = new OutlineEditor($("bigoutline"), { big: true },
    (pts, live) => commit(`drawn${outlineWindow.k}`, pts, live),
    () => close.setAttribute("aria-pressed", String(outlineWindow.editor.closeUp())));
  close.addEventListener("click", () => outlineWindow.editor.setCloseUp(!outlineWindow.editor.closeUp()));
  $("winfit").addEventListener("click", () => outlineWindow.editor.fit());
  $("windone").addEventListener("click", () => $("outlinewin").close());
  $("outlinewin").addEventListener("close", () => { outlineWindow.k = 0; });
  $("winrepeat").addEventListener("change", (e) => {
    const n = Math.min(Math.max(Math.round(Number(e.target.value)), 1), 100);
    if (n) commit(`repeat${outlineWindow.k}`, n);
  });
  const start = $("winstart");
  start.append(new Option("Start from…", ""), ...C.outlines.map((o, i) => new Option(o.name, String(i))),
    new Option("Trace a picture…", "trace"));
  start.addEventListener("change", () => {
    const v = start.value;
    start.value = "";
    if (v === "trace") tracePicture(outlineWindow.k);
    else if (v !== "") useOutline(outlineWindow.k, C.outlines[Number(v)].points, C.outlines[Number(v)].repeat);
  });
}

// ================================================================== the gallery, help and files
function buildGallery() {
  const designs = $("designs");
  const entries = [{ title: "Plain cylinder", slug: "plain_cylinder",
    about: "200 mm across and 200 mm tall, with everything else off: a blank start for your own shape or function" }]
    .concat(C.gallery);
  for (const g of entries) {
    const b = document.createElement("button");
    b.className = "design";
    b.title = g.about;
    b.innerHTML = `<img src="gallery/${g.slug}.png" alt="" loading="lazy"><b></b>`;
    b.querySelector("b").textContent = g.title;
    b.addEventListener("click", () => {
      $("gallery").close();
      chooseDesign(g.title);
    });
    designs.append(b);
  }
  const menu = $("designsmenu");
  for (const g of C.gallery) {
    const b = document.createElement("button");
    b.textContent = g.title;
    b.title = g.about;
    b.addEventListener("click", () => {
      closeMenus();
      chooseDesign(g.title);
    });
    menu.append(b);
  }
}

function chooseDesign(title) {
  return withBusy("Getting it ready…", async () =>
    replace(JSON.parse(await helper.call("design_of", title, JSON.stringify(params)))));
}

function openHelp(which) {
  const titles = { printing: "Printing it watertight", function: "Your own function", drawing: "Drawing a cross-section",
    about: `About Vaseinator ${C.version}` };
  $("helptitle").textContent = titles[which];
  $("helptext").innerHTML = C.help[which];
  $("helpexamples").hidden = which !== "function";
  $("help").showModal();
}

async function withBusy(text, work) {
  showBusy(text);
  try {
    await work();
  } catch (err) {
    showProblem(err.message);
    throw err;
  } finally {
    if (!busy) showBusy(null);
  }
}

function download(data, name, type) {
  const url = URL.createObjectURL(data instanceof Blob ? data : new Blob([data], { type }));
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10000);
}

function fileName() {
  return (params.name || "vase").replace(/[^\w\- ]/g, "_").trim() || "vase";
}

// ================================================================== the menus and buttons
let currentView = 0;

function setView(n) {
  currentView = n;
  view.setMode(n);
  document.querySelectorAll(".views button").forEach((b) => b.setAttribute("aria-pressed", String(Number(b.dataset.view) === n)));
}

function toggle(id, on) {
  $(id).setAttribute("aria-pressed", String(on));
}

function effectiveLight() {
  const t = document.documentElement.dataset.theme;
  return t ? t === "light" : window.matchMedia("(prefers-color-scheme: light)").matches;
}

const actions = {
  new: () => replace({ ...C.defaults, ...Object.fromEntries(C.printer_keys.map((k) => [k, params[k]])) }),
  plain: () => chooseDesign("Plain cylinder"),
  open: () => $("openfile").click(),
  savevase: async () => download(await helper.call("save_vase", JSON.stringify(params)), fileName() + ".vase", "application/json"),
  print: () => withBusy("Making the file for your slicer…", async () => {
    const { data, steps } = await builder.call("export_3mf", JSON.stringify(params));
    download(data, fileName() + ".3mf", "model/3mf");
    $("steplist").innerHTML = steps;
    $("steps").showModal();
  }).catch(() => {}),
  stl: () => withBusy("Making the STL…", async () =>
    download(await builder.call("export_stl", JSON.stringify(params)), fileName() + ".stl", "model/stl")).catch(() => {}),
  "3mf": () => withBusy("Making the 3MF…", async () => {
    const { data } = await builder.call("export_3mf", JSON.stringify(params));
    download(data, fileName() + ".3mf", "model/3mf");
    status(`Saved ${fileName()}.3mf - in your slicer use File ▸ Import`);
  }).catch(() => {}),
  picture: async () => download(await view.picture(), fileName() + "_3d.png", "image/png"),
  undo: () => step(undoStack, redoStack),
  redo: () => step(redoStack, undoStack),
  surprise: () => withBusy("Thinking of something…", async () =>
    replace(JSON.parse(await helper.call("surprise_me", JSON.stringify(params), Math.floor(Math.random() * 1e6))))).catch(() => {}),
  plan: async () => {
    if (!meta) return;
    try {
      await navigator.clipboard.writeText(meta.plan);
      status("Colour changes copied to the clipboard");
    } catch {
      status("The browser didn't allow copying: the colour changes are in the panel");
    }
  },
  gallery: () => $("gallery").showModal(),
  view0: () => setView(0),
  view1: () => setView(1),
  view2: () => setView(2),
  view3: () => setView(3),
  spin: () => {
    const on = $("spin").getAttribute("aria-pressed") !== "true";
    view.setSpin(on);
    toggle("spin", on);
  },
  printing: () => {
    const on = $("printing").getAttribute("aria-pressed") !== "true";
    view.setPrinting(on);
    toggle("printing", on);
  },
  reset: () => view.reset(),
  bigger: () => {
    const on = $("bigger").getAttribute("aria-pressed") !== "true";
    document.documentElement.style.setProperty("--scale", on ? "1.25" : "1");
    toggle("bigger", on);
    store.set("bigger", on);
  },
  theme: () => {
    const light = !effectiveLight();
    document.documentElement.dataset.theme = light ? "light" : "dark";
    store.set("theme", light ? "light" : "dark");
    drawPlots();
    Object.values(editors).forEach((e) => e.draw());
    for (const w of widgets.values()) if (w.set) w.set(params);
  },
  "help-printing": () => openHelp("printing"),
  "help-function": () => openHelp("function"),
  "help-drawing": () => openHelp("drawing"),
  "help-about": () => openHelp("about"),
};

function closeMenus(except) {
  document.querySelectorAll(".menu[open]").forEach((m) => { if (m !== except) m.open = false; });
}

function wire() {
  document.addEventListener("click", (e) => {
    const b = e.target.closest("[data-do]");
    if (b) {
      closeMenus();
      if (C && actions[b.dataset.do]) actions[b.dataset.do]();
      return;
    }
    if (!e.target.closest(".menu")) closeMenus();
  });
  document.querySelectorAll(".menu").forEach((m) => m.addEventListener("toggle", () => { if (m.open) closeMenus(m); }));
  document.querySelectorAll(".views button").forEach((b) => b.addEventListener("click", () => setView(Number(b.dataset.view))));
  $("simplebtn").addEventListener("click", () => setMode(false));
  $("advancedbtn").addEventListener("click", () => setMode(true));
  $("openfile").addEventListener("change", async (e) => {
    const file = e.target.files[0];
    e.target.value = "";
    if (!file) return;
    await withBusy("Opening it…", async () => replace(JSON.parse(await helper.call("open_vase", await file.text())))).catch(() => {});
  });
  $("picturefile").addEventListener("change", (e) => {
    const file = e.target.files[0];
    e.target.value = "";
    if (file) traceFile(file);
  });
  $("useexample").addEventListener("click", () => {
    setFormula($("examplepick").value);
    $("help").close();
  });
  document.addEventListener("keydown", (e) => {
    if (!C) return;
    const typing = e.target.matches("input, textarea, select");
    if (e.ctrlKey || e.metaKey) {
      const key = e.key.toLowerCase();
      const act = { z: e.shiftKey ? "redo" : "undo", y: "redo", s: "savevase", o: "open", g: "gallery" }[key];
      if (!act || (typing && (key === "z" || key === "y"))) return;
      e.preventDefault();
      actions[act]();
    } else if (!typing && !e.target.matches("canvas") && (e.key === "s" || e.key === "S")) {
      actions.spin();
    }
  });
  const theme = store.get("theme");
  if (theme) document.documentElement.dataset.theme = theme;
  if (store.get("bigger")) actions.bigger();
}

// ================================================================== starting up
function failed(text) {
  $("loading").hidden = false;
  $("loading").classList.add("failed");
  $("loadingtext").textContent = `Vaseinator couldn't start: ${text}. Check the internet connection, then reload ` +
    "the page.";
}

async function boot() {
  wire();
  try {
    const [choices] = await Promise.all([helper.call("start"), builder.call("start")]);
    C = JSON.parse(choices);
  } catch (err) {
    failed(err.message);
    return;
  }
  K = C.constants;
  $("examplepick").append(...C.examples.map(([n, f]) => new Option(`${n}:  ${f}`, f)));
  buildSimple();
  buildAdvanced();
  buildOutlineWindow();
  buildGallery();
  const printer = store.get("printer") || {};
  params = { ...C.defaults, ...(store.get("design") || {}), ...printer };
  $("loading").hidden = true;
  undoButtons();
  setMode(Boolean(store.get("advanced")));
  settled({ refit: true });
}

boot();
