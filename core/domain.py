"""Puerta de dominio: ¿esto es superficie de hoja?

Boromir gobierna este módulo. La compuerta corre sobre el recorte que devolvió el
aislamiento, no sobre la escena completa: cuando llega acá el fondo ya se fue y
lo que queda debería ser hoja. Por eso no pregunta «¿hay verde en la foto?» sino
«¿este recorte tiene aspecto de tejido de hoja?».

El tejido de hoja abarca del verde al ocre: una hoja sana, una clorótica y una
curada son el mismo producto en distinto punto de secado. Pedir verde dejaba
afuera justamente las hojas secas, que son las que se clasifican (ADR-023). El
peso del rechazo queda en la textura y la entropía, que una pared, un documento
o el cielo no imitan.

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

# Lado al que se lleva la textura antes de medirla. Una hoja de 165 px y una de
# 1100 px tienen que juzgarse con la misma vara: sin esto el grano de una foto
# chica se lee como «textura de ruido» y la hoja se rechaza por su resolución, no
# por su aspecto.
TEXTURE_REFERENCE_SIDE = 600
TEXTURE_WINDOW = 5

# Familia de matices del tejido de hoja, en HSV de OpenCV (0–179): del ocre (5,
# ≈10°) al verde azulado (95, ≈190°). Fuera quedan el cielo y el azul; el gris
# sin croma no entra porque exige saturación.
TISSUE_HUE_RANGE = (5, 95)
TISSUE_MIN_SATURATION = 40


@dataclass(frozen=True)
class DomainThresholds:
    """Envolvente de rasgos. Un valor fuera de rango es un síntoma, no un veredicto.

    El color se juzga como familia —tejido de hoja, del ocre al verde— y no como
    exigencia de verde: una hoja seca sigue siendo hoja. El peso del rechazo
    queda en la textura y la entropía, que una pared, un documento o el cielo no
    imitan.

    Se aplican sobre píxeles originales, no balanceados: el gray-world del
    preproceso reparte el verde de un primer plano entre los tres canales y
    puede dejar una hoja legítima por debajo de cualquier umbral de color.
    """

    # Medido sobre hoja real: una hoja muy curada llega a 0.54 y un primer plano
    # sano a 1.00. El límite queda en 0.45 para no depender de la tolerancia; el
    # cielo y el fondo sin croma marcan 0.00.
    min_tissue_fraction: float = 0.45
    max_bright_fraction: float = 0.30
    min_local_variance: float = 2.0
    max_local_variance: float = 400.0
    min_entropy: float = 5.5
    max_entropy: float = 8.0
    allowed_violations: int = 1

    def __post_init__(self) -> None:
        for name in ("min_tissue_fraction", "max_bright_fraction"):
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
    """Rasgos del recorte. Los de textura se miden a tamaño de referencia."""
    rgb = image.astype(np.float32)
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    exg = (2.0 * rgb[..., 1] - rgb[..., 0] - rgb[..., 2]) / 255.0
    hsv = cv2.cvtColor(image, cv2.COLOR_RGB2HSV)
    hue, saturation = hsv[..., 0], hsv[..., 1]

    tissue = (
        (hue >= TISSUE_HUE_RANGE[0])
        & (hue <= TISSUE_HUE_RANGE[1])
        & (saturation >= TISSUE_MIN_SATURATION)
    )

    texture_gray, texture_valid = _texture_view(gray, valid)
    variance = _local_variance(texture_gray)[texture_valid]

    return {
        # Fracción de píxeles con croma de tejido de hoja: verde, amarillo u ocre.
        # Es el rasgo de color que decide; el ExG queda como lectura de apoyo.
        "tissue_fraction": round(float(tissue[valid].mean()), 4),
        "green_fraction": round(float((exg[valid] > 0.05).mean()), 4),
        "exg_mean": round(float(exg[valid].mean()), 4),
        "bright_fraction": round(float((gray[valid] > 220).mean()), 4),
        "local_variance": round(float(variance.mean()), 3),
        "entropy": round(_entropy(texture_gray[texture_valid]), 4),
    }


def _texture_view(gray: np.ndarray, valid: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Lleva la textura a un tamaño de referencia, venga la foto grande o chica.

    Agrandar suaviza el grano de una foto chica y achicar promedia el de una
    grande, así que después de esto un tejido parecido mide parecido. Sin esta
    normalización el límite superior dependía de la resolución del archivo.
    """
    height, width = gray.shape
    side = min(height, width)
    if side <= 0:
        return gray, valid
    scale = TEXTURE_REFERENCE_SIDE / float(side)
    if abs(scale - 1.0) < 0.05:
        return gray, valid
    size = (max(8, round(width * scale)), max(8, round(height * scale)))
    interpolation = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LINEAR
    resized = cv2.resize(gray, size, interpolation=interpolation)
    mask = cv2.resize(valid.astype(np.uint8), size, interpolation=cv2.INTER_NEAREST)
    resized_mask = mask.astype(bool)
    if int(resized_mask.sum()) < 100:  # pragma: no cover - el recorte trae superficie
        return gray, valid
    return resized, resized_mask


def _local_variance(gray: np.ndarray) -> np.ndarray:
    """Varianza en ventana chica: distingue tejido de pared y de ruido."""
    values = gray.astype(np.float64)
    mean = cv2.blur(values, (TEXTURE_WINDOW, TEXTURE_WINDOW))
    square_mean = cv2.blur(values * values, (TEXTURE_WINDOW, TEXTURE_WINDOW))
    return np.clip(square_mean - mean * mean, 0.0, None)


def _entropy(values: np.ndarray) -> float:
    histogram = np.bincount(values.ravel(), minlength=256).astype(np.float64)
    probabilities = histogram / max(float(histogram.sum()), 1.0)
    nonzero = probabilities[probabilities > 0]
    # El + 0.0 convierte el -0.0 de una imagen de un solo nivel en 0.0, que es lo
    # que se lee en la traza.
    return float(-(nonzero * np.log2(nonzero)).sum()) + 0.0


def _violations(features: dict[str, float], limits: DomainThresholds) -> list[str]:
    """Traduce cada rasgo fuera de envolvente a un motivo legible."""
    reasons: list[str] = []

    if features["tissue_fraction"] < limits.min_tissue_fraction:
        reasons.append(
            f"tejido fuera de la familia foliar: {features['tissue_fraction']:.1%} "
            f"(mínimo {limits.min_tissue_fraction:.0%})"
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
