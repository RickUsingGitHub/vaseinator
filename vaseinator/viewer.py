"""Lightweight OpenGL 3D viewer (QOpenGLWidget + PyOpenGL, GLSL 1.20).

Besides plain colours it can colour the vase by height (filament bands), by
the filament used so far (a gradient spool), or by how far each face leans
(the overhang check), and it can cut the vase in half or at a height.
"""

from __future__ import annotations

import ctypes
import math

import numpy as np
from OpenGL import GL as gl
from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtOpenGLWidgets import QOpenGLWidget

MAX_BANDS = 64

VERT_SRC = """
#version 120
attribute vec3 a_pos;
attribute vec3 a_nrm;
attribute vec2 a_val;
uniform mat4 u_model;
uniform mat4 u_view;
uniform mat4 u_proj;
varying vec3 v_nrm;
varying vec3 v_pos;
varying vec3 v_world;
varying vec3 v_obj;
varying vec2 v_val;
void main() {
    vec4 w = u_model * vec4(a_pos, 1.0);
    v_world = w.xyz;
    v_obj = a_pos;
    v_val = a_val;
    vec4 vp = u_view * w;
    v_pos = vp.xyz;
    v_nrm = mat3(u_view) * mat3(u_model) * a_nrm;
    gl_Position = u_proj * vp;
}
"""

FRAG_SRC = """
#version 120
uniform vec3 u_color;
uniform float u_alpha;
uniform int u_mode;          // 0 unlit, 1 lit, 2 background gradient
uniform int u_colmode;       // 0 plain, 1 bands by height, 2 gradient spool, 3 overhang check
uniform float u_bz[64];
uniform vec3 u_bc[64];
uniform int u_nb;
uniform vec3 u_gc[4];
uniform int u_ng;
uniform float u_limit;
uniform int u_look;          // 0 matte, 1 silk, 2 glossy, 3 translucent
uniform int u_clip;
uniform vec4 u_plane;
uniform int u_cut;
uniform float u_cutz;
uniform vec3 u_bg_top;
uniform vec3 u_bg_bot;
uniform float u_vh;
varying vec3 v_nrm;
varying vec3 v_pos;
varying vec3 v_world;
varying vec3 v_obj;
varying vec2 v_val;

vec3 band_colour(float z) {
    vec3 c = u_bc[0];
    for (int i = 1; i < 64; i++) {
        if (i >= u_nb) break;
        if (z >= u_bz[i]) c = u_bc[i];
    }
    return c;
}

vec3 gradient_colour(float phase) {
    float p = fract(phase) * float(u_ng);
    float k = floor(p);
    float k1 = mod(k + 1.0, float(u_ng));
    float t = smoothstep(0.0, 1.0, p - k);
    vec3 a = u_gc[0];
    vec3 b = u_gc[0];
    for (int i = 0; i < 4; i++) {
        if (float(i) == k) a = u_gc[i];
        if (float(i) == k1) b = u_gc[i];
    }
    return mix(a, b, t);
}

vec3 heat(float a) {
    if (a < 0.0) return vec3(0.50, 0.53, 0.58);            // floors and rims: not a wall
    if (a > u_limit + 0.3) return vec3(0.92, 0.16, 0.14);  // over the limit: needs support
    float t = clamp((a / u_limit - 0.55) / 0.45, 0.0, 1.0);
    return mix(vec3(0.18, 0.68, 0.36), vec3(1.0, 0.70, 0.12), t);
}

void main() {
    if (u_mode == 2) {
        float t = clamp(gl_FragCoord.y / u_vh, 0.0, 1.0);
        gl_FragColor = vec4(mix(u_bg_bot, u_bg_top, t), 1.0);
        return;
    }
    if (u_clip == 1 && dot(vec4(v_world, 1.0), u_plane) > 0.0) discard;
    if (u_cut == 1 && v_obj.z > u_cutz) discard;
    if (u_mode == 0) { gl_FragColor = vec4(u_color, u_alpha); return; }
    vec3 col = u_color;
    if (u_colmode == 1) col = band_colour(v_obj.z);
    else if (u_colmode == 2) col = gradient_colour(v_val.y);
    else if (u_colmode == 3) col = heat(v_val.x);
    vec3 n = normalize(v_nrm);
    if (!gl_FrontFacing) {            // the cut face of a sectioned vase
        n = -n;
        col = col * 0.5;
    }
    vec3 vdir = normalize(-v_pos);
    vec3 l1 = normalize(vec3(0.45, 0.75, 0.55));
    vec3 l2 = normalize(vec3(-0.7, -0.25, 0.45));
    float d1 = max(dot(n, l1), 0.0);
    float d2 = max(dot(n, l2), 0.0);
    float ndv = max(dot(n, vdir), 0.0);
    vec3 h = normalize(l1 + vdir);
    float nh = max(dot(n, h), 0.0);
    vec3 c;
    float alpha = u_alpha;
    if (u_colmode == 3 || u_look == 0) {                    // matte
        c = col * (0.30 + d1 * 0.62 + d2 * 0.22) + vec3(pow(nh, 16.0) * 0.05);
    } else if (u_look == 1) {                               // silk: bright tinted sheen at the edges
        vec3 tint = mix(vec3(1.0), col, 0.55);
        c = col * (0.22 + d1 * 0.62 + d2 * 0.2) + tint * (pow(nh, 22.0) * 0.55 + pow(nh, 6.0) * 0.12)
            + col * pow(1.0 - ndv, 2.0) * 0.35;
    } else if (u_look == 2) {                               // glossy
        c = col * (0.24 + d1 * 0.66 + d2 * 0.22) + vec3(pow(nh, 90.0) * 0.6 + pow(1.0 - ndv, 4.0) * 0.12);
    } else {                                                // translucent: light through the wall
        c = col * (0.42 + d1 * 0.45 + d2 * 0.2 + 0.25 * (1.0 - ndv)) + vec3(pow(nh, 60.0) * 0.4);
        alpha = min(alpha, 0.55 + 0.35 * (1.0 - ndv));
    }
    gl_FragColor = vec4(c, alpha);
}
"""


