"""
Standard Size Charts (Fallback)
Industry-average sizing used when products don't have their own size chart.
All measurements in centimeters.
"""

from typing import Dict, Any

# Canonical size ordering
SIZE_ORDER = ["XS", "S", "M", "L", "XL", "XXL"]

# ============================================================================
# Men's Tops (T-shirts, shirts, polos)
# ============================================================================
TOPS_MEN = {
    "XS": {
        "chest":          {"min": 81, "max": 86, "unit": "cm"},
        "waist":          {"min": 66, "max": 71, "unit": "cm"},
        "shoulder_width": {"min": 40, "max": 42, "unit": "cm"},
    },
    "S": {
        "chest":          {"min": 86, "max": 91, "unit": "cm"},
        "waist":          {"min": 71, "max": 76, "unit": "cm"},
        "shoulder_width": {"min": 42, "max": 44, "unit": "cm"},
    },
    "M": {
        "chest":          {"min": 91, "max": 97, "unit": "cm"},
        "waist":          {"min": 76, "max": 81, "unit": "cm"},
        "shoulder_width": {"min": 44, "max": 46, "unit": "cm"},
    },
    "L": {
        "chest":          {"min": 97, "max": 102, "unit": "cm"},
        "waist":          {"min": 81, "max": 86, "unit": "cm"},
        "shoulder_width": {"min": 46, "max": 48, "unit": "cm"},
    },
    "XL": {
        "chest":          {"min": 102, "max": 107, "unit": "cm"},
        "waist":          {"min": 86, "max": 91, "unit": "cm"},
        "shoulder_width": {"min": 48, "max": 50, "unit": "cm"},
    },
    "XXL": {
        "chest":          {"min": 107, "max": 112, "unit": "cm"},
        "waist":          {"min": 91, "max": 96, "unit": "cm"},
        "shoulder_width": {"min": 50, "max": 52, "unit": "cm"},
    },
}

# ============================================================================
# Women's Tops (T-shirts, blouses, shirts)
# ============================================================================
TOPS_WOMEN = {
    "XS": {
        "chest":          {"min": 76, "max": 80, "unit": "cm"},
        "waist":          {"min": 58, "max": 62, "unit": "cm"},
        "shoulder_width": {"min": 35, "max": 37, "unit": "cm"},
    },
    "S": {
        "chest":          {"min": 80, "max": 85, "unit": "cm"},
        "waist":          {"min": 62, "max": 67, "unit": "cm"},
        "shoulder_width": {"min": 37, "max": 39, "unit": "cm"},
    },
    "M": {
        "chest":          {"min": 85, "max": 90, "unit": "cm"},
        "waist":          {"min": 67, "max": 72, "unit": "cm"},
        "shoulder_width": {"min": 39, "max": 41, "unit": "cm"},
    },
    "L": {
        "chest":          {"min": 90, "max": 96, "unit": "cm"},
        "waist":          {"min": 72, "max": 78, "unit": "cm"},
        "shoulder_width": {"min": 41, "max": 43, "unit": "cm"},
    },
    "XL": {
        "chest":          {"min": 96, "max": 102, "unit": "cm"},
        "waist":          {"min": 78, "max": 84, "unit": "cm"},
        "shoulder_width": {"min": 43, "max": 45, "unit": "cm"},
    },
    "XXL": {
        "chest":          {"min": 102, "max": 108, "unit": "cm"},
        "waist":          {"min": 84, "max": 90, "unit": "cm"},
        "shoulder_width": {"min": 45, "max": 47, "unit": "cm"},
    },
}

