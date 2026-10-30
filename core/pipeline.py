"""Composición del pipeline. Aragorn decide el orden y las dependencias.

Este módulo es el único lugar donde se eligen las implementaciones concretas.
El orquestador recibe un ``Pipeline`` ya armado; los routers no construyen
etapas.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field

from core.chlorosis import ChlorosisDetector
from core.descriptors import ColorTextureDescriber, Describer
from core.domain import DomainGate, DomainThresholds, LeafDomainGate
from core.isolation import LeafIsolator
from core.morphometry import DefectMeasurer, Measurer
from core.preprocess import Preprocessor, StandardPreprocessor
from core.quality import QualityGate
from core.segmentation import LesionSegmenter, Segmenter, VeinEnhancer
from core.version import __version__


@dataclass(frozen=True)
class PipelineSettings:
    """Parámetros declarados de la corrida. Cambiarlos exige revisar Boromir."""

    clip_limit: float = 2.0
    tile_grid: int = 8
    denoise: bool = True
    isolation_max_side: int = 1100
    isolation_closeup_fraction: float = 0.97
    isolation_min_leaf_fraction: float = 0.005
    # Cuánta diferencia de color con el fondo hace falta para llamar hoja a un
    # píxel (ADR-020). 1.0 es el criterio calibrado; más alto recorta más fino.
    isolation_sensitivity: float = 1.0
    # Pardeamiento: píxel donde el rojo iguala o supera al verde.
    redness_threshold: float = 0.0
    # Oscurecimiento: caída de luminancia respecto de su entorno o del tejido
    # sano. 0 lo apaga y deja solo el criterio de color.
    darkness_threshold: float = 0.35
    darkness_scale_fraction: float = 0.015
    min_lesion_area_fraction: float = 0.0002
    # Histéresis del segmentador (ADR-014): el umbral estricto siembra y el bajo
    # recupera el halo. ``hysteresis=False`` reproduce la máscara de un umbral.
    hysteresis: bool = True
    hysteresis_fraction: float = 0.5
    hysteresis_max_growth_px: int = 8
    hysteresis_max_drop: float = 0.15
    # Nervaduras: cresta clara u oscura sobre el canal verde.
    vein_kernel: int = 9
    vein_percentile: float = 97.0
    # Clorosis (ADR-015): familia aparte del pardo. Mide pérdida de verde, no rojo.
    chlorosis_hue_threshold: float = 0.85
    chlorosis_min_chroma: float = 10.0
    min_sharpness: float = 15.0
    max_saturated_fraction: float = 0.20
    min_valid_fraction: float = 0.50
    domain_thresholds: DomainThresholds = field(default_factory=DomainThresholds)


@dataclass(frozen=True)
class Pipeline:
    isolator: LeafIsolator
    preprocessor: Preprocessor
    domain_gate: DomainGate
    segmenter: Segmenter
    measurer: Measurer
    describer: Describer
    quality_gate: QualityGate
    # Con valor por defecto para no romper construcción de pipelines en tests
    # que no miden clorosis.
    chlorosis: ChlorosisDetector = field(default_factory=ChlorosisDetector)


def method_fingerprint(settings: PipelineSettings | None = None) -> str:
    """Huella corta de la corrida: parámetros declarados más versión publicada.

    Dos registros con la misma huella se midieron con el mismo método, así que
    el informe del lote puede promediarlos sin mentir. Cambiar un umbral, una
    etapa o la versión produce una huella nueva y el informe lo advierte
    (ADR-016).
    """
    config = settings or PipelineSettings()
    payload = json.dumps(
        {"version": __version__, **asdict(config)},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:8]


def build_pipeline(settings: PipelineSettings | None = None) -> Pipeline:
    """Arma el pipeline clásico con las implementaciones por defecto."""
    config = settings or PipelineSettings()
    return Pipeline(
        isolator=LeafIsolator(
            max_side=config.isolation_max_side,
            closeup_fraction=config.isolation_closeup_fraction,
            min_leaf_fraction=config.isolation_min_leaf_fraction,
            sensitivity=config.isolation_sensitivity,
        ),
        preprocessor=StandardPreprocessor(
            clip_limit=config.clip_limit,
            tile_grid=config.tile_grid,
            denoise=config.denoise,
        ),
        domain_gate=LeafDomainGate(config.domain_thresholds),
        segmenter=LesionSegmenter(
            min_area_fraction=config.min_lesion_area_fraction,
            redness_threshold=config.redness_threshold,
            darkness_threshold=config.darkness_threshold,
            darkness_scale_fraction=config.darkness_scale_fraction,
            hysteresis=config.hysteresis,
            hysteresis_fraction=config.hysteresis_fraction,
            hysteresis_max_growth_px=config.hysteresis_max_growth_px,
            hysteresis_max_drop=config.hysteresis_max_drop,
            vein_detector=VeinEnhancer(
                kernel_size=config.vein_kernel,
                percentile=config.vein_percentile,
            ),
        ),
        measurer=DefectMeasurer(),
        describer=ColorTextureDescriber(),
        quality_gate=QualityGate(
            min_sharpness=config.min_sharpness,
            max_saturated_fraction=config.max_saturated_fraction,
            min_valid_fraction=config.min_valid_fraction,
        ),
        chlorosis=ChlorosisDetector(
            hue_threshold=config.chlorosis_hue_threshold,
            min_chroma=config.chlorosis_min_chroma,
        ),
    )
