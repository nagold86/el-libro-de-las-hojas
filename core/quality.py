"""Puerta de calidad: decide si una imagen permite un análisis confiable.

Boromir gobierna este módulo. No mide lesiones: rechaza la imagen antes de que
una métrica inválida llegue al informe. Cada bandera tiene un motivo legible.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass(frozen=True)
class QualityReport:
    usable: bool
    sharpness: float
    saturated_fraction: float
    valid_fraction: float
    flags: tuple[str, ...]


class QualityGate:
    """Reglas mínimas de nitidez, exposición y superficie analizable."""

    def __init__(
        self,
        min_sharpness: float = 15.0,
        max_saturated_fraction: float = 0.20,
        min_valid_fraction: float = 0.50,
    ) -> None:
        if min_sharpness < 0:
            raise ValueError("min_sharpness debe ser >= 0.")
        if not 0.0 <= max_saturated_fraction <= 1.0:
            raise ValueError("max_saturated_fraction debe estar en [0, 1].")
        if not 0.0 <= min_valid_fraction <= 1.0:
            raise ValueError("min_valid_fraction debe estar en [0, 1].")
        self.min_sharpness = float(min_sharpness)
        self.max_saturated_fraction = float(max_saturated_fraction)
        self.min_valid_fraction = float(min_valid_fraction)

    def evaluate(self, image: np.ndarray, valid_mask: np.ndarray) -> QualityReport:
        _require_rgb(image)
        valid = np.asarray(valid_mask).astype(bool)
        if valid.shape != image.shape[:2]:
            raise ValueError("La máscara válida no coincide con la imagen.")

        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        # El aislamiento deja fondo negro: el borde del recorte es un filo
        # artificial. Se mide la nitidez solo en el interior de la superficie
        # válida y la exposición sobre esos mismos píxeles.
        interior = cv2.erode(valid.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)
        sample = laplacian[interior] if interior.any() else laplacian[valid]
        sharpness = float(sample.var()) if sample.size else 0.0
        saturated = (
            float(np.mean(np.any(image[valid] >= 250, axis=1))) if valid.any() else 0.0
        )
        valid_fraction = float(valid.mean())

        flags: list[str] = []
        if sharpness < self.min_sharpness:
            flags.append("borrosa")
        if saturated > self.max_saturated_fraction:
            flags.append("sobreexpuesta")
        if valid_fraction < self.min_valid_fraction:
            flags.append("poca_superficie_valida")

        # La falta de superficie válida no invalida por sí sola si hay imagen
        # suficiente: se informa como advertencia. Nitidez y exposición sí.
        usable = "borrosa" not in flags and "sobreexpuesta" not in flags

        return QualityReport(
            usable=usable,
            sharpness=round(sharpness, 3),
            saturated_fraction=round(saturated, 4),
            valid_fraction=round(valid_fraction, 4),
            flags=tuple(flags),
        )


def _require_rgb(image: np.ndarray) -> None:
    if image.dtype != np.uint8 or image.ndim != 3 or image.shape[2] != 3:
        raise ValueError("Se esperaba una imagen RGB uint8 de H×W×3.")
