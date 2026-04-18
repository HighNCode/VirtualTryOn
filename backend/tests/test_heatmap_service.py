from types import SimpleNamespace

import pytest

from app.services.heatmap_service import HeatmapService


def _size_chart(size_name: str, measurements: dict) -> SimpleNamespace:
    return SimpleNamespace(size_name=size_name, measurements=measurements)


@pytest.mark.parametrize(
    ("delta", "expected_label"),
    [
        (-4.0, "tight"),
        (-2.0, "snug"),
        (0.0, "perfect"),
        (2.0, "loose"),
        (4.0, "very_loose"),
    ],
)
def test_classify_fit_label(delta: float, expected_label: str) -> None:
    assert HeatmapService._classify_fit_label(delta) == expected_label


def test_generate_returns_zone_payload_for_tops() -> None:
    service = HeatmapService()
    size_chart = _size_chart(
        "M",
        {
            "chest": {"min": 90, "max": 94},
            "waist": {"min": 78, "max": 82},
            "shoulder_width": {"min": 44, "max": 46},
            "neck": {"min": 38, "max": 40},
            "arm_length": {"min": 63, "max": 65},
        },
    )
    user_measurements = {
        "chest": 92.0,
        "waist": 79.0,
        "shoulder_width": 45.0,
        "neck": 39.0,
        "arm_length": 64.0,
    }

    result = service.generate(
        user_measurements=user_measurements,
        gender="unisex",
        category="tops",
        size_name="M",
        size_charts_db=[size_chart],
    )

    assert result["size"] == "M"
    assert "zones" in result
    assert "legend" in result
    assert "svg_overlay" not in result
    assert "image_dimensions" not in result

    expected_zones = {"shoulders", "chest", "waist", "neck", "sleeves"}
    assert set(result["zones"].keys()) == expected_zones

    chest = result["zones"]["chest"]
    assert chest["delta_cm"] == 0.0
    assert chest["fit_label"] == "perfect"
    assert isinstance(chest["fit_score"], int)
    assert chest["color"] == result["legend"][chest["fit_label"]]


def test_generate_raises_when_no_zone_can_be_computed() -> None:
    service = HeatmapService()
    size_chart = _size_chart(
        "M",
        {
            "chest": {"min": 90, "max": 94},
        },
    )

    with pytest.raises(ValueError, match="Could not compute fit for any body zone"):
        service.generate(
            user_measurements={},
            gender="unisex",
            category="tops",
            size_name="M",
            size_charts_db=[size_chart],
        )


def test_generate_skips_invalid_non_numeric_values() -> None:
    service = HeatmapService()
    size_chart = _size_chart(
        "M",
        {
            "chest": {"min": "90", "max": "94"},
            "waist": {"min": "bad", "max": 82},
        },
    )
    result = service.generate(
        user_measurements={"chest": "92", "waist": 79},
        gender="unisex",
        category="unknown",
        size_name="M",
        size_charts_db=[size_chart],
    )

    assert "chest" in result["zones"]
    assert "waist" not in result["zones"]
