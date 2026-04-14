import json
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


def load_calibration(path: Optional[str]) -> Dict[str, Any]:
    if not path:
        return {}
    fp = Path(path)
    if not fp.exists():
        return {}
    try:
        return json.loads(fp.read_text(encoding="utf-8"))
    except Exception:
        return {}


def apply_metric_calibration(
    metric: str,
    value: Optional[float],
    quality_score: Optional[float],
    calibration_cfg: Dict[str, Any],
) -> Tuple[Optional[float], Dict[str, Any]]:
    if value is None:
        return None, {"calibration_applied": False}
    metrics = calibration_cfg.get("metrics") or {}
    cfg = metrics.get(metric)
    if not isinstance(cfg, dict):
        return value, {"calibration_applied": False}
    min_quality = float(cfg.get("min_quality", 0.0))
    if quality_score is None or float(quality_score) < min_quality:
        return value, {"calibration_applied": False, "reason": "quality_below_threshold"}
    a = float(cfg.get("a", 1.0))
    b = float(cfg.get("b", 0.0))
    calibrated = round(a * float(value) + b, 1)
    return calibrated, {
        "calibration_applied": True,
        "a": a,
        "b": b,
        "min_quality": min_quality,
    }