def _perspective(fovy_deg, aspect, near, far):
    f = 1.0 / math.tan(math.radians(fovy_deg) / 2.0)
    m = np.zeros((4, 4))
    m[0, 0] = f / aspect
    m[1, 1] = f
    m[2, 2] = (far + near) / (near - far)
    m[2, 3] = 2.0 * far * near / (near - far)
    m[3, 2] = -1.0
    return m


def _look_at(eye, target, up):
    f = target - eye
    f = f / np.linalg.norm(f)
    s = np.cross(f, up)
    s = s / np.linalg.norm(s)
    u = np.cross(s, f)
    m = np.identity(4)
    m[0, :3], m[1, :3], m[2, :3] = s, u, -f
    m[0, 3], m[1, 3], m[2, 3] = -s @ eye, -u @ eye, f @ eye
    return m


def spin_transform(deg: float) -> np.ndarray:
    """4x4 model matrix turning the vase round its own axis."""
    a = math.radians(deg)
    m = np.identity(4)
    m[0, 0], m[0, 1], m[1, 0], m[1, 1] = math.cos(a), -math.sin(a), math.sin(a), math.cos(a)
    return m


def plane_cut(tri: np.ndarray, dist: np.ndarray) -> np.ndarray:
    """Where triangles (K,3,3) cross a plane, given each corner's distance from it: segments (S,2,3)."""
    cross = (dist.min(1) < 0) & (dist.max(1) > 0)
    tri, dist = tri[cross], dist[cross]
    pts, hits = [], []
    for a, b in ((0, 1), (1, 2), (2, 0)):
        da, db = dist[:, a], dist[:, b]
        hit = da * db < 0
        t = np.where(hit, da / np.where(hit, da - db, 1.0), 0.0)
        pts.append(tri[:, a] + (tri[:, b] - tri[:, a]) * t[:, None])
        hits.append(hit)
    P, H = np.stack(pts, 1), np.stack(hits, 1)
    two = np.argsort(~H, axis=1, kind="stable")[:, :2]
    seg = np.take_along_axis(P, two[:, :, None], axis=1)
    return seg[H.sum(1) >= 2]


