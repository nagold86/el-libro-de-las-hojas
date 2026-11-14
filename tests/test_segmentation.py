"""Segmentación: pardeamiento por rojo-sobre-verde y realce de nervaduras."""

from __future__ import annotations

import cv2
import numpy as np
import pytest

from core.segmentation import LesionSegmenter, VeinEnhancer


class _EveryPixelIsAVein:
    """Detector de nervaduras que marca todo: sirve para probar el tope por vena."""

    name = "todo_vena"

    def detect(self, image: np.ndarray, valid_mask: np.ndarray):
        return np.ones(image.shape[:2], dtype=bool), {"vein_fraction": 1.0}


def _green(height: int = 200, width: int = 200) -> tuple[np.ndarray, np.ndarray]:
    image = np.zeros((height, width, 3), dtype=np.uint8)
    image[...] = (74, 122, 58)
    return image, np.ones((height, width), dtype=bool)


def _spot_with_halo(height: int = 200, width: int = 300, patch_to: int = 0) -> tuple[np.ndarray, np.ndarray]:
    """Núcleo oscuro (puntaje +0,25) rodeado de un halo pálido (puntaje −0,055)."""
    image, valid = _green(height, width)
    if patch_to:
        # Zona ancha, no una cresta: así no la intercepta el detector de nervaduras.
        cv2.rectangle(image, (100, 55), (patch_to, 145), (86, 96, 52), -1)
    cv2.circle(image, (100, 100), 18, (86, 96, 52), -1)   # halo: no pasa el umbral 0
    cv2.circle(image, (100, 100), 10, (96, 62, 40), -1)   # núcleo: semilla
    return image, valid


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


def test_green_shadow_is_not_detected_as_a_lesion():
    image, valid = _green()
    cv2.rectangle(image, (35, 35), (165, 165), (37, 61, 29), -1)

    result = LesionSegmenter().segment(image, valid)

    assert not result.lesions[35:166, 35:166].any()


def test_achromatic_necrosis_is_detected_as_a_lesion():
    image, valid = _green()
    cv2.circle(image, (100, 100), 18, (28, 28, 28), -1)

    result = LesionSegmenter().segment(image, valid)

    assert result.lesions[100, 100]


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


def test_rejects_invalid_hysteresis_parameters():
    for kwargs in (
        {"hysteresis_fraction": 0.0},
        {"hysteresis_fraction": 1.5},
        {"hysteresis_max_growth_px": -1},
        {"hysteresis_max_growth_px": 65},
        {"hysteresis_max_drop": 0.0},
        {"hysteresis_max_drop": 1.0},
    ):
        with pytest.raises(ValueError):
            LesionSegmenter(**kwargs)


def test_vein_enhancer_rejects_invalid_kernel():
    with pytest.raises(ValueError):
        VeinEnhancer(kernel_size=4)
    with pytest.raises(ValueError):
        VeinEnhancer(percentile=100.0)


def test_hysteresis_recovers_the_pale_halo_around_a_seed():
    """El halo pálido entra solo si hay semilla: eso es la histéresis."""
    image, valid = _spot_with_halo()

    plain = LesionSegmenter(hysteresis=False).segment(image, valid)
    grown = LesionSegmenter().segment(image, valid)

    assert not plain.lesions[100, 115]  # halo a 5 px del núcleo, fuera del umbral 0
    assert grown.lesions[100, 115]
    assert np.all(grown.lesions[plain.lesions])  # solo agrega, nunca quita
    assert grown.params["grown_px"] > 0
    assert grown.params["lesion_fraction"] > plain.params["lesion_fraction"]
    assert grown.params["hysteresis_low_threshold"] < grown.params["redness_threshold"]


def test_hysteresis_stops_at_the_depth_cap():
    """La zona pálida es continua hasta 250, pero el crecimiento se corta antes."""
    image, valid = _spot_with_halo(patch_to=250)

    near = LesionSegmenter(hysteresis_max_growth_px=6).segment(image, valid)
    far = LesionSegmenter(hysteresis_max_growth_px=40).segment(image, valid)

    assert near.lesions[100, 114]        # dentro del tope de 6 px
    assert not near.lesions[100, 140]    # 30 px del núcleo: fuera del tope
    assert far.lesions[100, 140]         # con más tope, la misma zona sí se alcanza


def test_hysteresis_never_creates_a_component_without_a_seed():
    image, valid = _green()
    cv2.circle(image, (40, 40), 18, (86, 96, 52), -1)  # halo sin núcleo

    result = LesionSegmenter().segment(image, valid)

    assert result.params["components_kept"] == 0
    assert not result.lesions.any()
    assert result.params["lesion_fraction"] == 0.0


def test_hysteresis_does_not_grow_over_detected_veins():
    image, valid = _spot_with_halo()

    plain = LesionSegmenter(vein_detector=_EveryPixelIsAVein()).segment(image, valid)
    grown = LesionSegmenter().segment(image, valid)

    assert not plain.lesions[100, 115]
    assert grown.lesions[100, 115]  # el mismo pixel, sin nervadura de por medio


def test_leaf_without_margin_does_not_grow():
    """Si el p50 sano ya está sobre el umbral, los dos umbrales coinciden."""
    image, valid = _green()
    image[...] = (96, 62, 40)

    result = LesionSegmenter().segment(image, valid)

    assert result.params["healthy_redness_p50"] > 0.0
    assert result.params["hysteresis_low_threshold"] == result.params["redness_threshold"]
    assert result.params["grown_px"] == 0


def test_rejects_non_rgb_input():
    with pytest.raises(ValueError):
        LesionSegmenter().segment(np.zeros((10, 10), dtype=np.uint8), np.ones((10, 10), dtype=bool))
