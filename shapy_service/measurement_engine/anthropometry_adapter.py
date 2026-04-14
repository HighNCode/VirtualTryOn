import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Sequence, Tuple

import numpy as np

from .joints import joint
from .section_utils import slice_circumference_cm


def _anthro_path() -> Path:
    explicit = os.environ.get("SMPL_ANTHROPOMETRY_PATH")
    if explicit:
        return Path(explicit)
    root = Path(__file__).resolve().parents[2]
    return root.parent / "backend" / "libs" / "smpl_anthropometry"


def _import_defs() -> Dict[str, Any]:
    path = _anthro_path()
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
    from landmark_definitions import SMPLX_LANDMARK_INDICES  # type: ignore
    from measurement_definitions import SMPLXMeasurementDefinitions  # type: ignore

    defs = SMPLXMeasurementDefinitions()
    return {
        "landmarks": SMPLX_LANDMARK_INDICES,
        "lengths": defs.LENGTHS,
        "circumferences": defs.CIRCUMFERENCES,
        "circumf_2_bodypart": defs.CIRCUMFERENCE_TO_BODYPARTS,
        "possible": defs.possible_measurements,
    }


def _load_face_segmentation() -> Dict[str, Sequence[int]]:
    seg_path = _anthro_path() / "data" / "smplx" / "smplx_body_parts_2_faces.json"
    if not seg_path.exists():
        return {}
    return json.loads(seg_path.read_text(encoding="utf-8"))


def _length_from_landmarks_cm(verts: np.ndarray, idx_a: Any, idx_b: Any) -> float:
    def point(i: Any) -> np.ndarray:
        if isinstance(i, tuple):
            return (verts[int(i[0])] + verts[int(i[1])]) / 2.0
        return verts[int(i)]

    p1 = point(idx_a)
    p2 = point(idx_b)
    return float(np.linalg.norm(p1 - p2) * 100.0)


def _torso_c7_to_waist_cm(verts: np.ndarray, landmarks: Dict[str, int]) -> Optional[float]:
    """
    Approximate torso length as upper-back (shoulder top ~ C7 proxy) to waist center.
    """
    required = ("SHOULDER_TOP", "BELLY_BUTTON", "BACK_BELLY_BUTTON")
    if any(k not in landmarks for k in required):
        return None
    c7_proxy = verts[int(landmarks["SHOULDER_TOP"])]
    waist_front = verts[int(landmarks["BELLY_BUTTON"])]
    waist_back = verts[int(landmarks["BACK_BELLY_BUTTON"])]
    waist_center = (waist_front + waist_back) / 2.0
    return float(np.linalg.norm(c7_proxy - waist_center) * 100.0)


def _body_parts_for_metric(metric_name: str, mapping: Dict[str, Any]) -> Optional[Sequence[str]]:
    value = mapping.get(metric_name)
    if value is None:
        return None
    if isinstance(value, list):
        return value
    return [value]


def _mirror_token(name: str) -> str:
    swaps = [
        ("left_", "__TMP__"),
        ("right_", "left_"),
        ("__TMP__", "right_"),
        ("LEFT_", "__TMP2__"),
        ("RIGHT_", "LEFT_"),
        ("__TMP2__", "RIGHT_"),
        ("left", "__TMP3__"),
        ("right", "left"),
        ("__TMP3__", "right"),
        ("Left", "__TMP4__"),
        ("Right", "Left"),
        ("__TMP4__", "Right"),
    ]
    out = name
    for a, b in swaps:
        out = out.replace(a, b)
    return out


