"""Your own function: a formula typed in the app, added to the vase's radius.

The formula is parsed, checked against a short list of allowed names and
operators, and only then evaluated with numpy over the whole surface at once.
Nothing else can be reached from it: no attributes, no imports, no built-ins.
"""

from __future__ import annotations

import ast
import math

import numpy as np

MAX_LENGTH = 800

VARIABLES = {
    "theta": "angle round the vase, 0 to 2·pi (radians)",
    "phi": "the same angle, turning with the twist",
    "z": "height above the bed (mm)",
    "h": "height as a share of the vase: 0 at the bottom, 1 at the top",
    "r": "the radius so far, before this function (mm)",
    "H": "the vase's height (mm)",
}
CONSTANTS = {"pi": math.pi, "tau": 2.0 * math.pi, "e": math.e}


def _smoothstep(edge0, edge1, x):
    t = np.clip((np.asarray(x, dtype=float) - edge0) / np.where(edge1 == edge0, 1e-9, edge1 - edge0), 0, 1)
    return t * t * (3.0 - 2.0 * t)


def _hash(ix, iy, iz):
    """A repeatable random number in -1..1 for each whole-number lattice point."""
    h = (ix.astype(np.uint64) * np.uint64(0x9E3779B1) ^ iy.astype(np.uint64) * np.uint64(0x85EBCA77)
         ^ iz.astype(np.uint64) * np.uint64(0xC2B2AE3D))
    h ^= h >> np.uint64(15)
    h *= np.uint64(0x2C1B3C6D)
    h ^= h >> np.uint64(12)
    h *= np.uint64(0x297A2D39)
    h ^= h >> np.uint64(15)
    return (h & np.uint64(0xFFFFFF)).astype(np.float64) / float(0xFFFFFF) * 2.0 - 1.0


def _noise(x, y=0.0, z=0.0):
    """Smooth value noise, about -1..1, changing over a distance of about 1."""
    x, y, z = np.broadcast_arrays(*(np.asarray(v, dtype=float) for v in (x, y, z)))
    fx, fy, fz = np.floor(x), np.floor(y), np.floor(z)
    tx, ty, tz = (_smoothstep(0.0, 1.0, t) for t in (x - fx, y - fy, z - fz))
    ix, iy, iz = (f.astype(np.int64) for f in (fx, fy, fz))
    out = np.zeros(x.shape)
    for dx in (0, 1):
        wx = tx if dx else 1 - tx
        for dy in (0, 1):
            wy = ty if dy else 1 - ty
            for dz in (0, 1):
                wz = tz if dz else 1 - tz
                out += wx * wy * wz * _hash(ix + dx, iy + dy, iz + dz)
    return out


FUNCTIONS = {
    "sin": np.sin, "cos": np.cos, "tan": np.tan, "asin": np.arcsin, "acos": np.arccos, "atan": np.arctan,
    "atan2": np.arctan2, "sinh": np.sinh, "cosh": np.cosh, "tanh": np.tanh, "sqrt": np.sqrt, "exp": np.exp,
    "log": np.log, "log10": np.log10, "abs": np.abs, "floor": np.floor, "ceil": np.ceil, "round": np.round,
    "sign": np.sign, "min": np.minimum, "max": np.maximum, "clip": np.clip, "mod": np.mod, "hypot": np.hypot,
    "pow": np.power, "where": np.where,
    "smoothstep": _smoothstep,
    "step": lambda edge, x: (np.asarray(x) >= edge).astype(float),
    "lerp": lambda a, b, t: a + (b - a) * t,
    "tri": lambda x: (2.0 / math.pi) * np.arcsin(np.sin(x)),                  # triangle wave, -1..1
    "saw": lambda x: 2.0 * np.mod(np.asarray(x) / (2.0 * math.pi), 1.0) - 1.0,  # sawtooth, -1..1
    "square": lambda x: np.sign(np.sin(x)),                                     # square wave, -1 or 1
    "noise": _noise,
}

