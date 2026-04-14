from typing import Any, Dict, Iterable, Optional, Tuple

import numpy as np

from .anthropometry_adapter import compute_anthropometry_metrics
from .calibration import apply_metric_calibration, load_calibration
from .circumference_measurements import compute_upper_arm_metric
from .constants import REQUIRED_JOINTS
from .joints import build_joint_index, normalize_keypoint_names, validate_required_joints


EXPECTED_MEASUREMENTS = (
    "height",
    "shoulder_width",
    "arm_length",
    "torso_length",
    "inseam",
    "chest",
    "waist",
    "hip",
    "neck",
    "thigh",
    "upper_arm",
    "wrist",
    "calf",
    "ankle",
    "bicep",
)


def _to_numpy(value: Any) -> np.ndarray:
    if hasattr(value, "detach"):
        value = value.detach().cpu().numpy()
    return np.asarray(value)


def _extract_mesh_bundle(npz_data: Any) -> Tuple[np.ndarray, np.ndarray, np.ndarray, Iterable[str]]:
    verts = None
    joints = None
    faces = None

    for key in ("vertices", "v_shaped"):
        if key in npz_data:
            cand = _to_numpy(npz_data[key])
            if cand.ndim == 3:
                cand = cand[0]
            if cand.ndim == 2 and cand.shape[1] >= 3:
                verts = cand[:, :3]
                break

    if "joints" in npz_data:
        cand = _to_numpy(npz_data["joints"])
        if cand.ndim == 3:
            cand = cand[0]
        if cand.ndim == 2 and cand.shape[1] >= 3:
            joints = cand[:, :3]

    if "faces" in npz_data:
        cand = _to_numpy(npz_data["faces"])
        if cand.ndim == 3:
            cand = cand[0]
        if cand.ndim == 2 and cand.shape[1] >= 3:
            faces = cand[:, :3].astype(np.int64)

    keypoint_names = npz_data.get("keypoint_names")
    if keypoint_names is None:
        raise RuntimeError("Missing keypoint_names in SHAPY npz output.")
    if verts is None or joints is None or faces is None:
        raise RuntimeError("Missing vertices/joints/faces in SHAPY npz output.")

    return verts, joints, faces, normalize_keypoint_names(_to_numpy(keypoint_names).tolist())


def _scale_to_height(verts: np.ndarray, joints: np.ndarray, height_cm: float) -> Tuple[np.ndarray, np.ndarray, float]:
    model_height_m = float(np.ptp(verts[:, 1]))
    if model_height_m <= 1e-8:
        return verts, joints, 1.0
    target_height_m = float(height_cm) / 100.0
    scale = target_height_m / model_height_m
    return verts * scale, joints * scale, scale


def _map_to_api_contract(h: Dict[str, Optional[float]]) -> Dict[str, Optional[float]]:
    left = h.get("arm left length")
    right = h.get("arm right length")
    if left is not None and right is not None:
        arm_length = round((left + right) / 2.0, 1)
    else:
        arm_length = left if left is not None else right

    shoulder_raw = h.get("shoulder breadth")
    shoulder_width = None if shoulder_raw is None else round(float(shoulder_raw) * 1.15, 1)
    torso_corrected = h.get("torso c7 waist length")

    return {
        "height": h.get("height"),
        "shoulder_width": shoulder_width,
        "arm_length": arm_length,
        "torso_length": torso_corrected if torso_corrected is not None else h.get("shoulder to crotch height"),
        "inseam": h.get("inside leg height"),
        "chest": h.get("chest circumference"),
        "waist": h.get("waist circumference"),
        "hip": h.get("hip circumference"),
        "neck": h.get("neck circumference"),
        "thigh": h.get("thigh left circumference"),
        "upper_arm": None,
        "wrist": h.get("wrist right circumference"),
        "calf": h.get("calf left circumference"),
        "ankle": h.get("ankle left circumference"),
        "bicep": h.get("bicep right circumference"),
    }


def _confidence(measurements: Dict[str, Optional[float]], diagnostics: Dict[str, Dict[str, Any]]) -> float:
    scores = []
    for metric in EXPECTED_MEASUREMENTS:
        value = measurements.get(metric)
        d = diagnostics.get(metric, {})
        q = float(d.get("quality_score", 0.0 if value is None else 0.85))
        fallback_penalty = 0.15 if d.get("fallback_path") else 0.0
        null_penalty = 0.45 if value is None else 0.0
        score = max(0.0, min(1.0, q - fallback_penalty - null_penalty))
        scores.append(score)
    return round(float(sum(scores) / max(1, len(scores))), 3)


