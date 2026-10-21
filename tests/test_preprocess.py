"""Preprocesado: forma, tipo y trazabilidad de parámetros."""

from __future__ import annotations

import numpy as np
import pytest

from core.preprocess import StandardPreprocessor


def test_apply_returns_rgb_and_params(leaf_image: np.ndarray):
    result = StandardPreprocessor().apply(leaf_image)
    assert result.image.dtype == np.uint8
    assert result.image.shape == leaf_image.shape
    assert result.valid_mask.dtype == np.bool_
    assert result.valid_mask.shape == leaf_image.shape[:2]

    params = result.params
    assert params["step"] == "standard"
    assert len(params["white_balance_gains"]) == 3
    assert all(0.75 <= gain <= 1.33 for gain in params["white_balance_gains"])
    assert 0.0 <= params["valid_fraction"] <= 1.0


def test_deterministic(leaf_image: np.ndarray):
    first = StandardPreprocessor().apply(leaf_image)
    second = StandardPreprocessor().apply(leaf_image)
    assert np.array_equal(first.image, second.image)


def test_rejects_non_rgb():
    with pytest.raises(ValueError):
        StandardPreprocessor().apply(np.zeros((10, 10), dtype=np.uint8))


def test_invalid_parameters():
    with pytest.raises(ValueError):
        StandardPreprocessor(clip_limit=0)
    with pytest.raises(ValueError):
        StandardPreprocessor(tile_grid=0)
