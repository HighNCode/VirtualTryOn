"""
Heatmap Generation Service
Generates color-coded fit visualization for body regions.

Two modes:
  1. Overlay mode: polygon coords based on actual pose landmarks (for overlaying on user's photo)
  2. Template mode: predefined polygons on a 200x500 canvas (standalone display)
"""

import math
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
    "neck": "neck",
    "arm_length": "sleeves",
    "thigh": "thigh",
    "calf": "calf",
    "ankle": "ankle",
}

# Template polygon coords on a normalized 200x500 canvas
# Each region is a list of sub-polygons; each sub-polygon is a list of [x, y] points.
# Multi-part regions (arms, legs) have two sub-polygons (left + right).
TEMPLATE_POLYGONS = {
    "shoulders": [
        [[40, 80], [160, 80], [155, 120], [45, 120]],
    ],
    "chest": [
        [[45, 120], [155, 120], [150, 185], [50, 185]],
    ],
    "waist": [
        [[55, 185], [145, 185], [148, 235], [52, 235]],
    ],
    "hips": [
        [[48, 235], [152, 235], [150, 285], [50, 285]],
    ],
    "neck": [
        [[82, 50], [118, 50], [115, 80], [85, 80]],
    ],
    "sleeves": [
        # Left arm (diagonal rectangle going outward-left)
        [[160, 90], [168, 85], [178, 220], [170, 225]],
        # Right arm (diagonal rectangle going outward-right)
        [[40, 90], [32, 85], [22, 220], [30, 225]],
    ],
    "thigh": [
        [[50, 285], [98, 285], [95, 355], [55, 355]],
        [[102, 285], [150, 285], [145, 355], [105, 355]],
    ],
    "calf": [
        [[58, 370], [92, 370], [88, 430], [62, 430]],
        [[108, 370], [142, 370], [138, 430], [112, 430]],
    ],
    "ankle": [
        [[62, 435], [88, 435], [86, 460], [64, 460]],
        [[112, 435], [138, 435], [136, 460], [114, 460]],
    ],
}

