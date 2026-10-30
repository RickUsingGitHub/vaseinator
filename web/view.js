// The 3D view, as the desktop app's: the vase; a section through the printed wall; every face coloured by how
// far it leans; the print layout on the bed inside the printer; a turntable; and the print played back.

import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";

export const VASE = 0;
export const SECTION = 1;
export const OVERHANGS = 2;
export const LAYOUT = 3;
const ANGLES = { [VASE]: [-60, 14], [SECTION]: [-90, 8], [OVERHANGS]: [-60, 14], [LAYOUT]: [-55, 32] };
const SPIN_SPEED = 30;          // degrees a second, on the turntable

function linear(v) {
  return v <= 0.04045 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
}

function heat(a, limit) {
  // green is easy, orange near the limit, red over it; grey for floors and rims, which are not a wall
  if (a < 0) return [0.5, 0.53, 0.58];
  if (a > limit + 0.3) return [0.92, 0.16, 0.14];
  const t = Math.min(Math.max((a / limit - 0.55) / 0.45, 0), 1);
  return [0.18 + (1.0 - 0.18) * t, 0.68 + (0.7 - 0.68) * t, 0.36 + (0.12 - 0.36) * t];
}

export function duration(seconds) {
  const m = Math.round(seconds / 60);
  return m >= 60 ? `${Math.floor(m / 60)} h ${String(m % 60).padStart(2, "0")} min` : `${Math.max(m, 1)} min`;
}

