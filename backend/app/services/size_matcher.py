"""
Size Recommendation Service
Matches user body measurements to product sizes and computes fit analysis.
"""

import logging
from typing import Dict, List, Optional, Tuple

from app.data.size_standards import SIZE_ORDER, get_standard_size_charts

logger = logging.getLogger(__name__)

# Which measurements matter for each product category
CATEGORY_MEASUREMENTS: Dict[str, List[str]] = {
    "tops":      ["chest", "waist", "shoulder_width", "neck", "arm_length"],
    "bottoms":   ["waist", "hip", "thigh", "calf", "ankle"],
    "dresses":   ["chest", "waist", "hip", "shoulder_width"],
    "outerwear": ["chest", "shoulder_width", "arm_length"],
    "unknown":   ["chest", "waist", "hip"],
}

# Importance weights per measurement within each category
CATEGORY_WEIGHTS: Dict[str, Dict[str, float]] = {
    "tops":      {"chest": 0.30, "waist": 0.15, "shoulder_width": 0.25, "neck": 0.15, "arm_length": 0.15},
    "bottoms":   {"waist": 0.30, "hip": 0.25, "thigh": 0.25, "calf": 0.10, "ankle": 0.10},
    "dresses":   {"chest": 0.25, "waist": 0.30, "hip": 0.30, "shoulder_width": 0.15},
    "outerwear": {"chest": 0.40, "shoulder_width": 0.35, "arm_length": 0.25},
    "unknown":   {"chest": 0.40, "waist": 0.30, "hip": 0.30},
}

SCORE_MODEL_VERSION = "unified_v1"


