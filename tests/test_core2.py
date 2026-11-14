"""Core2 stays classical and separates shadow from tissue categories."""

from __future__ import annotations

import subprocess
import sys

import cv2
import numpy as np

from core2 import Core2ChlorosisDetector, Core2Segmenter


def _green(size: int = 200) -> tuple[np.ndarray, np.ndarray]:
    image = np.full((size, size, 3), (74, 122, 58), dtype=np.uint8)
    return image, np.ones((size, size), dtype=bool)


def test_core2_imports_without_preloading_core_or_app():
    result = subprocess.run(
        [sys.executable, "-c", "import core2; print(core2.Core2Segmenter.name)"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "core2_illumination_chromaticity"


def test_core2_ignores_uniform_shadow_and_detects_brown_lesion():
    image, valid = _green()
    cv2.rectangle(image, (20, 20), (85, 180), (37, 61, 29), -1)
    cv2.ellipse(image, (140, 100), (24, 18), 0, 0, 360, (96, 62, 40), -1)

    result = Core2Segmenter().segment(image, valid)

    assert not result.lesions[20:86, 20:86].any()
    assert result.lesions[100, 140]
    assert result.params["method"] == "luminancia_normalizada_mas_cromaticidad_relativa"
    assert "core2_luz_normalizada" in {layer.key for layer in result.layers}


def test_core2_detects_achromatic_necrosis():
    image, valid = _green()
    cv2.circle(image, (100, 100), 18, (28, 28, 28), -1)

    result = Core2Segmenter().segment(image, valid)

    assert result.lesions[100, 100]


def test_core2_chlorosis_uses_yellow_chromaticity_and_ignores_shadow():
    image, valid = _green()
    cv2.rectangle(image, (15, 15), (75, 180), (37, 61, 29), -1)
    cv2.rectangle(image, (110, 50), (180, 150), (150, 160, 50), -1)

    result = Core2ChlorosisDetector().detect(image, valid)

    assert not result.mask[15:76, 15:76].any()
    assert result.mask[100, 140]


def test_core2_chlorosis_does_not_mark_healthy_green():
    image, valid = _green()

    result = Core2ChlorosisDetector().detect(image, valid)

    assert not result.mask.any()
