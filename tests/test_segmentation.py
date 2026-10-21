"""Segmentación: pardeamiento por rojo-sobre-verde y realce de nervaduras."""

from __future__ import annotations

import cv2
import numpy as np
import pytest

from core.segmentation import LesionSegmenter, VeinEnhancer


def _green(height: int = 200, width: int = 200) -> tuple[np.ndarray, np.ndarray]:
    image = np.zeros((height, width, 3), dtype=np.uint8)
    image[...] = (74, 122, 58)
    return image, np.ones((height, width), dtype=bool)


def test_detects_brown_spot_and_ignores_green():
    image, valid = _green()
    cv2.ellipse(image, (100, 100), (24, 18), 0, 0, 360, (96, 62, 40), -1)

    result = LesionSegmenter().segment(image, valid)

    assert result.lesions.dtype == np.bool_
    assert result.lesions.shape == image.shape[:2]
    assert result.params["step"] == "redness_threshold"
    assert result.params["components_kept"] >= 1
    assert result.lesions[100, 100]
    assert not result.lesions[10, 10]
    assert 0.005 < result.params["lesion_fraction"] < 0.10


def test_green_surface_has_no_lesions():
    image, valid = _green()

    result = LesionSegmenter().segment(image, valid)

    assert not result.lesions.any()
    assert result.params["components_kept"] == 0
    assert result.params["lesion_fraction"] == 0.0


def test_invalid_surface_is_excluded_from_the_mask():
    image, _ = _green()
    valid = np.zeros(image.shape[:2], dtype=bool)
    valid[50:150, 50:150] = True

    result = LesionSegmenter().segment(image, valid)

    assert not result.lesions[0:50].any()
    assert not result.lesions[150:].any()


def test_min_compactness_discards_round_spot():
    """Un disco casi llena su caja: exigir 0.99 de compacidad lo descarta."""
    image, valid = _green()
    cv2.circle(image, (100, 100), 20, (96, 62, 40), -1)

    result = LesionSegmenter(min_compactness=0.99).segment(image, valid)

    assert not result.lesions.any()
    assert result.params["components_kept"] == 0


def test_min_area_discards_everything():
    image, valid = _green()
    cv2.circle(image, (100, 100), 20, (96, 62, 40), -1)

    result = LesionSegmenter(min_area_px=10_000, min_area_fraction=0.0).segment(image, valid)

    assert not result.lesions.any()


def test_flat_surface_has_no_veins():
    image, valid = _green()

    veins, params = VeinEnhancer().detect(image, valid)

    assert not veins.any()
    assert params["vein_kernel_px"] == 9
    assert params["vein_fraction"] == 0.0


def test_without_valid_pixels_returns_empty_masks():
    image, valid = _green()
    valid[:] = False

    result = LesionSegmenter().segment(image, valid)

    assert result.params["reason"] == "sin_pixeles_validos"
    assert not result.lesions.any()
    assert not result.veins.any()


@pytest.mark.parametrize(
    "kwargs",
    [
        {"min_area_fraction": -0.1},
        {"min_area_px": 0},
        {"redness_threshold": 2.0},
        {"min_compactness": 1.5},
    ],
)
def test_rejects_invalid_parameters(kwargs):
    with pytest.raises(ValueError):
        LesionSegmenter(**kwargs)


def test_vein_enhancer_rejects_invalid_kernel():
    with pytest.raises(ValueError):
        VeinEnhancer(kernel_size=4)
    with pytest.raises(ValueError):
        VeinEnhancer(percentile=100.0)


def test_rejects_non_rgb_input():
    with pytest.raises(ValueError):
        LesionSegmenter().segment(np.zeros((10, 10), dtype=np.uint8), np.ones((10, 10), dtype=bool))
