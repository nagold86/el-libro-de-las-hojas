"""Puerta de dominio: ¿esto es superficie de hoja?

Boromir gobierna este módulo. Antes de medir una lesión hay que saber si la
imagen pertenece al dominio: un documento, una pared, el cielo o una mano no
tienen lesiones, tienen otra cosa. El criterio es una envolvente de rasgos
interpretables calibrada sobre hojas reales; no hay modelo aprendido.

La puerta no mide ni segmenta: acepta o rechaza, y cuando rechaza explica qué
rasgo quedó fuera para que el veredicto se pueda discutir.

Los rasgos se miden sobre la imagen original, antes del balance de blancos: una
escena dominada por verde puede quedar neutralizada por el preproceso y la hoja
volverse invisible para la compuerta.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import cv2
import numpy as np


@dataclass(frozen=True)
class DomainThresholds:
    """Envolvente de rasgos. Un valor fuera de rango es un síntoma, no un veredicto.

    Los umbrales de color son deliberadamente flojos: una hoja necrótica o
    clorótica sigue siendo una hoja. El peso del rechazo queda en la textura y
    la entropía, que una pared, un documento o el cielo no imitan.

    Se aplican sobre píxeles originales, no balanceados: el gray-world del
    preproceso reparte el verde de un primer plano entre los tres canales y
    puede dejar una hoja legítima por debajo de cualquier umbral de color.
    """

    min_exg: float = 0.10
    min_green_fraction: float = 0.55
    min_green_hue_fraction: float = 0.50
    max_bright_fraction: float = 0.30
    min_local_variance: float = 2.0
    max_local_variance: float = 400.0
    min_entropy: float = 5.5
    max_entropy: float = 8.0
    allowed_violations: int = 1

    def __post_init__(self) -> None:
        for name in ("min_exg", "min_green_fraction", "min_green_hue_fraction", "max_bright_fraction"):
            value = getattr(self, name)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} debe estar en [0, 1].")
        if self.min_local_variance < 0:
            raise ValueError("min_local_variance debe ser >= 0.")
        if self.min_local_variance >= self.max_local_variance:
            raise ValueError("El rango de varianza local está invertido.")
        if not 0.0 <= self.min_entropy < self.max_entropy <= 8.0:
            raise ValueError("El rango de entropía debe cumplir 0 <= min < max <= 8.")
        if self.allowed_violations < 0:
            raise ValueError("allowed_violations debe ser >= 0.")


@dataclass(frozen=True)
class DomainReport:
    gate: str
    in_domain: bool
    score: int
    features: dict[str, float]
    reasons: tuple[str, ...]


class DomainGate(ABC):
    """Contrato de validación de dominio."""

    name: str

    @abstractmethod
    def evaluate(self, image: np.ndarray, valid_mask: np.ndarray) -> DomainReport:
        """Devuelve el veredicto y los rasgos que lo sostienen."""


class LeafDomainGate(DomainGate):
    """Acepta si la mayoría de los rasgos cae dentro de la envolvente foliar.

    Espera la imagen original con la máscara de píxeles confiables; el
    orquestador no debe pasarle la versión balanceada.
    """

    name = "envelope_v1"

    def __init__(self, thresholds: DomainThresholds | None = None) -> None:
        self.thresholds = thresholds or DomainThresholds()

    def evaluate(self, image: np.ndarray, valid_mask: np.ndarray) -> DomainReport:
        _require_rgb(image)
        valid = np.asarray(valid_mask)
        if valid.shape != image.shape[:2]:
            raise ValueError("La máscara válida no coincide con la imagen.")
        valid = valid.astype(bool)

        if int(valid.sum()) < 100:
            return DomainReport(
                gate=self.name,
                in_domain=False,
                score=1,
                features={},
                reasons=("no hay píxeles válidos suficientes para decidir",),
            )

        features = _measure(image, valid)
        reasons = _violations(features, self.thresholds)
        return DomainReport(
            gate=self.name,
            in_domain=len(reasons) <= self.thresholds.allowed_violations,
            score=len(reasons),
            features=features,
            reasons=tuple(reasons),
        )


def _measure(image: np.ndarray, valid: np.ndarray) -> dict[str, float]:
    rgb = image.astype(np.float32)
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    exg = (2.0 * rgb[..., 1] - rgb[..., 0] - rgb[..., 2]) / 255.0
    hsv = cv2.cvtColor(image, cv2.COLOR_RGB2HSV)
    hue, saturation = hsv[..., 0], hsv[..., 1]

    values = gray.astype(np.float64)
    mean = cv2.blur(values, (5, 5))
    square_mean = cv2.blur(values * values, (5, 5))
    variance = np.clip(square_mean - mean * mean, 0.0, None)

    histogram = np.bincount(gray[valid].ravel(), minlength=256).astype(np.float64)
    probabilities = histogram / max(float(histogram.sum()), 1.0)
    nonzero = probabilities[probabilities > 0]
    entropy = float(-(nonzero * np.log2(nonzero)).sum())

    return {
        "exg_mean": round(float(exg[valid].mean()), 4),
        "green_fraction": round(float((exg[valid] > 0.05).mean()), 4),
        "green_hue_fraction": round(
            float(
                (
                    (hue[valid] >= 30)
                    & (hue[valid] <= 95)
                    & (saturation[valid] >= 40)
                ).mean()
            ),
            4,
        ),
        "bright_fraction": round(float((gray[valid] > 220).mean()), 4),
        "local_variance": round(float(variance[valid].mean()), 3),
        "entropy": round(entropy, 4),
    }


def _violations(features: dict[str, float], limits: DomainThresholds) -> list[str]:
    """Traduce cada rasgo fuera de envolvente a un motivo legible."""
    reasons: list[str] = []

    if features["exg_mean"] < limits.min_exg:
        reasons.append(
            f"verde insuficiente: ExG medio {features['exg_mean']:.3f} "
            f"(mínimo {limits.min_exg:.2f})"
        )
    if features["green_fraction"] < limits.min_green_fraction:
        reasons.append(
            f"poca superficie verde: {features['green_fraction']:.1%} "
            f"(mínimo {limits.min_green_fraction:.0%})"
        )
    if features["green_hue_fraction"] < limits.min_green_hue_fraction:
        reasons.append(
            f"matiz verde insuficiente: {features['green_hue_fraction']:.1%} "
            f"(mínimo {limits.min_green_hue_fraction:.0%})"
        )
    if features["bright_fraction"] > limits.max_bright_fraction:
        reasons.append(
            f"demasiado brillo: {features['bright_fraction']:.1%} "
            f"(máximo {limits.max_bright_fraction:.0%})"
        )
    if features["local_variance"] < limits.min_local_variance:
        reasons.append(
            f"textura plana: varianza local {features['local_variance']:.2f} "
            f"(mínimo {limits.min_local_variance:.1f})"
        )
    elif features["local_variance"] > limits.max_local_variance:
        reasons.append(
            f"textura de ruido: varianza local {features['local_variance']:.0f} "
            f"(máximo {limits.max_local_variance:.0f})"
        )
    if not limits.min_entropy <= features["entropy"] <= limits.max_entropy:
        reasons.append(
            f"entropía fuera de rango: {features['entropy']:.2f} bits "
            f"(esperado {limits.min_entropy:.1f}–{limits.max_entropy:.1f})"
        )
    return reasons


def _require_rgb(image: np.ndarray) -> None:
    if image.dtype != np.uint8 or image.ndim != 3 or image.shape[2] != 3:
        raise ValueError("Se esperaba una imagen RGB uint8 de H×W×3.")
