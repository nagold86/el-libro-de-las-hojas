"""Segmentación de lesiones y nervaduras sobre superficie foliar.

Legolas gobierna este módulo. No hay hoja completa ni fondo: el objeto es la
mancha. El criterio es explicable y determinista. Una mancha se decide con **dos
evidencias complementarias** (ADR-021), porque una sola dejaba familias afuera:

- **Pardeamiento**: ``(R − G) / (R + G) > umbral``. Es invariante a la
  iluminación global y separa el tejido oxidado del verde sano.
- **Oscurecimiento**: caída de luminancia respecto de su entorno *y* respecto
  del tejido sano. Rescata la necrosis negra y las manchas sucias, que tienen
  R ≈ G y el criterio de color no ve. Una sombra no entra: es un cambio de baja
  frecuencia y conserva el matiz de la hoja.

La máscara se arma en dos tiempos (ADR-014). El umbral estricto solo decide qué
componentes existen: esos son las semillas. Después, desde cada semilla se crece
hacia el halo pálido que la rodea con un umbral bajo calculado sobre el tejido
sano de la propia hoja, con dos topes: profundidad en píxeles y nervaduras
detectadas. El crecimiento nunca inventa una mancha donde no había semilla.

Las nervaduras se detectan **antes** que las manchas por una razón concreta: una
nervadura es una cresta oscura, así que sin este paso la evidencia de
oscurecimiento marcaría toda la red como lesión. Se detectan con sombrero negro
y sombrero blanco a dos escalas, que cubren nervaduras finas y gruesas sin
depender de si están claras u oscuras respecto del tejido.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import cv2
import numpy as np
from scipy import ndimage

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
    def detect(
        self, image: np.ndarray, valid_mask: np.ndarray
    ) -> tuple[np.ndarray, dict[str, Any]]:
        """Devuelve máscara de nervaduras y parámetros."""


class VeinEnhancer(VeinDetector):
    """Sombrero negro + sombrero blanco sobre el canal verde, a dos escalas.

    Las nervaduras aparecen como crestas claras u oscuras según la iluminación;
    combinar ambas polaridades evita depender de una sola. La segunda escala usa
    medio kernel para las nervaduras finas: con un solo tamaño, o se pierden las
    venas menores o se engordan las mayores.

    Después del umbral se descartan los componentes que no tienen forma de
    cresta (área chica y sin alargamiento): eso quita grano, manchas pequeñas y
    esquinas, que si no se confunden con nervadura y cortan el crecimiento de
    una lesión real.
    """

    name = "vein_blackhat_tophat"

    def __init__(
        self,
        kernel_size: int = 9,
        percentile: float = 97.0,
        min_response: float = 8.0,
        min_ridge_area: int = 12,
        min_elongation: float = 1.8,
        keep_area: int = 120,
    ) -> None:
        if kernel_size < 3 or kernel_size % 2 == 0:
            raise ValueError("kernel_size debe ser impar y >= 3.")
        if not 50.0 < percentile < 100.0:
            raise ValueError("percentile debe estar entre 50 y 100.")
        if min_ridge_area < 1:
            raise ValueError("min_ridge_area debe ser >= 1.")
        if min_elongation < 1.0:
            raise ValueError("min_elongation debe ser >= 1.")
        self.kernel_size = int(kernel_size)
        self.percentile = float(percentile)
        self.min_response = float(min_response)
        self.min_ridge_area = int(min_ridge_area)
        self.min_elongation = float(min_elongation)
        self.keep_area = int(keep_area)

    def detect(
        self, image: np.ndarray, valid_mask: np.ndarray
    ) -> tuple[np.ndarray, dict[str, Any]]:
        _require_rgb(image)
        valid = valid_mask.astype(bool)
        green = image[..., 1]

        response = _ridge_response(green, self.kernel_size)
        fine = _ridge_response(green, max(3, (self.kernel_size // 2) * 2 - 1))
        response = cv2.max(response, fine)
        response = cv2.GaussianBlur(response, (0, 0), 1.0)

        values = response[valid]
        if values.size == 0:
            return np.zeros(image.shape[:2], dtype=bool), {
                "vein_kernel_px": self.kernel_size,
                "vein_percentile": self.percentile,
                "vein_fraction": 0.0,
            }

        threshold = max(float(np.percentile(values, self.percentile)), self.min_response)
        veins = (response > threshold) & valid
        veins = _keep_ridges(
            veins, self.min_ridge_area, self.min_elongation, self.keep_area
        )

        params = {
            "vein_kernel_px": self.kernel_size,
            "vein_percentile": self.percentile,
            "vein_threshold": round(threshold, 2),
            "vein_fraction": round(float(veins.mean()), 4),
            "vein_components": int(cv2.connectedComponents(veins.astype(np.uint8))[0] - 1),
        }
        return veins, params


class LesionSegmenter(Segmenter):
    """Mancha = pardeamiento u oscurecimiento, sembrado por umbral y crecido por histéresis."""

    name = "redness_threshold"

    def __init__(
        self,
        min_area_fraction: float = 0.0002,
        min_area_px: int = 24,
        redness_threshold: float = 0.0,
        darkness_threshold: float = 0.35,
        darkness_scale_fraction: float = 0.015,
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
        if not 0.0 <= darkness_threshold < 1.0:
            raise ValueError("darkness_threshold debe estar en [0, 1).")
        if not 0.0 < darkness_scale_fraction <= 0.2:
            raise ValueError("darkness_scale_fraction debe estar en (0, 0.2].")
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
        self.darkness_threshold = float(darkness_threshold)
        self.darkness_scale_fraction = float(darkness_scale_fraction)
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
        brown = (redness > self.redness_threshold) & valid

        # Las nervaduras se detectan primero: una cresta oscura no es una mancha.
        # El guardián dilatado evita que el borde de la vena siembre una semilla.
        veins, vein_params = self.vein_detector.detect(image, valid)
        vein_guard = cv2.dilate(veins.astype(np.uint8), _ellipse(3)).astype(bool)

        darkness = self._darkness(image, valid, brown, vein_guard)
        if self.darkness_threshold > 0.0:
            dark_seed = (darkness > self.darkness_threshold) & valid & ~vein_guard
        else:
            dark_seed = np.zeros_like(valid)

        raw = ((brown | dark_seed) & valid).astype(np.uint8)
        opening = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        closing = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        cleaned = cv2.morphologyEx(raw, cv2.MORPH_OPEN, opening)
        cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_CLOSE, closing)

        min_area = max(self.min_area_px, int(self.min_area_fraction * int(valid.sum())))
        seeds, discarded, kept, rejected = _filter_components(
            cleaned, min_area, self.min_compactness
        )

        # El tejido sano de esta hoja fija el umbral bajo de la histéresis. Se
        # excluye lo que ya es mancha: si no, una hoja muy afectada sube su
        # mediana y el halo deja de recuperarse.
        healthy = valid & ~brown & ~vein_guard
        if int(healthy.sum()) < 100:
            healthy = valid & ~vein_guard
        if int(healthy.sum()) < 100:
            # Sin tejido sano a la vista (una hoja entera cubierta, o una máscara
            # de nervaduras que ocupa todo) no hay umbral bajo que calcular: la
            # histéresis se apaga en vez de inventar un número sobre el vacío.
            healthy_p50 = self.redness_threshold
        else:
            healthy_p50 = float(np.median(redness[healthy]))
        low = min(
            self.redness_threshold,
            healthy_p50 + self.hysteresis_fraction * (self.redness_threshold - healthy_p50),
        )
        low = max(low, self.redness_threshold - self.hysteresis_max_drop)

        dark_low = self.darkness_threshold * 0.5
        weak = ((redness > low) | (darkness > dark_low)) & valid & ~vein_guard
        if self.hysteresis:
            grown = _grow_within(seeds, weak, self.hysteresis_max_growth_px)
        else:
            grown = seeds.astype(bool)

        params = {
            "step": self.name,
            "method": "pardeamiento_y_oscurecimiento",
            "redness_threshold": self.redness_threshold,
            "darkness_threshold": self.darkness_threshold,
            "darkness_scale_px": round(self._darkness_sigma(image), 2),
            "dark_fraction": round(float(dark_seed.mean()), 5),
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
            "brown_seed_fraction": round(float(brown.mean()), 5),
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
                    "respecto del verde; el gris es tejido sin evidencia. Es la "
                    "primera de las dos evidencias de mancha."
                ),
                image=render_score(image, redness, pivot=self.redness_threshold),
            ),
            Layer(
                key="segmentacion_oscuridad",
                stage="segmentacion",
                title="Puntaje de oscurecimiento",
                caption=(
                    "Cuánto más oscuro es un píxel que su entorno y que el tejido "
                    f"sano. La tinta aparece a partir de {self.darkness_threshold:.2f}. "
                    "Es la segunda evidencia: rescata la necrosis negra, que no tiene "
                    "rojo. Una sombra se mueve con su entorno y no se marca."
                ),
                image=render_score(
                    image, darkness, pivot=self.darkness_threshold, span=0.30
                ),
            ),
            Layer(
                key="segmentacion_cruda",
                stage="segmentacion",
                title="Umbral crudo",
                caption=(
                    f"Unión de las dos evidencias dentro de la superficie válida: "
                    f"pardeamiento > {self.redness_threshold:.3f} u oscurecimiento > "
                    f"{self.darkness_threshold:.2f}. Es el corte puro: todavía incluye "
                    "ruido de un píxel y manchas partidas."
                ),
                image=render_mask(raw.astype(bool)),
            ),
            Layer(
                key="segmentacion_morfologia",
                stage="segmentacion",
                title="Limpieza morfológica",
                caption=(
                    "Apertura 5×5 para borrar trazos sueltos y cierre 5×5 para unir "
                    "manchas partidas. No cambia el criterio, solo la forma."
                ),
                image=render_mask(cleaned.astype(bool)),
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
                    "Resultado final de la segmentación: pardeamiento más "
                    "oscurecimiento, núcleo más halo. Es lo que se mide y se pinta en "
                    "el overlay. Tejido amarillo (clorosis) y manchas casi blancas no "
                    "entran en este criterio."
                ),
                image=render_mask(grown),
            ),
        )
        vein_layer = Layer(
            key="segmentacion_nervaduras",
            stage="segmentacion",
            title="Nervaduras",
            caption=(
                "Crestas claras y oscuras del canal verde, a dos escalas, por encima "
                f"del percentil {vein_params.get('vein_percentile', 97)} y con forma "
                "alargada. Se detectan antes que las manchas para no contar la red "
                "como lesión."
            ),
            image=render_mask(veins, color=VEIN_RGB),
        )
        return SegmentationResult(
            grown.astype(bool), veins, params, layers=(*layers, vein_layer)
        )

    # -- Evidencia de oscurecimiento -------------------------------------
    def _darkness_sigma(self, image: np.ndarray) -> float:
        height, width = image.shape[:2]
        return float(np.clip(self.darkness_scale_fraction * max(height, width), 3.0, 24.0))

    def _darkness(
        self,
        image: np.ndarray,
        valid: np.ndarray,
        brown: np.ndarray,
        vein_guard: np.ndarray,
    ) -> np.ndarray:
        """Caída de luminancia local, con guardia contra sombras y nervaduras.

        - ``local``: se compara el píxel con un desenfoque de su entorno. Un
          cambio de iluminación es de baja frecuencia y se cancela; una mancha
          chica no.
        - ``global``: se compara con la mediana del tejido sano. Rescata las
          manchas grandes, que el entorno ya absorbió, pero solo si el píxel es
          acromático o pardo: una sombra conserva el matiz verde de la hoja.
        """
        if self.darkness_threshold <= 0.0:
            return np.zeros_like(valid, dtype=np.float32)

        luminance = cv2.cvtColor(image, cv2.COLOR_RGB2LAB)[..., 0].astype(np.float32)
        sigma_fine = self._darkness_sigma(image)
        sigma_coarse = float(np.clip(sigma_fine * 4.0, 8.0, 96.0))

        fine = ndimage.gaussian_filter(luminance, sigma_fine, mode="nearest")
        coarse = ndimage.gaussian_filter(luminance, sigma_coarse, mode="nearest")
        local_ratio = np.clip(
            np.minimum(
                (fine - luminance) / np.maximum(fine, 1.0),
                (coarse - luminance) / np.maximum(coarse, 1.0),
            ),
            0.0,
            1.0,
        )

        healthy = valid & ~brown & ~vein_guard
        if int(healthy.sum()) < 100:
            healthy = valid & ~vein_guard
        if int(healthy.sum()) < 100:
            return local_ratio.astype(np.float32)

        healthy_l = float(np.median(luminance[healthy]))
        lab = cv2.cvtColor(image, cv2.COLOR_RGB2LAB).astype(np.float32)
        chroma = np.hypot(lab[..., 1] - 128.0, lab[..., 2] - 128.0)
        healthy_chroma = float(np.median(chroma[healthy]))

        global_ratio = np.clip(
            (healthy_l - luminance) / max(healthy_l, 1.0), 0.0, 1.0
        )
        achromatic = chroma < max(0.6 * healthy_chroma, 6.0)
        rgb = image.astype(np.float32)
        brownish = (rgb[..., 0] - rgb[..., 1]) > -0.02 * (rgb[..., 0] + rgb[..., 1])
        global_dark = np.where(achromatic | brownish, global_ratio, 0.0)

        return np.maximum(local_ratio, global_dark).astype(np.float32)


def _ridge_response(green: np.ndarray, kernel_size: int) -> np.ndarray:
    """Máximo entre cresta oscura y cresta clara, para un tamaño de kernel."""
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
    dark = cv2.morphologyEx(green, cv2.MORPH_BLACKHAT, kernel)
    bright = cv2.morphologyEx(green, cv2.MORPH_TOPHAT, kernel)
    return cv2.max(dark, bright)


def _keep_ridges(
    mask: np.ndarray, min_area: int, min_elongation: float, keep_area: int
) -> np.ndarray:
    """Conserva solo componentes con forma de cresta: chicos y alargados."""
    count, labels, stats, _ = cv2.connectedComponentsWithStats(
        mask.astype(np.uint8), connectivity=8
    )
    kept = np.zeros_like(mask, dtype=bool)
    for label in range(1, count):
        area = int(stats[label, cv2.CC_STAT_AREA])
        if area >= keep_area:
            kept[labels == label] = True
            continue
        if area < min_area:
            continue
        component = (labels == label).astype(np.uint8)
        contours, _ = cv2.findContours(component, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            continue
        (_, _), (rect_w, rect_h), _ = cv2.minAreaRect(max(contours, key=cv2.contourArea))
        short, long = sorted((max(rect_w, 1e-3), max(rect_h, 1e-3)))
        if long / short >= min_elongation:
            kept[labels == label] = True
    return kept


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


def _ellipse(size: int) -> np.ndarray:
    size = max(1, int(size))
    if size % 2 == 0:
        size += 1
    return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (size, size))


def _require_rgb(image: np.ndarray) -> None:
    if image.dtype != np.uint8 or image.ndim != 3 or image.shape[2] != 3:
        raise ValueError("Se esperaba una imagen RGB uint8 de H×W×3.")
