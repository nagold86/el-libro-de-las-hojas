"""Capas de procesamiento: la traza visual de lo que se le hace a la imagen.

Celebrimbor gobierna la lectura y Aragorn el orden. Una capa no es un
resultado: es una imagen explicable que existe para que el operario vea por qué
el detector decidió lo que decidió. Su ficha técnica viaja en
``trace.layers``; los píxeles se guardan aparte como PNG y el contrato solo
publica la URL.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import numpy as np

LAYER_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]{2,40}$")
STAGES = ("entrada", "aislamiento", "preproceso", "segmentacion", "medicion")


@dataclass(frozen=True)
class Layer:
    """Una etapa visible: clave estable, ficha en español y píxeles uint8."""

    key: str
    stage: str
    title: str
    caption: str
    image: np.ndarray

    def __post_init__(self) -> None:
        if not LAYER_KEY_PATTERN.fullmatch(self.key):
            raise ValueError(f"Clave de capa inválida: {self.key!r}.")
        if self.stage not in STAGES:
            raise ValueError(f"Etapa de capa desconocida: {self.stage!r}.")
        image = np.asarray(self.image)
        if image.dtype != np.uint8:
            raise ValueError("Una capa se guarda como uint8.")
        if image.ndim == 2:
            pass
        elif image.ndim == 3 and image.shape[2] == 3:
            pass
        else:
            raise ValueError("Una capa es H×W en gris o H×W×3 en RGB.")
        object.__setattr__(self, "image", image)

    @property
    def channels(self) -> int:
        return 1 if self.image.ndim == 2 else int(self.image.shape[2])

    def to_dict(self) -> dict[str, Any]:
        """Ficha serializable; los píxeles no viajan por el contrato."""
        return {
            "key": self.key,
            "stage": self.stage,
            "title": self.title,
            "caption": self.caption,
            "width": int(self.image.shape[1]),
            "height": int(self.image.shape[0]),
            "channels": self.channels,
        }
