"""Aislamiento de la hoja respecto del fondo.

Legolas gobierna este módulo. La etapa separa **una hoja dominante** del fondo
que la rodea; no identifica especies ni recorta lesiones.

El criterio viejo pedía verde: una hoja clorótica, una hoja seca o una foto con
luz cálida caían fuera y el pipeline decía «no es una hoja». El criterio nuevo
(ADR-020) no pregunta de qué color es la hoja sino **cuánto se diferencia del
fondo**:

1. Se modela el fondo con los píxeles del borde y de las esquinas: su color
   mediano en Lab y su dispersión robusta (MAD). Nada de promedios globales.
2. Cada píxel recibe una **distancia al fondo** normalizada por esa dispersión.
   Un píxel es candidato si está lejos del fondo, o si tiene exceso de verde
   (una hoja muy parecida a la mesa igual se reconoce por su color).
3. Se descartan los candidatos que tocan el borde (eso es fondo, no objeto) y
   los trazos finos (texto, cables, sombras alargadas).
4. El componente más grande se refina con GrabCut, que ajusta el borde por color
   local en vez de por umbral global.
5. Se recorta con un margen pequeño, se rellena el interior y se devuelve la
   máscara. Si la hoja ocupa casi todo el cuadro, no se recorta nada.

La decisión y sus límites están en ``docs/DECISIONES.md`` (ADR-009 y ADR-020).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np

from core.layers import Layer
from core.render import MASK_INK_RGB, render_mask, render_score

# Rango de tono que se considera tejido vegetal (verde a amarillo).
GREEN_HUE = (10, 115)
GREEN_MIN_SATURATION = 20
GREEN_MIN_EXG = 0.01

# Una región de hoja no es un trazo: se exige un mínimo de espesor y de relleno.
MIN_ASPECT = 0.10
MIN_FILL = 0.25
# Espesor mínimo, en fracción del lado menor, para no confundir texto, cables o el
# borde de la mesa con una hoja. Se mide la transformada de distancia (el radio
# del disco más grande que cabe dentro del objeto) y no la relación de aspecto:
# una mancha alargada sigue siendo hoja, una línea de texto nunca lo es.
MIN_BODY_FRACTION = 0.025


@dataclass(frozen=True)
class IsolationReport:
    """Procedencia del recorte, sin máscaras: es lo que viaja en el trace."""

    method: str
    source_width: int
    source_height: int
    analysis_width: int
    analysis_height: int
    bbox: tuple[int, int, int, int]
    prior_fraction: float
    leaf_fraction: float
    components: int
    warnings: tuple[str, ...] = ()
    # Retrato del fondo que se descontó y del umbral que se aplicó. Sin esto el
    # recorte no se puede discutir.
    background_lab: tuple[float, float, float] = ()
    threshold: float = 0.0
    foreground_fraction: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "method": self.method,
            "source": {"width": self.source_width, "height": self.source_height},
            "analysis": {
                "width": self.analysis_width,
                "height": self.analysis_height,
            },
            "bbox": list(self.bbox),
            "prior_fraction": round(self.prior_fraction, 4),
            "leaf_fraction": round(self.leaf_fraction, 4),
            "components": self.components,
            "background_lab": [round(value, 2) for value in self.background_lab],
            "threshold": round(self.threshold, 2),
            "foreground_fraction": round(self.foreground_fraction, 4),
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class IsolationResult:
    """Imagen recortada, máscara de hoja y procedencia."""

    image: np.ndarray
    mask: np.ndarray
    report: IsolationReport
    # Capas visibles de la etapa: candidatos, distancia al fondo, máscara y recorte.
    layers: tuple[Layer, ...] = ()

    @property
    def has_leaf(self) -> bool:
        return bool(self.mask.any())


@dataclass(frozen=True)
class _Foreground:
    """Resultado interno de la separación gruesa, antes de GrabCut."""

    candidate: np.ndarray
    foreground: np.ndarray
    distance: np.ndarray
    threshold: float
    background_lab: tuple[float, float, float]
    components: int
    warnings: tuple[str, ...]


class LeafIsolator:
    """Separa una hoja dominante del fondo por color de contraste y GrabCut."""

    name = "background_contrast_grabcut"

    def __init__(
        self,
        max_side: int = 1100,
        closeup_fraction: float = 0.97,
        min_leaf_fraction: float = 0.005,
        sensitivity: float = 1.0,
        crop_margin_fraction: float = 0.02,
        rng_seed: int = 0,
    ) -> None:
        if max_side < 64:
            raise ValueError("max_side debe ser >= 64.")
        if not 0.0 < closeup_fraction <= 1.0:
            raise ValueError("closeup_fraction debe estar en (0, 1].")
        if not 0.0 < min_leaf_fraction < 1.0:
            raise ValueError("min_leaf_fraction debe estar en (0, 1).")
        if not 0.1 <= sensitivity <= 10.0:
            raise ValueError("sensitivity debe estar en [0.1, 10].")
        if not 0.0 <= crop_margin_fraction <= 0.2:
            raise ValueError("crop_margin_fraction debe estar en [0, 0.2].")
        if rng_seed < 0:
            raise ValueError("rng_seed debe ser >= 0.")
        self.max_side = int(max_side)
        self.closeup_fraction = float(closeup_fraction)
        self.min_leaf_fraction = float(min_leaf_fraction)
        self.sensitivity = float(sensitivity)
        self.crop_margin_fraction = float(crop_margin_fraction)
        self.rng_seed = int(rng_seed)

    # -- Etapa pública ---------------------------------------------------
    def isolate(self, image: np.ndarray) -> IsolationResult:
        _require_rgb(image)
        height, width = image.shape[:2]

        # Las imágenes minúsculas no tienen fondo suficiente para modelar;
        # que decidan la puerta de calidad y la compuerta de dominio.
        if min(height, width) < 48:
            return self._all_leaf(image, method="primer_plano", prior_fraction=1.0)

        small = _downscale(image, self.max_side)
        coarse = _foreground(small, self.sensitivity)

        prior_layer = Layer(
            key="aislamiento_prior",
            stage="aislamiento",
            title="Candidatos de hoja",
            caption=(
                "Píxeles que se diferencian del fondo o tienen exceso de verde. "
                "Es una pista de color, no una lesión: todavía incluye fondo "
                "parecido y sombras."
            ),
            image=render_mask(_fit(coarse.candidate, (height, width))),
        )
        background_layer = Layer(
            key="aislamiento_fondo",
            stage="aislamiento",
            title="Distancia al fondo",
            caption=(
                "Cuánto se aleja cada píxel del color medido en el borde "
                f"(Lab {coarse.background_lab[0]:.0f}/{coarse.background_lab[1]:.0f}/"
                f"{coarse.background_lab[2]:.0f}). La tinta marca lo que supera el "
                f"umbral {coarse.threshold:.1f}. El fondo es lo que queda en papel."
            ),
            image=_fit_rgb(
                render_score(
                    small,
                    coarse.distance,
                    pivot=coarse.threshold,
                    span=max(coarse.threshold, 1.0),
                    color=MASK_INK_RGB,
                ),
                (height, width),
            ),
        )
        layers = (prior_layer, background_layer)

        prior_fraction = float(coarse.candidate.mean())
        foreground_fraction = float(coarse.foreground.mean())

        # La hoja ocupa casi todo el cuadro: recortar comería nervaduras y bordes.
        if foreground_fraction >= self.closeup_fraction:
            return self._all_leaf(
                image,
                method="primer_plano",
                prior_fraction=prior_fraction,
                foreground_fraction=foreground_fraction,
                threshold=coarse.threshold,
                background_lab=coarse.background_lab,
                components=coarse.components,
                extra_layers=layers,
            )

        base = _largest_component(coarse.foreground)
        if float(base.mean()) < self.min_leaf_fraction:
            return self._no_leaf(
                image, coarse, prior_fraction, extra_layers=layers
            )

        final_small = _grabcut_mask(small, base, self.rng_seed)
        leaf_fraction = float(final_small.mean())
        if leaf_fraction < self.min_leaf_fraction:
            return self._no_leaf(
                image, coarse, prior_fraction, extra_layers=layers
            )
        if leaf_fraction > self.closeup_fraction:
            return self._all_leaf(
                image,
                method="primer_plano",
                prior_fraction=prior_fraction,
                foreground_fraction=foreground_fraction,
                threshold=coarse.threshold,
                background_lab=coarse.background_lab,
                components=coarse.components,
                warnings=("fondo_escaso",),
                extra_layers=layers,
            )

        final = _fit(final_small, (height, width)).astype(bool)
        warnings = list(coarse.warnings)
        if coarse.components > 1:
            warnings.append("varias_regiones_de_hoja")

        return self._crop(
            image,
            final,
            method="grabcut",
            coarse=coarse,
            prior_fraction=prior_fraction,
            foreground_fraction=foreground_fraction,
            components=coarse.components,
            threshold=coarse.threshold,
            background_lab=coarse.background_lab,
            warnings=tuple(warnings),
            extra_layers=layers,
        )

    # -- Salidas ---------------------------------------------------------
    def _all_leaf(
        self,
        image: np.ndarray,
        *,
        method: str,
        prior_fraction: float,
        components: int = 1,
        warnings: tuple[str, ...] = (),
        extra_layers: tuple[Layer, ...] = (),
        foreground_fraction: float = 1.0,
        threshold: float = 0.0,
        background_lab: tuple[float, float, float] = (),
    ) -> IsolationResult:
        mask = np.ones(image.shape[:2], dtype=bool)
        return self._crop(
            image,
            mask,
            method=method,
            coarse=None,
            prior_fraction=prior_fraction,
            foreground_fraction=foreground_fraction,
            threshold=threshold,
            background_lab=background_lab,
            components=components,
            warnings=warnings,
            extra_layers=extra_layers,
            margin=False,
        )

    def _no_leaf(
        self,
        image: np.ndarray,
        coarse: _Foreground,
        prior_fraction: float,
        extra_layers: tuple[Layer, ...] = (),
    ) -> IsolationResult:
        height, width = image.shape[:2]
        mask = np.zeros((height, width), dtype=bool)
        report = IsolationReport(
            method="sin_hoja",
            source_width=width,
            source_height=height,
            analysis_width=0,
            analysis_height=0,
            bbox=(0, 0, 0, 0),
            prior_fraction=prior_fraction,
            leaf_fraction=0.0,
            components=coarse.components,
            warnings=("sin_hoja",),
            background_lab=coarse.background_lab,
            threshold=coarse.threshold,
            foreground_fraction=float(coarse.foreground.mean()),
        )
        return IsolationResult(image=image, mask=mask, report=report, layers=extra_layers)

    def _crop(
        self,
        image: np.ndarray,
        mask: np.ndarray,
        *,
        method: str,
        coarse: _Foreground | None,
        prior_fraction: float,
        foreground_fraction: float,
        components: int,
        warnings: tuple[str, ...],
        extra_layers: tuple[Layer, ...] = (),
        threshold: float = 0.0,
        background_lab: tuple[float, float, float] = (),
        margin: bool = True,
    ) -> IsolationResult:
        height, width = image.shape[:2]
        ys, xs = np.nonzero(mask)
        if xs.size == 0:
            if coarse is not None:
                return self._no_leaf(image, coarse, prior_fraction, extra_layers=extra_layers)
            empty = np.zeros((height, width), dtype=bool)
            report = IsolationReport(
                method="sin_hoja",
                source_width=width,
                source_height=height,
                analysis_width=0,
                analysis_height=0,
                bbox=(0, 0, 0, 0),
                prior_fraction=prior_fraction,
                leaf_fraction=0.0,
                components=components,
                warnings=("sin_hoja",),
            )
            return IsolationResult(image=image, mask=empty, report=report, layers=extra_layers)

        x0, x1 = int(xs.min()), int(xs.max()) + 1
        y0, y1 = int(ys.min()), int(ys.max()) + 1
        if margin:
            # Un margen pequeño evita cortar el contorno de la hoja: el borde
            # del recorte deja de coincidir con el borde del tejido.
            pad = int(round(self.crop_margin_fraction * max(x1 - x0, y1 - y0)))
            x0, y0 = max(0, x0 - pad), max(0, y0 - pad)
            x1, y1 = min(width, x1 + pad), min(height, y1 + pad)

        crop = image[y0:y1, x0:x1].copy()
        crop_mask = mask[y0:y1, x0:x1].astype(bool)
        crop[~crop_mask] = 0

        report = IsolationReport(
            method=method,
            source_width=width,
            source_height=height,
            analysis_width=x1 - x0,
            analysis_height=y1 - y0,
            bbox=(x0, y0, x1, y1),
            prior_fraction=prior_fraction,
            leaf_fraction=float(crop_mask.mean()),
            components=components,
            warnings=warnings,
            background_lab=background_lab,
            threshold=threshold,
            foreground_fraction=foreground_fraction,
        )
        layers = list(extra_layers)
        layers.append(
            Layer(
                key="aislamiento_hoja",
                stage="aislamiento",
                title="Máscara de hoja",
                caption=(
                    "Superficie que el pipeline considera hoja. Verde: se analiza. "
                    "Papel: fondo descartado de todas las medidas."
                    if method != "primer_plano"
                    else "No había fondo que separar: la toma ya es superficie de "
                    "hoja de borde a borde, así que la máscara cubre todo."
                ),
                image=render_mask(crop_mask),
            )
        )
        layers.append(
            Layer(
                key="aislamiento_recorte",
                stage="aislamiento",
                title="Recorte de la hoja",
                caption=(
                    "Lo que ve el resto del pipeline: la hoja recortada, con el "
                    "fondo en negro y fuera del cálculo."
                    if method != "primer_plano"
                    else "No hubo recorte: se conserva la imagen completa para no "
                    "perder nervaduras ni bordes de mancha."
                ),
                image=crop,
            )
        )
        return IsolationResult(
            image=crop, mask=crop_mask, report=report, layers=tuple(layers)
        )


def _foreground(image: np.ndarray, sensitivity: float) -> _Foreground:
    """Separa hoja de fondo sin saber de qué color es la hoja."""
    height, width = image.shape[:2]
    lab = cv2.cvtColor(image, cv2.COLOR_RGB2LAB).astype(np.float32)
    background, spread = _background_model(lab)
    distance = np.sqrt(
        sum(((lab[..., index] - background[index]) / spread[index]) ** 2 for index in range(3))
    )

    # 3 desviaciones robustas es "otro objeto"; la sensibilidad mueve ese corte.
    threshold = float(np.clip(3.0 / max(sensitivity, 0.1), 1.2, 12.0))
    color_candidate = distance > threshold
    candidate = (color_candidate | _green_prior(image)).astype(np.uint8)
    candidate = cv2.morphologyEx(candidate, cv2.MORPH_OPEN, _ellipse(3))
    candidate = cv2.morphologyEx(candidate, cv2.MORPH_CLOSE, _ellipse(7))

    foreground, components, dropped = _remove_background_and_strokes(candidate)
    warnings: list[str] = []
    if dropped:
        warnings.append("fondo_descartado")

    return _Foreground(
        candidate=candidate,
        foreground=foreground,
        distance=distance,
        threshold=threshold,
        background_lab=tuple(float(value) for value in background),
        components=components,
        warnings=tuple(warnings),
    )


def _background_model(lab: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Color mediano del borde y su dispersión robusta por canal.

    El borde es lo único que con seguridad no es la hoja. Se usa mediana y MAD
    porque una esquina con una sombra o un dedo no debe arrastrar el modelo.
    """
    height, width = lab.shape[:2]
    thickness = max(3, int(0.03 * min(height, width)))
    ring = np.zeros((height, width), dtype=bool)
    ring[:thickness, :] = True
    ring[-thickness:, :] = True
    ring[:, :thickness] = True
    ring[:, -thickness:] = True

    sample = lab[ring]
    if sample.size == 0:  # pragma: no cover - solo imágenes diminutas
        sample = lab.reshape(-1, 3)

    center = np.median(sample, axis=0)
    deviation = np.median(np.abs(sample - center), axis=0)
    # 1.4826 lleva el MAD a desviación típica; el piso evita dividir por cero en
    # fondos perfectamente planos (un PNG recortado, por ejemplo).
    spread = np.clip(1.4826 * deviation, 4.0, 40.0)
    return center.astype(np.float32), spread.astype(np.float32)


