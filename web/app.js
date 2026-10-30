// Vaseinator on the web: Simple mode, as in the desktop app. The vase is built by the app's own Python
// (in worker.js, with Pyodide) and drawn here with three.js.

import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";

const $ = (id) => document.getElementById(id);

// what this browser remembers: the design, the printer, bigger text - if it may
const store = {
  get(key) {
    try { return JSON.parse(localStorage.getItem("vaseinator." + key)); } catch { return null; }
  },
  set(key, value) {
    try { localStorage.setItem("vaseinator." + key, JSON.stringify(value)); } catch { /* private window */ }
  },
};

// ================================================================== the worker
const worker = new Worker("worker.js");
const waiting = new Map();
let nextId = 1;
worker.onmessage = (event) => {
  const { id, ok, result, error } = event.data;
  const w = waiting.get(id);
  waiting.delete(id);
  if (ok) w.resolve(result);
  else w.reject(new Error(lastLine(error)));
};
worker.onerror = (event) => failed(event.message || "the worker stopped");

function call(name, ...args) {
  return new Promise((resolve, reject) => {
    const id = nextId++;
    waiting.set(id, { resolve, reject });
    worker.postMessage({ id, call: name, args });
  });
}

function lastLine(text) {
  // a Python error comes with its whole traceback: its last line says what went wrong
  const lines = String(text).trim().split("\n");
  return lines[lines.length - 1].replace(/^\w*Error: /, "");
}

// ================================================================== the design
let C = null;                 // the choices and constants, from Python
let params = null;            // the design's settings
let meta = null;              // what the last build says about it
const undoStack = [];
const redoStack = [];

function remember() {
  undoStack.push(JSON.stringify(params));
  if (undoStack.length > 100) undoStack.shift();
  redoStack.length = 0;
  undoButtons();
}

function undoButtons() {
  $("undo").disabled = !undoStack.length;
  $("redo").disabled = !redoStack.length;
}

function needsNormal(p) {
  // holes, a face, an open bottom or a wall part way round: spiral vase mode prints one closed line a layer
  return p.holes !== 0 || p.open_bottom || p.around < 360 || p.eyes !== 0 || p.mouth !== 0 || p.straps;
}

function change(updates) {
  if (!C) return;
  remember();
  Object.assign(params, updates);
  settled({});
}

function settled({ refit = false }) {
  if (params.vase_mode === C.constants.REAL_VASE && needsNormal(params)) params.vase_mode = C.constants.FAKE_VASE;
  store.set("design", params);
  refreshPanel();
  rebuild(refit);
}

