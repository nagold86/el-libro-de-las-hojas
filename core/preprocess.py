"""Preprocesado: dos vistas de la misma hoja, una que se mide y otra que se mira.

Sam gobierna este módulo. Regla: ningún paso puede separar hoja de fondo (no hay
fondo) ni suavizar la textura hasta volverla irreconocible. Cada parámetro
aplicado se devuelve para que la corrida sea trazable.

El balance de blancos gray-world y el CLAHE existen para que el ojo lea la hoja:
el primero depende del promedio de la escena y el segundo del histograma local,
así que ambos mueven el cero del detector de manchas. Por eso corrigen solo la
vista de presentación (ADR-013). La vista de análisis es el recorte sin ruido:
un píxel pardo es pardo respecto de la hoja, no respecto del promedio del cuadro.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import cv2
import numpy as np

from core.layers import Layer
from core.render import render_mask


@dataclass(frozen=True)
class PreprocessResult:
    # Vista de análisis: la imagen que decide. Nada que dependa de la escena.
    image: np.ndarray
    # Vista de presentación: la misma hoja corregida para que el ojo la lea.
    display: np.ndarray
    valid_mask: np.ndarray
    params: dict[str, Any] = field(default_factory=dict)
    # Capas visibles: análisis, balance, contraste, suavizado y superficie válida.
    layers: tuple[Layer, ...] = ()


class Preprocessor(ABC):
    """Contrato de una etapa de preprocesado."""

    name: str

    @abstractmethod
    def apply(self, image: np.ndarray) -> PreprocessResult:
        """Devuelve imagen RGB uint8, máscara de píxeles confiables y parámetros."""


class StandardPreprocessor(Preprocessor):
    """Vista de análisis canónica y vista de presentación corregida.

    - Análisis: el recorte sin ruido. Es lo que segmenta, mide y describe.
    - Presentación: balance de blancos + CLAHE en luminancia + bilateral. Es lo
      que se muestra; no interviene en ninguna cifra.
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
        # y del análisis posterior. Se miden sobre la imagen que entra, que es la
        # que también se analiza.
        valid = np.all(image < 250, axis=2) & np.all(image > 5, axis=2)
        if int(valid.sum()) < 0.05 * valid.size:
            valid = np.ones(image.shape[:2], dtype=bool)

        # Vista de análisis: solo pierde ruido. Ningún paso que dependa de la
        # escena entra acá, así que el cero del detector no se mueve con la foto.
        analysis = _denoise(image) if self.denoise else image.copy()

        # Vista de presentación: se corrige para que el ojo lea la hoja.
        reference = pixels[valid].mean(axis=0)
        target = float(reference.mean())
        gains = np.clip(target / np.maximum(reference, 1e-3), 0.75, 1.33)
        balanced = np.clip(pixels * gains.reshape(1, 1, 3), 0, 255).astype(np.uint8)

        lab = cv2.cvtColor(balanced, cv2.COLOR_RGB2LAB)
        clahe = cv2.createCLAHE(clipLimit=self.clip_limit, tileGridSize=(self.tile_grid, self.tile_grid))
        lab[..., 0] = clahe.apply(lab[..., 0])
        contrasted = cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)

        display = _denoise(contrasted) if self.denoise else contrasted

        params: dict[str, Any] = {
            "step": self.name,
            "white_balance_gains": [round(float(g), 4) for g in gains],
            "clahe_clip_limit": self.clip_limit,
            "clahe_tile_grid": self.tile_grid,
            "bilateral": self.denoise,
            "valid_fraction": round(float(valid.mean()), 4),
            "analysis_view": "canonica_sin_balance",
            "white_balance_applies_to": "display",
        }
        layers = [
            Layer(
                key="preproceso_analisis",
                stage="preproceso",
                title="Imagen de análisis",
                caption=(
                    "La imagen que entra al detector: el recorte tal cual, solo "
                    "sin grano. No pasa por balance de blancos ni por contraste "
                    "local, para que el criterio de mancha no dependa del promedio "
                    "de la escena. Todo lo que se mide sale de acá."
                ),
                image=analysis,
            ),
            Layer(
                key="preproceso_balance",
                stage="preproceso",
                title="Balance de blancos (visual)",
                caption=(
                    "Ganancias por canal "
                    f"R×{gains[0]:.3f} · G×{gains[1]:.3f} · B×{gains[2]:.3f}. "
                    "Acerca el promedio al gris neutro para quitar dominantes de "
                    "la cámara. Solo para ver: en una hoja verde dos de las tres "
                    "ganancias quedan pegadas al límite y el promedio se corre "
                    "hacia el rojo, así que no entra en la medición."
                ),
                image=balanced,
            ),
            Layer(
                key="preproceso_contraste",
                stage="preproceso",
                title="Contraste local (visual)",
                caption=(
                    f"Ecualización adaptativa solo en luminancia (clip "
                    f"{self.clip_limit:.1f}, mosaico {self.tile_grid}×{self.tile_grid}). "
                    "Levanta textura en sombra sin tocar los ejes de color. Solo "
                    "para ver: el histograma local no describe la mancha."
                ),
                image=contrasted,
            ),
            Layer(
                key="preproceso_ruido",
                stage="preproceso",
                title="Suavizado bilateral",
                caption=(
                    "Filtro bilateral (d=5, σ color y espacio 35) aplicado a las "
                    "dos vistas: baja el grano conservando el borde de la mancha. "
                    "Acá se ve sobre la versión visual."
                    if self.denoise
                    else "Suavizado desactivado: el detector ve el ruido original."
                ),
                image=display,
            ),
            Layer(
                key="preproceso_valido",
                stage="preproceso",
                title="Superficie válida",
                caption=(
                    "Píxeles que cuentan: se excluyen los canales ≥ 250 "
                    "(quemados) y ≤ 5 (negros). Verde: se miden las manchas solo acá."
                ),
                image=render_mask(valid),
            ),
        ]
        return PreprocessResult(
            image=analysis,
            display=display,
            valid_mask=valid,
            params=params,
            layers=tuple(layers),
        )


def _denoise(image: np.ndarray) -> np.ndarray:
    """Bilateral suave: quita grano sin borrar bordes de mancha ni nervadura."""
    return cv2.bilateralFilter(image, d=5, sigmaColor=35, sigmaSpace=35)


def _require_rgb(image: np.ndarray) -> None:
    if image.dtype != np.uint8 or image.ndim != 3 or image.shape[2] != 3:
        raise ValueError("Se esperaba una imagen RGB uint8 de H×W×3.")
