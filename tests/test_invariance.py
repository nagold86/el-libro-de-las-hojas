"""El área de lesión no debe moverse con la exposición ni con el entorno.

Es la propiedad que el criterio promete en ADR-007 —``(R − G)/(R + G)`` es
invariante a un cambio global de brillo— y que el preprocesado rompía: el balance
de blancos gray-world aplica una ganancia distinta por canal, así que el cero del
detector dependía del promedio de la escena. ADR-013 saca el balance del camino
de la medición y estos tests lo sostienen.
"""

from __future__ import annotations

import numpy as np
import pytest

from core.metrics import compare_masks
from core.preprocess import StandardPreprocessor
from core.segmentation import LesionSegmenter

GAINS = (0.75, 0.9, 1.1)


def _masks(image: np.ndarray) -> dict[float, np.ndarray]:
    preprocessor = StandardPreprocessor()
    segmenter = LesionSegmenter()
    masks: dict[float, np.ndarray] = {}
    for gain in (1.0, *GAINS):
        variant = np.clip(image.astype(np.float32) * gain, 0, 255).astype(np.uint8)
        pre = preprocessor.apply(variant)
        masks[gain] = segmenter.segment(pre.image, pre.valid_mask).lesions
    return masks


def test_lesion_mask_is_stable_under_global_brightness(leaf_image: np.ndarray):
    masks = _masks(leaf_image)

    for gain in GAINS:
        agreement = compare_masks(masks[gain], masks[1.0])
        assert agreement.iou >= 0.98, f"El brillo {gain} movió la máscara: IoU {agreement.iou}"


def test_lesion_count_and_area_do_not_depend_on_exposure(leaf_image: np.ndarray):
    masks = _masks(leaf_image)
    base_area = float(masks[1.0].mean())

    assert base_area > 0.0, "la hoja de prueba debe tener al menos una mancha"
    for gain in GAINS:
        assert float(masks[gain].mean()) == pytest.approx(base_area, abs=1e-4)


def test_a_shadow_and_a_black_band_do_not_enter_the_criterion(leaf_image: np.ndarray):
    # Un borde de recorte negro (fondo del aislamiento) no es tejido: la máscara
    # válida lo excluye y no aporta manchas nuevas.
    with_band = leaf_image.copy()
    with_band[:, :30] = 0

    preprocessor = StandardPreprocessor()
    segmenter = LesionSegmenter()
    clean = preprocessor.apply(leaf_image)
    banded = preprocessor.apply(with_band)

    clean_mask = segmenter.segment(clean.image, clean.valid_mask).lesions
    banded_mask = segmenter.segment(banded.image, banded.valid_mask).lesions

    assert not banded.valid_mask[:, :30].any()
    assert not banded_mask[:, :30].any()
    assert compare_masks(banded_mask, clean_mask).iou >= 0.98
