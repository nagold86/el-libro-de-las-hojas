"""Morfometría: conteo, área relativa, forma y orientación en píxeles."""

from __future__ import annotations

import cv2
import numpy as np
import pytest

from core.morphometry import DefectMeasurer

SIZE = 200


def _blank() -> np.ndarray:
    return np.zeros((SIZE, SIZE), dtype=np.uint8)


def _valid() -> np.ndarray:
    return np.ones((SIZE, SIZE), dtype=bool)


def test_single_circle_metrics():
    mask = _blank()
    cv2.circle(mask, (100, 100), 20, 1, -1)
    lesions = mask.astype(bool)

    metrics = DefectMeasurer().measure(lesions, np.zeros_like(lesions), _valid())

    assert metrics.count == 1
    assert 0.02 < metrics.area_fraction < 0.05
    assert metrics.mean_circularity > 0.85
    assert metrics.orientation_deg is not None
    assert -90.0 <= metrics.orientation_deg <= 90.0
    assert 50 < metrics.max_feret_px < 65
    assert metrics.mean_area_px > 1_000


def test_two_components_are_counted_and_averaged():
    mask = _blank()
    cv2.circle(mask, (40, 40), 14, 1, -1)
    cv2.circle(mask, (150, 150), 10, 1, -1)
    lesions = mask.astype(bool)

    metrics = DefectMeasurer().measure(lesions, np.zeros_like(lesions), _valid())

    assert metrics.count == 2
    assert metrics.max_feret_px > metrics.mean_area_px ** 0.5
    assert metrics.mean_area_px < 700


def test_components_below_min_area_are_ignored():
    mask = _blank()
    mask[10:13, 10:13] = 1

    metrics = DefectMeasurer().measure(mask.astype(bool), np.zeros_like(mask, dtype=bool), _valid())

    assert metrics.count == 0
    assert metrics.orientation_deg is None


def test_empty_mask_reports_zero():
    empty = np.zeros((SIZE, SIZE), dtype=bool)

    metrics = DefectMeasurer().measure(empty, empty, _valid())

    assert metrics.count == 0
    assert metrics.area_fraction == 0.0
    assert metrics.max_feret_px == 0.0
    assert metrics.orientation_deg is None


def test_vein_density_uses_valid_area_as_denominator():
    veins = np.zeros((SIZE, SIZE), dtype=bool)
    veins[:10, :10] = True  # 100 px
    valid = np.zeros((SIZE, SIZE), dtype=bool)
    valid[:, :100] = True  # 20 000 px
    lesions = np.zeros((SIZE, SIZE), dtype=bool)

    metrics = DefectMeasurer().measure(lesions, veins, valid)

    assert metrics.vein_density == pytest.approx(100 / 20_000, abs=1e-6)


def test_area_fraction_is_relative_to_valid_pixels():
    mask = _blank()
    cv2.circle(mask, (100, 100), 20, 1, -1)
    lesions = mask.astype(bool)
    valid = np.zeros((SIZE, SIZE), dtype=bool)
    valid[:, :100] = True  # la mitad de la imagen

    metrics = DefectMeasurer().measure(lesions, np.zeros_like(lesions), valid)

    assert metrics.area_fraction == pytest.approx(lesions.sum() / 20_000, abs=1e-6)


def test_zero_valid_area_returns_zeros():
    empty = np.zeros((SIZE, SIZE), dtype=bool)

    metrics = DefectMeasurer().measure(empty, empty, np.zeros((SIZE, SIZE), dtype=bool))

    assert metrics.count == 0
    assert metrics.vein_density == 0.0


def test_rejects_non_2d_mask():
    with pytest.raises(ValueError):
        DefectMeasurer().measure(
            np.zeros((10, 10, 3), dtype=bool),
            np.zeros((10, 10), dtype=bool),
            np.ones((10, 10), dtype=bool),
        )


def test_rejects_invalid_min_area():
    with pytest.raises(ValueError):
        DefectMeasurer(min_area_px=0)
