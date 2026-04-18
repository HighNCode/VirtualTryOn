"""
Heatmap Generation Service
Generates zone-based fit data for frontend SVG rendering.
"""

from typing import Dict, Optional

from app.data.size_standards import get_standard_size_charts

FIT_COLORS = {
    "tight": "#C04020",
    "snug": "#E87040",
    "perfect": "#2D9E5A",
    "loose": "#4A8FD4",
    "very_loose": "#1A5FAA",
}

MEASUREMENT_TO_ZONE = {
    "shoulder_width": "shoulders",
    "chest": "chest",
    "waist": "waist",
    "hip": "hips",
    "neck": "neck",
    "arm_length": "sleeves",
    "thigh": "thigh",
    "calf": "calf",
    "ankle": "ankle",
}

CATEGORY_ZONES = {
    "tops": ["shoulders", "chest", "waist", "neck", "sleeves"],
    "bottoms": ["waist", "hips", "thigh", "calf", "ankle"],
    "dresses": ["shoulders", "chest", "waist", "hips"],
    "outerwear": ["shoulders", "chest", "sleeves"],
    "unknown": ["chest", "waist", "hips"],
}

ZONE_TO_MEASUREMENT = {v: k for k, v in MEASUREMENT_TO_ZONE.items()}


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

        category_key = category if category in CATEGORY_ZONES else "unknown"
        zones_to_render = CATEGORY_ZONES[category_key]

        zones = {}
        scores = []

        for zone in zones_to_render:
            measurement_name = ZONE_TO_MEASUREMENT.get(zone)
            if not measurement_name:
                continue

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
            fit_label = self._classify_fit_label(delta)
            fit_score = self._score_from_delta(delta)

            zones[zone] = {
                "delta_cm": delta,
                "user_cm": round(user_num, 1),
                "product_cm": product_val,
                "fit_label": fit_label,
                "fit_score": fit_score,
                "color": FIT_COLORS[fit_label],
            }
            scores.append(fit_score)

        if not zones:
            raise ValueError("Could not compute fit for any body zone")

        overall_fit_score = round(sum(scores) / len(scores))
        return {
            "size": size_name,
            "overall_fit_score": overall_fit_score,
            "zones": zones,
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
    def _classify_fit_label(delta: float) -> str:
        if delta < -3.5:
            return "tight"
        if delta < -1.0:
            return "snug"
        if delta <= 1.5:
            return "perfect"
        if delta <= 3.5:
            return "loose"
        return "very_loose"

    @staticmethod
    def _score_from_delta(delta: float) -> int:
        abs_delta = abs(delta)
        if abs_delta <= 1.5:
            score = 100 - (abs_delta / 1.5) * 10
        elif abs_delta <= 3.5:
            score = 90 - ((abs_delta - 1.5) / 2.0) * 20
        elif abs_delta <= 6.0:
            score = 70 - ((abs_delta - 3.5) / 2.5) * 25
        else:
            score = 45 - (abs_delta - 6.0) * 5

        return max(20, min(100, round(score)))