CREASE_COS = math.cos(math.radians(28.0))        # edges sharper than this are drawn crisp


class _Mesh:
    def __init__(self, verts, faces, color, face_vals=None, vert_vals=None, flat=False):
        tri = verts[faces].astype(np.float32)                     # (m,3,3)
        area_n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])    # length = 2 x area
        ln = np.linalg.norm(area_n, axis=1, keepdims=True)
        ln[ln == 0] = 1
        n = (area_n / ln).astype(np.float32)
        # Smooth shading where the surface curves gently, flat shading at real
        # edges (the rim, a polygon's corners, low-poly facets).  A vertex is
        # smooth only if every face round it is close to the averaged normal.
        nv = len(verts)
        flat_idx = faces.ravel()
        vn = np.stack([np.bincount(flat_idx, weights=np.repeat(area_n[:, k], 3), minlength=nv)
                       for k in range(3)], 1)
        vl = np.linalg.norm(vn, axis=1, keepdims=True)
        vl[vl == 0] = 1
        vn = (vn / vl).astype(np.float32)
        corner_vn = vn[faces]
        too_sharp = np.einsum("mij,mj->mi", corner_vn, n) < CREASE_COS
        creased = np.bincount(flat_idx, weights=too_sharp.ravel(), minlength=nv) > 0
        smooth = ~creased[faces] & (not flat)
        data = np.zeros((len(faces), 3, 8), dtype=np.float32)
        data[:, :, :3] = tri
        data[:, :, 3:6] = np.where(smooth[:, :, None], corner_vn, n[:, None, :])
        if face_vals is not None:
            data[:, :, 6] = np.asarray(face_vals, dtype=np.float32)[:, None]
        if vert_vals is not None:
            data[:, :, 7] = np.asarray(vert_vals, dtype=np.float32)[faces]
        self.data = data.reshape(-1, 8)
        self.count = len(self.data)
        self.lo = verts.min(axis=0)
        self.hi = verts.max(axis=0)
        self.color = color
        self.vbo = None


