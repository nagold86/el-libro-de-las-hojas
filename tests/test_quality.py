"""Puerta de calidad: rechaza antes de medir y explica cada bandera."""

from __future__ import annotations

import numpy as np
import pytest

from core.quality import QualityGate


def _valid(image: np.ndarray) -> np.ndarray:
    return np.ones(image.shape[:2], dtype=bool)


def test_flat_image_is_flagged_as_blurry(blank_image: np.ndarray):
    report = QualityGate().evaluate(blank_image, _valid(blank_image))

    assert report.usable is False
    assert report.sharpness == 0.0
    assert "borrosa" in report.flags


def test_textured_leaf_is_usable(leaf_image: np.ndarray):
    report = QualityGate().evaluate(leaf_image, _valid(leaf_image))

    assert report.usable is True
    assert report.flags == ()
    assert report.sharpness >= 15.0
    assert 0.0 <= report.saturated_fraction <= 1.0


def test_overexposed_image_is_rejected(leaf_image: np.ndarray):
    overexposed = leaf_image.copy()
    overexposed[: overexposed.shape[0] // 2] = 255

    report = QualityGate().evaluate(overexposed, _valid(overexposed))

    assert report.usable is False
    assert "sobreexpuesta" in report.flags
    assert report.saturated_fraction > 0.2


def test_small_valid_area_warns_but_does_not_reject(leaf_image: np.ndarray):
    valid = np.zeros(leaf_image.shape[:2], dtype=bool)
    valid[: leaf_image.shape[0] // 6] = True

    report = QualityGate().evaluate(leaf_image, valid)

    assert "poca_superficie_valida" in report.flags
    assert report.usable is True


def test_rejects_mask_shape_mismatch(leaf_image: np.ndarray):
    with pytest.raises(ValueError):
        QualityGate().evaluate(leaf_image, np.ones((10, 10), dtype=bool))


@pytest.mark.parametrize(
    "kwargs",
    [
        {"min_sharpness": -1.0},
        {"max_saturated_fraction": 1.5},
        {"min_valid_fraction": -0.1},
    ],
)
def test_rejects_invalid_thresholds(kwargs):
    with pytest.raises(ValueError):
        QualityGate(**kwargs)


def test_rejects_non_rgb_input():
    with pytest.raises(ValueError):
        QualityGate().evaluate(np.zeros((10, 10), dtype=np.uint8), np.ones((10, 10), dtype=bool))