export class View {
  constructor(canvas, container, onHint) {
    this.canvas = canvas;
    this.onHint = onHint;
    this.mode = VASE;
    this.meta = null;
    this.colours = null;
    this.heat = null;
    this.lean = null;
    this.spinning = false;
    this.printing = null;          // when the print began, while it plays
    this.home = null;
    this.fitted = null;
    const r = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, preserveDrawingBuffer: true });
    r.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    r.localClippingEnabled = true;
    this.renderer = r;
    this.scene = new THREE.Scene();
    const pmrem = new THREE.PMREMGenerator(r);
    this.scene.environment = pmrem.fromScene(new RoomEnvironment(r), 0.04).texture;
    this.camera = new THREE.PerspectiveCamera(30, 1, 1, 20000);
    this.controls = new OrbitControls(this.camera, canvas);
    this.controls.enableDamping = true;
    this.moved = false;                                            // turned or zoomed by hand: kept as it is
    this.controls.addEventListener("start", () => { this.moved = true; });
    this.scene.add(new THREE.HemisphereLight(0xffffff, 0x3a3f48, 0.6));
    const sun = new THREE.DirectionalLight(0xffffff, 1.4);
    sun.position.set(300, 600, 450);
    this.scene.add(sun);
    const fill = new THREE.DirectionalLight(0xffffff, 0.5);
    fill.position.set(-500, 150, -300);
    this.scene.add(fill);
    // the vase is built z-up, on the bed; three.js looks y-up. The turntable turns it round its axis.
    this.turntable = new THREE.Group();
    this.scene.add(this.turntable);
    this.world = new THREE.Group();
    this.world.rotation.x = -Math.PI / 2;
    this.turntable.add(this.world);
    this.mesh = new THREE.Mesh(new THREE.BufferGeometry(), new THREE.MeshStandardMaterial());
    this.world.add(this.mesh);
    this.bed = null;
    this.bedKey = "";
    this.cut = { value: -1e9 };                                    // the print's height so far, while it plays
    this.sectionPlane = new THREE.Plane(new THREE.Vector3(0, 0, -1), 0);
    this.printPlane = new THREE.Plane(new THREE.Vector3(0, -1, 0), 1e9);
    new ResizeObserver(() => this.resize()).observe(container);
    this.container = container;
    this.last = performance.now();
    r.setAnimationLoop(() => this.frame());
  }

  resize() {
    const w = this.container.clientWidth;
    const h = this.container.clientHeight;
    if (!w || !h) return;
    this.renderer.setSize(w, h, false);
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
    if (this.fitted !== null && !this.moved) this.fit();
  }

  material(look) {
    const base = { vertexColors: true };
    let m;
    if (look === 0) m = new THREE.MeshStandardMaterial({ ...base, roughness: 0.85, metalness: 0 });          // matte
    else if (look === 2) m = new THREE.MeshPhysicalMaterial({ ...base, roughness: 0.2, clearcoat: 1 });       // glossy
    else if (look === 3) m = new THREE.MeshPhysicalMaterial({ ...base, roughness: 0.35, transparent: true, opacity: 0.72 });
    else m = new THREE.MeshStandardMaterial({ ...base, roughness: 0.32, metalness: 0.35 });                   // silk
    if (this.mode === OVERHANGS) {
      m.metalness = 0;
      m.roughness = 0.7;
      m.transparent = false;
      m.opacity = 1;
    }
    const planes = [];
    if (this.mode === SECTION) planes.push(this.sectionPlane);
    if (this.printing !== null) planes.push(this.printPlane);
    m.clippingPlanes = planes;
    m.side = planes.length ? THREE.DoubleSide : THREE.FrontSide;
    const cut = this.cut;
    m.onBeforeCompile = (shader) => {
      shader.uniforms.uCut = cut;
      shader.vertexShader = "varying float vHeight;\n" + shader.vertexShader.replace("#include <begin_vertex>",
        "#include <begin_vertex>\nvHeight = (modelMatrix * vec4(transformed, 1.0)).y;");
      shader.fragmentShader = "varying float vHeight;\nuniform float uCut;\n" + shader.fragmentShader
        .replace("#include <color_fragment>",
          "#include <color_fragment>\nif (!gl_FrontFacing) diffuseColor.rgb *= 0.45;   // the cut face")
        .replace("#include <emissivemap_fragment>",
          "#include <emissivemap_fragment>\n"
          + "if (uCut > -1.0e8 && vHeight > uCut - 0.8) totalEmissiveRadiance += vec3(1.0, 0.42, 0.08);   // the layer printing");
    };
    return m;
  }

  show(result, meta, refit) {
    this.meta = meta;
    const positions = new Float32Array(result.positions);
    const colours = new Float32Array(result.colours);
    for (let i = 0; i < colours.length; i++) colours[i] = linear(colours[i]);
    this.colours = colours;
    this.lean = new Float32Array(result.lean);
    this.heat = null;
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    geometry.setAttribute("color", new THREE.BufferAttribute(this.mode === OVERHANGS ? this.heatColours() : colours, 3));
    geometry.setIndex(new THREE.BufferAttribute(new Uint32Array(result.triangles), 1));
    geometry.computeVertexNormals();
    this.mesh.geometry.dispose();
    this.mesh.geometry = geometry;
    this.restyle();
    this.setBed(meta.bed);
    const size = [Math.round(meta.size[0]), Math.round(meta.size[1]), Math.round(meta.height)].join("x");
    if (refit || this.fitted !== `${this.mode} ${size}`) {
      if (refit) this.moved = false;
      if (refit || !this.moved) this.fit();
    }
    this.hint();
  }

  heatColours() {
    if (!this.heat) {
      const limit = this.meta ? this.meta.limit : 45;
      this.heat = new Float32Array(this.lean.length * 3);
      this.lean.forEach((a, i) => {
        const c = heat(a, limit);
        this.heat[3 * i] = linear(c[0]);
        this.heat[3 * i + 1] = linear(c[1]);
        this.heat[3 * i + 2] = linear(c[2]);
      });
    }
    return this.heat;
  }

  restyle() {
    if (!this.meta) return;
    this.mesh.material.dispose();
    this.mesh.material = this.material(this.meta.look);
    const attr = this.mesh.geometry.getAttribute("color");
    if (attr) {
      const want = this.mode === OVERHANGS ? this.heatColours() : this.colours;
      if (attr.array !== want) {
        this.mesh.geometry.setAttribute("color", new THREE.BufferAttribute(want, 3));
      }
    }
    if (this.box) this.box.visible = this.mode === LAYOUT;
  }

  setMode(mode) {
    this.mode = mode;
    this.moved = false;
    this.restyle();
    this.fit();
    this.hint();
  }

  setBed([x, y, height]) {
    const key = `${x}x${y}x${height}`;
    if (key === this.bedKey) return;
    this.bedKey = key;
    if (this.bed) {
      this.world.remove(this.bed);
      this.bed.traverse((o) => o.geometry && o.geometry.dispose());
    }
    this.bed = new THREE.Group();
    const plate = new THREE.Mesh(new THREE.PlaneGeometry(x, y),
      new THREE.MeshStandardMaterial({ color: 0x2a2e35, roughness: 0.9, transparent: true, opacity: 0.55 }));
    plate.position.z = -0.3;
    this.bed.add(plate);
    const lines = [];
    for (let gx = -x / 2; gx <= x / 2 + 1e-6; gx += 10) lines.push(gx, -y / 2, 0, gx, y / 2, 0);
    for (let gy = -y / 2; gy <= y / 2 + 1e-6; gy += 10) lines.push(-x / 2, gy, 0, x / 2, gy, 0);
    const grid = new THREE.BufferGeometry();
    grid.setAttribute("position", new THREE.Float32BufferAttribute(lines, 3));
    const g = new THREE.LineSegments(grid, new THREE.LineBasicMaterial({ color: 0x59606b, transparent: true, opacity: 0.5 }));
    g.position.z = -0.2;
    this.bed.add(g);
    // the printer's build volume, for the print layout
    const box = new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(x, y, height)),
      new THREE.LineBasicMaterial({ color: 0x8892a0, transparent: true, opacity: 0.6 }));
    box.position.z = height / 2;
    box.visible = this.mode === LAYOUT;
    this.box = box;
    this.bed.add(box);
    this.world.add(this.bed);
  }

  fit() {
    if (!this.meta) return;
    const m = this.meta;
    const r = 0.5 * Math.hypot(m.size[0], m.size[1]);
    const reach = Math.hypot(r, 0.5 * m.height);
    const vfov = THREE.MathUtils.degToRad(this.camera.fov);
    const fov = vfov * Math.min(1, this.camera.aspect);
    const dist = (reach / Math.sin(fov / 2)) * (this.mode === LAYOUT ? 1.75 : 1.12);
    const [yaw, pitch] = ANGLES[this.mode].map((d) => THREE.MathUtils.degToRad(d));
    const dir = new THREE.Vector3(Math.cos(pitch) * Math.cos(yaw), Math.sin(pitch), -Math.cos(pitch) * Math.sin(yaw));
    const target = new THREE.Vector3(0, 0.5 * m.height, 0);
    this.camera.position.copy(target).addScaledVector(dir, dist);
    this.camera.near = dist / 100;
    this.camera.far = dist * 50;
    this.camera.updateProjectionMatrix();
    this.controls.target.copy(target);
    this.controls.update();
    this.home = { position: this.camera.position.clone(), target: target.clone() };
    this.fitted = `${this.mode} ${[Math.round(m.size[0]), Math.round(m.size[1]), Math.round(m.height)].join("x")}`;
  }

  reset() {
    this.moved = false;
    this.fit();
  }

  setSpin(on) {
    this.spinning = on;
    if (!on) this.turntable.rotation.y = 0;
  }

  setPrinting(on) {
    this.printing = on && this.meta ? performance.now() : null;
    this.cut.value = -1e9;
    this.printPlane.constant = 1e9;
    this.restyle();
    this.hint();
  }

  hint(text) {
    if (text) return this.onHint(text);
    if (this.mode === OVERHANGS && this.meta) {
      this.onHint(`Green: easy · orange: near ${this.meta.limit}° · red: over it, needs support`);
    } else if (this.printing === null) {
      this.onHint("Drag to turn · wheel or pinch to zoom · right-drag to move");
    }
  }

  frame() {
    const now = performance.now();
    const dt = Math.min((now - this.last) / 1000, 0.1);
    this.last = now;
    if (this.spinning) this.turntable.rotation.y += THREE.MathUtils.degToRad(SPIN_SPEED) * dt;
    if (this.printing !== null && this.meta) this.playPrint(now);
    this.controls.update();
    this.renderer.render(this.scene, this.camera);
  }

  playPrint(now) {
    // the real print time: the filament used up to each height, at an even speed
    const m = this.meta;
    const span = Math.min(Math.max(6 + m.height / 30, 6), 16);
    let t = (now - this.printing) / 1000 / span;
    if (t > 1.25) {                                                // hold the finished vase a moment, then again
      this.printing = now;
      t = 0;
    }
    t = Math.min(t, 1);
    const { z, at, layers, seconds, grams } = m.printing;
    const done = at[at.length - 1] * t;
    let height = t * m.height;
    if (at[at.length - 1] > 0) {
      let k = 1;
      while (k < at.length - 1 && at[k] < done) k++;
      const f = (done - at[k - 1]) / Math.max(at[k] - at[k - 1], 1e-9);
      height = z[k - 1] + Math.min(Math.max(f, 0), 1) * (z[k] - z[k - 1]);
    }
    height = Math.min(Math.max(height, 0.05), m.height);
    const playing = t < 1;
    this.cut.value = playing ? height : -1e9;
    this.printPlane.constant = playing ? height : 1e9;
    const layer = Math.min(Math.ceil((height / m.height) * layers), layers);
    this.onHint(playing ? `Printing: layer ${layer} of ${layers} · ${duration(seconds * t)} of ${duration(seconds)}`
      : `Done: ${duration(seconds)}, ${Math.round(grams)} g of filament`);
  }

  picture() {
    this.renderer.render(this.scene, this.camera);
    return new Promise((resolve) => this.canvas.toBlob(resolve, "image/png"));
  }
}
