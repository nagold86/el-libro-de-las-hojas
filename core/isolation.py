"""Aislamiento de la hoja respecto del fondo.

Legolas gobierna este módulo. La etapa separa una hoja dominante del fondo con
un prior de color verde y GrabCut; no identifica especies ni recorta lesiones.
El resultado es un recorte RGB con el fondo en negro y una máscara de hoja que
el resto del pipeline usa como superficie analizable.

La decisión y sus límites están en ``docs/DECISIONES.md`` (ADR-009). En tomas
de primer plano el aislamiento no aporta nada: se conserva la imagen completa
para no destruir nervaduras ni bordes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np

from core.layers import Layer
from core.render import render_mask


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
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class IsolationResult:
    """Imagen recortada, máscara de hoja y procedencia."""

    image: np.ndarray
    mask: np.ndarray
    report: IsolationReport
    # Capas visibles de la etapa: prior de color, máscara de hoja y recorte.
    layers: tuple[Layer, ...] = ()

    @property
    def has_leaf(self) -> bool:
        return bool(self.mask.any())


class LeafIsolator:
    """Separa una hoja dominante del fondo con color y GrabCut determinista."""

    name = "green_prior_grabcut"

    def __init__(
        self,
        max_side: int = 1100,
        closeup_fraction: float = 0.97,
        min_leaf_fraction: float = 0.005,
        rng_seed: int = 0,
    ) -> None:
        if max_side < 64:
            raise ValueError("max_side debe ser >= 64.")
        if not 0.0 < closeup_fraction <= 1.0:
            raise ValueError("closeup_fraction debe estar en (0, 1].")
        if not 0.0 < min_leaf_fraction < 1.0:
            raise ValueError("min_leaf_fraction debe estar en (0, 1).")
        if rng_seed < 0:
            raise ValueError("rng_seed debe ser >= 0.")
        self.max_side = int(max_side)
        self.closeup_fraction = float(closeup_fraction)
        self.min_leaf_fraction = float(min_leaf_fraction)
        self.rng_seed = int(rng_seed)

    def isolate(self, image: np.ndarray) -> IsolationResult:
        _require_rgb(image)
        height, width = image.shape[:2]

        # Las imágenes minúsculas no tienen fondo suficiente para modelar;
        # que decidan la puerta de calidad y la compuerta de dominio.
        if min(height, width) < 48:
            return self._all_leaf(image, method="primer_plano", prior_fraction=1.0)

        scale = min(1.0, self.max_side / max(height, width))
        if scale < 1.0:
            small = cv2.resize(
                image,
                (max(1, round(width * scale)), max(1, round(height * scale))),
                interpolation=cv2.INTER_AREA,
            )
        else:
            small = image

        prior = _color_prior(small)
        prior_fraction = float(prior.mean())
        components = _count_components(prior)
        prior_layer = Layer(
            key="aislamiento_prior",
            stage="aislamiento",
            title="Prior de tejido verde",
            caption=(
                "Píxeles candidatos por color: exceso de verde > 0,01, saturación "
                "> 20 y tono HSV entre 15 y 105. Es una pista para separar hoja de "
                "fondo, no una lesión."
            ),
            image=render_mask(_fit(prior, (height, width))),
        )

        # Un primer plano de hoja no requiere separar nada: el fondo ya es
        # marginal y GrabCut podría comerse nervaduras o lesiones claras.
        if prior_fraction >= self.closeup_fraction:
            return self._all_leaf(
                image,
                method="primer_plano",
                prior_fraction=prior_fraction,
                components=components,
                extra_layers=(prior_layer,),
            )

        base = _largest_component(prior)
        if float(base.mean()) < self.min_leaf_fraction:
            return self._no_leaf(image, prior_fraction, components)

        final_small = _grabcut_mask(small, base, self.rng_seed)
        if float(final_small.mean()) > 0.95:
            return self._all_leaf(
                image,
                method="primer_plano",
                prior_fraction=prior_fraction,
                components=components,
                warnings=("fondo_escaso",),
                extra_layers=(prior_layer,),
            )

        if scale < 1.0:
            final = cv2.resize(
                final_small, (width, height), interpolation=cv2.INTER_NEAREST
            ).astype(bool)
        else:
            final = final_small.astype(bool)

        warnings: list[str] = []
        if components > 1:
            warnings.append("varias_regiones_verdes")

        return self._crop(
            image,
            final,
            method="grabcut",
            prior_fraction=prior_fraction,
            components=components,
            warnings=tuple(warnings),
            extra_layers=(prior_layer,),
        )

    def _all_leaf(
        self,
        image: np.ndarray,
        *,
        method: str,
        prior_fraction: float,
        components: int = 1,
        warnings: tuple[str, ...] = (),
        extra_layers: tuple[Layer, ...] = (),
    ) -> IsolationResult:
        mask = np.ones(image.shape[:2], dtype=bool)
        return self._crop(
            image,
            mask,
            method=method,
            prior_fraction=prior_fraction,
            components=components,
            warnings=warnings,
            extra_layers=extra_layers,
        )

    def _no_leaf(
        self, image: np.ndarray, prior_fraction: float, components: int
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
            components=components,
            warnings=("sin_hoja",),
        )
        return IsolationResult(image=image, mask=mask, report=report)

    def _crop(
        self,
        image: np.ndarray,
        mask: np.ndarray,
        *,
        method: str,
        prior_fraction: float,
        components: int,
        warnings: tuple[str, ...],
        extra_layers: tuple[Layer, ...] = (),
    ) -> IsolationResult:
        height, width = image.shape[:2]
        ys, xs = np.nonzero(mask)
        if xs.size == 0:
            return self._no_leaf(image, prior_fraction, components)

        x0, x1 = int(xs.min()), int(xs.max()) + 1
        y0, y1 = int(ys.min()), int(ys.max()) + 1
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


def _color_prior(image: np.ndarray) -> np.ndarray:
    """Máscara gruesa de tejido verde: ExG, saturación y tono foliar."""
    rgb = image.astype(np.float32)
    exg = (2.0 * rgb[..., 1] - rgb[..., 0] - rgb[..., 2]) / 255.0
    hsv = cv2.cvtColor(image, cv2.COLOR_RGB2HSV)
    prior = (
        (exg > 0.01)
        & (hsv[..., 1] > 20)
        & (hsv[..., 0] >= 15)
        & (hsv[..., 0] <= 105)
    ).astype(np.uint8)
    prior = cv2.morphologyEx(prior, cv2.MORPH_OPEN, _ellipse(3))
    prior = cv2.morphologyEx(prior, cv2.MORPH_CLOSE, _ellipse(9))
    return prior


def _count_components(prior: np.ndarray) -> int:
    count, _, stats, _ = cv2.connectedComponentsWithStats(prior, connectivity=8)
    if count <= 1:
        return 0
    min_area = max(1, int(0.005 * prior.size))
    return sum(
        1
        for index in range(1, count)
        if int(stats[index, cv2.CC_STAT_AREA]) >= min_area
    )


def _largest_component(mask: np.ndarray) -> np.ndarray:
    count, labels, stats, _ = cv2.connectedComponentsWithStats(
        mask.astype(np.uint8), connectivity=8
    )
    if count <= 1:
        return np.zeros_like(mask, dtype=np.uint8)
    largest = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    return (labels == largest).astype(np.uint8)


def _grabcut_mask(image: np.ndarray, base: np.ndarray, seed: int) -> np.ndarray:
    """Refina el prior con GrabCut y devuelve una máscara binaria limpia."""
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
    contours, _ = cv2.findContours(
        mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    filled = np.zeros_like(mask, dtype=np.uint8)
    if contours:
        cv2.drawContours(filled, contours, -1, 1, thickness=cv2.FILLED)
    return filled


def _fit(mask: np.ndarray, shape: tuple[int, int]) -> np.ndarray:
    """Lleva una máscara a la resolución del recorte para poder mostrarla."""
    if mask.shape[:2] == shape:
        return mask.astype(np.uint8, copy=False)
    return cv2.resize(mask.astype(np.uint8), (shape[1], shape[0]), interpolation=cv2.INTER_NEAREST)


def _ellipse(size: int) -> np.ndarray:
    size = max(1, int(size))
    if size % 2 == 0:
        size += 1
    return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (size, size))


def _require_rgb(image: np.ndarray) -> None:
    if image.dtype != np.uint8 or image.ndim != 3 or image.shape[2] != 3:
        raise ValueError("Se esperaba una imagen RGB uint8 de H×W×3.")
