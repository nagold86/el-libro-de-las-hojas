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

# Tokens de las capas de procesamiento (lectura interna, no del overlay final).
MASK_INK_RGB = (44, 74, 51)     # #2C4A33 — --moss-800: superficie detectada
MASK_PAPER_RGB = (255, 252, 242)  # #FFFCF2 — --cream-50: fondo de la máscara
DISCARD_RGB = (138, 124, 94)    # #8A7C5E — --edge-500: componente descartado
# Halo recuperado por histéresis: LESION_RGB al 45 % sobre MASK_PAPER_RGB. No es
# un color nuevo, es la terracota de lesión con menos tinta.
HALO_RGB = (215, 166, 149)
# Clorosis: (217, 164, 65) = #D9A441 = --honey-500. Ni oro de nervadura ni
# terracota de lesión: es la tercera familia de tejido.
CHLOROSIS_RGB = (217, 164, 65)


def render_overlay(
    image: np.ndarray,
    lesion_mask: np.ndarray,
    vein_mask: np.ndarray | None = None,
    lesion_alpha: float = 0.55,
    vein_alpha: float = 0.35,
    chlorosis_mask: np.ndarray | None = None,
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

    if chlorosis_mask is not None:
        chlorosis = np.asarray(chlorosis_mask).astype(bool)
        if chlorosis.shape != image.shape[:2]:
            raise ValueError("La máscara de clorosis no coincide con la imagen.")
        # Trama diagonal en vez de relleno: la clorosis se solapa casi siempre
        # con la lesión, y un relleno quedaría tapado por la terracota.
        if chlorosis.any():
            height, width = chlorosis.shape
            rows = np.arange(height)[:, None]
            cols = np.arange(width)[None, :]
            dots = chlorosis & (((rows + cols) % 6) == 0)
            output[dots] = _blend(output[dots], CHLOROSIS_RGB, 0.9)

    return np.clip(output, 0, 255).astype(np.uint8)


def render_mask(
    mask: np.ndarray,
    color: tuple[int, int, int] = MASK_INK_RGB,
    paper: tuple[int, int, int] = MASK_PAPER_RGB,
) -> np.ndarray:
    """Máscara booleana como imagen RGB legible: tinta sobre papel."""
    values = np.asarray(mask).astype(bool)
    if values.ndim != 2:
        raise ValueError("Se esperaba una máscara 2D.")
    output = np.empty(values.shape + (3,), dtype=np.uint8)
    output[...] = np.array(paper, dtype=np.uint8)
    output[values] = np.array(color, dtype=np.uint8)
    return output


def render_components(
    kept: np.ndarray, discarded: np.ndarray
) -> np.ndarray:
    """Componentes conservados en terracota y descartados en gris neutro."""
    kept_mask = np.asarray(kept).astype(bool)
    discarded_mask = np.asarray(discarded).astype(bool)
    if kept_mask.shape != discarded_mask.shape:
        raise ValueError("Las dos máscaras deben tener la misma forma.")
    output = render_mask(discarded_mask, color=DISCARD_RGB)
    output[kept_mask] = np.array(LESION_RGB, dtype=np.uint8)
    return output


def render_growth(seeds: np.ndarray, grown: np.ndarray) -> np.ndarray:
    """Núcleo estricto en terracota plena y halo recuperado en terracota lavada.

    Sirve para auditar la histéresis: lo que se ve en tinta llena lo decidió el
    umbral estricto; lo que se ve lavado lo agregó el crecimiento.
    """
    seed_mask = np.asarray(seeds).astype(bool)
    grown_mask = np.asarray(grown).astype(bool)
    if seed_mask.shape != grown_mask.shape:
        raise ValueError("Las dos máscaras deben tener la misma forma.")
    output = render_mask(grown_mask & ~seed_mask, color=HALO_RGB)
    output[seed_mask] = np.array(LESION_RGB, dtype=np.uint8)
    return output


def render_score(
    image: np.ndarray,
    score: np.ndarray,
    pivot: float = 0.0,
    span: float = 0.35,
    alpha: float = 0.85,
    color: tuple[int, int, int] = LESION_RGB,
) -> np.ndarray:
    """Pinta el puntaje de un detector sobre la imagen en escala de grises.

    ``score`` es adimensional y continuo; ``pivot`` es el valor que se declara
    "sin evidencia" y ``span`` la distancia a la que la marca satura. La marca
    usa la terracota de lesión para que el ojo la lea como el mismo dato.
    """
    if image.dtype != np.uint8 or image.ndim != 3 or image.shape[2] != 3:
        raise ValueError("Se esperaba una imagen RGB uint8 de H×W×3.")
    values = np.asarray(score, dtype=np.float32)
    if values.shape != image.shape[:2]:
        raise ValueError("El puntaje no coincide con la imagen.")
    if span <= 0:
        raise ValueError("span debe ser positivo.")

    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    base = cv2.cvtColor(gray, cv2.COLOR_GRAY2RGB).astype(np.float32) * 0.72
    weight = np.clip((values - pivot) / span, 0.0, 1.0) * alpha
    weight = weight[..., None]
    tinted = base * (1.0 - weight) + np.array(color, dtype=np.float32) * weight
    return np.clip(tinted, 0, 255).astype(np.uint8)


def to_rgb(image: np.ndarray) -> np.ndarray:
    """Prepara una capa para PNG: el gris se replica a tres canales."""
    values = np.asarray(image)
    if values.ndim == 3 and values.shape[2] == 3:
        return values.astype(np.uint8, copy=False)
    if values.ndim == 2:
        return cv2.cvtColor(values.astype(np.uint8, copy=False), cv2.COLOR_GRAY2RGB)
    raise ValueError("Se esperaba una capa H×W o H×W×3.")


def _blend(region: np.ndarray, color: tuple[int, int, int], alpha: float) -> np.ndarray:
    return region * (1.0 - alpha) + np.array(color, dtype=np.float32) * alpha