function replace(next, refit = true) {
  remember();
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

function rebuild(fit = false) {
  seq += 1;
  refit = refit || fit;
  clearTimeout(refineTimer);
  wanted = { seq, draft: true, text: JSON.stringify(params) };
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
    result = await call("build", job.text, job.draft);
  } catch (err) {
    showProblem(err.message);
  }
  busy = false;
  if (result && job.seq === seq) {
    show(result);
    if (job.draft) {
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

// ================================================================== the 3D view
const canvas = $("canvas");
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
const scene = new THREE.Scene();
const pmrem = new THREE.PMREMGenerator(renderer);
scene.environment = pmrem.fromScene(new RoomEnvironment(renderer), 0.04).texture;
const camera = new THREE.PerspectiveCamera(30, 1, 1, 20000);
const controls = new OrbitControls(camera, canvas);
controls.enableDamping = true;
controls.autoRotateSpeed = 1.5;
scene.add(new THREE.HemisphereLight(0xffffff, 0x3a3f48, 0.6));
const sun = new THREE.DirectionalLight(0xffffff, 1.4);
sun.position.set(300, 600, 450);
scene.add(sun);
const fill = new THREE.DirectionalLight(0xffffff, 0.5);
fill.position.set(-500, 150, -300);
scene.add(fill);

// the vase is built z-up, on the bed; three.js looks y-up
const world = new THREE.Group();
world.rotation.x = -Math.PI / 2;
scene.add(world);
const mesh = new THREE.Mesh(new THREE.BufferGeometry(), new THREE.MeshStandardMaterial());
world.add(mesh);
let bed = null;
let bedSize = "";
let home = null;

function materialFor(look) {
  const base = { vertexColors: true };
  if (look === 0) return new THREE.MeshStandardMaterial({ ...base, roughness: 0.85, metalness: 0.0 });     // matte
  if (look === 2) return new THREE.MeshPhysicalMaterial({ ...base, roughness: 0.2, clearcoat: 1.0 });      // glossy
  if (look === 3) {                                                                                       // translucent
    return new THREE.MeshPhysicalMaterial({ ...base, roughness: 0.35, transparent: true, opacity: 0.72 });
  }
  return new THREE.MeshStandardMaterial({ ...base, roughness: 0.32, metalness: 0.35 });                   // silk
}

function linear(srgb) {
  // the colours come as the filament's own (sRGB); three.js lights in linear light
  for (let i = 0; i < srgb.length; i++) {
    const v = srgb[i];
    srgb[i] = v <= 0.04045 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
  }
  return srgb;
}

function setBed([x, y]) {
  const key = `${x}x${y}`;
  if (key === bedSize) return;
  bedSize = key;
  if (bed) {
    world.remove(bed);
    bed.traverse((o) => o.geometry && o.geometry.dispose());
  }
  bed = new THREE.Group();
  const plate = new THREE.Mesh(new THREE.PlaneGeometry(x, y),
    new THREE.MeshStandardMaterial({ color: 0x2a2e35, roughness: 0.9, transparent: true, opacity: 0.55 }));
  plate.position.z = -0.3;
  bed.add(plate);
  const lines = [];
  for (let gx = -x / 2; gx <= x / 2 + 1e-6; gx += 10) lines.push(gx, -y / 2, 0, gx, y / 2, 0);
  for (let gy = -y / 2; gy <= y / 2 + 1e-6; gy += 10) lines.push(-x / 2, gy, 0, x / 2, gy, 0);
  const grid = new THREE.BufferGeometry();
  grid.setAttribute("position", new THREE.Float32BufferAttribute(lines, 3));
  const g = new THREE.LineSegments(grid, new THREE.LineBasicMaterial({ color: 0x59606b, transparent: true, opacity: 0.5 }));
  g.position.z = -0.2;
  bed.add(g);
  world.add(bed);
}

function fitCamera() {
  world.updateMatrixWorld(true);              // the turn to y-up, before the first frame has drawn it
  const box = new THREE.Box3().setFromObject(mesh);
  if (box.isEmpty()) return;
  const centre = box.getCenter(new THREE.Vector3());
  const radius = box.getSize(new THREE.Vector3()).length() / 2;
  const vfov = THREE.MathUtils.degToRad(camera.fov);
  const hfov = 2 * Math.atan(Math.tan(vfov / 2) * camera.aspect);
  const dist = radius / Math.sin(Math.min(vfov, hfov) / 2) * 1.12;
  // as the desktop app starts: from the front and a little to the right, a little above
  const dir = new THREE.Vector3(0.475, 0.309, 0.823).normalize();
  camera.position.copy(centre).addScaledVector(dir, dist);
  camera.near = dist / 100;
  camera.far = dist * 50;
  camera.updateProjectionMatrix();
  controls.target.copy(centre);
  controls.update();
  home = { position: camera.position.clone(), target: centre.clone() };
}

function resize() {
  const view = $("viewer");
  const w = view.clientWidth;
  const h = view.clientHeight;
  if (!w || !h) return;
  renderer.setSize(w, h, false);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
}
new ResizeObserver(resize).observe($("viewer"));
renderer.setAnimationLoop(() => {
  controls.update();
  renderer.render(scene, camera);
});

function show(result) {
  const m = JSON.parse(result.meta);
  if (m.errors && m.errors.length) {
    facts(null, m.errors, m.warnings || [], []);
    return;
  }
  meta = m;
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.BufferAttribute(new Float32Array(result.positions), 3));
  geometry.setAttribute("color", new THREE.BufferAttribute(linear(new Float32Array(result.colours)), 3));
  geometry.setIndex(new THREE.BufferAttribute(new Uint32Array(result.triangles), 1));
  geometry.computeVertexNormals();
  mesh.geometry.dispose();
  mesh.geometry = geometry;
  mesh.material.dispose();
  mesh.material = materialFor(m.look);
  setBed(m.bed);
  if (refit) {
    fitCamera();
    refit = false;
  }
  setNumber($("head"), m.head);
  lightTile($("pattern"), m.pattern);
  facts(m.info, [], m.warnings, m.notes);
}

// ================================================================== the facts
function facts(info, errors, warnings, notes) {
  const table = $("facts");
  table.replaceChildren();
  for (const [k, v] of Object.entries(info || {})) {
    const tr = document.createElement("tr");
    const a = document.createElement("td");
    const b = document.createElement("td");
    a.textContent = k;
    b.textContent = v;
    if (v.endsWith("✓")) b.className = "good";
    else if (v.endsWith("✗")) b.className = "bad";
    tr.append(a, b);
    table.append(tr);
  }
  const box = $("notes");
  box.replaceChildren();
  const add = (text, cls, mark) => {
    const p = document.createElement("p");
    p.className = cls;
    p.textContent = `${mark} ${text}`;
    box.append(p);
  };
  errors.forEach((e) => add(e, "err", "✗"));
  warnings.forEach((w) => add(w, "warn", "⚠"));
  notes.forEach((n) => add(n, "", "ℹ"));
}

function showProblem(text) {
  facts(meta ? meta.info : null, [text], [], []);
}

// ================================================================== the pictures
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
  const bands = colours.map((c, k) =>
    `<rect x="0" y="${40 - (40 * (k + 1)) / n}" width="40" height="${40 / n + 0.5}" fill="${c}"/>`).join("");
  return `<svg viewBox="0 0 40 40" aria-hidden="true"><defs><clipPath id="s${colours.join("").replace(/#/g, "")}">` +
    `<circle cx="20" cy="20" r="19"/></clipPath></defs><g clip-path="url(#s${colours.join("").replace(/#/g, "")})">` +
    `${bands}</g></svg>`;
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

// ================================================================== the panel
function widest() {
  return Math.max(...params.silhouette.map(([, d]) => d));
}

function setNumber(input, value) {
  if (document.activeElement !== input && value !== undefined && value !== null) input.value = value;
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

function refreshPanel() {
  const p = params;
  const K = C.constants;
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

function buildPanel() {
  const K = C.constants;
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
      const cols = Object.fromEntries(m.colours.map((c, i) => [`color${i + 1}`, c]));
      change({ ...m.settings, ...cols });
    }
  }, "swatch");

  // the gallery: the plain cylinder, then every ready-made design
  const designs = $("designs");
  const entries = [{ title: "Plain cylinder", slug: "plain_cylinder",
    about: "200 mm across and 200 mm tall, with everything else off: a blank start" }].concat(C.gallery);
  for (const g of entries) {
    const b = document.createElement("button");
    b.className = "design";
    b.title = g.about;
    b.innerHTML = `<img src="gallery/${g.slug}.png" alt="" loading="lazy"><b></b>`;
    b.querySelector("b").textContent = g.title;
    b.addEventListener("click", async () => {
      $("gallery").close();
      await withBusy("Getting it ready…", async () => replace(JSON.parse(await call("design_of", g.title, JSON.stringify(params)))));
    });
    designs.append(b);
  }
}

async function withBusy(text, work) {
  showBusy(text);
  try {
    await work();
  } catch (err) {
    showProblem(err.message);
  } finally {
    if (!busy) showBusy(null);
  }
}

function download(data, name, type) {
  const url = URL.createObjectURL(new Blob([data], { type }));
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

function wire() {
  $("choose").addEventListener("click", () => C && $("gallery").showModal());
  $("surprise").addEventListener("click", () => C && withBusy("Thinking of something…", async () =>
    replace(JSON.parse(await call("surprise_me", JSON.stringify(params), Math.floor(Math.random() * 1e6))))));
  $("tall").addEventListener("change", (e) => {
    const cm = parseFloat(e.target.value);
    if (cm > 0) change({ height: Math.round(cm * 100) / 10 });
  });
  $("wide").addEventListener("change", (e) => {
    const cm = parseFloat(e.target.value);
    const old = widest();
    if (cm > 0 && old > 0) {
      change({ silhouette: params.silhouette.map(([h, d]) => [h, Math.round((d * cm * 10 * 1000) / old) / 1000]) });
    }
  });
  $("head").addEventListener("change", (e) => {
    const cm = parseFloat(e.target.value);
    if (cm > 0 && C) {
      withBusy("Fitting it to the head…", async () => replace(JSON.parse(await call("fit", JSON.stringify(params), cm * 10)), false));
    }
  });
  $("twist").addEventListener("input", (e) => {
    $("twistwords").textContent = twistWords(15 * e.target.value);
  });
  $("twist").addEventListener("change", (e) => {
    const updates = { twist: 15 * Number(e.target.value) };
    if (params.twist_style === C.constants.OWN) updates.twist_style = C.constants.EVENLY;
    change(updates);
  });
  for (const input of document.querySelectorAll("#printer input")) {
    input.addEventListener("change", () => {
      const v = parseFloat(input.value);
      if (!(v > 0)) return;
      change({ [input.dataset.key]: input.dataset.key === "walls" ? Math.round(v) : v });
      store.set("printer", Object.fromEntries(C.printer_keys.map((k) => [k, params[k]])));
    });
  }
  $("save").addEventListener("click", () => C && withBusy("Making the file for your slicer…", async () => {
    const data = await call("export_3mf", JSON.stringify(params));
    const name = fileName() + ".3mf";
    download(data, name, "model/3mf");
    $("saved").innerHTML = "";
    $("saved").append(`Saved ${name} to your downloads.`);
    $("steplist").innerHTML = (meta ? meta.steps : []).map((s) => `<li>${s}</li>`).join("");
    $("steps").showModal();
  }));
  $("stl").addEventListener("click", () => C && withBusy("Making the STL…", async () =>
    download(await call("export_stl", JSON.stringify(params)), fileName() + ".stl", "model/stl")));
  $("savevase").addEventListener("click", async () => {
    if (!C) return;
    download(await call("save_vase", JSON.stringify(params)), fileName() + ".vase", "application/json");
  });
  $("openvase").addEventListener("click", () => C && $("openfile").click());
  $("openfile").addEventListener("change", async (e) => {
    const file = e.target.files[0];
    e.target.value = "";
    if (!file) return;
    await withBusy("Opening it…", async () => replace(JSON.parse(await call("open_vase", await file.text()))));
  });
  $("undo").addEventListener("click", () => step(undoStack, redoStack));
  $("redo").addEventListener("click", () => step(redoStack, undoStack));
  document.addEventListener("keydown", (e) => {
    if (e.target.matches("input") || !(e.ctrlKey || e.metaKey)) return;
    const key = e.key.toLowerCase();
    if (key === "z" && !e.shiftKey) step(undoStack, redoStack);
    else if (key === "y" || (key === "z" && e.shiftKey)) step(redoStack, undoStack);
    else return;
    e.preventDefault();
  });
  $("spin").addEventListener("click", (e) => {
    controls.autoRotate = !controls.autoRotate;
    e.currentTarget.setAttribute("aria-pressed", String(controls.autoRotate));
  });
  $("reset").addEventListener("click", () => {
    if (!home) return;
    camera.position.copy(home.position);
    controls.target.copy(home.target);
    controls.update();
  });
  const bigger = $("bigger");
  const scale = (on) => {
    document.documentElement.style.setProperty("--scale", on ? "1.25" : "1");
    bigger.setAttribute("aria-pressed", String(on));
    store.set("bigger", on);
  };
  scale(Boolean(store.get("bigger")));
  bigger.addEventListener("click", () => scale(bigger.getAttribute("aria-pressed") !== "true"));
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
    C = JSON.parse(await call("start"));
  } catch (err) {
    failed(err.message);
    return;
  }
  buildPanel();
  const printer = store.get("printer") || {};
  params = { ...C.defaults, ...(store.get("design") || {}), ...printer };
  $("loading").hidden = true;
  undoButtons();
  settled({ refit: true });
}

boot();