# Which regions to show per product category
CATEGORY_REGIONS = {
    "tops":      ["shoulders", "chest", "waist", "neck", "sleeves"],
    "bottoms":   ["waist", "hips", "thigh", "calf", "ankle"],
    "dresses":   ["chest", "waist", "hips", "shoulders"],
    "outerwear": ["shoulders", "chest", "sleeves"],
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

    @staticmethod
    def _arm_rect(
        sh_x: float, sh_y: float,
        wr_x: float, wr_y: float,
        half_w: float,
    ) -> List[List[float]]:
        """
        Build a rectangle along the arm direction (shoulder→wrist)
        with width perpendicular to that direction.
        """
        dx = wr_x - sh_x
        dy = wr_y - sh_y
        length = math.hypot(dx, dy)
        if length < 1:
            return []
        # Unit perpendicular vector
        px = -dy / length * half_w
        py = dx / length * half_w
        # Narrower at wrist end
        wpx = px * 0.65
        wpy = py * 0.65
        return [
            [round(sh_x + px, 1), round(sh_y + py, 1)],
            [round(sh_x - px, 1), round(sh_y - py, 1)],
            [round(wr_x - wpx, 1), round(wr_y - wpy, 1)],
            [round(wr_x + wpx, 1), round(wr_y + wpy, 1)],
        ]

    def _polygon_from_landmarks(
        self,
        region_name: str,
        landmarks: np.ndarray,
        image_shape: Tuple[int, int],
    ) -> List[List[List[float]]]:
        """
        Generate polygon coordinates from MediaPipe pose landmarks.

        Returns a list of sub-polygons. Single-part regions have one sub-polygon,
        paired regions (sleeves, thigh, calf, ankle) have two (left + right).
        Landmarks are normalized (0-1), so we scale by image dimensions.
        """
        H, W = image_shape

        def lm(idx):
            """Get pixel coordinates for a landmark."""
            x = float(landmarks[idx, 0]) * W
            y = float(landmarks[idx, 1]) * H
            return x, y

        def pt(x, y):
            return [round(x, 1), round(y, 1)]

        try:
            if region_name == "shoulders":
                l_sh_x, l_sh_y = lm(11)
                r_sh_x, r_sh_y = lm(12)
                mid_y = (l_sh_y + r_sh_y) / 2
                wp = abs(l_sh_x - r_sh_x) * 0.15
                return [[
                    pt(r_sh_x - wp, mid_y - 15),
                    pt(l_sh_x + wp, mid_y - 15),
                    pt(l_sh_x + wp, mid_y + 25),
                    pt(r_sh_x - wp, mid_y + 25),
                ]]

            elif region_name == "chest":
                l_sh_x, l_sh_y = lm(11)
                r_sh_x, r_sh_y = lm(12)
                l_hip_x, l_hip_y = lm(23)
                r_hip_x, r_hip_y = lm(24)
                top_y = (l_sh_y + r_sh_y) / 2 + 20
                bot_y = top_y + (((l_hip_y + r_hip_y) / 2) - top_y) * 0.45
                return [[
                    pt(r_sh_x, top_y),
                    pt(l_sh_x, top_y),
                    pt(l_sh_x * 0.97 + l_hip_x * 0.03, bot_y),
                    pt(r_sh_x * 0.97 + r_hip_x * 0.03, bot_y),
                ]]

            elif region_name == "waist":
                l_sh_x, l_sh_y = lm(11)
                r_sh_x, r_sh_y = lm(12)
                l_hip_x, l_hip_y = lm(23)
                r_hip_x, r_hip_y = lm(24)
                torso_top = (l_sh_y + r_sh_y) / 2
                torso_bot = (l_hip_y + r_hip_y) / 2
                top_y = torso_top + (torso_bot - torso_top) * 0.4
                bot_y = torso_top + (torso_bot - torso_top) * 0.7
                left_x = l_sh_x * 0.6 + l_hip_x * 0.4
                right_x = r_sh_x * 0.6 + r_hip_x * 0.4
                return [[
                    pt(right_x, top_y),
                    pt(left_x, top_y),
                    pt(left_x * 0.95 + l_hip_x * 0.05, bot_y),
                    pt(right_x * 0.95 + r_hip_x * 0.05, bot_y),
                ]]

            elif region_name == "hips":
                l_hip_x, l_hip_y = lm(23)
                r_hip_x, r_hip_y = lm(24)
                mid_y = (l_hip_y + r_hip_y) / 2
                wp = abs(l_hip_x - r_hip_x) * 0.1
                return [[
                    pt(r_hip_x - wp, mid_y - 20),
                    pt(l_hip_x + wp, mid_y - 20),
                    pt(l_hip_x + wp, mid_y + 30),
                    pt(r_hip_x - wp, mid_y + 30),
                ]]

            elif region_name == "neck":
                nose_x, nose_y = lm(0)
                l_sh_x, l_sh_y = lm(11)
                r_sh_x, r_sh_y = lm(12)
                mid_sh_x = (l_sh_x + r_sh_x) / 2
                mid_sh_y = (l_sh_y + r_sh_y) / 2
                nw = abs(l_sh_x - r_sh_x) * 0.2
                top_y = nose_y + (mid_sh_y - nose_y) * 0.4
                bot_y = mid_sh_y - 5
                return [[
                    pt(mid_sh_x - nw, top_y),
                    pt(mid_sh_x + nw, top_y),
                    pt(mid_sh_x + nw * 1.1, bot_y),
                    pt(mid_sh_x - nw * 1.1, bot_y),
                ]]

            elif region_name == "sleeves":
                # Perpendicular-to-arm-direction rectangles
                l_sh_x, l_sh_y = lm(11)
                r_sh_x, r_sh_y = lm(12)
                l_wr_x, l_wr_y = lm(15)
                r_wr_x, r_wr_y = lm(16)
                half_w = abs(l_sh_x - r_sh_x) * 0.08
                left_arm = self._arm_rect(l_sh_x, l_sh_y, l_wr_x, l_wr_y, half_w)
                right_arm = self._arm_rect(r_sh_x, r_sh_y, r_wr_x, r_wr_y, half_w)
                parts = []
                if left_arm:
                    parts.append(left_arm)
                if right_arm:
                    parts.append(right_arm)
                return parts if parts else TEMPLATE_POLYGONS.get("sleeves", [])

            elif region_name == "thigh":
                l_hip_x, l_hip_y = lm(23)
                r_hip_x, r_hip_y = lm(24)
                l_knee_x, l_knee_y = lm(25)
                r_knee_x, r_knee_y = lm(26)
                mid_x = (l_hip_x + r_hip_x) / 2
                tw = abs(l_hip_x - r_hip_x) * 0.22
                return [
                    # Left thigh
                    [
                        pt(l_hip_x + tw, l_hip_y + 10),
                        pt(mid_x + 5, l_hip_y + 10),
                        pt(l_knee_x + tw * 0.7, l_knee_y - 5),
                        pt(l_knee_x - tw * 0.7, l_knee_y - 5),
                    ],
                    # Right thigh
                    [
                        pt(mid_x - 5, r_hip_y + 10),
                        pt(r_hip_x - tw, r_hip_y + 10),
                        pt(r_knee_x - tw * 0.7, r_knee_y - 5),
                        pt(r_knee_x + tw * 0.7, r_knee_y - 5),
                    ],
                ]

            elif region_name == "calf":
                l_knee_x, l_knee_y = lm(25)
                r_knee_x, r_knee_y = lm(26)
                l_ank_x, l_ank_y = lm(27)
                r_ank_x, r_ank_y = lm(28)
                cw = abs(l_knee_x - r_knee_x) * 0.18
                return [
                    [
                        pt(l_knee_x + cw, l_knee_y + 5),
                        pt(l_knee_x - cw, l_knee_y + 5),
                        pt(l_ank_x - cw * 0.6, l_ank_y - 10),
                        pt(l_ank_x + cw * 0.6, l_ank_y - 10),
                    ],
                    [
                        pt(r_knee_x - cw, r_knee_y + 5),
                        pt(r_knee_x + cw, r_knee_y + 5),
                        pt(r_ank_x + cw * 0.6, r_ank_y - 10),
                        pt(r_ank_x - cw * 0.6, r_ank_y - 10),
                    ],
                ]

            elif region_name == "ankle":
                l_ank_x, l_ank_y = lm(27)
                r_ank_x, r_ank_y = lm(28)
                aw = abs(l_ank_x - r_ank_x) * 0.12
                return [
                    [
                        pt(l_ank_x + aw, l_ank_y - 10),
                        pt(l_ank_x - aw, l_ank_y - 10),
                        pt(l_ank_x - aw, l_ank_y + 15),
                        pt(l_ank_x + aw, l_ank_y + 15),
                    ],
                    [
                        pt(r_ank_x - aw, r_ank_y - 10),
                        pt(r_ank_x + aw, r_ank_y - 10),
                        pt(r_ank_x + aw, r_ank_y + 15),
                        pt(r_ank_x - aw, r_ank_y + 15),
                    ],
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
        """Build SVG overlay string with colored polygon regions.

        polygon_coords is a list of sub-polygons (each is a list of [x,y] points).
        Each sub-polygon renders as its own <polygon> element.
        """
        parts = [
            f'<svg viewBox="0 0 {width} {height}" '
            f'xmlns="http://www.w3.org/2000/svg">'
        ]

        for region_name, data in regions.items():
            color = data["color"]
            sub_polys = data["polygon_coords"]
            if not sub_polys:
                continue

            for sub_poly in sub_polys:
                if not sub_poly:
                    continue
                points_str = " ".join(f"{p[0]},{p[1]}" for p in sub_poly)
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