class Viewer3D(QOpenGLWidget):
    BG_TOP = (0.20, 0.23, 0.28)
    BG_BOT = (0.08, 0.09, 0.11)

    dragged = Signal()                # the user moved the camera
    reset_requested = Signal()        # double-click or F: back to the chosen view
    resized = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.meshes: dict[str, _Mesh] = {}
        self._stale_vbos: list[int] = []
        self.prog = None
        self.grid_vbo = None
        self.grid_count = 0
        self.box_count = 0
        self.bed = (256.0, 256.0, 250.0)   # printer bed (mm) and the height it prints to
        self.show_bed = False
        self._grid_bed = None
        self.model = np.identity(4)
        self.fov = 30.0
        self.yaw = -60.0
        self.pitch = 18.0
        self.dist = 400.0
        self.target = np.array([0.0, 0.0, 90.0])
        # how the vase is coloured and drawn
        self.colmode = 0
        self.bands = [(0.0, (0.8, 0.8, 0.8))]
        self.gradient = [(0.8, 0.8, 0.8)]
        self.limit = 45.0
        self.look = 0
        self.section = False
        self.cut_z = None             # draw only what is below this height (the print animation)
        self.lines = None             # (segments (K,2,3) float32, colour)
        self._lines_vbo = None
        self._lines_dirty = False
        self._cut_src = None          # the shown triangles, for the section's outline
        self._cut_key = None
        self._cut_vbo = None
        self._cut_count = 0
        self._last = None
        self._gl_error = None
        self.setMinimumSize(320, 240)
        self.setFocusPolicy(Qt.StrongFocus)

    # ------------------------------------------------------------ scene API
    def set_mesh(self, name, verts, faces, color, face_vals=None, vert_vals=None, flat=False):
        """flat: every face drawn flat, as low-poly facets should be."""
        old = self.meshes.get(name)
        if old is not None and old.vbo is not None:
            self._stale_vbos.append(old.vbo)
        self.meshes[name] = _Mesh(verts, faces, color, face_vals, vert_vals, flat)
        self.update()

    def remove_mesh(self, name):
        old = self.meshes.pop(name, None)
        if old is not None and old.vbo is not None:
            self._stale_vbos.append(old.vbo)
        self.update()

    def set_model(self, model):
        self.model = model
        self.update()

    def set_bed(self, width: float, depth: float, height: float):
        bed = (float(width), float(depth), float(height))
        if bed != self.bed:
            self.bed = bed
            self.update()

    def set_section_source(self, verts, faces):
        """The triangles whose cut is outlined in the section view."""
        self._cut_src = np.asarray(verts, dtype=np.float32)[faces]
        self._cut_key = None
        self.update()

    def set_lines(self, segments, color=(1.0, 0.85, 0.35)):
        self.lines = None if segments is None or not len(segments) else (
            np.asarray(segments, dtype=np.float32).reshape(-1, 3), color)
        self._lines_dirty = True
        self.update()

    def scene_bounds(self):
        lo = np.array([np.inf] * 3)
        hi = -lo
        for m in self.meshes.values():
            corners = np.array([[x, y, z] for x in (m.lo[0], m.hi[0])
                                for y in (m.lo[1], m.hi[1]) for z in (m.lo[2], m.hi[2])])
            pts = corners @ self.model[:3, :3].T + self.model[:3, 3]
            lo = np.minimum(lo, pts.min(0))
            hi = np.maximum(hi, pts.max(0))
        if not np.isfinite(lo).all():
            return np.zeros(3), np.ones(3) * 50
        return lo, hi

    def fit_distance(self, lo=None, hi=None):
        """Camera distance that shows the whole scene, whatever way it is turned."""
        if lo is None:
            lo, hi = self.scene_bounds()
        radius = max(np.linalg.norm(hi - lo) / 2.0, 10.0)
        aspect = max(self.width(), 1) / max(self.height(), 1)
        fov = math.radians(self.fov) * min(1.0, aspect)
        return radius / math.sin(fov / 2.0) * 1.02

    # ---------------------------------------------------------------- GL
    def initializeGL(self):
        for m in self.meshes.values():
            m.vbo = None
        self._stale_vbos.clear()
        self.grid_vbo = None
        self._grid_bed = None
        self._lines_vbo = None
        self._lines_dirty = True
        self._cut_vbo = None
        self._cut_key = None
        try:
            self.prog = self._build_program()
            self._quad_vbo = gl.glGenBuffers(1)
            quad = np.array([[-1, -1, 0], [1, -1, 0], [1, 1, 0],
                             [-1, -1, 0], [1, 1, 0], [-1, 1, 0]], dtype=np.float32)
            gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self._quad_vbo)
            gl.glBufferData(gl.GL_ARRAY_BUFFER, quad.nbytes, quad, gl.GL_STATIC_DRAW)
            gl.glBindBuffer(gl.GL_ARRAY_BUFFER, 0)
            self._gl_error = None
        except Exception as exc:  # pragma: no cover - driver specific
            self.prog = None
            self._gl_error = str(exc)

    def _build_program(self):
        def compile_shader(src, kind):
            sh = gl.glCreateShader(kind)
            gl.glShaderSource(sh, src)
            gl.glCompileShader(sh)
            if not gl.glGetShaderiv(sh, gl.GL_COMPILE_STATUS):
                raise RuntimeError(gl.glGetShaderInfoLog(sh).decode(errors="replace"))
            return sh

        vs = compile_shader(VERT_SRC, gl.GL_VERTEX_SHADER)
        fs = compile_shader(FRAG_SRC, gl.GL_FRAGMENT_SHADER)
        prog = gl.glCreateProgram()
        gl.glAttachShader(prog, vs)
        gl.glAttachShader(prog, fs)
        gl.glBindAttribLocation(prog, 0, "a_pos")
        gl.glBindAttribLocation(prog, 1, "a_nrm")
        gl.glBindAttribLocation(prog, 2, "a_val")
        gl.glLinkProgram(prog)
        if not gl.glGetProgramiv(prog, gl.GL_LINK_STATUS):
            raise RuntimeError(gl.glGetProgramInfoLog(prog).decode(errors="replace"))
        gl.glDeleteShader(vs)
        gl.glDeleteShader(fs)
        self._loc = {n: gl.glGetUniformLocation(prog, n) for n in (
            "u_model", "u_view", "u_proj", "u_color", "u_alpha", "u_mode", "u_colmode", "u_bz", "u_bc",
            "u_nb", "u_gc", "u_ng", "u_limit", "u_look", "u_clip", "u_plane", "u_cut", "u_cutz",
            "u_bg_top", "u_bg_bot", "u_vh")}
        return prog

    def _upload(self, m: _Mesh):
        m.vbo = gl.glGenBuffers(1)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, m.vbo)
        gl.glBufferData(gl.GL_ARRAY_BUFFER, m.data.nbytes, m.data, gl.GL_STATIC_DRAW)

    def _ensure_grid(self):
        """The printer bed: a 10 mm grid of its real size, an outline, and the space it prints in."""
        if self.grid_vbo is not None and self._grid_bed == self.bed:
            return
        if self.grid_vbo is not None:
            gl.glDeleteBuffers(1, [self.grid_vbo])
        bx, by, bz = self.bed
        x0, y0, x1, y1 = -bx / 2.0, -by / 2.0, bx / 2.0, by / 2.0
        lines = []
        for x in x0 + np.arange(0.0, bx + 1e-6, 10.0):
            lines += [(x, y0, 0), (x, y1, 0)]
        for y in y0 + np.arange(0.0, by + 1e-6, 10.0):
            lines += [(x0, y, 0), (x1, y, 0)]
        self.grid_count = len(lines)
        corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
        box = []
        for k in range(4):
            (ax, ay), (cx, cy) = corners[k], corners[(k + 1) % 4]
            box += [(ax, ay, 0), (cx, cy, 0), (ax, ay, bz), (cx, cy, bz), (ax, ay, 0), (ax, ay, bz)]
        self.box_count = len(box)
        arr = np.array(lines + box, dtype=np.float32)
        self.grid_vbo = gl.glGenBuffers(1)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.grid_vbo)
        gl.glBufferData(gl.GL_ARRAY_BUFFER, arr.nbytes, arr, gl.GL_STATIC_DRAW)
        self._grid_bed = self.bed

    def _mat(self, name, m):
        gl.glUniformMatrix4fv(self._loc[name], 1, gl.GL_TRUE, m.astype(np.float32))

    def eye(self):
        y, p = math.radians(self.yaw), math.radians(self.pitch)
        off = np.array([math.cos(p) * math.cos(y), math.cos(p) * math.sin(y), math.sin(p)])
        return self.target + off * self.dist

    def view_matrix(self):
        return _look_at(self.eye(), self.target, np.array([0.0, 0.0, 1.0]))

    def resizeGL(self, w, h):
        self.resized.emit()

    def paintGL(self):
        if self.prog is None:
            gl.glClearColor(0.1, 0.1, 0.1, 1)
            gl.glClear(gl.GL_COLOR_BUFFER_BIT)
            return
        try:
            self._paint()
        except Exception as exc:  # pragma: no cover
            self._gl_error = str(exc)

    def _set_colouring(self):
        L = self._loc
        gl.glUniform1i(L["u_colmode"], self.colmode)
        bands = self.bands[:MAX_BANDS]
        bz = np.zeros(MAX_BANDS, dtype=np.float32)
        bc = np.zeros((MAX_BANDS, 3), dtype=np.float32)
        for i, (z, c) in enumerate(bands):
            bz[i], bc[i] = z, c
        gl.glUniform1fv(L["u_bz"], MAX_BANDS, bz)
        gl.glUniform3fv(L["u_bc"], MAX_BANDS, bc)
        gl.glUniform1i(L["u_nb"], len(bands))
        gc = np.zeros((4, 3), dtype=np.float32)
        for i, c in enumerate(self.gradient[:4]):
            gc[i] = c
        gl.glUniform3fv(L["u_gc"], 4, gc)
        gl.glUniform1i(L["u_ng"], max(1, min(len(self.gradient), 4)))
        gl.glUniform1f(L["u_limit"], float(self.limit))
        gl.glUniform1i(L["u_look"], int(self.look))

    def _paint(self):
        if self._stale_vbos:
            gl.glDeleteBuffers(len(self._stale_vbos), self._stale_vbos)
            self._stale_vbos.clear()
        w, h = max(self.width(), 1), max(self.height(), 1)
        dpr = self.devicePixelRatioF()
        gl.glClearColor(*self.BG_BOT, 1.0)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
        gl.glUseProgram(self.prog)
        L = self._loc

        # background gradient
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glDisable(gl.GL_CULL_FACE)
        eye4 = np.identity(4)
        self._mat("u_model", eye4)
        self._mat("u_view", eye4)
        self._mat("u_proj", eye4)
        gl.glUniform1i(L["u_mode"], 2)
        gl.glUniform1i(L["u_clip"], 0)
        gl.glUniform1i(L["u_cut"], 0)
        gl.glUniform3f(L["u_bg_top"], *self.BG_TOP)
        gl.glUniform3f(L["u_bg_bot"], *self.BG_BOT)
        gl.glUniform1f(L["u_vh"], h * dpr)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self._quad_vbo)
        gl.glEnableVertexAttribArray(0)
        gl.glVertexAttribPointer(0, 3, gl.GL_FLOAT, gl.GL_FALSE, 12, ctypes.c_void_p(0))
        gl.glDisableVertexAttribArray(1)
        gl.glDisableVertexAttribArray(2)
        gl.glVertexAttrib3f(1, 0.0, 0.0, 1.0)
        gl.glVertexAttrib2f(2, 0.0, 0.0)
        gl.glDrawArrays(gl.GL_TRIANGLES, 0, 6)

        gl.glEnable(gl.GL_DEPTH_TEST)
        gl.glDepthFunc(gl.GL_LEQUAL)
        lo, hi = self.scene_bounds()
        size = float(np.linalg.norm(hi - lo))
        reach = size + (math.hypot(self.bed[0], self.bed[1]) + self.bed[2] if self.show_bed else 0.0)
        near = max(self.dist - reach, self.dist * 0.01, 0.5)
        proj = _perspective(self.fov, w / h, near, self.dist + reach + 10.0)
        self._mat("u_view", self.view_matrix())
        self._mat("u_proj", proj)
        # the section cuts away the half nearer the camera, through the axis
        e = self.eye()
        toward = np.array([e[0] - self.target[0], e[1] - self.target[1]])
        if np.linalg.norm(toward) < 1e-6:
            toward = np.array([0.0, -1.0])
        toward /= np.linalg.norm(toward)
        gl.glUniform4f(L["u_plane"], float(toward[0]), float(toward[1]), 0.0, 0.0)

        if self.show_bed:                 # printer bed: grid, outline, and the space it prints in
            self._ensure_grid()
            self._mat("u_model", eye4)
            gl.glUniform1i(L["u_mode"], 0)
            gl.glUniform1f(L["u_alpha"], 1.0)
            gl.glUniform3f(L["u_color"], 0.27, 0.30, 0.35)
            gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.grid_vbo)
            gl.glVertexAttribPointer(0, 3, gl.GL_FLOAT, gl.GL_FALSE, 12, ctypes.c_void_p(0))
            gl.glDrawArrays(gl.GL_LINES, 0, self.grid_count)
            gl.glUniform3f(L["u_color"], 0.42, 0.47, 0.55)
            gl.glDrawArrays(gl.GL_LINES, self.grid_count, self.box_count)

        gl.glUniform1i(L["u_mode"], 1)
        gl.glUniform1i(L["u_clip"], 1 if self.section else 0)
        gl.glUniform1i(L["u_cut"], 1 if self.cut_z is not None else 0)
        gl.glUniform1f(L["u_cutz"], float(self.cut_z or 0.0))
        self._set_colouring()
        gl.glEnableVertexAttribArray(1)
        gl.glEnableVertexAttribArray(2)
        self._mat("u_model", self.model)
        clear = self.look == 3 and self.colmode != 3 and not self.section
        if clear:
            gl.glEnable(gl.GL_BLEND)
            gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
            gl.glDepthMask(gl.GL_FALSE)
            gl.glEnable(gl.GL_CULL_FACE)
            for face in (gl.GL_FRONT, gl.GL_BACK):
                gl.glCullFace(face)
                for m in self.meshes.values():
                    self._draw(m)
            gl.glDepthMask(gl.GL_TRUE)
            gl.glDisable(gl.GL_BLEND)
        else:
            if self.section or self.cut_z is not None:
                gl.glDisable(gl.GL_CULL_FACE)
            else:
                gl.glEnable(gl.GL_CULL_FACE)
                gl.glCullFace(gl.GL_BACK)
            for m in self.meshes.values():
                self._draw(m)
        gl.glDisable(gl.GL_CULL_FACE)
        gl.glDisableVertexAttribArray(1)
        gl.glDisableVertexAttribArray(2)

        if self.section and self._cut_src is not None:      # the printed wall, cut through
            n_obj = self.model[:3, :3].T @ np.array([toward[0], toward[1], 0.0])
            key = tuple(np.round(n_obj, 4))
            if key != self._cut_key or self._cut_vbo is None:
                dist = self._cut_src @ n_obj.astype(np.float32)
                seg = plane_cut(self._cut_src, dist).astype(np.float32).reshape(-1, 3)
                if self._cut_vbo is None:
                    self._cut_vbo = gl.glGenBuffers(1)
                gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self._cut_vbo)
                gl.glBufferData(gl.GL_ARRAY_BUFFER, max(seg.nbytes, 12), seg if len(seg) else
                                np.zeros(3, np.float32), gl.GL_DYNAMIC_DRAW)
                self._cut_count = len(seg)
                self._cut_key = key
            if self._cut_count:
                gl.glDisable(gl.GL_DEPTH_TEST)
                gl.glUniform1i(L["u_mode"], 0)
                gl.glUniform1i(L["u_clip"], 0)
                gl.glUniform1i(L["u_cut"], 1 if self.cut_z is not None else 0)
                gl.glUniform1f(L["u_alpha"], 1.0)
                gl.glUniform3f(L["u_color"], 1.0, 0.85, 0.35)
                gl.glLineWidth(2.5)
                gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self._cut_vbo)
                gl.glVertexAttribPointer(0, 3, gl.GL_FLOAT, gl.GL_FALSE, 12, ctypes.c_void_p(0))
                gl.glDrawArrays(gl.GL_LINES, 0, self._cut_count)
                gl.glLineWidth(1.0)
                gl.glEnable(gl.GL_DEPTH_TEST)

        if self.lines is not None:        # the nozzle's path round the current layer
            if self._lines_dirty or self._lines_vbo is None:
                if self._lines_vbo is None:
                    self._lines_vbo = gl.glGenBuffers(1)
                gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self._lines_vbo)
                gl.glBufferData(gl.GL_ARRAY_BUFFER, self.lines[0].nbytes, self.lines[0], gl.GL_DYNAMIC_DRAW)
                self._lines_dirty = False
            gl.glDisable(gl.GL_DEPTH_TEST)
            gl.glUniform1i(L["u_mode"], 0)
            gl.glUniform1i(L["u_cut"], 0)
            gl.glUniform1i(L["u_clip"], 1 if self.section else 0)
            gl.glUniform1f(L["u_alpha"], 1.0)
            gl.glUniform3f(L["u_color"], *self.lines[1])
            gl.glLineWidth(2.0)
            gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self._lines_vbo)
            gl.glVertexAttribPointer(0, 3, gl.GL_FLOAT, gl.GL_FALSE, 12, ctypes.c_void_p(0))
            gl.glDrawArrays(gl.GL_LINES, 0, len(self.lines[0]))
            gl.glLineWidth(1.0)
            gl.glEnable(gl.GL_DEPTH_TEST)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, 0)
        gl.glUseProgram(0)

    def _draw(self, m: _Mesh):
        if m.vbo is None:
            self._upload(m)
        L = self._loc
        gl.glUniform3f(L["u_color"], *m.color)
        gl.glUniform1f(L["u_alpha"], 1.0)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, m.vbo)
        gl.glVertexAttribPointer(0, 3, gl.GL_FLOAT, gl.GL_FALSE, 32, ctypes.c_void_p(0))
        gl.glVertexAttribPointer(1, 3, gl.GL_FLOAT, gl.GL_FALSE, 32, ctypes.c_void_p(12))
        gl.glVertexAttribPointer(2, 2, gl.GL_FLOAT, gl.GL_FALSE, 32, ctypes.c_void_p(24))
        gl.glDrawArrays(gl.GL_TRIANGLES, 0, m.count)

    # ------------------------------------------------------------- mouse
    def mousePressEvent(self, ev):
        self._last = ev.position()

    def mouseMoveEvent(self, ev):
        if self._last is None:
            self._last = ev.position()
            return
        d: QPointF = ev.position() - self._last
        self._last = ev.position()
        if ev.buttons() & Qt.LeftButton and not (ev.modifiers() & Qt.ShiftModifier):
            self.yaw -= d.x() * 0.4
            self.pitch = max(-89.0, min(89.0, self.pitch + d.y() * 0.4))
        elif ev.buttons() & (Qt.RightButton | Qt.MiddleButton | Qt.LeftButton):
            v = self.view_matrix()
            right, up = v[0, :3], v[1, :3]
            k = self.dist * 2.0 * math.tan(math.radians(self.fov) / 2.0) / max(self.height(), 1)
            self.target = self.target - right * d.x() * k + up * d.y() * k
        self.dragged.emit()
        self.update()

    def mouseReleaseEvent(self, ev):
        self._last = None

    def mouseDoubleClickEvent(self, ev):
        self.reset_requested.emit()

    def wheelEvent(self, ev):
        steps = ev.angleDelta().y() / 120.0
        self.dist = max(5.0, min(20000.0, self.dist * (0.88 ** steps)))
        self.dragged.emit()
        self.update()

    def keyPressEvent(self, ev):
        k = ev.key()
        if k == Qt.Key_Left:
            self.yaw += 5
        elif k == Qt.Key_Right:
            self.yaw -= 5
        elif k == Qt.Key_Up:
            self.pitch = min(89.0, self.pitch + 5)
        elif k == Qt.Key_Down:
            self.pitch = max(-89.0, self.pitch - 5)
        elif k in (Qt.Key_Plus, Qt.Key_Equal):
            self.dist *= 0.9
        elif k == Qt.Key_Minus:
            self.dist /= 0.9
        elif k in (Qt.Key_Home, Qt.Key_F):
            self.reset_requested.emit()
            return
        else:
            super().keyPressEvent(ev)
            return
        self.dragged.emit()
        self.update()
