"""Detección de clorosis: pérdida de verde sin oxidación (amarillamiento).

Legolas gobierna también este módulo, pero es una familia distinta de la de
`core/segmentation.py`. Allí se mide **pardeamiento** (rojo ≥ verde); acá se mide
**pérdida de verde**, que es otra cosa: un tejido clorótico es amarillo y pálido,
no pardo. Con un solo criterio las dos familias se confunden, y por eso la
clorosis quedaba fuera de la máscara de lesiones y la hoja clorótica se reportaba
como casi toda enferma.

El criterio es un ángulo, no una diferencia de canales. En Lab, el matiz
`b* / (|a*| + b*)` vale cerca de 1 cuando el tejido deja de ser verde:

    verde sano:  a* ≈ −28, b* ≈ 48  ->  0,63
    clorótica:   a* ≈  −1, b* ≈ 35  ->  0,97
    necrosis:    a* ≈ +10, b* ≈ 22  ->  0,69

La medida se hace sobre la vista canónica (ADR-013), que conserva el color real
del tejido. El croma mínimo descarta grises, brillos y ruido, donde el ángulo no
significa nada.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import cv2
import numpy as np

from core.layers import Layer
from core.render import CHLOROSIS_RGB, render_mask, render_score


@dataclass(frozen=True)
class ChlorosisResult:
    mask: np.ndarray
    params: dict[str, Any] = field(default_factory=dict)
    layers: tuple[Layer, ...] = ()


class ChlorosisDetector:
    """Tejido amarillo y pálido, separado del pardo y del verde.

    El umbral 0,85 sale de la calibración sobre 31 hojas sanas (mediana 0,646,
    p90 de la cola por encima de 0,85: 3,0 %) contra la hoja clorótica conocida
    (0,906 de mediana, 64,6 % de su superficie por encima del umbral).
    """

    name = "hue_angle_chlorosis"

    def __init__(
        self,
        hue_threshold: float = 0.85,
        min_chroma: float = 10.0,
        min_area_fraction: float = 0.0005,
        min_area_px: int = 60,
        min_compactness: float = 0.10,
    ) -> None:
        if not 0.0 < hue_threshold < 1.0:
            raise ValueError("hue_threshold debe estar en (0, 1).")
        if min_chroma < 0.0:
            raise ValueError("min_chroma debe ser >= 0.")
        if not 0.0 <= min_area_fraction < 1.0:
            raise ValueError("min_area_fraction debe estar en [0, 1).")
        if min_area_px < 1:
            raise ValueError("min_area_px debe ser >= 1.")
        if not 0.0 <= min_compactness <= 1.0:
            raise ValueError("min_compactness debe estar en [0, 1].")
        self.hue_threshold = float(hue_threshold)
        self.min_chroma = float(min_chroma)
        self.min_area_fraction = float(min_area_fraction)
        self.min_area_px = int(min_area_px)
        self.min_compactness = float(min_compactness)

    def detect(
        self,
        image: np.ndarray,
        valid_mask: np.ndarray,
        lesion_mask: np.ndarray | None = None,
    ) -> ChlorosisResult:
        _require_rgb(image)
        valid = valid_mask.astype(bool)
        if int(valid.sum()) < 100:
            return ChlorosisResult(
                np.zeros(image.shape[:2], dtype=bool), {"reason": "sin_pixeles_validos"}
            )

        lab = cv2.cvtColor(image, cv2.COLOR_RGB2LAB).astype(np.float32)
        a = lab[..., 1] - 128.0
        b = lab[..., 2] - 128.0
        hue = b / (np.abs(a) + b + 1e-3)
        chroma = np.hypot(a, b)

        raw = (hue > self.hue_threshold) & (chroma >= self.min_chroma) & valid
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        cleaned = cv2.morphologyEx(raw.astype(np.uint8), cv2.MORPH_OPEN, kernel)
        cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_CLOSE, kernel)

        min_area = max(self.min_area_px, int(self.min_area_fraction * int(valid.sum())))
        mask, kept, rejected = _filter(cleaned, min_area, self.min_compactness)

        touched = hue[valid]
        params = {
            "step": self.name,
            "hue_threshold": self.hue_threshold,
            "min_chroma": self.min_chroma,
            "min_area_px": min_area,
            "min_compactness": self.min_compactness,
            "median_hue_angle": round(float(np.median(touched)), 4),
            "chlorosis_fraction": round(float(mask.mean()), 5),
            "chlorosis_fraction_valid": round(
                float(mask.sum()) / max(int(valid.sum()), 1), 5
            ),
            "components_kept": kept,
            "components_discarded": rejected,
        }
        if lesion_mask is not None:
            lesions = np.asarray(lesion_mask).astype(bool)
            both = int((mask & lesions).sum())
            # Fracción del tejido amarillo que además está pardo: 0 significa
            # clorosis limpia, 1 que todo lo amarillo ya se cuenta como lesión.
            params["overlap_with_lesions"] = round(
                both / max(int(mask.sum()), 1), 4
            )
            params["chlorosis_only_fraction"] = round(
                float((mask & ~lesions).sum()) / max(int(valid.sum()), 1), 5
            )

        layers = (
            Layer(
                key="clorosis_puntaje",
                stage="segmentacion",
                title="Ángulo de matiz",
                caption=(
                    "b*/(|a*|+b*): 0,63 en una hoja verde, cerca de 1 cuando el "
                    "tejido perdió el verde. Miel = tejido amarillento; el gris es "
                    "verde sano o píxel sin croma."
                ),
                image=render_score(
                    image, hue, pivot=self.hue_threshold, span=0.15, color=CHLOROSIS_RGB
                ),
            ),
            Layer(
                key="clorosis_mascara",
                stage="segmentacion",
                title="Máscara de clorosis",
                caption=(
                    f"Tejido con ángulo > {self.hue_threshold:.2f}, croma ≥ "
                    f"{self.min_chroma:.0f} y área ≥ {min_area} px. Es una familia "
                    "aparte de la mancha parda: puede solaparse con ella y nunca se "
                    "suma a la de lesiones."
                ),
                image=render_mask(mask, color=CHLOROSIS_RGB),
            ),
        )
        return ChlorosisResult(mask.astype(bool), params, layers)


def _filter(mask: np.ndarray, min_area: int, min_compactness: float) -> tuple[np.ndarray, int, int]:
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    kept = np.zeros_like(mask, dtype=np.uint8)
    kept_count = 0
    rejected_count = 0
    for label in range(1, count):
        area = int(stats[label, cv2.CC_STAT_AREA])
        width = int(stats[label, cv2.CC_STAT_WIDTH])
        height = int(stats[label, cv2.CC_STAT_HEIGHT])
        compactness = area / float(max(width * height, 1))
        if area >= min_area and compactness >= min_compactness:
            kept[labels == label] = 1
            kept_count += 1
        else:
            rejected_count += 1
    return kept, kept_count, rejected_count


def _require_rgb(image: np.ndarray) -> None:
    if image.dtype != np.uint8 or image.ndim != 3 or image.shape[2] != 3:
        raise ValueError("Se esperaba una imagen RGB uint8 de H×W×3.")