class SizeMatcher:
    """
    Matches user measurements against product size charts to find the best fit.
    """

    def recommend(
        self,
        user_measurements: Dict[str, Optional[float]],
        gender: str,
        category: str,
        size_charts_db: list,
    ) -> Dict:
        """
        Main entry point for size recommendation.

        Args:
            user_measurements: Dict of measurement name -> value in cm (can be None)
            gender: 'male', 'female', or 'unisex'
            category: Product category ('tops', 'bottoms', 'dresses', 'outerwear', 'unknown')
            size_charts_db: List of SizeChart ORM objects for this product

        Returns:
            Dict with recommended_size, confidence, fit_score, fit_analysis,
            alternative_sizes, all_sizes
        """
        # Build size chart dict: size_name -> {measurement_name -> {min, max, unit}}
        size_chart = self._build_size_chart(size_charts_db, category, gender)

        if not size_chart:
            raise ValueError("No size chart data available for this product")

        category_key = self._normalize_category(category)
        evaluated = self.evaluate_all_sizes(
            user_measurements=user_measurements,
            category=category_key,
            size_chart=size_chart,
        )

        scored_sizes = [
            (size_name, payload["score"], payload["fit_analysis"])
            for size_name, payload in evaluated.items()
            if payload.get("score") is not None
        ]
        if not scored_sizes:
            raise ValueError(
                "Insufficient measurement data for size recommendation. "
                f"Need at least one valid range in size chart for: {CATEGORY_MEASUREMENTS[category_key]}"
            )

        scored_sizes.sort(key=lambda x: x[1], reverse=True)
        best_size, best_score, best_analysis = scored_sizes[0]
        best_coverage = evaluated[best_size]["coverage"]
        confidence = self._derive_confidence(best_score, best_coverage)

        # Build alternative sizes (exclude best, only include fit_score >= 40)
        alternatives = []
        for size_name, score, analysis in scored_sizes[1:]:
            if score < 40:
                continue
            note = self._generate_note(best_size, size_name, best_analysis, analysis)
            alternatives.append({
                "size": size_name,
                "fit_score": score,
                "note": note,
            })

        # All sizes in standard order
        all_sizes = [s for s in SIZE_ORDER if s in size_chart]
        # Include any non-standard size names not in SIZE_ORDER
        for s in size_chart:
            if s not in all_sizes:
                all_sizes.append(s)

        logger.info(
            f"Size recommendation: best={best_size}, score={best_score}, "
            f"confidence={confidence}, category={category}"
        )

        size_scores = {size_name: payload["score"] for size_name, payload in evaluated.items()}
        coverage_by_size = {size_name: payload["coverage"] for size_name, payload in evaluated.items()}

        return {
            "recommended_size": best_size,
            "confidence": confidence,
            "fit_score": best_score,
            "fit_analysis": best_analysis,
            "alternative_sizes": alternatives,
            "all_sizes": all_sizes,
            "size_scores": size_scores,
            "coverage_by_size": coverage_by_size,
            "score_model_version": SCORE_MODEL_VERSION,
        }

    def score_single_size(
        self,
        user_measurements: Dict[str, Optional[float]],
        category: str,
        size_measurements: Dict[str, Dict],
    ) -> Dict:
        category_key = self._normalize_category(category)
        expected_keys = CATEGORY_MEASUREMENTS[category_key]
        weights = CATEGORY_WEIGHTS[category_key]
        return self._compute_size_fit_with_coverage(
            user_measurements=user_measurements or {},
            expected_keys=expected_keys,
            size_measurements=size_measurements,
            weights=weights,
        )

    def evaluate_all_sizes(
        self,
        user_measurements: Dict[str, Optional[float]],
        category: str,
        size_chart: Dict[str, Dict],
    ) -> Dict[str, Dict]:
        category_key = self._normalize_category(category)
        expected_keys = CATEGORY_MEASUREMENTS[category_key]
        weights = CATEGORY_WEIGHTS[category_key]

        results: Dict[str, Dict] = {}
        for size_name, size_measurements in size_chart.items():
            results[size_name] = self._compute_size_fit_with_coverage(
                user_measurements=user_measurements or {},
                expected_keys=expected_keys,
                size_measurements=size_measurements,
                weights=weights,
            )
        return results

    def _build_size_chart(
        self, size_charts_db: list, category: str, gender: str
    ) -> Dict[str, Dict]:
        """
        Build a unified size chart dict from DB records or fallback standards.

        Returns:
            {size_name: {measurement_name: {"min": float, "max": float}}}
        """
        if size_charts_db:
            chart = {}
            for sc in size_charts_db:
                chart[sc.size_name] = sc.measurements
            return chart

        # Fallback to standard charts
        return get_standard_size_charts(category, gender)

    def _compute_size_fit_with_coverage(
        self,
        user_measurements: Dict[str, Optional[float]],
        expected_keys: List[str],
        size_measurements: Dict[str, Dict],
        weights: Dict[str, float],
    ) -> Dict:
        fit_analysis = {}
        weighted_score = 0.0
        total_weight = 0.0
        used_weight = 0.0
        used_measurements = 0

        for measurement_name in expected_keys:
            user_value = user_measurements.get(measurement_name)
            if user_value is None:
                continue
            try:
                user_numeric = float(user_value)
            except (TypeError, ValueError):
                continue

            size_range = size_measurements.get(measurement_name)
            if size_range is None:
                continue

            min_val = size_range.get("min")
            max_val = size_range.get("max")
            if min_val is None or max_val is None:
                continue
            try:
                min_numeric = float(min_val)
                max_numeric = float(max_val)
            except (TypeError, ValueError):
                continue

            score, status, difference = self._region_score(user_numeric, min_numeric, max_numeric)

            fit_analysis[measurement_name] = {
                "status": status,
                "user_value": round(user_numeric, 1),
                "size_range": [round(min_numeric, 1), round(max_numeric, 1)],
                "difference": difference,
            }

            w = weights.get(measurement_name, 0.0)
            weighted_score += score * w
            total_weight += w
            used_weight += w
            used_measurements += 1

        coverage = {
            "used_measurements": used_measurements,
            "expected_measurements": len(expected_keys),
            "used_weight": round(used_weight, 4),
            "total_weight": round(sum(weights.get(key, 0.0) for key in expected_keys), 4),
        }

        if total_weight <= 0:
            return {
                "score": None,
                "fit_analysis": fit_analysis,
                "coverage": coverage,
                "confidence": "insufficient_data",
            }

        fit_score = round(weighted_score / total_weight)
        fit_score = max(0, min(100, fit_score))
        confidence = self._derive_confidence(fit_score, coverage)

        return {
            "score": fit_score,
            "fit_analysis": fit_analysis,
            "coverage": coverage,
            "confidence": confidence,
        }

    @staticmethod
    def _normalize_category(category: str) -> str:
        normalized = (category or "").strip().lower()
        return normalized if normalized in CATEGORY_MEASUREMENTS else "unknown"

    @staticmethod
    def _derive_confidence(score: Optional[int], coverage: Dict) -> str:
        if score is None:
            return "insufficient_data"
        total_weight = float(coverage.get("total_weight") or 0.0)
        used_weight = float(coverage.get("used_weight") or 0.0)
        ratio = (used_weight / total_weight) if total_weight > 0 else 0.0
        if score >= 85 and ratio >= 0.75:
            return "high"
        if score >= 70 and ratio >= 0.55:
            return "medium"
        return "low"

    @staticmethod
    def _region_score(
        user_value: float, min_val: float, max_val: float
    ) -> Tuple[float, str, float]:
        """
        Compute fit score, status, and difference for a single measurement.

        PRD thresholds:
            Within range      -> perfect_fit
            0-2cm outside      -> perfect_fit (score 85-95)
            2-4cm outside      -> good_fit (score 70-85)
            4-7cm outside      -> slightly_loose/slightly_tight (score 40-70)
            >7cm outside       -> too_loose/too_tight (score 0-40)

        Returns:
            (score, status, difference)
            difference: positive = user exceeds max (tight), negative = user below min (loose)
        """
        if min_val <= user_value <= max_val:
            return (100.0, "perfect_fit", 0.0)

        if user_value < min_val:
            overshoot = min_val - user_value
            difference = round(-overshoot, 1)

            if overshoot <= 2:
                status = "perfect_fit"
                score = 95 - (overshoot / 2) * 10
            elif overshoot <= 4:
                status = "good_fit"
                score = 85 - ((overshoot - 2) / 2) * 15
            elif overshoot <= 7:
                status = "slightly_loose"
                score = 70 - ((overshoot - 4) / 3) * 30
            else:
                status = "too_loose"
                score = max(0, 40 - (overshoot - 7) * 5)
        else:
            overshoot = user_value - max_val
            difference = round(overshoot, 1)

            if overshoot <= 2:
                status = "perfect_fit"
                score = 95 - (overshoot / 2) * 10
            elif overshoot <= 4:
                status = "good_fit"
                score = 85 - ((overshoot - 2) / 2) * 15
            elif overshoot <= 7:
                status = "slightly_tight"
                score = 70 - ((overshoot - 4) / 3) * 30
            else:
                status = "too_tight"
                score = max(0, 40 - (overshoot - 7) * 5)

        return (round(score, 1), status, difference)

    @staticmethod
    def _generate_note(
        best_size: str,
        alt_size: str,
        best_analysis: Dict,
        alt_analysis: Dict,
    ) -> str:
        """Generate a human-readable note for an alternative size."""
        # Determine if alt_size is bigger or smaller
        best_idx = SIZE_ORDER.index(best_size) if best_size in SIZE_ORDER else -1
        alt_idx = SIZE_ORDER.index(alt_size) if alt_size in SIZE_ORDER else -1

        if alt_idx > best_idx:
            direction = "looser"
        elif alt_idx < best_idx:
            direction = "tighter"
        else:
            direction = "similar"

        # Find regions where alt_size fits better or worse
        better_regions = []
        worse_regions = []
        for region, alt_fit in alt_analysis.items():
            best_fit = best_analysis.get(region)
            if not best_fit:
                continue
            alt_status = alt_fit["status"]
            best_status = best_fit["status"]
            if alt_status == best_status:
                continue
            # Rank statuses
            rank = {
                "perfect_fit": 5, "good_fit": 4,
                "slightly_loose": 3, "slightly_tight": 3,
                "too_loose": 1, "too_tight": 1,
            }
            if rank.get(alt_status, 0) > rank.get(best_status, 0):
                better_regions.append(region.replace("_", " "))
            else:
                worse_regions.append(region.replace("_", " "))

        if better_regions:
            return f"{direction.capitalize()} fit, better for {', '.join(better_regions)}"
        if worse_regions:
            return f"{direction.capitalize()} fit on {', '.join(worse_regions)}"
        return f"{direction.capitalize()} fit overall"
