"""Preprocesado: dos vistas, forma, tipo y trazabilidad de parámetros."""

from __future__ import annotations

import cv2
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


def test_analysis_view_is_the_input_without_scene_statistics(leaf_image: np.ndarray):
    # La vista que decide solo pierde ruido: si alguien vuelve a meter balance o
    # CLAHE en el camino de la medición, este test cae.
    result = StandardPreprocessor().apply(leaf_image)

    expected = cv2.bilateralFilter(leaf_image, d=5, sigmaColor=35, sigmaSpace=35)
    assert np.array_equal(result.image, expected)


def test_without_denoise_the_analysis_view_is_the_input(leaf_image: np.ndarray):
    result = StandardPreprocessor(denoise=False).apply(leaf_image)

    assert np.array_equal(result.image, leaf_image)
    assert np.array_equal(result.display, _white_balanced_and_contrasted(leaf_image, result))


def test_display_view_is_white_balanced_and_analysis_is_not(leaf_image: np.ndarray):
    result = StandardPreprocessor().apply(leaf_image)

    assert not np.array_equal(result.image, result.display)
    # El balance reparte el verde de la hoja entre los tres canales: en la vista
    # de presentación los promedios quedan más parejos que en la canónica.
    assert _channel_spread(result.display) < _channel_spread(result.image)


def test_analysis_view_does_not_depend_on_scene_composition(leaf_image: np.ndarray):
    # Misma hoja, distinto entorno: una banda oscura arriba mueve el promedio de
    # la escena y con él las ganancias, pero no la imagen que se mide.
    scene = leaf_image.copy()
    scene[:60, :] = 20

    base = StandardPreprocessor().apply(leaf_image)
    altered = StandardPreprocessor().apply(scene)

    assert base.params["white_balance_gains"] != altered.params["white_balance_gains"]
    region = (slice(120, 240), slice(80, 240))
    assert np.array_equal(base.image[region], altered.image[region])
    # La vista de presentación sí cambia con el entorno: por eso no mide.
    assert not np.array_equal(base.display[region], altered.display[region])


def test_params_declare_where_the_white_balance_goes(leaf_image: np.ndarray):
    params = StandardPreprocessor().apply(leaf_image).params

    assert params["analysis_view"] == "canonica_sin_balance"
    assert params["white_balance_applies_to"] == "display"


def _channel_spread(image: np.ndarray) -> float:
    means = image.reshape(-1, 3).mean(axis=0)
    return float(means.max() - means.min())


def _white_balanced_and_contrasted(image: np.ndarray, result) -> np.ndarray:
    """Reproduce el camino de presentación sin suavizado, como control."""
    gains = np.array(result.params["white_balance_gains"], dtype=np.float32)
    balanced = np.clip(image.astype(np.float32) * gains.reshape(1, 1, 3), 0, 255).astype(np.uint8)
    lab = cv2.cvtColor(balanced, cv2.COLOR_RGB2LAB)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    lab[..., 0] = clahe.apply(lab[..., 0])
    return cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)
