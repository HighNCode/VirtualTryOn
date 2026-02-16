"""
Heatmap Generation Service
Generates color-coded fit visualization for body regions.

Two modes:
  1. Overlay mode: polygon coords based on actual pose landmarks (for overlaying on user's photo)
  2. Template mode: predefined polygons on a 200x500 canvas (standalone display)
"""

import logging
from typing import Dict, List, Optional, Tuple

import numpy as np

from app.data.size_standards import get_standard_size_charts
from app.services.size_matcher import SizeMatcher, CATEGORY_MEASUREMENTS

logger = logging.getLogger(__name__)

# ============================================================================
# Constants
# ============================================================================

FIT_COLORS = {
    "perfect_fit":    "#4CAF50",
    "good_fit":       "#8BC34A",
    "slightly_loose": "#FFC107",
    "slightly_tight": "#FF9800",
    "too_loose":      "#F44336",
    "too_tight":      "#D32F2F",
}

LEGEND = {
    "perfect": "#4CAF50",
    "good": "#8BC34A",
    "slightly_loose": "#FFC107",
    "slightly_tight": "#FF9800",
    "too_loose": "#F44336",
    "too_tight": "#D32F2F",
}

# Map measurement names → display region names
MEASUREMENT_TO_REGION = {
    "shoulder_width": "shoulders",
    "chest": "chest",
    "waist": "waist",
    "hip": "hips",
    "inseam": "legs",
}

# Template polygon coords on a normalized 200x500 canvas
# Each region is a list of [x, y] points forming a closed polygon
TEMPLATE_POLYGONS = {
    "shoulders": [
        [40, 80], [160, 80], [155, 120], [45, 120],
    ],
    "chest": [
        [45, 120], [155, 120], [150, 185], [50, 185],
    ],
    "waist": [
        [55, 185], [145, 185], [148, 235], [52, 235],
    ],
    "hips": [
        [48, 235], [152, 235], [150, 285], [50, 285],
    ],
    "legs": [
        [50, 285], [95, 285], [92, 450], [55, 450],
        [55, 450], [92, 450], [95, 285], [50, 285],  # left leg
        [105, 285], [150, 285], [145, 450], [108, 450],  # right leg
    ],
}

# Which regions to show per product category
CATEGORY_REGIONS = {
    "tops":      ["shoulders", "chest", "waist"],
    "bottoms":   ["waist", "hips", "legs"],
    "dresses":   ["chest", "waist", "hips"],
    "outerwear": ["shoulders", "chest"],
    "unknown":   ["chest", "waist", "hips"],
}

# Reverse mapping: region name → measurement name
REGION_TO_MEASUREMENT = {v: k for k, v in MEASUREMENT_TO_REGION.items()}


# ============================================================================
# MediaPipe landmark indices
# ============================================================================
# 11 = Left Shoulder, 12 = Right Shoulder
# 23 = Left Hip,      24 = Right Hip
# 27 = Left Ankle,    28 = Right Ankle


