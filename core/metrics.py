"""Acuerdo entre la máscara de lesión y una referencia anotada a mano.

Boromir gobierna este módulo. El área relativa no dice si una segmentación está
bien: dice cuánto marcó. El veredicto necesita una referencia humana por hoja y
métricas de solapamiento. Sin referencia, cualquier ajuste de umbral es a ciegas.

Convenciones:
- Ambas máscaras son H×W; se convierten a booleano.
- Dos máscaras vacías son acuerdo perfecto (IoU 1.0), no un caso indefinido.
- ``precision`` castiga el exceso (marca sana como lesión) y ``recall`` el
  defecto (pierde la mancha). Se publican juntas porque el área puede coincidir
  con el error compensado.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass(frozen=True)
class MaskAgreement:
    """Solapamiento entre lo predicho y lo anotado."""

    intersection: int
    union: int
    predicted: int
    reference: int
    iou: float
    dice: float
    precision: float
    recall: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "intersection": self.intersection,
            "union": self.union,
            "predicted": self.predicted,
            "reference": self.reference,
            "iou": self.iou,
            "dice": self.dice,
            "precision": self.precision,
            "recall": self.recall,
        }


def compare_masks(predicted: np.ndarray, reference: np.ndarray) -> MaskAgreement:
    """Compara una máscara contra la referencia anotada para la misma imagen."""
    pred = _as_mask(predicted, "predicha")
    truth = _as_mask(reference, "referencia")
    if pred.shape != truth.shape:
        raise ValueError(
            f"Las máscaras no coinciden en tamaño: {pred.shape} contra {truth.shape}."
        )

    predicted_px = int(pred.sum())
    reference_px = int(truth.sum())
    intersection = int(np.logical_and(pred, truth).sum())
    union = predicted_px + reference_px - intersection

    return MaskAgreement(
        intersection=intersection,
        union=union,
        predicted=predicted_px,
        reference=reference_px,
        iou=round(_ratio(intersection, union, empty=1.0), 6),
        dice=round(_ratio(2 * intersection, predicted_px + reference_px, empty=1.0), 6),
        precision=round(_ratio(intersection, predicted_px), 6),
        recall=round(_ratio(intersection, reference_px), 6),
    )


def _ratio(numerator: int, denominator: int, empty: float = 0.0) -> float:
    """Cociente con denominador vacío explícito: 0 px no es un error de cálculo."""
    return float(numerator) / float(denominator) if denominator else empty


def _as_mask(array: np.ndarray, label: str) -> np.ndarray:
    mask = np.asarray(array)
    if mask.ndim != 2:
        raise ValueError(f"La máscara {label} debe ser 2D, no {mask.ndim}D.")
    return mask.astype(bool)