FUNCTION_HELP = [
    ("sin cos tan asin acos atan atan2 sinh cosh tanh", "trigonometry, in radians"),
    ("sqrt exp log log10 abs sign pow hypot", "the usual"),
    ("floor ceil round mod", "whole numbers and remainders"),
    ("min(a, b)  max(a, b)  clip(x, lo, hi)", "limits"),
    ("where(cond, a, b)", "a where the condition holds, b elsewhere (use < > <= >=)"),
    ("smoothstep(e0, e1, x)  step(e, x)  lerp(a, b, t)", "soft and hard steps, blends"),
    ("tri(x)  saw(x)  square(x)", "triangle, sawtooth and square waves, period 2·pi, -1..1"),
    ("noise(x, y, z)", "smooth random value, -1..1, changing over about 1 unit"),
]

EXAMPLES = [
    ("Waves winding round", "1.5 * sin(6*theta + 4*pi*h)"),
    ("Bubbles", "2 * max(sin(9*phi) * sin(pi*z/9), 0)**2"),
    ("Scales", "1.4 * abs(sin(10*phi + pi*floor(z/7))) * smoothstep(0, 1, mod(z, 7)/2)"),
    ("Bark", "1.8 * noise(5*cos(theta), 5*sin(theta), z/14) + 0.6*noise(14*cos(theta), 14*sin(theta), z/4)"),
    ("Swelling pulse", "4 * sin(pi*h)**8 * (0.5 + 0.5*cos(5*phi))"),
    ("Zigzag ribs", "1.2 * tri(12*theta + 3*tri(2*pi*z/25))"),
    ("Pinch at the waist", "-0.12 * r * exp(-((h - 0.5)/0.12)**2)"),
    ("Terraces", "-0.9 * smoothstep(0.55, 1, mod(z, 9)/9)"),
]

_ALLOWED_NODES = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Call, ast.Name, ast.Load, ast.Constant,
                  ast.Compare, ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.Mod, ast.FloorDiv,
                  ast.USub, ast.UAdd, ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.Eq, ast.NotEq)


class ExprError(ValueError):
    """The formula can't be used; the message says why, in plain words."""


class _Floats(ast.NodeTransformer):
    """Every number becomes a float, so a power like 9**9**9 overflows at once instead of hanging."""

    def visit_Constant(self, node):
        return ast.copy_location(ast.Constant(float(node.value)), node)


def compile_expression(text: str):
    """Check a formula and return a function of the variables, or raise ExprError."""
    text = text.strip()
    if not text:
        return None
    if len(text) > MAX_LENGTH:
        raise ExprError(f"The function is longer than {MAX_LENGTH} characters.")
    try:
        tree = ast.parse(text, mode="eval")
    except SyntaxError as exc:
        raise ExprError(f"The function doesn't read as a formula (near character {exc.offset or 0}).") \
            from None
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_NODES):
            raise ExprError(f"“{type(node).__name__}” isn't allowed in a function: use numbers, "
                            "the variables, + - * / ** % and the listed functions.")
        if isinstance(node, ast.Constant) and (isinstance(node.value, bool)
                                               or not isinstance(node.value, (int, float))):
            raise ExprError("Only numbers can be written in a function.")
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in FUNCTIONS:
                name = node.func.id if isinstance(node.func, ast.Name) else "that"
                raise ExprError(f"There is no function called “{name}”.")
            if node.keywords:
                raise ExprError("Give a function's values in order, without names.")
        if isinstance(node, ast.Name) and node.id not in VARIABLES and node.id not in CONSTANTS \
                and node.id not in FUNCTIONS:
            raise ExprError(f"“{node.id}” isn't a variable: use theta, phi, z, h, r or H.")
    tree = ast.fix_missing_locations(_Floats().visit(tree))
    code = compile(tree, "<your function>", "eval")

    def run(**env):
        shape = np.broadcast(*env.values()).shape
        scope = {"__builtins__": {}}
        names = {**FUNCTIONS, **CONSTANTS, **env}
        try:
            with np.errstate(all="ignore"):
                value = eval(code, scope, names)  # noqa: S307 - checked above: names and numbers only
        except OverflowError:
            raise ExprError("The function gives numbers too big to use.") from None
        except (TypeError, ValueError, ZeroDivisionError) as exc:
            raise ExprError(f"The function can't be worked out: {exc}.") from None
        value = np.broadcast_to(np.asarray(value, dtype=float), shape).astype(float)
        if not np.isfinite(value).all():
            raise ExprError("The function gives no number at some points (dividing by zero, the "
                            "square root or log of a negative number, or numbers too big).")
        return value

    return run
