"""Overlay de máscaras para lectura humana.

Celebrimbor gobierna este módulo. Los colores y las opacidades provienen del
sistema visual (`docs/DESIGN.md`, `frontend/tokens.css`): lesión en terracota,
nervadura en oro viejo. La textura original debe seguir viéndose.

El overlay tiene dos modos. El básico mezcla las máscaras y no agrega nada: es
el que se usa para auditar píxeles. El anotado (``annotate=True``) agrega lo que
hace falta para leer la foto sin explicación: contorno de cada mancha, un número
en su interior y una leyenda con los tres tejidos. No cambia el tamaño de la
imagen: el resultado sigue midiendo lo mismo que la imagen analizada.
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

# Leyenda del overlay anotado: placa de tinta verde con texto en crema. Va sobre
# la foto, así que necesita contraste propio en cualquier iluminación.
LEGEND_PLATE_RGB = MASK_INK_RGB
LEGEND_TEXT_RGB = MASK_PAPER_RGB
# Enumerar más manchas de las que el ojo puede seguir tapa más de lo que aclara.
MAX_ANNOTATED_LESIONS = 24


def render_overlay(
    image: np.ndarray,
    lesion_mask: np.ndarray,
    vein_mask: np.ndarray | None = None,
    lesion_alpha: float = 0.55,
    vein_alpha: float = 0.35,
    chlorosis_mask: np.ndarray | None = None,
    annotate: bool = False,
) -> np.ndarray:
    """Devuelve una copia RGB con las máscaras mezcladas de forma legible.

    Con ``annotate=True`` agrega contorno y número a cada mancha y una leyenda
    con los tejidos detectados. El tamaño no cambia: la imagen sigue midiendo
    lo mismo que el recorte analizado.
    """
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

    rendered = np.clip(output, 0, 255).astype(np.uint8)
    if not annotate:
        return rendered
    return _annotate(
        rendered,
        lesions,
        has_veins=vein_mask is not None,
        has_chlorosis=chlorosis_mask is not None,
    )


def _annotate(
    image: np.ndarray,
    lesions: np.ndarray,
    *,
    has_veins: bool,
    has_chlorosis: bool,
) -> np.ndarray:
    """Contorno, número y leyenda sobre el overlay ya mezclado.

    El número se coloca en el punto más profundo de la mancha —el centro del
    disco más grande que cabe dentro— y no en el centroide, que puede caer fuera
    de una mancha en medialuna y dejar el número flotando sobre tejido sano.
    """
    output = image.copy()
    height, width = output.shape[:2]
    scale = float(np.clip(min(height, width) / 700.0, 0.45, 1.1))
    stroke = max(1, int(round(scale)))

    if lesions.any():
        contours, _ = cv2.findContours(
            lesions.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        cv2.drawContours(output, contours, -1, LESION_EDGE_RGB, stroke + 1, cv2.LINE_AA)

        count, labels, stats, _ = cv2.connectedComponentsWithStats(
            lesions.astype(np.uint8), connectivity=8
        )
        # De la mancha más grande a la más chica: el operario lee primero lo que
        # más pesa en el área medida.
        order = np.argsort(stats[1:count, cv2.CC_STAT_AREA])[::-1] + 1
        depth = cv2.distanceTransform(lesions.astype(np.uint8), cv2.DIST_L2, 5)
        for number, label in enumerate(order[:MAX_ANNOTATED_LESIONS], start=1):
            ys, xs = np.nonzero(labels == label)
            if xs.size == 0:  # pragma: no cover - connectedComponents no lo produce
                continue
            deepest = int(np.argmax(depth[ys, xs]))
            _put_tag(output, str(number), (int(xs[deepest]), int(ys[deepest])), scale)

    return _draw_legend(output, has_veins=has_veins, has_chlorosis=has_chlorosis, scale=scale)


def _put_tag(
    image: np.ndarray, text: str, center: tuple[int, int], scale: float
) -> None:
    """Número legible sobre cualquier fondo: crema con halo de tinta."""
    font = cv2.FONT_HERSHEY_SIMPLEX
    size = max(1, int(round(scale)))
    (text_width, text_height), baseline = cv2.getTextSize(text, font, 0.5 * scale, size)
    origin = (
        int(center[0]) - text_width // 2,
        int(center[1]) + (text_height + baseline) // 2,
    )
    cv2.putText(image, text, origin, font, 0.5 * scale, LESION_EDGE_RGB, size + 2, cv2.LINE_AA)
    cv2.putText(image, text, origin, font, 0.5 * scale, LEGEND_TEXT_RGB, size, cv2.LINE_AA)


def _draw_legend(
    image: np.ndarray,
    *,
    has_veins: bool,
    has_chlorosis: bool,
    scale: float,
) -> np.ndarray:
    """Placa con un color y una palabra por tejido detectado, abajo a la izquierda.

    Los rótulos van sin tildes a propósito: ``cv2.putText`` solo dibuja ASCII.
    """
    # «lesion» sin tilde: la placa se dibuja con ``putText``, que solo hace ASCII,
    # y el rótulo tiene que decir lo mismo que la leyenda de la página.
    entries: list[tuple[str, tuple[int, int, int]]] = [("lesion", LESION_RGB)]
    if has_veins:
        entries.append(("nervadura", VEIN_RGB))
    if has_chlorosis:
        entries.append(("clorosis", CHLOROSIS_RGB))

    font = cv2.FONT_HERSHEY_SIMPLEX
    text_scale = 0.5 * scale
    text_size = max(1, int(round(scale)))
    pad = max(4, int(round(8 * scale)))
    swatch = max(8, int(round(16 * scale)))
    row = max(14, int(round(24 * scale)))

    widths = [
        cv2.getTextSize(label, font, text_scale, text_size)[0][0] + swatch + 3 * pad
        for label, _ in entries
    ]
    plate_width = max(widths) + pad
    plate_height = row * len(entries) + pad

    height, width = image.shape[:2]
    x0 = pad
    y0 = height - plate_height - pad
    x1 = min(width, x0 + plate_width)
    y1 = min(height, y0 + plate_height)
    if x1 <= x0 or y1 <= y0:  # pragma: no cover - imagen más chica que la placa
        return image

    # Placa semitransparente: se lee la leyenda y todavía se adivina la hoja.
    region = image[y0:y1, x0:x1].astype(np.float32)
    image[y0:y1, x0:x1] = _blend(
        region.reshape(-1, 3), LEGEND_PLATE_RGB, 0.82
    ).reshape(region.shape).astype(np.uint8)

    for index, (label, color) in enumerate(entries):
        top = y0 + pad // 2 + index * row
        bottom = min(y1 - pad // 2, top + swatch)
        left = x0 + pad
        cv2.rectangle(
            image, (left, top), (left + swatch, bottom), color, cv2.FILLED, cv2.LINE_AA
        )
        origin = (
            left + swatch + pad,
            top + (bottom - top) // 2 + int(text_size * 4.5 * text_scale),
        )
        cv2.putText(
            image, label, origin, font, text_scale, LEGEND_TEXT_RGB, text_size, cv2.LINE_AA
        )
    return image


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
