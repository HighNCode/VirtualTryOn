import math
from typing import Any, Dict, Optional, Tuple

import numpy as np


def ellipse_perimeter(points_2d: np.ndarray) -> Optional[float]:
    if points_2d.shape[0] < 5:
        return None
    centered = points_2d - points_2d.mean(axis=0)
    cov = np.cov(centered.T)
    eigvals, eigvecs = np.linalg.eigh(cov)
    projected = centered @ eigvecs
    a = float((projected[:, 0].max() - projected[:, 0].min()) / 2.0)
    b = float((projected[:, 1].max() - projected[:, 1].min()) / 2.0)
    if a <= 1e-8 or b <= 1e-8:
        return None
    h = ((a - b) ** 2) / ((a + b) ** 2)
    return math.pi * (a + b) * (1 + (3 * h) / (10 + math.sqrt(max(1e-8, 4 - 3 * h))))


def convex_hull_perimeter(points_2d: np.ndarray) -> Optional[float]:
    if points_2d.shape[0] < 3:
        return None
    pts = sorted((float(p[0]), float(p[1])) for p in points_2d)
    if len(pts) < 3:
        return None

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    upper = []
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    hull = lower[:-1] + upper[:-1]
    if len(hull) < 3:
        return None
    ordered = np.array(hull, dtype=np.float64)
    perimeter = 0.0
    for i in range(len(ordered)):
        j = (i + 1) % len(ordered)
        perimeter += float(np.linalg.norm(ordered[j] - ordered[i]))
    return perimeter


def robust_perimeter(points_2d: np.ndarray) -> Tuple[Optional[float], Dict[str, Any]]:
    if points_2d.shape[0] < 3:
        return None, {"method": None}
    ellipse = ellipse_perimeter(points_2d)
    if ellipse is not None:
        return ellipse, {"method": "ellipse"}
    hull = convex_hull_perimeter(points_2d)
    if hull is not None:
        return hull, {"method": "hull"}
    return None, {"method": None}
