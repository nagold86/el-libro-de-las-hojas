"""Descriptores de apariencia: color y textura de la superficie foliar.

Merry gobierna este módulo. La señal dominante del dataset es cromática; la
textura aporta uniformidad, rugosidad y nervadura. Todo descriptor declara su
espacio de color y su unidad.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import cv2
import numpy as np
from scipy import ndimage


@dataclass(frozen=True)
class AppearanceMetrics:
    lab_mean: list[float]
    lab_std: list[float]
    exg_mean: float
    browning_index: float
    texture_entropy: float
    local_variance: float
    gradient_mean: float
    lesion_color_delta: float


class Describer(ABC):
    """Contrato de descriptores de apariencia."""

    @abstractmethod
    def describe(
        self, image: np.ndarray, lesions: np.ndarray, valid_mask: np.ndarray
    ) -> AppearanceMetrics:
        """Devuelve color y textura sobre los píxeles válidos."""


class ColorTextureDescriber(Describer):
    """Lab, exceso de verde, pardeamiento, entropía, varianza local y gradiente.

    - ``lab_mean``/``lab_std``: OpenCV Lab de 8 bit (L 0-255, a/b 0-255).
    - ``exg_mean``: exceso de verde (2G − R − B)/255, adimensional.
    - ``browning_index``: (a + b)/2 en Lab, indicador simplificado de oxidación.
    - ``texture_entropy``: entropía de Shannon del histograma de gris (bits).
    - ``local_variance``: media de la varianza en ventanas de 5×5 (niveles²).
    - ``gradient_mean``: magnitud media de Sobel (niveles).
    - ``lesion_color_delta``: distancia euclídea Lab entre lesión y tejido sano.
    """

    def describe(
        self, image: np.ndarray, lesions: np.ndarray, valid_mask: np.ndarray
    ) -> AppearanceMetrics:
        _require_rgb(image)
        valid = np.asarray(valid_mask).astype(bool)
        lesion_mask = np.asarray(lesions).astype(bool) & valid
        if int(valid.sum()) == 0:
            raise ValueError("No hay píxeles válidos para describir.")

        lab = cv2.cvtColor(image, cv2.COLOR_RGB2LAB).astype(np.float32)
        lab_values = lab[valid]
        lab_mean = [round(float(v), 3) for v in lab_values.mean(axis=0)]
        lab_std = [round(float(v), 3) for v in lab_values.std(axis=0)]

        rgb = image.astype(np.float32)
        exg = (2.0 * rgb[..., 1] - rgb[..., 0] - rgb[..., 2]) / 255.0
        exg_mean = round(float(exg[valid].mean()), 4)
        browning = round(float(lab_values[:, 1].mean() + lab_values[:, 2].mean()) / 2.0, 3)

        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        entropy = _entropy(gray[valid])
        local_variance = _local_variance(gray, valid)
        gradient = _gradient_mean(gray, valid)
        delta = _lesion_delta(lab, lesion_mask, valid)

        return AppearanceMetrics(
            lab_mean=lab_mean,
            lab_std=lab_std,
            exg_mean=exg_mean,
            browning_index=browning,
            texture_entropy=entropy,
            local_variance=local_variance,
            gradient_mean=gradient,
            lesion_color_delta=delta,
        )


def _entropy(values: np.ndarray) -> float:
    histogram = np.bincount(np.asarray(values, dtype=np.uint8).ravel(), minlength=256)
    probabilities = histogram.astype(np.float64) / max(int(histogram.sum()), 1)
    nonzero = probabilities[probabilities > 0]
    return round(float(-(nonzero * np.log2(nonzero)).sum()), 4)


def _local_variance(gray: np.ndarray, valid: np.ndarray) -> float:
    values = gray.astype(np.float64)
    mean = ndimage.uniform_filter(values, size=5)
    square_mean = ndimage.uniform_filter(values * values, size=5)
    variance = np.clip(square_mean - mean * mean, 0.0, None)
    return round(float(variance[valid].mean()), 3)


def _gradient_mean(gray: np.ndarray, valid: np.ndarray) -> float:
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    magnitude = cv2.magnitude(gx, gy)
    return round(float(magnitude[valid].mean()), 3)


def _lesion_delta(lab: np.ndarray, lesions: np.ndarray, valid: np.ndarray) -> float:
    healthy = valid & ~lesions
    if not lesions.any() or not healthy.any():
        return 0.0
    lesion_mean = lab[lesions].mean(axis=0)
    healthy_mean = lab[healthy].mean(axis=0)
    return round(float(np.linalg.norm(lesion_mean - healthy_mean)), 3)


def _require_rgb(image: np.ndarray) -> None:
    if image.dtype != np.uint8 or image.ndim != 3 or image.shape[2] != 3:
        raise ValueError("Se esperaba una imagen RGB uint8 de H×W×3.")