# ============================================================================
# Men's Bottoms (pants, jeans, trousers)
# ============================================================================
BOTTOMS_MEN = {
    "XS": {
        "waist": {"min": 66, "max": 71, "unit": "cm"},
        "hip":   {"min": 86, "max": 91, "unit": "cm"},
        "inseam": {"min": 76, "max": 79, "unit": "cm"},
    },
    "S": {
        "waist": {"min": 71, "max": 76, "unit": "cm"},
        "hip":   {"min": 91, "max": 96, "unit": "cm"},
        "inseam": {"min": 79, "max": 81, "unit": "cm"},
    },
    "M": {
        "waist": {"min": 76, "max": 81, "unit": "cm"},
        "hip":   {"min": 96, "max": 101, "unit": "cm"},
        "inseam": {"min": 81, "max": 83, "unit": "cm"},
    },
    "L": {
        "waist": {"min": 81, "max": 86, "unit": "cm"},
        "hip":   {"min": 101, "max": 106, "unit": "cm"},
        "inseam": {"min": 81, "max": 83, "unit": "cm"},
    },
    "XL": {
        "waist": {"min": 86, "max": 91, "unit": "cm"},
        "hip":   {"min": 106, "max": 111, "unit": "cm"},
        "inseam": {"min": 81, "max": 83, "unit": "cm"},
    },
    "XXL": {
        "waist": {"min": 91, "max": 96, "unit": "cm"},
        "hip":   {"min": 111, "max": 116, "unit": "cm"},
        "inseam": {"min": 81, "max": 83, "unit": "cm"},
    },
}

# ============================================================================
# Women's Bottoms (pants, jeans, trousers)
# ============================================================================
BOTTOMS_WOMEN = {
    "XS": {
        "waist": {"min": 58, "max": 62, "unit": "cm"},
        "hip":   {"min": 82, "max": 87, "unit": "cm"},
        "inseam": {"min": 74, "max": 76, "unit": "cm"},
    },
    "S": {
        "waist": {"min": 62, "max": 67, "unit": "cm"},
        "hip":   {"min": 87, "max": 92, "unit": "cm"},
        "inseam": {"min": 76, "max": 78, "unit": "cm"},
    },
    "M": {
        "waist": {"min": 67, "max": 72, "unit": "cm"},
        "hip":   {"min": 92, "max": 97, "unit": "cm"},
        "inseam": {"min": 76, "max": 78, "unit": "cm"},
    },
    "L": {
        "waist": {"min": 72, "max": 78, "unit": "cm"},
        "hip":   {"min": 97, "max": 102, "unit": "cm"},
        "inseam": {"min": 76, "max": 78, "unit": "cm"},
    },
    "XL": {
        "waist": {"min": 78, "max": 84, "unit": "cm"},
        "hip":   {"min": 102, "max": 108, "unit": "cm"},
        "inseam": {"min": 76, "max": 78, "unit": "cm"},
    },
    "XXL": {
        "waist": {"min": 84, "max": 90, "unit": "cm"},
        "hip":   {"min": 108, "max": 114, "unit": "cm"},
        "inseam": {"min": 76, "max": 78, "unit": "cm"},
    },
}

# ============================================================================
# Dresses (women's)
# ============================================================================
DRESSES = {
    "XS": {
        "chest": {"min": 76, "max": 80, "unit": "cm"},
        "waist": {"min": 58, "max": 62, "unit": "cm"},
        "hip":   {"min": 82, "max": 87, "unit": "cm"},
    },
    "S": {
        "chest": {"min": 80, "max": 85, "unit": "cm"},
        "waist": {"min": 62, "max": 67, "unit": "cm"},
        "hip":   {"min": 87, "max": 92, "unit": "cm"},
    },
    "M": {
        "chest": {"min": 85, "max": 90, "unit": "cm"},
        "waist": {"min": 67, "max": 72, "unit": "cm"},
        "hip":   {"min": 92, "max": 97, "unit": "cm"},
    },
    "L": {
        "chest": {"min": 90, "max": 96, "unit": "cm"},
        "waist": {"min": 72, "max": 78, "unit": "cm"},
        "hip":   {"min": 97, "max": 102, "unit": "cm"},
    },
    "XL": {
        "chest": {"min": 96, "max": 102, "unit": "cm"},
        "waist": {"min": 78, "max": 84, "unit": "cm"},
        "hip":   {"min": 102, "max": 108, "unit": "cm"},
    },
    "XXL": {
        "chest": {"min": 102, "max": 108, "unit": "cm"},
        "waist": {"min": 84, "max": 90, "unit": "cm"},
        "hip":   {"min": 108, "max": 114, "unit": "cm"},
    },
}

