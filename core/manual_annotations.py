"""Apply human brush strokes as overrides to automatic tissue masks."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import cv2
import numpy as np

from core.descriptors import Describer
from core.layers import Layer
from core.morphometry import Measurer
from core.orchestrator import InspectionResult
from core.render import render_overlay

LABELS = {"healthy": 0, "diseased": 1, "chlorosis": 2, "erase": 255}


def apply_manual_annotations(
    result: InspectionResult,
    strokes: list[dict[str, Any]],
    measurer: Measurer,
    describer: Describer,
) -> InspectionResult:
    """Apply ordered healthy/lesion/chlorosis overrides and recompute measures.

    Eraser strokes restore the automatic mask at those pixels. All coordinates
    and brush widths are normalized to the analyzed image dimensions.
    """
    labels = _rasterize(result.image.shape[:2], strokes)
    healthy = labels == LABELS["healthy"]
    diseased = labels == LABELS["diseased"]
    chlorotic = labels == LABELS["chlorosis"]
    if not (healthy.any() or diseased.any() or chlorotic.any()):
        return result

    lesion_mask = result.lesion_mask.copy()
    chlorosis_mask = result.chlorosis_mask.copy()
    lesion_mask[healthy | chlorotic] = False
    lesion_mask[diseased] = True
    chlorosis_mask[healthy | diseased] = False
    chlorosis_mask[chlorotic] = True
    lesion_mask &= result.valid_mask
    chlorosis_mask &= result.valid_mask

    lesions = measurer.measure(lesion_mask, result.vein_mask, result.valid_mask)
    chlorosis = measurer.measure(chlorosis_mask, result.vein_mask, result.valid_mask)
    appearance = describer.describe(result.image, lesion_mask, result.valid_mask)
    segmentation = {
        **result.segmentation,
        "manual_annotations_applied": True,
        "manual_healthy_px": int(healthy.sum()),
        "manual_lesion_px": int(diseased.sum()),
        "manual_chlorosis_px": int(chlorotic.sum()),
        "lesion_fraction": round(float(lesion_mask.mean()), 5),
        "lesion_fraction_valid": round(
            float(lesion_mask.sum()) / max(int(result.valid_mask.sum()), 1), 5
        ),
        "components_kept": lesions.count,
    }
    chlorosis_params = {
        **result.chlorosis_params,
        "manual_annotations_applied": True,
        "chlorosis_fraction": round(float(chlorosis_mask.mean()), 5),
        "chlorosis_fraction_valid": round(
            float(chlorosis_mask.sum()) / max(int(result.valid_mask.sum()), 1), 5
        ),
    }
    manual_layer = Layer(
        key="edicion_manual_mascaras",
        stage="segmentacion",
        title="Máscaras corregidas manualmente",
        caption=(
            "Las zonas sanas eliminan ambas clases; lesión y clorosis fuerzan su "
            "máscara correspondiente. El borrador devuelve la clasificación "
            "automática original. Las medidas y el informe usan estas máscaras."
        ),
        image=render_overlay(
            result.image,
            lesion_mask,
            result.vein_mask,
            chlorosis_mask=chlorosis_mask,
        ),
    )
    return replace(
        result,
        lesions=lesions,
        chlorosis=chlorosis,
        appearance=appearance,
        segmentation=segmentation,
        chlorosis_params=chlorosis_params,
        lesion_mask=lesion_mask,
        chlorosis_mask=chlorosis_mask,
        layers=(*result.layers, manual_layer),
    )


def _rasterize(shape: tuple[int, int], strokes: list[dict[str, Any]]) -> np.ndarray:
    height, width = shape
    labels = np.full(shape, 255, dtype=np.uint8)
    brush_scale = min(height, width)
    for stroke in strokes:
        value = LABELS.get(str(stroke.get("label")))
        points = stroke.get("points") or []
        if value is None or not points:
            continue
        thickness = max(1, int(round(float(stroke.get("width", 0.01)) * brush_scale)))
        pixels = [
            (
                int(round(float(point["x"]) * (width - 1))),
                int(round(float(point["y"]) * (height - 1))),
            )
            for point in points
        ]
        if len(pixels) == 1:
            cv2.circle(labels, pixels[0], max(1, thickness // 2), int(value), -1)
            continue
        for start, end in zip(pixels, pixels[1:], strict=False):
            cv2.line(labels, start, end, int(value), thickness, cv2.LINE_8)
        radius = max(1, thickness // 2)
        cv2.circle(labels, pixels[0], radius, int(value), -1)
        cv2.circle(labels, pixels[-1], radius, int(value), -1)
    return labels
