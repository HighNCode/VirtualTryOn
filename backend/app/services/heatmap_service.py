"""
Heatmap Generation Service
Generates zone-based fit data for frontend SVG rendering.
"""

from typing import Dict, Optional

from app.data.size_standards import get_standard_size_charts
from app.services.size_matcher import SizeMatcher

FIT_COLORS = {
    "tight": "#C04020",
    "snug": "#E87040",
    "perfect": "#2D9E5A",
    "loose": "#4A8FD4",
    "very_loose": "#1A5FAA",
}

ALL_MEASUREMENT_KEYS = [
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

CATEGORY_MEASUREMENTS = {
    "tops": [
        "neck",
        "shoulder_width",
        "chest",
        "torso_length",
        "waist",
        "arm_length",
        "upper_arm",
        "bicep",
        "wrist",
    ],
    "outerwear": [
        "neck",
        "shoulder_width",
        "chest",
        "torso_length",
        "waist",
        "arm_length",
        "upper_arm",
        "bicep",
        "wrist",
    ],
    "bottoms": ["waist", "hip", "thigh", "calf", "ankle", "inseam"],
    "dresses": [
        "neck",
        "shoulder_width",
        "chest",
        "torso_length",
        "waist",
        "hip",
        "upper_arm",
        "bicep",
        "wrist",
        "thigh",
        "calf",
        "ankle",
    ],
    "unknown": ALL_MEASUREMENT_KEYS,
}


class HeatmapService:
    """
    Computes fit deltas and classification labels per body zone.
    """

    def generate(
        self,
        user_measurements: Dict[str, Optional[float]],
        gender: str,
        category: str,
        size_name: str,
        size_charts_db: list,
    ) -> Dict:
        size_data = self._get_size_data(size_name, size_charts_db, category, gender)
        if not size_data:
            raise ValueError(f"Size '{size_name}' not found in size charts")
        if not isinstance(user_measurements, dict):
            user_measurements = {}

        normalized_category = (category or "").strip().lower()
        category_key = normalized_category if normalized_category in CATEGORY_MEASUREMENTS else "unknown"
        measurements_to_render = CATEGORY_MEASUREMENTS[category_key]

        zones = {}
        matcher = SizeMatcher()
        for measurement_name in measurements_to_render:
            user_val = user_measurements.get(measurement_name)
            size_range = size_data.get(measurement_name)
            if user_val is None or size_range is None:
                continue

            min_val = size_range.get("min")
            max_val = size_range.get("max")
            if min_val is None or max_val is None:
                continue

            try:
                user_num = float(user_val)
                min_num = float(min_val)
                max_num = float(max_val)
            except (TypeError, ValueError):
                continue

            product_val = round((min_num + max_num) / 2, 1)
            delta = round(product_val - user_num, 1)
            metric_score, metric_status, metric_difference = matcher._region_score(user_num, min_num, max_num)
            fit_label = self._fit_label_from_status(metric_status, metric_difference)
            fit_score = max(20, min(100, round(metric_score)))

            zones[measurement_name] = {
                "delta_cm": delta,
                "user_cm": round(user_num, 1),
                "product_cm": product_val,
                "fit_label": fit_label,
                "fit_score": fit_score,
                "color": FIT_COLORS[fit_label],
            }

        if not zones:
            raise ValueError("Could not compute fit for any body zone")

        canonical = SizeMatcher().score_single_size(
            user_measurements=user_measurements,
            category=category_key,
            size_measurements=size_data,
        )
        overall_fit_score = canonical.get("score")
        canonical_coverage = canonical.get("coverage", {}) or {}
        zone_deltas = {zone_name: zone_payload["delta_cm"] for zone_name, zone_payload in zones.items()}
        return {
            "size": size_name,
            "category": category_key,
            "overall_fit_score": overall_fit_score,
            "zones": zones,
            "zone_deltas": zone_deltas,
            "coverage_available": int(canonical_coverage.get("used_measurements") or len(zones)),
            "coverage_total": int(canonical_coverage.get("expected_measurements") or len(ALL_MEASUREMENT_KEYS)),
            "legend": FIT_COLORS,
        }

    def _get_size_data(
        self,
        size_name: str,
        size_charts_db: list,
        category: str,
        gender: str,
    ) -> Optional[Dict]:
        if size_charts_db:
            for sc in size_charts_db:
                if sc.size_name == size_name:
                    return sc.measurements
            return None
        standard = get_standard_size_charts(category, gender)
        return standard.get(size_name)

    @staticmethod
    def _fit_label_from_status(status: str, difference: float) -> str:
        if status == "perfect_fit":
            return "perfect"
        if status == "good_fit":
            return "snug" if difference > 0 else "loose"
        if status == "slightly_tight":
            return "snug"
        if status == "slightly_loose":
            return "loose"
        if status == "too_tight":
            return "tight"
        if status == "too_loose":
            return "very_loose"
        return "perfect"