def _enforce_ranges_cm(measurements: Dict[str, Optional[float]], diagnostics: Dict[str, Dict[str, Any]]) -> None:
    bounds = {
        "height": (100.0, 250.0),
        "shoulder_width": (30.0, 70.0),
        "arm_length": (40.0, 90.0),
        "torso_length": (35.0, 90.0),
        "inseam": (55.0, 115.0),
        "chest": (60.0, 180.0),
        "waist": (45.0, 180.0),
        "hip": (60.0, 190.0),
        "neck": (28.0, 55.0),
        "thigh": (30.0, 90.0),
        "upper_arm": (18.0, 65.0),
        "wrist": (11.0, 30.0),
        "calf": (22.0, 70.0),
        "ankle": (14.0, 40.0),
        "bicep": (20.0, 65.0),
    }
    for metric, value in measurements.items():
        if value is None:
            continue
        lo, hi = bounds.get(metric, (0.0, 1000.0))
        if value < lo or value > hi:
            measurements[metric] = None
            diagnostics.setdefault(metric, {})
            diagnostics[metric]["range_check"] = "failed"
            diagnostics[metric]["failure_reason"] = diagnostics[metric].get("failure_reason") or "out_of_range"
            diagnostics[metric]["quality_score"] = 0.0


def compute_measurements_from_npz(npz_path: str, height_cm: float, calibration_path: Optional[str] = None) -> Dict[str, Any]:
    data = np.load(npz_path, allow_pickle=True)
    verts, joints, faces, keypoint_names = _extract_mesh_bundle(data)
    idx = build_joint_index(keypoint_names)
    missing = validate_required_joints(idx, REQUIRED_JOINTS)
    if missing:
        raise RuntimeError(f"Missing required joints in SHAPY output: {missing}")

    verts_s, joints_s, scale = _scale_to_height(verts, joints, height_cm)

    anthropometry_values, anthropometry_diag = compute_anthropometry_metrics(
        verts=verts_s,
        faces=faces,
        joints_xyz=joints_s,
        joint_index=idx,
    )
    measurements = _map_to_api_contract(anthropometry_values)

    upper_arm, upper_arm_diag = compute_upper_arm_metric(
        verts_xyz=verts_s,
        faces=faces,
        joints_xyz=joints_s,
        index_by_name=idx,
        face_segmentation=None,
    )
    measurements["upper_arm"] = upper_arm

    diagnostics: Dict[str, Dict[str, Any]] = {
        "height": anthropometry_diag.get("height", {"source": "anthropometry", "quality_score": 1.0}),
        "shoulder_width": {
            **anthropometry_diag.get("shoulder breadth", {"source": "anthropometry", "quality_score": 0.0}),
            "correction_applied": "x1.15",
        },
        "arm_length": {
            "source": "anthropometry",
            "quality_score": 1.0 if measurements.get("arm_length") is not None else 0.0,
            "fallback_path": "single_side" if (anthropometry_values.get("arm left length") is None) ^ (anthropometry_values.get("arm right length") is None) else None,
        },
        "torso_length": anthropometry_diag.get(
            "torso c7 waist length",
            anthropometry_diag.get("shoulder to crotch height", {"source": "anthropometry", "quality_score": 0.0}),
        ),
        "inseam": anthropometry_diag.get("inside leg height", {"source": "anthropometry", "quality_score": 0.0}),
        "chest": anthropometry_diag.get("chest circumference", {"source": "anthropometry", "quality_score": 0.0}),
        "waist": anthropometry_diag.get("waist circumference", {"source": "anthropometry", "quality_score": 0.0}),
        "hip": anthropometry_diag.get("hip circumference", {"source": "anthropometry", "quality_score": 0.0}),
        "neck": anthropometry_diag.get("neck circumference", {"source": "anthropometry", "quality_score": 0.0}),
        "thigh": anthropometry_diag.get("thigh left circumference", {"source": "anthropometry", "quality_score": 0.0}),
        "upper_arm": upper_arm_diag,
        "wrist": anthropometry_diag.get("wrist right circumference", {"source": "anthropometry", "quality_score": 0.0}),
        "calf": anthropometry_diag.get("calf left circumference", {"source": "anthropometry", "quality_score": 0.0}),
        "ankle": anthropometry_diag.get("ankle left circumference", {"source": "anthropometry", "quality_score": 0.0}),
        "bicep": anthropometry_diag.get("bicep right circumference", {"source": "anthropometry", "quality_score": 0.0}),
    }

    cal_cfg = load_calibration(calibration_path)
    for metric in EXPECTED_MEASUREMENTS:
        value = measurements.get(metric)
        quality = diagnostics.get(metric, {}).get("quality_score")
        measurements[metric], cal_meta = apply_metric_calibration(metric, value, quality, cal_cfg)
        diagnostics.setdefault(metric, {}).update(cal_meta)

    _enforce_ranges_cm(measurements, diagnostics)

    units = {k: "cm" for k in EXPECTED_MEASUREMENTS}
    return {
        "measurements": measurements,
        "diagnostics": diagnostics,
        "meta": {
            "scale_to_height": scale,
            "units": units,
            "keypoint_count": len(keypoint_names),
        },
        "confidence_score": _confidence(measurements, diagnostics),
    }