def _mirror_bodypart_mapping(mapping: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for k, v in mapping.items():
        mk = _mirror_token(k)
        if isinstance(v, list):
            out[mk] = [_mirror_token(x) for x in v]
        elif isinstance(v, str):
            out[mk] = _mirror_token(v)
        else:
            out[mk] = v
    return out


def _circumference_from_definition_cm(
    metric_name: str,
    definition: Dict[str, Any],
    verts: np.ndarray,
    faces: np.ndarray,
    joints_xyz: np.ndarray,
    joint_index: Dict[str, int],
    landmarks: Dict[str, int],
    circumf_2_bodypart: Dict[str, Any],
    face_segmentation: Dict[str, Sequence[int]],
    plane_shift_dir: Optional[np.ndarray] = None,
    attempts: Sequence[float] = (0.0,),
) -> Tuple[Optional[float], Dict[str, Any]]:
    lms = definition["LANDMARKS"]
    lm_ids = [landmarks[n] for n in lms]
    plane_origin = np.mean(verts[lm_ids, :], axis=0)
    j1_name, j2_name = definition["JOINTS"]
    n = joint(joints_xyz, joint_index, j1_name) - joint(joints_xyz, joint_index, j2_name)
    n_norm = float(np.linalg.norm(n))
    if n_norm <= 1e-9:
        return None, {"failure_reason": "invalid_plane_normal"}
    plane_normal = n / n_norm
    shift_dir = plane_shift_dir if plane_shift_dir is not None else plane_normal
    shift_dir = shift_dir / (np.linalg.norm(shift_dir) + 1e-9)

    best_diag = {"failure_reason": "no_attempts"}
    body_parts = _body_parts_for_metric(metric_name, circumf_2_bodypart)
    target = plane_origin
    metric_lower = metric_name.lower()
    allow_filter_relax = ("hip circumference" in metric_lower) or ("ankle" in metric_lower)
    for i, shift in enumerate(attempts):
        origin = plane_origin + (shift_dir * float(shift))
        out = slice_circumference_cm(
            vertices=verts,
            faces=faces,
            plane_origin=origin,
            plane_normal=plane_normal,
            target_point=target,
            body_parts=body_parts,
            face_segmentation=face_segmentation,
            allow_filter_relax=allow_filter_relax,
        )
        out["attempt_index"] = i
        out["attempt_shift_m"] = float(shift)
        if out.get("value_cm") is not None:
            return float(out["value_cm"]), out
        best_diag = out
    return None, best_diag


def compute_anthropometry_metrics(
    verts: np.ndarray,
    faces: np.ndarray,
    joints_xyz: np.ndarray,
    joint_index: Dict[str, int],
) -> Tuple[Dict[str, Optional[float]], Dict[str, Dict[str, Any]]]:
    defs = _import_defs()
    landmarks = defs["landmarks"]
    lengths = defs["lengths"]
    circumf = defs["circumferences"]
    circumf_2_bodypart = defs["circumf_2_bodypart"]
    face_segmentation = _load_face_segmentation()

    out: Dict[str, Optional[float]] = {}
    diag: Dict[str, Dict[str, Any]] = {}

    for m_name, lm_pair in lengths.items():
        if not isinstance(lm_pair, tuple) or len(lm_pair) < 2:
            continue
        value = _length_from_landmarks_cm(verts, lm_pair[0], lm_pair[1])
        out[m_name] = round(value, 1)
        diag[m_name] = {
            "source": "anthropometry",
            "measurement_type": "length",
            "quality_score": 1.0,
        }

    torso_custom = _torso_c7_to_waist_cm(verts, landmarks)
    if torso_custom is not None:
        out["torso c7 waist length"] = round(torso_custom, 1)
        diag["torso c7 waist length"] = {
            "source": "anthropometry",
            "measurement_type": "length",
            "quality_score": 1.0,
        }

    for m_name, m_def in circumf.items():
        value, d = _circumference_from_definition_cm(
            metric_name=m_name,
            definition=m_def,
            verts=verts,
            faces=faces,
            joints_xyz=joints_xyz,
            joint_index=joint_index,
            landmarks=landmarks,
            circumf_2_bodypart=circumf_2_bodypart,
            face_segmentation=face_segmentation,
        )
        if value is None:
            # Fallback 1: mirrored side
            mirrored = {
                "LANDMARKS": [_mirror_token(n) for n in m_def["LANDMARKS"]],
                "JOINTS": tuple(_mirror_token(n) for n in m_def["JOINTS"]),
            }
            try:
                value_m, d_m = _circumference_from_definition_cm(
                    metric_name=_mirror_token(m_name),
                    definition=mirrored,
                    verts=verts,
                    faces=faces,
                    joints_xyz=joints_xyz,
                    joint_index=joint_index,
                    landmarks=landmarks,
                    circumf_2_bodypart=_mirror_bodypart_mapping(circumf_2_bodypart),
                    face_segmentation=face_segmentation,
                )
            except Exception:
                value_m, d_m = None, {"failure_reason": "mirror_failed"}
            if value_m is not None:
                value = value_m
                d = {**d_m, "fallback_path": "mirror_side"}
            else:
                # Fallback 2: local plane shifts +-10mm
                value_s, d_s = _circumference_from_definition_cm(
                    metric_name=m_name,
                    definition=m_def,
                    verts=verts,
                    faces=faces,
                    joints_xyz=joints_xyz,
                    joint_index=joint_index,
                    landmarks=landmarks,
                    circumf_2_bodypart=circumf_2_bodypart,
                    face_segmentation=face_segmentation,
                    attempts=(0.0, 0.01, -0.01),
                )
                value = value_s
                d = {**d_s, "fallback_path": "plane_shift"}

        out[m_name] = None if value is None else round(float(value), 1)
        diag[m_name] = {
            "source": "anthropometry",
            "measurement_type": "circumference",
            "loop_count": d.get("loop_count"),
            "selected_loop_length_cm": d.get("selected_loop_length_cm"),
            "segments_before_filter": d.get("segments_before_filter"),
            "segments_after_filter": d.get("segments_after_filter"),
            "filter_relaxed": d.get("filter_relaxed"),
            "attempt_shift_m": d.get("attempt_shift_m"),
            "attempt_index": d.get("attempt_index"),
            "failure_reason": d.get("failure_reason"),
            "fallback_path": d.get("fallback_path"),
            "quality_score": 1.0 if value is not None else 0.0,
        }

    return out, diag