def _green_prior(image: np.ndarray) -> np.ndarray:
    """Pista de tejido vegetal: exceso de verde, saturación y tono foliar.

    No decide por sí sola —una mesa parda también puede caer en el rango de
    tono—, pero rescata hojas cuyo color se parece al fondo.
    """
    rgb = image.astype(np.float32)
    exg = (2.0 * rgb[..., 1] - rgb[..., 0] - rgb[..., 2]) / 255.0
    hsv = cv2.cvtColor(image, cv2.COLOR_RGB2HSV)
    return (
        (exg > GREEN_MIN_EXG)
        & (hsv[..., 1] > GREEN_MIN_SATURATION)
        & (hsv[..., 0] >= GREEN_HUE[0])
        & (hsv[..., 0] <= GREEN_HUE[1])
    )


def _remove_background_and_strokes(
    candidate: np.ndarray,
) -> tuple[np.ndarray, int, bool]:
    """Quita fondo conectado al borde y objetos sin cuerpo; deja regiones de hoja.

    Tres descartes, cada uno por un motivo distinto:

    - **área**: por debajo de ``max(64, 0,05 % del cuadro)`` es grano;
    - **borde**: un objeto que toca el borde es continuidad del fondo, salvo que
      ocupe casi todo el cuadro (hoja sin margen, que se conserva);
    - **cuerpo**: el radio del disco más grande que cabe dentro del objeto debe
      superar el 2,5 % del lado menor. Texto, cables y bordes de mesa son trazos
      finos y no contienen ese disco.
    """
    count, labels, stats, _ = cv2.connectedComponentsWithStats(candidate, connectivity=8)
    if count <= 1:
        return np.zeros_like(candidate, dtype=np.uint8), 0, False

    height, width = candidate.shape
    size = float(height * width)
    body = cv2.distanceTransform((candidate > 0).astype(np.uint8), cv2.DIST_L2, 5)
    min_body = max(3.0, MIN_BODY_FRACTION * min(height, width))
    # Etiquetas que tocan el borde: eso es continuidad del fondo, no un objeto.
    border = set(int(value) for value in np.unique(labels[0, :]))
    border |= set(int(value) for value in np.unique(labels[-1, :]))
    border |= set(int(value) for value in np.unique(labels[:, 0]))
    border |= set(int(value) for value in np.unique(labels[:, -1]))

    kept = np.zeros_like(candidate, dtype=np.uint8)
    components = 0
    dropped = False
    for label in range(1, count):
        area = int(stats[label, cv2.CC_STAT_AREA])
        if area < max(64, int(0.0005 * size)):
            dropped = True
            continue
        box_w = int(stats[label, cv2.CC_STAT_WIDTH])
        box_h = int(stats[label, cv2.CC_STAT_HEIGHT])
        aspect = min(box_w, box_h) / float(max(box_w, box_h, 1))
        fill = area / float(max(box_w * box_h, 1))
        # Un fondo grande que toca el borde se descarta; si toca el borde pero
        # ocupa casi todo el cuadro, es una hoja sin margen y se conserva.
        if label in border and area < 0.35 * size:
            dropped = True
            continue
        if aspect < MIN_ASPECT or fill < MIN_FILL:
            dropped = True
            continue
        if float(body[labels == label].max(initial=0.0)) < min_body:
            dropped = True
            continue
        kept[labels == label] = 1
        components += 1

    return kept, components, dropped


