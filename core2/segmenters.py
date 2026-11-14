"""Illumination-aware classical segmentation for leaves.

Core2 estimates a broad illumination field in Lab luminance, normalizes it,
and makes tissue decisions from chromaticity. It uses no learned parameters.
"""

from __future__ import annotations

from typing import Any

import cv2
import numpy as np

from core.chlorosis import ChlorosisDetector, ChlorosisResult
from core.layers import Layer
from core.render import CHLOROSIS_RGB, render_mask, render_score
from core.segmentation import SegmentationResult, Segmenter, VeinEnhancer


class Core2Segmenter(Segmenter):
    """Detect brown and dark lesions after broad illumination normalization."""

    name = "core2_illumination_chromaticity"

    def __init__(
        self,
        min_area_px: int = 24,
        min_area_fraction: float = 0.0002,
        redness_threshold: float = 0.02,
        darkness_threshold: float = 0.22,
        vein_detector: VeinEnhancer | None = None,
    ) -> None:
        if min_area_px < 1:
            raise ValueError("min_area_px debe ser >= 1.")
        if not 0.0 <= min_area_fraction < 1.0:
            raise ValueError("min_area_fraction debe estar en [0, 1).")
        if not -1.0 <= redness_threshold <= 1.0:
            raise ValueError("redness_threshold debe estar en [-1, 1].")
        if not 0.0 <= darkness_threshold < 1.0:
            raise ValueError("darkness_threshold debe estar en [0, 1).")
        self.min_area_px = int(min_area_px)
        self.min_area_fraction = float(min_area_fraction)
        self.redness_threshold = float(redness_threshold)
        self.darkness_threshold = float(darkness_threshold)
        self.vein_detector = vein_detector or VeinEnhancer()

    def segment(self, image: np.ndarray, valid_mask: np.ndarray) -> SegmentationResult:
        _require_rgb(image)
        valid = np.asarray(valid_mask).astype(bool)
        if valid.shape != image.shape[:2]:
            raise ValueError("La máscara válida no coincide con la imagen.")
        if int(valid.sum()) < 100:
            empty = np.zeros(image.shape[:2], dtype=bool)
            return SegmentationResult(empty, empty, {"reason": "sin_pixeles_validos"})

        normalized_l, normalized_rgb, illumination = _normalize_luminance(image, valid)
        rgb = image.astype(np.float32)
        redness = (rgb[..., 0] - rgb[..., 1]) / (rgb[..., 0] + rgb[..., 1] + 1e-3)

        veins, vein_params = self.vein_detector.detect(image, valid)
        vein_guard = cv2.dilate(veins.astype(np.uint8), _ellipse(3)).astype(bool)
        healthy = valid & ~vein_guard & (redness <= self.redness_threshold)
        if int(healthy.sum()) < 100:
            healthy = valid & ~vein_guard
        if int(healthy.sum()) < 100:
            empty = np.zeros(image.shape[:2], dtype=bool)
            return SegmentationResult(empty, veins, {"reason": "sin_referencia_sana"})

        healthy_redness = float(np.median(redness[healthy]))
        healthy_luminance = float(np.median(normalized_l[healthy]))
        color_shift = redness - healthy_redness
        relative_darkness = np.clip(
            (healthy_luminance - normalized_l) / max(healthy_luminance, 1.0), 0.0, 1.0
        )

        brown = redness > self.redness_threshold
        dark = (relative_darkness > self.darkness_threshold) & (color_shift > 0.08)
        raw = (brown | dark) & valid & ~vein_guard
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        cleaned = cv2.morphologyEx(raw.astype(np.uint8), cv2.MORPH_OPEN, kernel)
        cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_CLOSE, kernel)
        min_area = max(self.min_area_px, int(self.min_area_fraction * int(valid.sum())))
        lesions, kept, rejected = _filter_components(cleaned, min_area)

        shadow_score = np.clip(
            (illumination - cv2.cvtColor(image, cv2.COLOR_RGB2LAB)[..., 0].astype(np.float32))
            / np.maximum(illumination, 1.0),
            0.0,
            1.0,
        )
        params: dict[str, Any] = {
            "step": self.name,
            "method": "luminancia_normalizada_mas_cromaticidad_relativa",
            "redness_threshold": self.redness_threshold,
            "darkness_threshold": self.darkness_threshold,
            "illumination_sigma_px": round(_illumination_sigma(image), 2),
            "min_area_px": min_area,
            "healthy_redness": round(healthy_redness, 4),
            "lesion_fraction": round(float(lesions.mean()), 5),
            "components_kept": kept,
            "components_discarded": rejected,
            **vein_params,
        }
        layers = (
            Layer(
                key="core2_luz_normalizada",
                stage="segmentacion",
                title="Luminancia normalizada",
                caption=(
                    "Se estima la iluminación amplia con un suavizado gaussiano y "
                    "se normaliza Lab L*. El color se conserva para separar tejido "
                    "pardo de oscurecimientos por sombra."
                ),
                image=normalized_rgb,
            ),
            Layer(
                key="core2_sombra",
                stage="segmentacion",
                title="Cambio local de iluminación",
                caption=(
                    "Diferencia entre la luminancia observada y el campo de "
                    "iluminación estimado. Sirve para explicar dónde se compensa "
                    "la luz; por sí sola no suma área de lesión."
                ),
                image=render_score(image, shadow_score, pivot=0.08, span=0.35),
            ),
            Layer(
                key="core2_lesiones",
                stage="segmentacion",
                title="Máscara Core2",
                caption=(
                    "Lesiones por cromaticidad parda o por oscuridad residual "
                    "acompañada de un cambio cromático respecto del tejido sano."
                ),
                image=render_mask(lesions),
            ),
        )
        return SegmentationResult(lesions, veins, params, layers=layers)


