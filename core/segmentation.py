"""Segmentación de lesiones y nervaduras sobre superficie foliar.

Legolas gobierna este módulo. No hay hoja completa ni fondo: el objeto es la
mancha. El criterio es explicable y determinista: pardeamiento medido como
rojo ≥ verde, con área y compacidad mínimas. No detecta clorosis (amarillamiento
sin pardeamiento): esa familia requiere otro segmentador.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import cv2
import numpy as np


@dataclass(frozen=True)
class SegmentationResult:
    lesions: np.ndarray
    veins: np.ndarray
    params: dict[str, Any] = field(default_factory=dict)


class Segmenter(ABC):
    """Contrato de segmentación de lesiones."""

    name: str

    @abstractmethod
    def segment(self, image: np.ndarray, valid_mask: np.ndarray) -> SegmentationResult:
        """Devuelve máscaras booleanas H×W y los parámetros usados."""


class VeinDetector(ABC):
    """Contrato de realce de la red de nervaduras."""

    name: str

    @abstractmethod
    def detect(self, image: np.ndarray, valid_mask: np.ndarray) -> tuple[np.ndarray, dict[str, Any]]:
        """Devuelve máscara de nervaduras y parámetros."""


class VeinEnhancer(VeinDetector):
    """Black-hat + top-hat sobre el canal verde, umbral por percentil.

    Las nervaduras aparecen como crestas claras u oscuras según la iluminación;
    combinar ambas polaridades evita depender de una sola.
    """

    name = "vein_blackhat_tophat"

    def __init__(self, kernel_size: int = 9, percentile: float = 97.0, min_response: float = 8.0) -> None:
        if kernel_size < 3 or kernel_size % 2 == 0:
            raise ValueError("kernel_size debe ser impar y >= 3.")
        if not 50.0 < percentile < 100.0:
            raise ValueError("percentile debe estar entre 50 y 100.")
        self.kernel_size = int(kernel_size)
        self.percentile = float(percentile)
        self.min_response = float(min_response)

    def detect(self, image: np.ndarray, valid_mask: np.ndarray) -> tuple[np.ndarray, dict[str, Any]]:
        _require_rgb(image)
        green = image[..., 1]
        kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, (self.kernel_size, self.kernel_size)
        )
        dark_ridges = cv2.morphologyEx(green, cv2.MORPH_BLACKHAT, kernel)
        bright_ridges = cv2.morphologyEx(green, cv2.MORPH_TOPHAT, kernel)
        response = cv2.max(dark_ridges, bright_ridges)
        response = cv2.GaussianBlur(response, (0, 0), 1.0)

        values = response[valid_mask]
        if values.size == 0:
            return np.zeros(image.shape[:2], dtype=bool), {"vein_percentile": self.percentile}

        threshold = max(float(np.percentile(values, self.percentile)), self.min_response)
        veins = (response > threshold) & valid_mask

        params = {
            "vein_kernel_px": self.kernel_size,
            "vein_percentile": self.percentile,
            "vein_threshold": round(threshold, 2),
            "vein_fraction": round(float(veins.mean()), 4),
        }
        return veins, params


class LesionSegmenter(Segmenter):
    """Lesión necrótica u oxidada = píxel donde el rojo iguala o supera al verde.

    El puntaje ``(R − G) / (R + G)`` es invariante a la iluminación global y
    separa el tejido pardo del verde sano; una sombra no cambia el signo. Se
    aplica apertura para descartar líneas de un píxel, cierre para unir manchas
    partidas y se descartan componentes con área o compacidad insuficientes.

    Limitación declarada: la clorosis (amarillo, R ≈ G) y las manchas casi
    blancas quedan fuera de esta máscara.
    """

    name = "redness_threshold"

    def __init__(
        self,
        min_area_fraction: float = 0.0002,
        min_area_px: int = 24,
        redness_threshold: float = 0.0,
        min_compactness: float = 0.15,
        vein_detector: VeinDetector | None = None,
    ) -> None:
        if not 0.0 <= min_area_fraction < 1.0:
            raise ValueError("min_area_fraction debe estar en [0, 1).")
        if min_area_px < 1:
            raise ValueError("min_area_px debe ser >= 1.")
        if not -1.0 <= redness_threshold <= 1.0:
            raise ValueError("redness_threshold debe estar en [-1, 1].")
        if not 0.0 <= min_compactness <= 1.0:
            raise ValueError("min_compactness debe estar en [0, 1].")
        self.min_area_fraction = float(min_area_fraction)
        self.min_area_px = int(min_area_px)
        self.redness_threshold = float(redness_threshold)
        self.min_compactness = float(min_compactness)
        self.vein_detector = vein_detector or VeinEnhancer()

    def segment(self, image: np.ndarray, valid_mask: np.ndarray) -> SegmentationResult:
        _require_rgb(image)
        valid = valid_mask.astype(bool)
        if int(valid.sum()) < 100:
            empty = np.zeros(image.shape[:2], dtype=bool)
            return SegmentationResult(empty, empty, {"reason": "sin_pixeles_validos"})

        rgb = image.astype(np.float32)
        redness = (rgb[..., 0] - rgb[..., 1]) / (rgb[..., 0] + rgb[..., 1] + 1e-3)
        mask = (redness > self.redness_threshold) & valid

        opening = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        closing = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        mask = cv2.morphologyEx(mask.astype(np.uint8), cv2.MORPH_OPEN, opening)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, closing)

        min_area = max(self.min_area_px, int(self.min_area_fraction * int(valid.sum())))
        mask, kept = _filter_components(mask, min_area, self.min_compactness)

        veins, vein_params = self.vein_detector.detect(image, valid)

        params = {
            "step": self.name,
            "redness_threshold": self.redness_threshold,
            "min_area_px": min_area,
            "min_compactness": self.min_compactness,
            "median_redness": round(float(np.median(redness[valid])), 4),
            "components_kept": kept,
            "lesion_fraction": round(float(mask.mean()), 5),
            **vein_params,
        }
        return SegmentationResult(mask.astype(bool), veins, params)


def _filter_components(
    mask: np.ndarray, min_area: int, min_compactness: float
) -> tuple[np.ndarray, int]:
    """Descarta ruido por área y por forma: líneas finas tienen baja compacidad."""
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    kept = np.zeros_like(mask, dtype=np.uint8)
    kept_count = 0
    for label in range(1, count):
        area = int(stats[label, cv2.CC_STAT_AREA])
        width = int(stats[label, cv2.CC_STAT_WIDTH])
        height = int(stats[label, cv2.CC_STAT_HEIGHT])
        compactness = area / float(max(width * height, 1))
        if area >= min_area and compactness >= min_compactness:
            kept[labels == label] = 1
            kept_count += 1
    return kept, kept_count


def _require_rgb(image: np.ndarray) -> None:
    if image.dtype != np.uint8 or image.ndim != 3 or image.shape[2] != 3:
        raise ValueError("Se esperaba una imagen RGB uint8 de H×W×3.")
