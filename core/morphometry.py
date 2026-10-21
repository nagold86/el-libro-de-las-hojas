"""Morfometría de defectos: qué se mide y en qué unidad.

Gimli gobierna este módulo. Sin patrón de escala no existen milímetros: se
reportan píxeles y fracción del área válida. La orientación solo tiene sentido
para el componente de mayor área.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from math import hypot, pi

import cv2
import numpy as np


@dataclass(frozen=True)
class DefectMetrics:
    count: int
    area_fraction: float
    mean_area_px: float
    max_feret_px: float
    mean_circularity: float
    orientation_deg: float | None
    vein_density: float


class Measurer(ABC):
    """Contrato de medición de defectos."""

    @abstractmethod
    def measure(
        self, lesions: np.ndarray, veins: np.ndarray, valid_mask: np.ndarray
    ) -> DefectMetrics:
        """Devuelve las medidas de la máscara de lesión."""


class DefectMeasurer(Measurer):
    """Cuenta componentes, área relativa, tamaño, forma y orientación.

    - Área: píxeles del componente y fracción del área válida de la imagen.
    - Feret: diagonal del rectángulo mínimo que contiene la lesión.
    - Circularidad: 4πA/P², acotada a [0, 1].
    - Orientación: ángulo del rectángulo mínimo de la lesión más grande.
    """

    def __init__(self, min_area_px: int = 16) -> None:
        if min_area_px < 1:
            raise ValueError("min_area_px debe ser >= 1.")
        self.min_area_px = int(min_area_px)

    def measure(
        self, lesions: np.ndarray, veins: np.ndarray, valid_mask: np.ndarray
    ) -> DefectMetrics:
        lesion_mask = _as_mask(lesions)
        vein_mask = _as_mask(veins)
        valid = _as_mask(valid_mask)
        valid_area = int(valid.sum())
        if valid_area == 0:
            return DefectMetrics(0, 0.0, 0.0, 0.0, 0.0, None, 0.0)

        count, labels, stats, _ = cv2.connectedComponentsWithStats(
            lesion_mask.astype(np.uint8), connectivity=8
        )

        areas: list[int] = []
        circularities: list[float] = []
        ferets: list[float] = []
        angles: list[float] = []

        for label in range(1, count):
            area = int(stats[label, cv2.CC_STAT_AREA])
            if area < self.min_area_px:
                continue

            component = (labels == label).astype(np.uint8)
            contours, _ = cv2.findContours(component, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
            if not contours:
                continue
            contour = max(contours, key=cv2.contourArea)

            perimeter = float(cv2.arcLength(contour, True))
            circularity = 4.0 * pi * area / (perimeter**2) if perimeter > 0 else 0.0

            (_, _), (rect_w, rect_h), angle = cv2.minAreaRect(contour)
            feret = float(hypot(rect_w, rect_h))

            areas.append(area)
            circularities.append(float(np.clip(circularity, 0.0, 1.0)))
            ferets.append(feret)
            angles.append(float(angle))

        if not areas:
            return DefectMetrics(
                count=0,
                area_fraction=0.0,
                mean_area_px=0.0,
                max_feret_px=0.0,
                mean_circularity=0.0,
                orientation_deg=None,
                vein_density=_density(vein_mask, valid_area),
            )

        largest = int(np.argmax(areas))
        return DefectMetrics(
            count=len(areas),
            area_fraction=round(sum(areas) / valid_area, 6),
            mean_area_px=round(float(np.mean(areas)), 2),
            max_feret_px=round(float(np.max(ferets)), 2),
            mean_circularity=round(float(np.mean(circularities)), 4),
            orientation_deg=round(_normalize_angle(angles[largest]), 2),
            vein_density=_density(vein_mask, valid_area),
        )


def _normalize_angle(angle: float) -> float:
    """Lleva el ángulo de OpenCV a (-90, 90]; 0 = eje horizontal de la imagen."""
    normalized = angle % 180.0
    return normalized - 180.0 if normalized > 90.0 else normalized


def _density(mask: np.ndarray, valid_area: int) -> float:
    return round(float(mask.sum()) / valid_area, 6)


def _as_mask(array: np.ndarray) -> np.ndarray:
    mask = np.asarray(array)
    if mask.ndim != 2:
        raise ValueError("Se esperaba una máscara 2D.")
    return mask.astype(bool)