class Core2ChlorosisDetector(ChlorosisDetector):
    """Find yellow tissue from normalized RGB chromaticity, not Lab hue angle."""

    name = "core2_yellow_chromaticity"

    def __init__(
        self,
        yellow_threshold: float = 0.10,
        green_balance_max: float = 0.06,
        min_area_px: int = 60,
    ) -> None:
        if not -1.0 <= yellow_threshold <= 1.0:
            raise ValueError("yellow_threshold debe estar en [-1, 1].")
        if not -1.0 <= green_balance_max <= 1.0:
            raise ValueError("green_balance_max debe estar en [-1, 1].")
        if min_area_px < 1:
            raise ValueError("min_area_px debe ser >= 1.")
        self.yellow_threshold = float(yellow_threshold)
        self.green_balance_max = float(green_balance_max)
        self.min_area_px = int(min_area_px)

    def detect(
        self,
        image: np.ndarray,
        valid_mask: np.ndarray,
        lesion_mask: np.ndarray | None = None,
    ) -> ChlorosisResult:
        _require_rgb(image)
        valid = np.asarray(valid_mask).astype(bool)
        if valid.shape != image.shape[:2]:
            raise ValueError("La máscara válida no coincide con la imagen.")
        if int(valid.sum()) < 100:
            return ChlorosisResult(
                np.zeros(image.shape[:2], dtype=bool), {"reason": "sin_pixeles_validos"}
            )

        rgb = image.astype(np.float32)
        total = np.maximum(rgb.sum(axis=2), 1.0)
        red, green, blue = (rgb[..., channel] / total for channel in range(3))
        yellow = np.minimum(red, green) - blue
        green_balance = green - red
        raw = (
            (yellow > self.yellow_threshold)
            & (green_balance > -0.02)
            & (green_balance < self.green_balance_max)
            & valid
        )
        if lesion_mask is not None:
            lesions = np.asarray(lesion_mask).astype(bool)
            if lesions.shape != valid.shape:
                raise ValueError("La máscara de lesión no coincide con la imagen.")
            raw &= ~lesions

        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        cleaned = cv2.morphologyEx(raw.astype(np.uint8), cv2.MORPH_OPEN, kernel)
        cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_CLOSE, kernel)
        mask, kept, rejected = _filter_components(cleaned, self.min_area_px)
        params = {
            "step": self.name,
            "yellow_threshold": self.yellow_threshold,
            "green_balance_max": self.green_balance_max,
            "min_area_px": self.min_area_px,
            "chlorosis_fraction": round(float(mask.mean()), 5),
            "components_kept": kept,
            "components_discarded": rejected,
        }
        layers = (
            Layer(
                key="core2_clorosis_puntaje",
                stage="segmentacion",
                title="Cromaticidad amarilla",
                caption=(
                    "min(r,g)−b mide el peso de rojo y verde frente al azul; "
                    "g−r dentro de una banda estrecha separa el amarillo del "
                    "verde y del pardo. La sombra uniforme conserva estas proporciones."
                ),
                image=render_score(
                    image, yellow, pivot=self.yellow_threshold, span=0.2, color=CHLOROSIS_RGB
                ),
            ),
            Layer(
                key="core2_clorosis_mascara",
                stage="segmentacion",
                title="Máscara Core2 de clorosis",
                caption=(
                    f"Cromaticidad amarilla > {self.yellow_threshold:.2f} y "
                    f"balance verde-rojo en (-0.02, {self.green_balance_max:.2f})."
                ),
                image=render_mask(mask, color=CHLOROSIS_RGB),
            ),
        )
        return ChlorosisResult(mask.astype(bool), params, layers)


def _normalize_luminance(
    image: np.ndarray, valid: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    lab = cv2.cvtColor(image, cv2.COLOR_RGB2LAB)
    luminance = lab[..., 0].astype(np.float32)
    sigma = _illumination_sigma(image)
    illumination = cv2.GaussianBlur(luminance, (0, 0), sigmaX=sigma)
    reference = float(np.median(illumination[valid]))
    normalized = np.clip(
        luminance * reference / np.maximum(illumination, 1.0), 0.0, 255.0
    )
    lab[..., 0] = normalized.astype(np.uint8)
    normalized_rgb = cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)
    return normalized, normalized_rgb, illumination


def _illumination_sigma(image: np.ndarray) -> float:
    return float(np.clip(max(image.shape[:2]) * 0.08, 12.0, 96.0))


def _filter_components(mask: np.ndarray, min_area: int) -> tuple[np.ndarray, int, int]:
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    kept = np.zeros(mask.shape, dtype=bool)
    kept_count = 0
    rejected_count = 0
    for label in range(1, count):
        area = int(stats[label, cv2.CC_STAT_AREA])
        width = int(stats[label, cv2.CC_STAT_WIDTH])
        height = int(stats[label, cv2.CC_STAT_HEIGHT])
        if area >= min_area and area / max(width * height, 1) >= 0.10:
            kept[labels == label] = True
            kept_count += 1
        else:
            rejected_count += 1
    return kept, kept_count, rejected_count


def _ellipse(size: int) -> np.ndarray:
    return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (size, size))


def _require_rgb(image: np.ndarray) -> None:
    if image.dtype != np.uint8 or image.ndim != 3 or image.shape[2] != 3:
        raise ValueError("Se esperaba una imagen RGB uint8 de H×W×3.")