def _largest_component(mask: np.ndarray) -> np.ndarray:
    count, labels, stats, _ = cv2.connectedComponentsWithStats(
        mask.astype(np.uint8), connectivity=8
    )
    if count <= 1:
        return np.zeros_like(mask, dtype=np.uint8)
    largest = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    return (labels == largest).astype(np.uint8)


def _grabcut_mask(image: np.ndarray, base: np.ndarray, seed: int) -> np.ndarray:
    """Refina la región candidata con GrabCut y devuelve una máscara limpia."""
    height, width = base.shape
    sure = cv2.erode(base, _ellipse(15))
    reach = max(9, (int(0.04 * max(height, width)) // 2) * 2 + 1)
    search = cv2.dilate(base, _ellipse(reach))

    trimap = np.full((height, width), cv2.GC_PR_BGD, np.uint8)
    trimap[base > 0] = cv2.GC_PR_FGD
    trimap[sure > 0] = cv2.GC_FGD
    trimap[search == 0] = cv2.GC_BGD

    background = np.zeros((1, 65), np.float64)
    foreground = np.zeros((1, 65), np.float64)
    cv2.setRNGSeed(seed)
    cv2.grabCut(
        image,
        trimap,
        None,
        background,
        foreground,
        5,
        cv2.GC_INIT_WITH_MASK,
    )

    final = ((trimap == cv2.GC_FGD) | (trimap == cv2.GC_PR_FGD)).astype(np.uint8)
    final = _largest_component(final)
    final = cv2.morphologyEx(final, cv2.MORPH_CLOSE, _ellipse(9))
    final = cv2.morphologyEx(final, cv2.MORPH_OPEN, _ellipse(5))
    return _fill_external(final)


def _fill_external(mask: np.ndarray) -> np.ndarray:
    """Rellena huecos interiores: una mancha oscura no es un agujero del fondo."""
    contours, _ = cv2.findContours(
        mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    filled = np.zeros_like(mask, dtype=np.uint8)
    if contours:
        cv2.drawContours(filled, contours, -1, 1, thickness=cv2.FILLED)
    return filled


def _downscale(image: np.ndarray, max_side: int) -> np.ndarray:
    height, width = image.shape[:2]
    scale = min(1.0, max_side / max(height, width))
    if scale >= 1.0:
        return image
    return cv2.resize(
        image,
        (max(1, round(width * scale)), max(1, round(height * scale))),
        interpolation=cv2.INTER_AREA,
    )


def _fit(mask: np.ndarray, shape: tuple[int, int]) -> np.ndarray:
    """Lleva una máscara a la resolución del recorte para poder mostrarla."""
    if mask.shape[:2] == shape:
        return mask.astype(np.uint8, copy=False)
    return cv2.resize(
        mask.astype(np.uint8), (shape[1], shape[0]), interpolation=cv2.INTER_NEAREST
    )


def _fit_rgb(image: np.ndarray, shape: tuple[int, int]) -> np.ndarray:
    """Lleva una imagen de color a la resolución del original, sin bloques."""
    if image.shape[:2] == shape:
        return np.ascontiguousarray(image, dtype=np.uint8)
    return cv2.resize(image, (shape[1], shape[0]), interpolation=cv2.INTER_LINEAR)


def _ellipse(size: int) -> np.ndarray:
    size = max(1, int(size))
    if size % 2 == 0:
        size += 1
    return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (size, size))


def _require_rgb(image: np.ndarray) -> None:
    if image.dtype != np.uint8 or image.ndim != 3 or image.shape[2] != 3:
        raise ValueError("Se esperaba una imagen RGB uint8 de H×W×3.")
