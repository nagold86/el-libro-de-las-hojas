"""Preprocesado: normaliza luz y color sin borrar la señal de la hoja.

Sam gobierna este módulo. Regla: ningún paso puede separar hoja de fondo (no hay
fondo) ni suavizar la textura hasta volverla irreconocible. Cada parámetro
aplicado se devuelve para que la corrida sea trazable.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import cv2
import numpy as np


@dataclass(frozen=True)
class PreprocessResult:
    image: np.ndarray
    valid_mask: np.ndarray
    params: dict[str, Any] = field(default_factory=dict)


class Preprocessor(ABC):
    """Contrato de una etapa de preprocesado."""

    name: str

    @abstractmethod
    def apply(self, image: np.ndarray) -> PreprocessResult:
        """Devuelve imagen RGB uint8, máscara de píxeles confiables y parámetros."""


class StandardPreprocessor(Preprocessor):
    """Balance de blancos gray-world + CLAHE en luminancia + bilateral suave.

    - El balance corrige dominantes de color de la cámara.
    - CLAHE actúa solo sobre L para no alterar el croma de la lesión.
    - El bilateral reduce ruido preservando bordes de mancha y nervadura.
    """

    name = "standard"

    def __init__(self, clip_limit: float = 2.0, tile_grid: int = 8, denoise: bool = True) -> None:
        if clip_limit <= 0:
            raise ValueError("clip_limit debe ser positivo.")
        if tile_grid < 1:
            raise ValueError("tile_grid debe ser >= 1.")
        self.clip_limit = float(clip_limit)
        self.tile_grid = int(tile_grid)
        self.denoise = bool(denoise)

    def apply(self, image: np.ndarray) -> PreprocessResult:
        _require_rgb(image)
        pixels = image.astype(np.float32)

        # Píxeles quemados o negros no aportan color: se excluyen de la referencia
        # y del análisis posterior.
        valid = np.all(image < 250, axis=2) & np.all(image > 5, axis=2)
        if int(valid.sum()) < 0.05 * valid.size:
            valid = np.ones(image.shape[:2], dtype=bool)

        reference = pixels[valid].mean(axis=0)
        target = float(reference.mean())
        gains = np.clip(target / np.maximum(reference, 1e-3), 0.75, 1.33)
        balanced = np.clip(pixels * gains.reshape(1, 1, 3), 0, 255).astype(np.uint8)

        lab = cv2.cvtColor(balanced, cv2.COLOR_RGB2LAB)
        clahe = cv2.createCLAHE(clipLimit=self.clip_limit, tileGridSize=(self.tile_grid, self.tile_grid))
        lab[..., 0] = clahe.apply(lab[..., 0])
        enhanced = cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)

        if self.denoise:
            enhanced = cv2.bilateralFilter(enhanced, d=5, sigmaColor=35, sigmaSpace=35)

        params: dict[str, Any] = {
            "step": self.name,
            "white_balance_gains": [round(float(g), 4) for g in gains],
            "clahe_clip_limit": self.clip_limit,
            "clahe_tile_grid": self.tile_grid,
            "bilateral": self.denoise,
            "valid_fraction": round(float(valid.mean()), 4),
        }
        return PreprocessResult(image=enhanced, valid_mask=valid, params=params)


def _require_rgb(image: np.ndarray) -> None:
    if image.dtype != np.uint8 or image.ndim != 3 or image.shape[2] != 3:
        raise ValueError("Se esperaba una imagen RGB uint8 de H×W×3.")
