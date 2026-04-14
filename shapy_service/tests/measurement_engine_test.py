import unittest

import numpy as np

from measurement_engine.geometry import robust_perimeter
from measurement_engine.joints import build_joint_index, validate_required_joints
from measurement_engine.section_utils import slice_circumference_cm


class MeasurementEngineTests(unittest.TestCase):
    def test_name_to_index_resolver(self):
        names = ["pelvis", "left_shoulder", "right_shoulder"]
        idx = build_joint_index(names)
        self.assertEqual(idx["left_shoulder"], 1)
        self.assertEqual(validate_required_joints(idx, ["pelvis"]), [])
        self.assertEqual(validate_required_joints(idx, ["neck"]), ["neck"])

    def test_perimeter_fallback(self):
        pts = np.array([[0.0, 0.0], [1.0, 0.0], [0.6, 0.7], [0.1, 0.8]], dtype=np.float64)
        value, meta = robust_perimeter(pts)
        self.assertIsNotNone(value)
        self.assertIn(meta["method"], {"ellipse", "hull"})

    def test_mesh_plane_circle_section(self):
        try:
            import trimesh
            import shapely  # noqa: F401
        except Exception:
            self.skipTest("trimesh/shapely unavailable in this environment")
        mesh = trimesh.creation.cylinder(radius=0.2, height=1.0, sections=64)
        out = slice_circumference_cm(
            vertices=np.asarray(mesh.vertices),
            faces=np.asarray(mesh.faces),
            plane_origin=np.array([0.0, 0.0, 0.0]),
            plane_normal=np.array([0.0, 1.0, 0.0]),
            target_point=np.array([0.0, 0.0, 0.0]),
        )
        self.assertIsNotNone(out["value_cm"])
        # Expected ~ 2*pi*r = 1.2566m = 125.66cm
        self.assertGreater(out["value_cm"], 118.0)
        self.assertLess(out["value_cm"], 133.0)


if __name__ == "__main__":
    unittest.main()
