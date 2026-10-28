"""Segmentación de lesiones y nervaduras sobre superficie foliar.

Legolas gobierna este módulo. No hay hoja completa ni fondo: el objeto es la
mancha. El criterio es explicable y determinista: pardeamiento medido como
rojo ≥ verde, con área y compacidad mínimas. No detecta clorosis (amarillamiento
sin pardeamiento): esa familia requiere otro segmentador.

La máscara se arma en dos tiempos (ADR-014). El umbral estricto solo decide qué
componentes existen: esos son las semillas. Después, desde cada semilla se crece
hacia el halo pálido que la rodea con un umbral bajo calculado sobre el tejido
sano de la propia hoja, con dos topes: profundidad en píxeles y nervaduras
detectadas. El crecimiento nunca inventa una mancha donde no había semilla.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import cv2
import numpy as np

from core.layers import Layer
from core.render import (
    VEIN_RGB,
    render_components,
    render_growth,
    render_mask,
    render_score,
)


@dataclass(frozen=True)
class SegmentationResult:
    lesions: np.ndarray
    veins: np.ndarray
    params: dict[str, Any] = field(default_factory=dict)
    # Capas visibles: puntaje, umbral, limpieza, componentes y máscaras finales.
    layers: tuple[Layer, ...] = ()


class Segmenter(ABC):
    """Contrato de segmentación de lesiones."""

    name: str

    @abstractmethod
    def segment(self, image: np.ndarray, valid_mask: np.ndarray) -> SegmentationResult:
        """Devuelve máscaras booleanas H×W y los parámetros usados."""


class VeinDetector(ABC):
    """Contrato de realce de la red de nervaduras."""

    name: str

    @abstractmethod
    def detect(self, image: np.ndarray, valid_mask: np.ndarray) -> tuple[np.ndarray, dict[str, Any]]:
        """Devuelve máscara de nervaduras y parámetros."""


class VeinEnhancer(VeinDetector):
    """Black-hat + top-hat sobre el canal verde, umbral por percentil.

    Las nervaduras aparecen como crestas claras u oscuras según la iluminación;
    combinar ambas polaridades evita depender de una sola.
    """

    name = "vein_blackhat_tophat"

    def __init__(self, kernel_size: int = 9, percentile: float = 97.0, min_response: float = 8.0) -> None:
        if kernel_size < 3 or kernel_size % 2 == 0:
            raise ValueError("kernel_size debe ser impar y >= 3.")
        if not 50.0 < percentile < 100.0:
            raise ValueError("percentile debe estar entre 50 y 100.")
        self.kernel_size = int(kernel_size)
        self.percentile = float(percentile)
        self.min_response = float(min_response)

    def detect(self, image: np.ndarray, valid_mask: np.ndarray) -> tuple[np.ndarray, dict[str, Any]]:
        _require_rgb(image)
        green = image[..., 1]
        kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, (self.kernel_size, self.kernel_size)
        )
        dark_ridges = cv2.morphologyEx(green, cv2.MORPH_BLACKHAT, kernel)
        bright_ridges = cv2.morphologyEx(green, cv2.MORPH_TOPHAT, kernel)
        response = cv2.max(dark_ridges, bright_ridges)
        response = cv2.GaussianBlur(response, (0, 0), 1.0)

        values = response[valid_mask]
        if values.size == 0:
            return np.zeros(image.shape[:2], dtype=bool), {"vein_percentile": self.percentile}

        threshold = max(float(np.percentile(values, self.percentile)), self.min_response)
        veins = (response > threshold) & valid_mask

        params = {
            "vein_kernel_px": self.kernel_size,
            "vein_percentile": self.percentile,
            "vein_threshold": round(threshold, 2),
            "vein_fraction": round(float(veins.mean()), 4),
        }
        return veins, params


class LesionSegmenter(Segmenter):
    """Lesión necrótica u oxidada = píxel donde el rojo iguala o supera al verde.

    El puntaje ``(R − G) / (R + G)`` es invariante a la iluminación global y
    separa el tejido pardo del verde sano; una sombra no cambia el signo. Se
    aplica apertura para descartar líneas de un píxel, cierre para unir manchas
    partidas y se descartan componentes con área o compacidad insuficientes.

    Limitación declarada: la clorosis (amarillo, R ≈ G) y las manchas casi
    blancas quedan fuera de esta máscara.

    La histéresis corrige la limitación de extensión: un umbral único alto deja
    afuera el halo pálido de la mancha, y uno bajo marca el tejido sano. Con dos
    umbrales, el alto siembra y el bajo solo puede crecer desde una semilla.
    """

    name = "redness_threshold"

    def __init__(
        self,
        min_area_fraction: float = 0.0002,
        min_area_px: int = 24,
        redness_threshold: float = 0.0,
        min_compactness: float = 0.15,
        vein_detector: VeinDetector | None = None,
        hysteresis: bool = True,
        hysteresis_fraction: float = 0.5,
        hysteresis_max_growth_px: int = 8,
        hysteresis_max_drop: float = 0.15,
    ) -> None:
        if not 0.0 <= min_area_fraction < 1.0:
            raise ValueError("min_area_fraction debe estar en [0, 1).")
        if min_area_px < 1:
            raise ValueError("min_area_px debe ser >= 1.")
        if not -1.0 <= redness_threshold <= 1.0:
            raise ValueError("redness_threshold debe estar en [-1, 1].")
        if not 0.0 <= min_compactness <= 1.0:
            raise ValueError("min_compactness debe estar en [0, 1].")
        if not 0.0 < hysteresis_fraction <= 1.0:
            raise ValueError("hysteresis_fraction debe estar en (0, 1].")
        if not 0 <= hysteresis_max_growth_px <= 64:
            raise ValueError("hysteresis_max_growth_px debe estar en [0, 64].")
        if not 0.0 < hysteresis_max_drop < 1.0:
            raise ValueError("hysteresis_max_drop debe estar en (0, 1).")
        self.min_area_fraction = float(min_area_fraction)
        self.min_area_px = int(min_area_px)
        self.redness_threshold = float(redness_threshold)
        self.min_compactness = float(min_compactness)
        self.vein_detector = vein_detector or VeinEnhancer()
        self.hysteresis = bool(hysteresis)
        self.hysteresis_fraction = float(hysteresis_fraction)
        self.hysteresis_max_growth_px = int(hysteresis_max_growth_px)
        self.hysteresis_max_drop = float(hysteresis_max_drop)

    def segment(self, image: np.ndarray, valid_mask: np.ndarray) -> SegmentationResult:
        _require_rgb(image)
        valid = valid_mask.astype(bool)
        if int(valid.sum()) < 100:
            empty = np.zeros(image.shape[:2], dtype=bool)
            return SegmentationResult(empty, empty, {"reason": "sin_pixeles_validos"})

        rgb = image.astype(np.float32)
        redness = (rgb[..., 0] - rgb[..., 1]) / (rgb[..., 0] + rgb[..., 1] + 1e-3)
        raw = (redness > self.redness_threshold) & valid

        opening = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        closing = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        cleaned = cv2.morphologyEx(raw.astype(np.uint8), cv2.MORPH_OPEN, opening)
        cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_CLOSE, closing)

        min_area = max(self.min_area_px, int(self.min_area_fraction * int(valid.sum())))
        seeds, discarded, kept, rejected = _filter_components(
            cleaned, min_area, self.min_compactness
        )

        veins, vein_params = self.vein_detector.detect(image, valid)

        # Histéresis (ADR-014). El umbral bajo sale del tejido sano de esta misma
        # hoja: se baja la mitad de la distancia que hay entre el p50 sano y el
        # umbral estricto, con un piso que impide que en hojas con mucho margen
        # el halo se lleve tejido verde. Si la hoja no tiene margen (p50 por
        # encima del umbral), los dos umbrales coinciden y no se crece nada.
        healthy_p50 = float(np.median(redness[valid]))
        low = min(
            self.redness_threshold,
            healthy_p50 + self.hysteresis_fraction * (self.redness_threshold - healthy_p50),
        )
        low = max(low, self.redness_threshold - self.hysteresis_max_drop)

        # Candidatos al halo: por encima del piso bajo, dentro de la superficie y
        # fuera de las nervaduras. Excluir la nervadura es lo que impide que el
        # crecimiento recorra una vena y se lleve media hoja.
        weak = (redness > low) & valid & ~veins
        if self.hysteresis:
            grown = _grow_within(seeds, weak, self.hysteresis_max_growth_px)
        else:
            grown = seeds.astype(bool)

        params = {
            "step": self.name,
            "redness_threshold": self.redness_threshold,
            "min_area_px": min_area,
            "min_compactness": self.min_compactness,
            "median_redness": round(healthy_p50, 4),
            "healthy_redness_p50": round(healthy_p50, 4),
            "hysteresis": self.hysteresis,
            "hysteresis_fraction": self.hysteresis_fraction,
            "hysteresis_low_threshold": round(low, 4),
            "hysteresis_max_growth_px": self.hysteresis_max_growth_px,
            "hysteresis_max_drop": self.hysteresis_max_drop,
            "seed_fraction": round(float(seeds.mean()), 5),
            "components_kept": kept,
            "components_discarded": rejected,
            "grown_px": int(grown.sum()) - int(seeds.sum()),
            "lesion_fraction": round(float(grown.mean()), 5),
            "lesion_fraction_valid": round(float(grown.sum()) / max(int(valid.sum()), 1), 5),
            **vein_params,
        }
        layers = (
            Layer(
                key="segmentacion_puntaje",
                stage="segmentacion",
                title="Puntaje de rojo",
                caption=(
                    "Cada píxel recibe (R−G)/(R+G). Cuanto más terracota, más rojo "
                    "respecto del verde; el gris es tejido sin evidencia. "
                    "Es el único criterio de mancha parda del método."
                ),
                image=render_score(image, redness, pivot=self.redness_threshold),
            ),
            Layer(
                key="segmentacion_cruda",
                stage="segmentacion",
                title="Umbral crudo",
                caption=(
                    f"Píxeles con puntaje > {self.redness_threshold:.3f} dentro de la "
                    "superficie válida. Es el corte puro: todavía incluye ruido de un "
                    "píxel y manchas partidas."
                ),
                image=render_mask(raw),
            ),
            Layer(
                key="segmentacion_morfologia",
                stage="segmentacion",
                title="Limpieza morfológica",
                caption=(
                    "Apertura 5×5 para borrar trazos sueltos y cierre 5×5 para unir "
                    "manchas partidas. No cambia el criterio, solo la forma."
                ),
                image=render_mask(cleaned),
            ),
            Layer(
                key="segmentacion_componentes",
                stage="segmentacion",
                title="Filtro por área y forma",
                caption=(
                    f"Terracota: componente conservado, y por lo tanto semilla "
                    f"(área ≥ {min_area} px y compacidad ≥ {self.min_compactness:.2f}). "
                    "Gris: descartado por ruido o por forma alargada. Un descarte acá "
                    "ya no se recupera después."
                ),
                image=render_components(seeds, discarded),
            ),
            Layer(
                key="segmentacion_histeresis",
                stage="segmentacion",
                title="Histéresis: núcleo → halo",
                caption=(
                    "Terracota pleno: núcleo que pasa el umbral estricto "
                    f"{self.redness_threshold:.3f}. Terracota lavado: halo recuperado "
                    f"con el umbral bajo {low:.3f}, que sale del tejido sano de esta "
                    f"hoja (p50 {healthy_p50:.3f}). El crecimiento se corta a "
                    f"{self.hysteresis_max_growth_px} px de la semilla y no atraviesa "
                    "nervaduras."
                ),
                image=render_growth(seeds, grown),
            ),
            Layer(
                key="segmentacion_lesiones",
                stage="segmentacion",
                title="Máscara de lesiones",
                caption=(
                    "Resultado final de la segmentación: núcleo más halo, lo que se "
                    "mide y se pinta en el overlay. Manchas claras, amarillas u "
                    "oscuras no entran en este criterio."
                ),
                image=render_mask(grown),
            ),
        )
        vein_layer = Layer(
            key="segmentacion_nervaduras",
            stage="segmentacion",
            title="Nervaduras",
            caption=(
                "Crestas claras y oscuras del canal verde por encima del percentil "
                f"{vein_params.get('vein_percentile', 97)}. Se detectan aparte para "
                "no contarlas como mancha."
            ),
            image=render_mask(veins, color=VEIN_RGB),
        )
        return SegmentationResult(
            grown.astype(bool), veins, params, layers=(*layers, vein_layer)
        )


def _grow_within(seeds: np.ndarray, candidates: np.ndarray, depth: int) -> np.ndarray:
    """Crece desde las semillas sin salir de ``candidates`` ni de ``depth`` píxeles.

    Dilatación geodésica acotada: cada paso avanza un píxel y solo se queda con
    lo que ya era candidato. Dos consecuencias que conviene tener presentes:

    - ningún componente nuevo puede aparecer, porque todo crecimiento está
      conectado a una semilla;
    - el tope de profundidad es real: un canal fino y alargado (una nervadura)
      no puede arrastrar el crecimiento más allá de ``depth`` píxeles.
    """
    grown = np.asarray(seeds).astype(bool)
    reachable = np.asarray(candidates).astype(bool)
    if depth <= 0 or not grown.any() or not reachable.any():
        return grown

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    for _ in range(int(depth)):
        previous = grown
        frontier = cv2.dilate(previous.astype(np.uint8), kernel).astype(bool)
        grown = previous | (frontier & reachable)
        if np.array_equal(grown, previous):
            break
    return grown


def _filter_components(
    mask: np.ndarray, min_area: int, min_compactness: float
) -> tuple[np.ndarray, np.ndarray, int, int]:
    """Descarta ruido por área y por forma: líneas finas tienen baja compacidad.

    Devuelve la máscara conservada, la descartada, cuántos componentes quedan y
    cuántos se rechazaron. Las dos máscaras se publican como capa para que el
    descarte sea auditable.
    """
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    kept = np.zeros_like(mask, dtype=np.uint8)
    discarded = np.zeros_like(mask, dtype=np.uint8)
    kept_count = 0
    rejected_count = 0
    for label in range(1, count):
        area = int(stats[label, cv2.CC_STAT_AREA])
        width = int(stats[label, cv2.CC_STAT_WIDTH])
        height = int(stats[label, cv2.CC_STAT_HEIGHT])
        compactness = area / float(max(width * height, 1))
        component = labels == label
        if area >= min_area and compactness >= min_compactness:
            kept[component] = 1
            kept_count += 1
        else:
            discarded[component] = 1
            rejected_count += 1
    return kept, discarded, kept_count, rejected_count


def _require_rgb(image: np.ndarray) -> None:
    if image.dtype != np.uint8 or image.ndim != 3 or image.shape[2] != 3:
        raise ValueError("Se esperaba una imagen RGB uint8 de H×W×3.")
