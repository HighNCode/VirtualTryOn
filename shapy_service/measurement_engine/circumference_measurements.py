from typing import Any, Dict, Optional, Sequence, Tuple

import numpy as np

from .joints import joint
from .section_utils import slice_circumference_cm


def _mirror_joint_name(name: str) -> str:
    if name.startswith("left_"):
        return "right_" + name[len("left_"):]
    if name.startswith("right_"):
        return "left_" + name[len("right_"):]
    return name


def _norm(v: np.ndarray) -> np.ndarray:
    return v / (np.linalg.norm(v) + 1e-9)


def _upper_arm_attempts(
    verts: np.ndarray,
    faces: np.ndarray,
    shoulder: np.ndarray,
    elbow: np.ndarray,
    body_parts: Optional[Sequence[str]],
    face_segmentation: Optional[Dict[str, Any]],
    attempts: Sequence[float],
) -> Tuple[Optional[float], Dict[str, Any]]:
    axis = elbow - shoulder
    axis_n = _norm(axis)
    base = shoulder + 0.45 * axis

    best = {"failure_reason": "no_attempts"}
    for i, shift in enumerate(attempts):
        origin = base + (axis_n * float(shift))
        out = slice_circumference_cm(
            vertices=verts,
            faces=faces,
            plane_origin=origin,
            plane_normal=axis_n,
            target_point=base,
            body_parts=body_parts,
            face_segmentation=face_segmentation,
        )
        out["attempt_index"] = i
        out["attempt_shift_m"] = float(shift)
        if out.get("value_cm") is not None:
            return float(out["value_cm"]), out
        best = out
    return None, best


def compute_upper_arm_metric(
    verts_xyz: np.ndarray,
    faces: np.ndarray,
    joints_xyz: np.ndarray,
    index_by_name: Dict[str, int],
    face_segmentation: Optional[Dict[str, Any]],
) -> Tuple[Optional[float], Dict[str, Any]]:
    left_sh = joint(joints_xyz, index_by_name, "left_shoulder")
    left_el = joint(joints_xyz, index_by_name, "left_elbow")

    value, d = _upper_arm_attempts(
        verts=verts_xyz,
        faces=faces,
        shoulder=left_sh,
        elbow=left_el,
        body_parts=["leftArm"],
        face_segmentation=face_segmentation,
        attempts=(0.0, 0.01, -0.01),
    )
    fallback = None

    if value is None:
        right_sh = joint(joints_xyz, index_by_name, _mirror_joint_name("left_shoulder"))
        right_el = joint(joints_xyz, index_by_name, _mirror_joint_name("left_elbow"))
        value_r, d_r = _upper_arm_attempts(
            verts=verts_xyz,
            faces=faces,
            shoulder=right_sh,
            elbow=right_el,
            body_parts=["rightArm"],
            face_segmentation=face_segmentation,
            attempts=(0.0, 0.01, -0.01),
        )
        if value_r is not None:
            value = value_r
            d = d_r
            fallback = "mirror_side"

    return (
        None if value is None else round(float(value), 1),
        {
            "source": "trimesh_custom",
            "loop_count": d.get("loop_count"),
            "selected_loop_length_cm": d.get("selected_loop_length_cm"),
            "attempt_index": d.get("attempt_index"),
            "attempt_shift_m": d.get("attempt_shift_m"),
            "failure_reason": d.get("failure_reason"),
            "fallback_path": fallback,
            "quality_score": 1.0 if value is not None else 0.0,
        },
    )
