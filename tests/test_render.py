"""Overlay de máscaras: colores del sistema visual y opacidades acotadas."""

from __future__ import annotations

import cv2
import numpy as np
import pytest

from core.render import LESION_EDGE_RGB, LESION_RGB, VEIN_RGB, render_overlay


def _circle_mask(shape: tuple[int, int], center: tuple[int, int], radius: int) -> np.ndarray:
    mask = np.zeros(shape, dtype=np.uint8)
    cv2.circle(mask, center, radius, 1, -1)
    return mask.astype(bool)


def test_output_keeps_shape_and_dtype(leaf_image: np.ndarray):
    mask = _circle_mask(leaf_image.shape[:2], (170, 90), 10)

    output = render_overlay(leaf_image, mask)

    assert output.shape == leaf_image.shape
    assert output.dtype == np.uint8


def test_lesion_center_is_tinted_oxide(leaf_image: np.ndarray):
    mask = _circle_mask(leaf_image.shape[:2], (170, 90), 10)

    output = render_overlay(leaf_image, mask)

    original = leaf_image[90, 170].astype(int)
    painted = output[90, 170].astype(int)
    assert np.array_equal(output[10, 10], leaf_image[10, 10])
    assert not np.array_equal(output, leaf_image)
    assert np.linalg.norm(painted - np.array(LESION_RGB)) < np.linalg.norm(
        original - np.array(LESION_RGB)
    )


def test_lesion_edge_uses_darker_tone(leaf_image: np.ndarray):
    mask = _circle_mask(leaf_image.shape[:2], (170, 90), 10)

    output = render_overlay(leaf_image, mask)

    top_edge = output[80, 170].astype(int)
    assert np.linalg.norm(top_edge - np.array(LESION_EDGE_RGB)) < 40


def test_zero_lesion_alpha_is_a_no_op(leaf_image: np.ndarray):
    mask = _circle_mask(leaf_image.shape[:2], (170, 90), 10)

    output = render_overlay(leaf_image, mask, lesion_alpha=0.0)

    assert np.array_equal(output, leaf_image)


def test_veins_are_tinted_gold(leaf_image: np.ndarray):
    veins = np.zeros(leaf_image.shape[:2], dtype=bool)
    veins[30:34, 30:34] = True

    output = render_overlay(leaf_image, np.zeros_like(veins), veins)
    tinted = render_overlay(leaf_image, np.zeros_like(veins), veins, vein_alpha=0.0)

    assert not np.array_equal(output, tinted)
    assert np.array_equal(tinted, leaf_image)
    assert np.linalg.norm(output[31, 31].astype(int) - np.array(VEIN_RGB)) < np.linalg.norm(
        leaf_image[31, 31].astype(int) - np.array(VEIN_RGB)
    )


def test_rejects_alpha_out_of_range(leaf_image: np.ndarray):
    mask = np.zeros(leaf_image.shape[:2], dtype=bool)

    with pytest.raises(ValueError):
        render_overlay(leaf_image, mask, lesion_alpha=1.5)
    with pytest.raises(ValueError):
        render_overlay(leaf_image, mask, vein_alpha=-0.1)


def test_rejects_mask_shape_mismatch(leaf_image: np.ndarray):
    with pytest.raises(ValueError):
        render_overlay(leaf_image, np.zeros((10, 10), dtype=bool))
    with pytest.raises(ValueError):
        render_overlay(
            leaf_image,
            np.zeros(leaf_image.shape[:2], dtype=bool),
            np.zeros((10, 10), dtype=bool),
        )


def test_rejects_non_rgb_image():
    with pytest.raises(ValueError):
        render_overlay(np.zeros((10, 10), dtype=np.uint8), np.zeros((10, 10), dtype=bool))
