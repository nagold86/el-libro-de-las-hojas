"""Descriptores de apariencia: color y textura con unidades declaradas."""

from __future__ import annotations

import numpy as np
import pytest

from core.descriptors import ColorTextureDescriber

GREEN = (74, 122, 58)
BROWN = (100, 62, 40)


def _solid(color: tuple[int, int, int], size: int = 60) -> np.ndarray:
    return np.full((size, size, 3), color, dtype=np.uint8)


def _valid(size: int = 60) -> np.ndarray:
    return np.ones((size, size), dtype=bool)


def test_green_surface_has_positive_excess_green():
    metrics = ColorTextureDescriber().describe(
        _solid(GREEN), np.zeros((60, 60), dtype=bool), _valid()
    )

    assert metrics.exg_mean > 0.3
    assert len(metrics.lab_mean) == 3
    assert len(metrics.lab_std) == 3
    assert metrics.lesion_color_delta == 0.0
    assert metrics.texture_entropy == 0.0
    assert metrics.local_variance == 0.0


def test_brown_surface_has_negative_excess_green():
    metrics = ColorTextureDescriber().describe(
        _solid(BROWN), np.zeros((60, 60), dtype=bool), _valid()
    )

    assert metrics.exg_mean < 0.0


def test_browning_index_separates_brown_from_green():
    green = ColorTextureDescriber().describe(
        _solid(GREEN, 80), np.zeros((80, 80), dtype=bool), _valid(80)
    )
    brown = ColorTextureDescriber().describe(
        _solid(BROWN, 80), np.zeros((80, 80), dtype=bool), _valid(80)
    )

    assert brown.browning_index > green.browning_index


def test_lesion_delta_grows_when_brown_area_is_marked():
    image = _solid(GREEN, 80)
    image[:, 40:] = BROWN
    lesions = image[..., 0] > 90  # solo la mitad parda

    plain = ColorTextureDescriber().describe(image, np.zeros((80, 80), dtype=bool), _valid(80))
    marked = ColorTextureDescriber().describe(image, lesions, _valid(80))

    assert plain.lesion_color_delta == 0.0
    assert marked.lesion_color_delta > 10.0


def test_texture_metrics_react_to_noise():
    rng = np.random.default_rng(3)
    smooth = _solid(GREEN, 80)
    noisy = np.clip(smooth.astype(np.float32) + rng.normal(0, 12, smooth.shape), 0, 255).astype(np.uint8)

    smooth_metrics = ColorTextureDescriber().describe(
        smooth, np.zeros((80, 80), dtype=bool), _valid(80)
    )
    noisy_metrics = ColorTextureDescriber().describe(
        noisy, np.zeros((80, 80), dtype=bool), _valid(80)
    )

    assert noisy_metrics.texture_entropy > smooth_metrics.texture_entropy
    assert noisy_metrics.local_variance > smooth_metrics.local_variance
    assert noisy_metrics.gradient_mean > smooth_metrics.gradient_mean


def test_is_deterministic(leaf_image: np.ndarray):
    valid = np.ones(leaf_image.shape[:2], dtype=bool)
    lesions = leaf_image[..., 0] > 90

    first = ColorTextureDescriber().describe(leaf_image, lesions, valid)
    second = ColorTextureDescriber().describe(leaf_image, lesions, valid)

    assert first == second


def test_rejects_image_without_valid_pixels():
    with pytest.raises(ValueError):
        ColorTextureDescriber().describe(
            _solid(GREEN), np.zeros((60, 60), dtype=bool), np.zeros((60, 60), dtype=bool)
        )


def test_rejects_non_rgb_input():
    with pytest.raises(ValueError):
        ColorTextureDescriber().describe(
            np.zeros((10, 10), dtype=np.uint8),
            np.zeros((10, 10), dtype=bool),
            np.ones((10, 10), dtype=bool),
        )
