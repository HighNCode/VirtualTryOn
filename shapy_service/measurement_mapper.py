from typing import Any, Dict, Optional


EXPECTED_MEASUREMENTS = [
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
]


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def map_shapy_output(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Map SHAPY-native output to backend's 15-measurement contract.
    """
    source = dict(raw or {})
    measurements = dict(source.get("measurements") or {})

    # Common alias normalization.
    if "hips" in measurements and "hip" not in measurements:
        measurements["hip"] = measurements.get("hips")

    normalized_measurements = {
        key: _to_float(measurements.get(key)) for key in EXPECTED_MEASUREMENTS
    }
    missing = [k for k, v in normalized_measurements.items() if v is None]

    confidence = _to_float(source.get("confidence_score"))
    return {
        "measurements": normalized_measurements,
        "body_type": source.get("body_type") or "average",
        "confidence_score": 0.7 if confidence is None else confidence,
        "missing_measurements": missing,
        "missing_reason": source.get("missing_reason"),
    }
