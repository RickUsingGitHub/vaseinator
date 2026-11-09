"""Shared feature and export regression tests: python -m unittest tests.test_workspace."""

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from vaseinator.params import VaseParams, clean_curve
from vaseinator.presets import plain_design
from vaseinator.geometry import VaseDesign, edge_check, mesh_volume, require_exportable
from vaseinator.workspace import (
    Workspace,
    LOCKS,
    locked_surprise,
    comparison,
    calibration_parts,
)
from vaseinator.threemf import write_3mf, read_3mf
from web import bridge


class WorkspaceTests(unittest.TestCase):
    def test_bad_numbers(self):
        for values in (
            {"height": "NaN"},
            {"height": "Infinity"},
            {"count1": float("inf")},
        ):
            with self.subTest(values=values), self.assertRaises(ValueError):
                VaseParams.from_dict(values)
        self.assertIsNone(clean_curve([[0, 2], [1, float("nan")]]))

    def test_export_gate(self):
        for design in (
            SimpleNamespace(errors=["bad"], closed=True),
            SimpleNamespace(errors=[], closed=False),
        ):
            with self.assertRaises(ValueError):
                require_exportable(design)

    def test_export_gate_in_browser(self):
        from unittest.mock import patch

        with patch.object(
            bridge, "VaseDesign", return_value=SimpleNamespace(errors=[], closed=False)
        ):
            for export in (bridge.export_stl, bridge.export_3mf, bridge.export_lid):
                with self.assertRaises(ValueError):
                    export("{}")

    def test_locks_and_bridge_parity(self):
        p = VaseParams(height=123, line_width=0.8)
        for group, keys in LOCKS.items():
            q = locked_surprise(p, 42, [group])
            for key in keys:
                self.assertEqual(getattr(p, key), getattr(q, key))
            self.assertEqual(q.line_width, 0.8)
        q = locked_surprise(p, 42, ["Dimensions"])
        self.assertAlmostEqual(
            max(v for _, v in q.silhouette), max(v for _, v in p.silhouette)
        )
        q = locked_surprise(p, 42, list(LOCKS))
        self.assertEqual(
            q.to_dict(),
            json.loads(
                bridge.surprise_me(json.dumps(p.to_dict()), 42, json.dumps(list(LOCKS)))
            ),
        )

    def test_library_roundtrip_profiles_favourites_and_recovery(self):
        w = Workspace()
        p = VaseParams(name="My variant", height=140, line_width=0.8, density=1.27)
        entry = w.add("designs", p)
        w.command("favorite", p, {"id": entry["id"]})
        printer = w.add("profiles", p, "Printer", kind="printer")
        material = w.add("profiles", p, "PETG", kind="material")
        base = VaseParams(height=99, density=1.1)
        q = w.apply_profile(base, printer["id"])
        self.assertEqual(q.height, 99)
        self.assertEqual(q.line_width, 0.8)
        self.assertEqual(q.density, 1.1)
        q = w.apply_profile(base, material["id"])
        self.assertEqual(q.density, 1.27)
        self.assertEqual(q.line_width, base.line_width)
        for n in range(35):
            w.add("recovery", VaseParams(height=100 + n))
        w.add("recovery", VaseParams(height=134))
        self.assertEqual(len(w.data["recovery"]), 30)
        restored = Workspace(json.loads(w.dumps()))
        self.assertEqual(restored.data, w.data)
        restored.merge(w.data)
        self.assertEqual(restored.data, w.data)
        result = json.loads(
            bridge.workspace_action(
                w.dumps(),
                json.dumps(base.to_dict()),
                "restore",
                json.dumps({"category": "designs", "id": entry["id"]}),
            )
        )
        self.assertEqual(result["params"], p.to_dict())
        self.assertTrue(result["workspace"]["designs"][0]["favorite"])
        with self.assertRaises(ValueError):
            Workspace({"format": "other"})

    def test_malformed_libraries_are_reported(self):
        good = Workspace().data
        p = plain_design().to_dict()
        for bad in (
            {**good, "locks": None},
            {**good, "locks": [[1]]},
            {**good, "profiles": [{"params": p, "kind": []}]},
            {**good, "designs": [{"params": p, "name": {}}]},
            {**good, "designs": [{"params": p, "favorite": "yes"}]},
        ):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                Workspace(bad)
        # missing or empty fields are fine: they take their usual values
        w = Workspace({**good, "designs": [{"params": p, "id": None, "name": None}]})
        self.assertEqual(w.data["designs"][0]["name"], "plain_cylinder")
        for payload in ({"locks": None}, {"locks": [["Colours"]]}):
            with self.assertRaises(ValueError):
                w.command("locks", plain_design(), payload)
        with self.assertRaises(ValueError):
            w.add("profiles", plain_design(), kind="nozzle")
        # and the browser reports them the same way
        with self.assertRaises(ValueError):
            bridge.workspace_action("", json.dumps(p), "import", json.dumps({**good, "locks": None}))

    def test_renaming_keeps_one_recovery_place(self):
        w = Workspace()
        first = VaseParams(height=120)
        w.add("recovery", first)
        q = VaseParams(height=150)
        for n in range(1, 40):                       # typing a long name, a letter at a time
            q = q.copy()
            q.name = "a long name for a vase"[:n]
            w.add("recovery", q)
        self.assertEqual([e["params"]["height"] for e in w.data["recovery"]], [120, 150])
        self.assertEqual(w.data["recovery"][-1]["name"], "a long name for a vase")

    def test_comparison_and_calibration(self):
        p = plain_design()
        p.facet_size = 2
        d = VaseDesign(p)
        data = comparison(d)
        self.assertEqual(data["moved"], 0)
        self.assertIn("<svg", data["svg"])
        parts = calibration_parts()
        self.assertEqual(len(parts), 10)
        for _, v, f, _, _ in parts:
            self.assertTrue(edge_check(f)[0])
            self.assertGreater(mesh_volume(v, f), 0)
            self.assertTrue(np.isfinite(v).all())
        for k in range(5):
            v = parts[2 * k][1]
            inner = v[192:288].copy()
            inner[:, 0] -= (k - 2) * 19
            self.assertTrue(
                np.allclose(np.linalg.norm(inner[:, :2], axis=1), 5 + 0.1 * (k + 1))
            )
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "samples.3mf")
            write_3mf(path, "samples", parts)
            self.assertEqual(len(read_3mf(path)), 10)


if __name__ == "__main__":
    unittest.main()
