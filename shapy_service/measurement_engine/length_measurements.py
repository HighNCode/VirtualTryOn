from typing import Dict, Optional

import numpy as np

from .joints import joint


def _segment_cm(joints_xyz: np.ndarray, index_by_name: Dict[str, int], a: str, b: str) -> float:
    return float(np.linalg.norm(joint(joints_xyz, index_by_name, a) - joint(joints_xyz, index_by_name, b)) * 100.0)


def compute_length_measurements(
    joints_xyz: np.ndarray,
    index_by_name: Dict[str, int],
    height_cm: float,
) -> Dict[str, Optional[float]]:
    return {
        "height": round(float(height_cm), 1),
        "shoulder_width": round(_segment_cm(joints_xyz, index_by_name, "left_shoulder", "right_shoulder"), 1),
        "arm_length": round(
            _segment_cm(joints_xyz, index_by_name, "left_shoulder", "left_elbow")
            + _segment_cm(joints_xyz, index_by_name, "left_elbow", "left_wrist"),
            1,
        ),
        "torso_length": round(_segment_cm(joints_xyz, index_by_name, "neck", "pelvis"), 1),
        "inseam": round(_segment_cm(joints_xyz, index_by_name, "left_hip", "left_ankle"), 1),
    }