# ============================================================================
# Men's Outerwear (jackets, coats, hoodies)
# ============================================================================
OUTERWEAR_MEN = {
    "XS": {
        "chest":          {"min": 84, "max": 89, "unit": "cm"},
        "shoulder_width": {"min": 41, "max": 43, "unit": "cm"},
    },
    "S": {
        "chest":          {"min": 89, "max": 94, "unit": "cm"},
        "shoulder_width": {"min": 43, "max": 45, "unit": "cm"},
    },
    "M": {
        "chest":          {"min": 94, "max": 100, "unit": "cm"},
        "shoulder_width": {"min": 45, "max": 47, "unit": "cm"},
    },
    "L": {
        "chest":          {"min": 100, "max": 105, "unit": "cm"},
        "shoulder_width": {"min": 47, "max": 49, "unit": "cm"},
    },
    "XL": {
        "chest":          {"min": 105, "max": 110, "unit": "cm"},
        "shoulder_width": {"min": 49, "max": 51, "unit": "cm"},
    },
    "XXL": {
        "chest":          {"min": 110, "max": 115, "unit": "cm"},
        "shoulder_width": {"min": 51, "max": 53, "unit": "cm"},
    },
}

# ============================================================================
# Women's Outerwear (jackets, coats, hoodies)
# ============================================================================
OUTERWEAR_WOMEN = {
    "XS": {
        "chest":          {"min": 79, "max": 83, "unit": "cm"},
        "shoulder_width": {"min": 36, "max": 38, "unit": "cm"},
    },
    "S": {
        "chest":          {"min": 83, "max": 88, "unit": "cm"},
        "shoulder_width": {"min": 38, "max": 40, "unit": "cm"},
    },
    "M": {
        "chest":          {"min": 88, "max": 93, "unit": "cm"},
        "shoulder_width": {"min": 40, "max": 42, "unit": "cm"},
    },
    "L": {
        "chest":          {"min": 93, "max": 99, "unit": "cm"},
        "shoulder_width": {"min": 42, "max": 44, "unit": "cm"},
    },
    "XL": {
        "chest":          {"min": 99, "max": 105, "unit": "cm"},
        "shoulder_width": {"min": 44, "max": 46, "unit": "cm"},
    },
    "XXL": {
        "chest":          {"min": 105, "max": 111, "unit": "cm"},
        "shoulder_width": {"min": 46, "max": 48, "unit": "cm"},
    },
}

# ============================================================================
# Lookup
# ============================================================================

_CHART_MAP = {
    ("tops", "male"):       TOPS_MEN,
    ("tops", "female"):     TOPS_WOMEN,
    ("tops", "unisex"):     TOPS_WOMEN,
    ("bottoms", "male"):    BOTTOMS_MEN,
    ("bottoms", "female"):  BOTTOMS_WOMEN,
    ("bottoms", "unisex"):  BOTTOMS_WOMEN,
    ("dresses", "male"):    DRESSES,
    ("dresses", "female"):  DRESSES,
    ("dresses", "unisex"):  DRESSES,
    ("outerwear", "male"):  OUTERWEAR_MEN,
    ("outerwear", "female"): OUTERWEAR_WOMEN,
    ("outerwear", "unisex"): OUTERWEAR_WOMEN,
}


def get_standard_size_charts(category: str, gender: str) -> Dict[str, Dict[str, Any]]:
    """
    Get standard size charts for a product category and gender.

    Args:
        category: Product category ('tops', 'bottoms', 'dresses', 'outerwear', 'unknown')
        gender: User gender ('male', 'female', 'unisex')

    Returns:
        Dict mapping size_name -> measurements dict
        e.g. {"M": {"chest": {"min": 91, "max": 97, "unit": "cm"}, ...}}
    """
    key = (category, gender)
    if key in _CHART_MAP:
        return _CHART_MAP[key]

    # Fallback for 'unknown' category: use tops
    fallback_key = ("tops", gender)
    return _CHART_MAP.get(fallback_key, TOPS_MEN)