class HeatmapService:
    """
    Generates fit heatmap data with color-coded body regions.
    """

    def generate(
        self,
        user_measurements: Dict[str, Optional[float]],
        gender: str,
        category: str,
        size_name: str,
        size_charts_db: list,
        pose_landmarks: Optional[np.ndarray] = None,
        image_shape: Optional[Tuple[int, int]] = None,
    ) -> Dict:
        """
        Generate heatmap data for a specific size.

        Args:
            user_measurements: Dict of measurement name → value in cm
            gender: 'male', 'female', or 'unisex'
            category: Product category
            size_name: Size to evaluate (e.g., "M")
            size_charts_db: List of SizeChart ORM objects
            pose_landmarks: Optional (33, 3) array of MediaPipe landmarks (x, y, visibility)
            image_shape: Optional (H, W) of the source image

        Returns:
            Dict matching HeatmapResponse shape
        """
        # Build size chart for this specific size
        size_data = self._get_size_data(size_name, size_charts_db, category, gender)
        if not size_data:
            raise ValueError(f"Size '{size_name}' not found in size charts")

        # Determine which regions to show
        cat_key = category if category in CATEGORY_REGIONS else "unknown"
        region_names = CATEGORY_REGIONS[cat_key]

        # Compute fit score for each region
        regions = {}
        scores = []

        for region_name in region_names:
            measurement_name = REGION_TO_MEASUREMENT.get(region_name)
            if not measurement_name:
                continue

            user_val = user_measurements.get(measurement_name)
            size_range = size_data.get(measurement_name)

            if user_val is None or size_range is None:
                continue

            min_val = size_range.get("min", 0)
            max_val = size_range.get("max", 0)
            if min_val == 0 and max_val == 0:
                continue

            score, status, _ = SizeMatcher._region_score(user_val, min_val, max_val)
            score_int = round(score)
            color = FIT_COLORS.get(status, "#9E9E9E")

            # Get polygon coordinates
            if pose_landmarks is not None and image_shape is not None:
                polygon = self._polygon_from_landmarks(
                    region_name, pose_landmarks, image_shape
                )
            else:
                polygon = TEMPLATE_POLYGONS.get(region_name, [])

            regions[region_name] = {
                "fit_status": status,
                "color": color,
                "score": score_int,
                "polygon_coords": polygon,
            }
            scores.append(score_int)

        if not regions:
            raise ValueError("Could not compute fit for any body region")

        overall_score = round(sum(scores) / len(scores)) if scores else 0

        # Determine SVG dimensions and generate
        if pose_landmarks is not None and image_shape is not None:
            svg_w, svg_h = image_shape[1], image_shape[0]  # W, H
            image_dimensions = [svg_w, svg_h]
        else:
            svg_w, svg_h = 200, 500
            image_dimensions = None

        svg_overlay = self._generate_svg(regions, svg_w, svg_h)

        return {
            "size": size_name,
            "overall_fit_score": overall_score,
            "regions": regions,
            "svg_overlay": svg_overlay,
            "legend": LEGEND,
            "image_dimensions": image_dimensions,
        }

    def _get_size_data(
        self,
        size_name: str,
        size_charts_db: list,
        category: str,
        gender: str,
    ) -> Optional[Dict]:
        """Get measurement ranges for a specific size."""
        # Try DB size charts first
        if size_charts_db:
            for sc in size_charts_db:
                if sc.size_name == size_name:
                    return sc.measurements
            return None

        # Fallback to standard charts
        standard = get_standard_size_charts(category, gender)
        return standard.get(size_name)

    def _polygon_from_landmarks(
        self,
        region_name: str,
        landmarks: np.ndarray,
        image_shape: Tuple[int, int],
    ) -> List[List[float]]:
        """
        Generate polygon coordinates from MediaPipe pose landmarks.

        Landmarks are normalized (0-1), so we scale by image dimensions.
        """
        H, W = image_shape

        def lm(idx):
            """Get pixel coordinates for a landmark."""
            x = float(landmarks[idx, 0]) * W
            y = float(landmarks[idx, 1]) * H
            return x, y

        def pad(x, y, dx, dy):
            """Expand a point outward for visual padding."""
            return [round(x + dx, 1), round(y + dy, 1)]

        try:
            if region_name == "shoulders":
                l_sh_x, l_sh_y = lm(11)
                r_sh_x, r_sh_y = lm(12)
                mid_y = (l_sh_y + r_sh_y) / 2
                width_pad = abs(l_sh_x - r_sh_x) * 0.15
                return [
                    pad(r_sh_x, mid_y, -width_pad, -15),
                    pad(l_sh_x, mid_y, width_pad, -15),
                    pad(l_sh_x, mid_y, width_pad, 25),
                    pad(r_sh_x, mid_y, -width_pad, 25),
                ]

            elif region_name == "chest":
                l_sh_x, l_sh_y = lm(11)
                r_sh_x, r_sh_y = lm(12)
                l_hip_x, l_hip_y = lm(23)
                r_hip_x, r_hip_y = lm(24)
                # Chest is upper third of torso
                top_y = (l_sh_y + r_sh_y) / 2 + 20
                bot_y = top_y + (((l_hip_y + r_hip_y) / 2) - top_y) * 0.45
                return [
                    [round(r_sh_x, 1), round(top_y, 1)],
                    [round(l_sh_x, 1), round(top_y, 1)],
                    [round(l_sh_x * 0.97 + l_hip_x * 0.03, 1), round(bot_y, 1)],
                    [round(r_sh_x * 0.97 + r_hip_x * 0.03, 1), round(bot_y, 1)],
                ]

            elif region_name == "waist":
                l_sh_x, l_sh_y = lm(11)
                r_sh_x, r_sh_y = lm(12)
                l_hip_x, l_hip_y = lm(23)
                r_hip_x, r_hip_y = lm(24)
                # Waist is middle third of torso
                torso_top = (l_sh_y + r_sh_y) / 2
                torso_bot = (l_hip_y + r_hip_y) / 2
                top_y = torso_top + (torso_bot - torso_top) * 0.4
                bot_y = torso_top + (torso_bot - torso_top) * 0.7
                # Interpolate x narrowing
                left_x = l_sh_x * 0.6 + l_hip_x * 0.4
                right_x = r_sh_x * 0.6 + r_hip_x * 0.4
                return [
                    [round(right_x, 1), round(top_y, 1)],
                    [round(left_x, 1), round(top_y, 1)],
                    [round(left_x * 0.95 + l_hip_x * 0.05, 1), round(bot_y, 1)],
                    [round(right_x * 0.95 + r_hip_x * 0.05, 1), round(bot_y, 1)],
                ]

            elif region_name == "hips":
                l_hip_x, l_hip_y = lm(23)
                r_hip_x, r_hip_y = lm(24)
                mid_y = (l_hip_y + r_hip_y) / 2
                width_pad = abs(l_hip_x - r_hip_x) * 0.1
                return [
                    pad(r_hip_x, mid_y, -width_pad, -20),
                    pad(l_hip_x, mid_y, width_pad, -20),
                    pad(l_hip_x, mid_y, width_pad, 30),
                    pad(r_hip_x, mid_y, -width_pad, 30),
                ]

            elif region_name == "legs":
                l_hip_x, l_hip_y = lm(23)
                r_hip_x, r_hip_y = lm(24)
                l_ank_x, l_ank_y = lm(27)
                r_ank_x, r_ank_y = lm(28)
                mid_x = (l_hip_x + r_hip_x) / 2
                # Left leg
                return [
                    [round(r_hip_x, 1), round(r_hip_y + 10, 1)],
                    [round(mid_x - 5, 1), round(r_hip_y + 10, 1)],
                    [round(r_ank_x + 5, 1), round(r_ank_y, 1)],
                    [round(r_ank_x - 10, 1), round(r_ank_y, 1)],
                    # gap
                    [round(mid_x + 5, 1), round(l_hip_y + 10, 1)],
                    [round(l_hip_x, 1), round(l_hip_y + 10, 1)],
                    [round(l_ank_x + 10, 1), round(l_ank_y, 1)],
                    [round(l_ank_x - 5, 1), round(l_ank_y, 1)],
                ]

        except (IndexError, ValueError) as e:
            logger.warning(f"Landmark polygon failed for {region_name}: {e}")

        # Fallback to template
        return TEMPLATE_POLYGONS.get(region_name, [])

    @staticmethod
    def _generate_svg(
        regions: Dict[str, Dict],
        width: int,
        height: int,
    ) -> str:
        """Build SVG overlay string with colored polygon regions."""
        parts = [
            f'<svg viewBox="0 0 {width} {height}" '
            f'xmlns="http://www.w3.org/2000/svg">'
        ]

        for region_name, data in regions.items():
            color = data["color"]
            coords = data["polygon_coords"]
            if not coords:
                continue

            points_str = " ".join(f"{p[0]},{p[1]}" for p in coords)
            parts.append(
                f'  <polygon points="{points_str}" '
                f'fill="{color}" opacity="0.4" '
                f'stroke="{color}" stroke-width="1.5" '
                f'data-region="{region_name}" '
                f'data-score="{data["score"]}" '
                f'data-status="{data["fit_status"]}"/>'
            )

        parts.append("</svg>")
        return "\n".join(parts)
