"""Overlay de máscaras para lectura humana.

Celebrimbor gobierna este módulo. Los colores y las opacidades provienen del
sistema visual (`docs/DESIGN.md`, `frontend/tokens.css`): lesión en terracota,
nervadura en oro viejo. La textura original debe seguir viéndose.
"""

from __future__ import annotations

import cv2
import numpy as np

# Tokens de datos, en RGB. Deben coincidir con --data-lesion / --data-vein.
LESION_RGB = (166, 62, 36)      # #A63E24 — --data-lesion
LESION_EDGE_RGB = (122, 31, 20)  # #7A1F14 — --data-lesion-edge
VEIN_RGB = (201, 162, 39)       # #C9A227 — --data-vein


def render_overlay(
    image: np.ndarray,
    lesion_mask: np.ndarray,
    vein_mask: np.ndarray | None = None,
    lesion_alpha: float = 0.55,
    vein_alpha: float = 0.35,
) -> np.ndarray:
    """Devuelve una copia RGB con las máscaras mezcladas de forma legible."""
    if image.dtype != np.uint8 or image.ndim != 3 or image.shape[2] != 3:
        raise ValueError("Se esperaba una imagen RGB uint8 de H×W×3.")
    if not 0.0 <= lesion_alpha <= 1.0 or not 0.0 <= vein_alpha <= 1.0:
        raise ValueError("Las opacidades deben estar en [0, 1].")

    lesions = np.asarray(lesion_mask).astype(bool)
    if lesions.shape != image.shape[:2]:
        raise ValueError("La máscara de lesión no coincide con la imagen.")

    output = image.astype(np.float32)

    if vein_mask is not None:
        veins = np.asarray(vein_mask).astype(bool)
        if veins.shape != image.shape[:2]:
            raise ValueError("La máscara de nervadura no coincide con la imagen.")
        if veins.any():
            output[veins] = _blend(output[veins], VEIN_RGB, vein_alpha)

    if lesions.any() and lesion_alpha > 0.0:
        output[lesions] = _blend(output[lesions], LESION_RGB, lesion_alpha)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        interior = cv2.erode(lesions.astype(np.uint8), kernel).astype(bool)
        edge = lesions & ~interior
        if edge.any():
            output[edge] = _blend(output[edge], LESION_EDGE_RGB, 0.85)

    return np.clip(output, 0, 255).astype(np.uint8)


def _blend(region: np.ndarray, color: tuple[int, int, int], alpha: float) -> np.ndarray:
    return region * (1.0 - alpha) + np.array(color, dtype=np.float32) * alpha
